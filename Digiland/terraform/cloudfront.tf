# =============================================================================
# Digiland - CloudFront CDN Distribution
# =============================================================================
# CDN for static assets, media files, and frontend SPA
# Custom origin for Django API with caching rules
# =============================================================================

# -----------------------------------------------------------------------------
# CloudFront Origin Access Control
# -----------------------------------------------------------------------------
resource "aws_cloudfront_origin_access_control" "static" {
  name                              = "digiland-${var.environment}-static-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# -----------------------------------------------------------------------------
# CloudFront Distribution
# -----------------------------------------------------------------------------
resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  comment             = "Digiland ${var.environment} CDN"
  default_root_object = "index.html"
  price_class         = var.cloudfront_price_class
  aliases             = var.domain_name != "" ? [var.domain_name, "www.${var.domain_name}"] : []

  # Static assets origin (S3)
  origin {
    domain_name              = aws_s3_bucket.static.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.static.id
    origin_id                = "s3-static"
  }

  # Media files origin (S3)
  origin {
    domain_name              = aws_s3_bucket.media.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.static.id
    origin_id                = "s3-media"
  }

  # API origin (ALB)
  origin {
    domain_name = aws_lb.main.dns_name
    origin_id   = "alb-api"
    origin_path = ""

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = var.environment == "production" ? "https-only" : "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # Default cache behavior (API)
  default_cache_behavior {
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "alb-api"

    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Host", "Origin", "X-Forwarded-For", "X-Forwarded-Proto"]

      cookies {
        forward = "all"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0

    compress = true
  }

  # Static files cache behavior
  ordered_cache_behavior {
    path_pattern     = "/static/*"
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "s3-static"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 86400     # 1 day
    default_ttl            = 2592000   # 30 days
    max_ttl                = 31536000  # 1 year

    compress = true
  }

  # Media files cache behavior
  ordered_cache_behavior {
    path_pattern     = "/media/*"
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "s3-media"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 604800    # 7 days
    max_ttl                = 2592000   # 30 days

    compress = true
  }

  # API cache behavior
  ordered_cache_behavior {
    path_pattern     = "/api/*"
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "alb-api"

    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Content-Type", "X-Request-ID"]

      cookies {
        forward = "all"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 60

    compress = true
  }

  # WebSocket support (no caching)
  ordered_cache_behavior {
    path_pattern     = "/ws/*"
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "alb-api"

    forwarded_values {
      query_string = true
      headers      = ["*"]

      cookies {
        forward = "all"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0
  }

  # SSL Certificate
  viewer_certificate {
    acm_certificate_arn      = var.ssl_certificate_arn != "" ? var.ssl_certificate_arn : null
    ssl_support_method       = var.ssl_certificate_arn != "" ? "sni-only" : null
    minimum_protocol_version = var.ssl_certificate_arn != "" ? "TLSv1.2_2021" : null
    cloudfront_default_certificate = var.ssl_certificate_arn == "" ? true : false
  }

  # Restrictions
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # Custom error responses
  custom_error_response {
    error_code         = 404
    response_code      = 404
    response_page_path = "/static/404.html"
  }

  custom_error_response {
    error_code         = 500
    response_code      = 500
    response_page_path = "/static/500.html"
  }

  tags = {
    Name = "digiland-${var.environment}-cdn"
  }
}
