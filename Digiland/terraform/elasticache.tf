# ─── ElastiCache Redis ──────────────────────────────────────────────────────────

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-redis-subnet"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${var.project_name}-${var.environment}-redis"
  description          = "Redis cluster for Digiland ${var.environment}"

  node_type            = var.redis_node_type
  number_cache_clusters = var.redis_num_nodes
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auto_minor_version_upgrade = true

  snapshot_retention_limit = var.environment == "production" ? 7 : 1
  snapshot_window          = "05:00-06:00"

  tags = {
    Name = "${var.project_name}-${var.environment}-redis"
  }
}
