environment = "staging"
aws_region  = "eu-west-1"

db_instance_class   = "db.t3.medium"
db_allocated_storage = 50
ecs_cpu             = 512
ecs_memory          = 1024
ecs_desired_count   = 2
celery_desired_count = 2
redis_node_type     = "cache.t3.small"
log_retention_days  = 14
