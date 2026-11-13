data "aws_caller_identity" "current" {}

locals {
  name       = "rag-app-${var.environment}-api"
  ssm_prefix = "/${var.platform_project}/${var.environment}"
}

# ---- resources published by the rag-platform-infra repo
data "aws_ssm_parameter" "kb_id" {
  name = "${local.ssm_prefix}/knowledge-base-id"
}

data "aws_ssm_parameter" "kb_arn" {
  name = "${local.ssm_prefix}/knowledge-base-arn"
}

# ---- package the handler
data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/build/lambda.zip"
}

# ---- execution role
data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = local.name
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "lambda_bedrock" {
  statement {
    sid       = "QueryKnowledgeBase"
    actions   = ["bedrock:Retrieve"]
    resources = [data.aws_ssm_parameter.kb_arn.value]
  }
  statement {
    # RetrieveAndGenerate does not support resource-level permissions.
    sid       = "RetrieveAndGenerate"
    actions   = ["bedrock:RetrieveAndGenerate"]
    resources = ["*"]
  }
  statement {
    sid     = "GenerateWithClaude"
    actions = ["bedrock:InvokeModel", "bedrock:GetInferenceProfile"]
    resources = [
      "arn:aws:bedrock:*::foundation-model/*",
      "arn:aws:bedrock:*:${data.aws_caller_identity.current.account_id}:inference-profile/*",
    ]
  }
}

resource "aws_iam_role_policy" "lambda_bedrock" {
  name   = "bedrock-rag"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda_bedrock.json
}

# ---- function
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = 14
}

resource "aws_lambda_function" "api" {
  function_name    = local.name
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.13"
  architectures    = ["arm64"]
  handler          = "handler.handler"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = 60
  memory_size      = 256

  environment {
    variables = {
      KB_ID    = data.aws_ssm_parameter.kb_id.value
      MODEL_ID = var.model_id
      TOP_K    = tostring(var.top_k)
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy_attachment.logs]
}

# HTTPS endpoint. AWS_IAM auth means callers must sign requests (SigV4), so the
# endpoint is not open to the internet.
resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "AWS_IAM"
}
