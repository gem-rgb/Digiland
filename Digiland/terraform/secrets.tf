# ─── Secrets Manager ────────────────────────────────────────────────────────────

resource "aws_kms_key" "secrets" {
  description             = "KMS key for Secrets Manager"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

resource "aws_secretsmanager_secret" "django_secret" {
  name                    = "${var.project_name}/${var.environment}/django-secret-key"
  recovery_window_in_days = 7
  kms_key_id              = aws_kms_key.secrets.id
}

resource "aws_secretsmanager_secret_version" "django_secret" {
  secret_id = aws_secretsmanager_secret.django_secret.id
  secret_string = "changeme-django-secret-${var.environment}-${random_id.secret.hex}"
}

resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${var.project_name}/${var.environment}/database-url"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  secret_string = "postgres://digiland_admin:${random_id.db_pass.hex}@${aws_db_instance.main.address}:5432/${var.project_name}"
}

resource "aws_secretsmanager_secret" "db_password" {
  name                    = "${var.project_name}/${var.environment}/db-password"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id = aws_secretsmanager_secret.db_password.id
  secret_string = random_id.db_pass.hex
}

resource "aws_secretsmanager_secret" "redis_url" {
  name                    = "${var.project_name}/${var.environment}/redis-url"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "redis_url" {
  secret_id = aws_secretsmanager_secret.redis_url.id
  secret_string = "redis://${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/0"
}

resource "aws_secretsmanager_secret" "celery_broker_url" {
  name                    = "${var.project_name}/${var.environment}/celery-broker-url"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "celery_broker_url" {
  secret_id = aws_secretsmanager_secret.celery_broker_url.id
  secret_string = "redis://${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/1"
}

# ─── Random IDs ────────────────────────────────────────────────────────────────

resource "random_id" "secret" {
  byte_length = 32
}

resource "random_id" "db_pass" {
  byte_length = 16
}
