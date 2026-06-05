# =============================================================================
# Digiland - CloudWatch Monitoring & X-Ray Tracing
# =============================================================================
# CloudWatch alarms, dashboards, log groups, and X-Ray tracing
# =============================================================================

# -----------------------------------------------------------------------------
# CloudWatch Log Groups
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "django" {
  name              = "/aws/digiland/${var.environment}/django"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn != "" ? var.kms_key_arn : null

  tags = {
    Name = "digiland-${var.environment}-django-logs"
  }
}

resource "aws_cloudwatch_log_group" "celery" {
  name              = "/aws/digiland/${var.environment}/celery"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "digiland-${var.environment}-celery-logs"
  }
}

resource "aws_cloudwatch_log_group" "nginx" {
  name              = "/aws/digiland/${var.environment}/nginx"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "digiland-${var.environment}-nginx-logs"
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Alarms - Web Service
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "web_high_cpu" {
  alarm_name          = "digiland-${var.environment}-web-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "Web service CPU utilization above 80%"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ServiceName = aws_ecs_service.web.name
    ClusterName = aws_ecs_cluster.main.name
  }

  alarm_actions = var.alert_sns_topic_arn != "" ? [var.alert_sns_topic_arn] : []
  ok_actions    = var.alert_sns_topic_arn != "" ? [var.alert_sns_topic_arn] : []

  tags = {
    Name = "digiland-${var.environment}-web-high-cpu-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "web_high_memory" {
  alarm_name          = "digiland-${var.environment}-web-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "85"
  alarm_description   = "Web service memory utilization above 85%"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ServiceName = aws_ecs_service.web.name
    ClusterName = aws_ecs_cluster.main.name
  }

  alarm_actions = var.alert_sns_topic_arn != "" ? [var.alert_sns_topic_arn] : []

  tags = {
    Name = "digiland-${var.environment}-web-high-memory-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "web_5xx_errors" {
  alarm_name          = "digiland-${var.environment}-web-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = "60"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "Web service 5XX errors above threshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
    TargetGroup  = aws_lb_target_group.web.arn_suffix
  }

  alarm_actions = var.alert_sns_topic_arn != "" ? [var.alert_sns_topic_arn] : []

  tags = {
    Name = "digiland-${var.environment}-web-5xx-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "web_response_time" {
  alarm_name          = "digiland-${var.environment}-web-high-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = "300"
  statistic           = "Average"
  threshold           = "5"
  alarm_description   = "Web service average response time above 5 seconds"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
  }

  alarm_actions = var.alert_sns_topic_arn != "" ? [var.alert_sns_topic_arn] : []

  tags = {
    Name = "digiland-${var.environment}-web-latency-alarm"
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Alarms - Database
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "db_high_cpu" {
  alarm_name          = "digiland-${var.environment}-db-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "Database CPU utilization above 80%"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }

  alarm_actions = var.alert_sns_topic_arn != "" ? [var.alert_sns_topic_arn] : []

  tags = {
    Name = "digiland-${var.environment}-db-high-cpu-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "db_low_storage" {
  alarm_name          = "digiland-${var.environment}-db-low-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "5000000000" # 5GB
  alarm_description   = "Database free storage below 5GB"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }

  alarm_actions = var.alert_sns_topic_arn != "" ? [var.alert_sns_topic_arn] : []

  tags = {
    Name = "digiland-${var.environment}-db-low-storage-alarm"
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Alarms - Redis
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "redis_high_memory" {
  alarm_name          = "digiland-${var.environment}-redis-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "85"
  alarm_description   = "Redis memory usage above 85%"
  treat_missing_data  = "notBreaching"

  dimensions = {
    CacheClusterId = aws_elasticache_replication_group.main.id
  }

  alarm_actions = var.alert_sns_topic_arn != "" ? [var.alert_sns_topic_arn] : []

  tags = {
    Name = "digiland-${var.environment}-redis-high-memory-alarm"
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Dashboard
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "digiland-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "ECS Web Service CPU & Memory"
          region  = var.aws_region
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ServiceName", aws_ecs_service.web.name, "ClusterName", aws_ecs_cluster.main.name],
            [".", "MemoryUtilization", ".", ".", ".", "."]
          ]
          view = "timeSeries"
          stat = "Average"
          period = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "ALB Request Count & Latency"
          region  = var.aws_region
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", aws_lb.main.arn_suffix],
            [".", "TargetResponseTime", ".", "."]
          ]
          view = "timeSeries"
          stat = "Average"
          period = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "RDS CPU & Connections"
          region  = var.aws_region
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", aws_db_instance.main.id],
            [".", "DatabaseConnections", ".", "."]
          ]
          view = "timeSeries"
          stat = "Average"
          period = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "Redis Memory & Connections"
          region  = var.aws_region
          metrics = [
            ["AWS/ElastiCache", "DatabaseMemoryUsagePercentage", "CacheClusterId", aws_elasticache_replication_group.main.id],
            [".", "CurrConnections", ".", "."]
          ]
          view = "timeSeries"
          stat = "Average"
          period = 300
        }
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# X-Ray Tracing
# -----------------------------------------------------------------------------
resource "aws_xray_sampling_rule" "main" {
  rule_name      = "digiland-${var.environment}"
  priority       = 1000
  version        = 1
  reservoir_size = var.environment == "production" ? 10 : 50
  fixed_rate     = var.environment == "production" ? 0.05 : 0.5
  service_name   = "digiland-*"
  host           = "*"
  http_method    = "*"
  url_path       = "*"
  resource_arn   = "*"
}
