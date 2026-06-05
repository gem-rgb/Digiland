# =============================================================================
# Digiland - Gunicorn Configuration
# =============================================================================
# Docs: https://docs.gunicorn.org/en/stable/settings.html
#
# Environment variables (set in .env or docker-compose):
#   GUNICORN_WORKERS   - Number of worker processes (default: CPU count * 2 + 1)
#   GUNICORN_THREADS   - Threads per worker (default: 2)
#   GUNICORN_TIMEOUT   - Worker timeout in seconds (default: 120)
#   GUNICORN_BIND      - Bind address (default: 0.0.0.0:8000)
# =============================================================================

import multiprocessing
import os

# ---------------------------------------------------------------------------
# Server Socket
# ---------------------------------------------------------------------------
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")
backlog = 2048

# ---------------------------------------------------------------------------
# Worker Processes
# ---------------------------------------------------------------------------
# Recommended: (2 x $num_cores) + 1
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))

# Use gevent for async I/O (better for handling concurrent requests with
# external API calls like Paystack, Daraja, GavaConnect)
worker_class = "gevent"

# Number of threads per worker (only used with 'gthread' worker class)
# Kept for fallback if worker_class is changed
threads = int(os.environ.get("GUNICORN_THREADS", 2))

# Maximum number of simultaneous clients per gevent worker
worker_connections = 1000

# Maximum number of requests a worker will process before restarting
# Helps prevent memory leaks
max_requests = 5000
max_requests_jitter = 500

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 120))
graceful_timeout = 30
keepalive = 5

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
# Limit request line size (8KB)
limit_request_line = 8190

# Limit request field size (8KB)
limit_request_field_size = 8190

# Maximum number of request fields
limit_request_fields = 100

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info").lower()

# Access log format
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Request timing threshold for warning (milliseconds)
# Logs a warning if request takes longer than this
# Disabled by default; uncomment to enable
# latency_threshold = 5000

# ---------------------------------------------------------------------------
# Process Naming
# ---------------------------------------------------------------------------
proc_name = "digiland"

# ---------------------------------------------------------------------------
# Server Mechanics
# ---------------------------------------------------------------------------
# Preload application before forking workers
# Reduces memory usage but means code changes require full restart
preload_app = True

# Run worker as a daemon (should be False for Docker)
daemon = False

# PID file location
pidfile = None

# Working directory
chdir = "/app"

# Temporary directory for worker heartbeat files
worker_tmp_dir = "/dev/shm" if os.path.isdir("/dev/shm") else None

# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------
def on_starting(server):
    """Called before the master process is initialized."""
    pass


def post_fork(server, worker):
    """Called after a worker has been forked."""
    server.log.info(f"Worker spawned (pid: {worker.pid})")


def pre_exec(server):
    """Called before a new master process is forked (e.g. during reload)."""
    server.log.info("Forked child, re-executing.")


def when_ready(server):
    """Called when the server is ready to accept connections."""
    server.log.info("Digiland Gunicorn server is ready. Spawned workers: %d" % server.num_workers)


def worker_int(worker):
    """Called when a worker receives the INT signal."""
    worker.log.info("Worker received INT signal")


def worker_abort(worker):
    """Called when a worker times out."""
    worker.log.info("Worker aborted (pid: %s)" % worker.pid)
