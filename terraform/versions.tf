terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.4"
    }
  }

  # Partial config: bucket/key/region are passed by the pipeline with -backend-config.
  backend "s3" {}
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "rag-app"
      Environment = var.environment
      ManagedBy   = "terraform"
      Repo        = "rag-app"
    }
  }
}
