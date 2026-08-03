import multiprocessing
import os


# 2GB RAM server profile:
# - Keep worker count conservative to avoid OOM
# - Use async worker class for FastAPI (ASGI)
worker_class = "uvicorn.workers.UvicornWorker"

# For 2GB with DB + frontend alongside, start with a single worker.
# Allow override via env if needed.
workers = int(os.getenv("GUNICORN_WORKERS", "1"))
threads = int(os.getenv("GUNICORN_THREADS", "1"))

# Bind inside container (compose maps host port separately)
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# Stability and resource guards
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# Recycle workers to mitigate memory creep on long uptime
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))

# Logging to stdout/stderr for Docker
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Use /dev/shm for heartbeat files when available
worker_tmp_dir = "/dev/shm"
