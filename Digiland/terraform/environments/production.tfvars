environment = "production"
aws_region  = "eu-west-1"

db_instance_class   = "db.r6g.large"
db_allocated_storage = 200
ecs_cpu             = 1024
ecs_memory          = 2048
ecs_desired_count   = 4
celery_desired_count = 4
redis_node_type     = "cache.r6g.large"
redis_num_nodes     = 3
log_retention_days  = 90
