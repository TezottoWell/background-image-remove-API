# gunicorn_config.py
import os

# Configurações de servidor
port = os.getenv("PORT", "5000")
bind = f"0.0.0.0:{port}"
backlog = 2048

# Configurações de worker
workers = 1  # Apenas um worker para economizar memória
worker_class = "sync"
worker_connections = 1000
timeout = 300  # Timeout maior para permitir carregamento do modelo
graceful_timeout = 30
keepalive = 2

# Configurações de processo
daemon = False
pidfile = None
umask = 0
user = None
group = None

# Logging
errorlog = "-"
loglevel = "info"
accesslog = "-"

# Configurações avançadas
preload_app = True  # Carregar o aplicativo antes de distribuir para os workers
max_requests = 100
max_requests_jitter = 10 