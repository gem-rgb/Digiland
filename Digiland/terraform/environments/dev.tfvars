environment = "dev"
aws_region  = "eu-west-1"

db_instance_class   = "db.t3.small"
db_allocated_storage = 20
ecs_cpu             = 256
ecs_memory          = 512
ecs_desired_count   = 1
celery_desired_count = 1
redis_node_type     = "cache.t3.micro"
log_retention_days  = 7
