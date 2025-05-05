# gunicorn_config.py
import os
import multiprocessing

# Configurações de servidor
port = int(os.environ.get("PORT", 5000))
bind = f"0.0.0.0:{port}"

# Configurações de workers
# Reduzido para evitar consumo excessivo de memória
workers = 2  # Valor fixo baixo em vez de workers = multiprocessing.cpu_count()
worker_class = "sync"
threads = 1

# Timeouts
timeout = 120  # Aumentado para permitir processamento de imagens grandes
graceful_timeout = 30
keepalive = 5

# Limite de memória - reiniciar worker após processar N requisições
max_requests = 50
max_requests_jitter = 10

# Logs
errorlog = "logs/gunicorn-error.log"
accesslog = "logs/gunicorn-access.log"
loglevel = "info"

# Configuração para limitar uso de memória
worker_tmp_dir = "/dev/shm"  # Usar memória compartilhada

# Configurações de processo
daemon = False
pidfile = None
umask = 0
user = None
group = None

# Configurações avançadas
preload_app = True  # Carregar o aplicativo antes de distribuir para os workers 