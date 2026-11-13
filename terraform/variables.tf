variable "region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "platform_project" {
  description = "Project name used by the platform repo for its SSM parameter prefix (/<project>/<env>/...)"
  type        = string
  default     = "rag-platform"
}

variable "model_id" {
  description = <<-EOT
    Bedrock inference profile (or model) ID used to generate answers. Claude models on Bedrock
    are called through an inference profile. List yours with:
      aws bedrock list-inference-profiles --query "inferenceProfileSummaries[?contains(inferenceProfileId,'anthropic')].inferenceProfileId"
  EOT
  type        = string
  default     = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "top_k" {
  description = "How many chunks to retrieve per question"
  type        = number
  default     = 3
}
