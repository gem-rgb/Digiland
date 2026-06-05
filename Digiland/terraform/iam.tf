# =============================================================================
# Digiland - IAM Roles and Policies
# =============================================================================
# IAM roles for ECS tasks, RDS monitoring, and deployment
# =============================================================================

# -----------------------------------------------------------------------------
# ECS Deployment IAM User (for CI/CD)
# -----------------------------------------------------------------------------
resource "aws_iam_user" "deploy" {
  count = var.create_deploy_user ? 1 : 0
  name  = "digiland-${var.environment}-deploy"

  tags = {
    Name = "digiland-${var.environment}-deploy-user"
  }
}

resource "aws_iam_access_key" "deploy" {
  count = var.create_deploy_user ? 1 : 0
  user  = aws_iam_user.deploy[0].name
}

resource "aws_iam_user_policy" "deploy" {
  count = var.create_deploy_user ? 1 : 0
  name  = "digiland-${var.environment}-deploy-policy"
  user  = aws_iam_user.deploy[0].name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:DescribeServices",
          "ecs:DescribeTaskDefinition",
          "ecs:RegisterTaskDefinition",
          "ecs:UpdateService",
          "ecs:DescribeTasks",
          "ecs:RunTask"
        ]
        Resource = [
          aws_ecs_cluster.main.arn,
          "arn:aws:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:service/${aws_ecs_cluster.main.name}/*",
          "arn:aws:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:task-definition/digiland-${var.environment}-*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.django_settings.arn,
          aws_secretsmanager_secret.database.arn,
          aws_secretsmanager_secret.redis.arn,
          aws_secretsmanager_secret.stripe.arn
        ]
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Django Application S3 Access Role
# -----------------------------------------------------------------------------
resource "aws_iam_role" "s3_access" {
  name = "digiland-${var.environment}-s3-access"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "s3_access" {
  name = "digiland-${var.environment}-s3-access-policy"
  role = aws_iam_role.s3_access.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetObjectVersion"
        ]
        Resource = [
          aws_s3_bucket.media.arn,
          "${aws_s3_bucket.media.arn}/*",
          aws_s3_bucket.static.arn,
          "${aws_s3_bucket.static.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudfront:CreateInvalidation",
          "cloudfront:GetInvalidation"
        ]
        Resource = aws_cloudfront_distribution.main.arn
      }
    ]
  })
}
