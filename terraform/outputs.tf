output "api_url" {
  description = "Lambda Function URL (AWS_IAM auth: sign requests with SigV4)"
  value       = aws_lambda_function_url.api.function_url
}

output "function_name" {
  value = aws_lambda_function.api.function_name
}
