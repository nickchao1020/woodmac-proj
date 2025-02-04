resource "aws_bedrock_inference_profile" "claude_3_5_sonnet_20241022_v2" {
  name        = "woodmac-generative-ai-challenge-claude-3-5-sonnet-20241022-v2"
  description = "Profile for the Wood Mackenzie Generative AI Challenge application"

  model_source {
    copy_from = "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/us.anthropic.claude-3-5-sonnet-20241022-v2:0"
  }
}

resource "aws_bedrock_inference_profile" "claude_3_haiku_20240307_v1" {
  name        = "woodmac-generative-ai-challenge-claude-3-haiku-20240307-v1"
  description = "Profile for the Wood Mackenzie Generative AI Challenge application"

  model_source {
    copy_from = "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/us.anthropic.claude-3-haiku-20240307-v1:0"
  }
}
