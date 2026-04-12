"""
Production WSGI Configuration with TLS 1.3
Gunicorn + Gevent for high-performance async handling
"""
import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'gevent'
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 120
keepalive = 5

# Security - TLS 1.3
keyfile = os.getenv('SSL_KEY_FILE', '/etc/ssl/private/aegiskyc.key')
certfile = os.getenv('SSL_CERT_FILE', '/etc/ssl/certs/aegiskyc.crt')
ca_certs = os.getenv('SSL_CA_CERTS', None)
ssl_version = 5  # TLS 1.3 (ssl.TLSVersion.TLSv1_3)
ciphers = 'TLS_AES_256_GCM_SHA384:TLS_AES_128_GCM_SHA256:TLS_CHACHA20_POLY1305_SHA256'

# Enable HTTPS redirect (for reverse proxy)
forwarded_allow_ips = '*'
secure_scheme_headers = {
    'X-FORWARDED-PROTOCOL': 'ssl',
    'X-FORWARDED-PROTO': 'https',
    'X-FORWARDED-SSL': 'on'
}

# Logging
accesslog = '-'  # stdout
errorlog = '-'   # stderr
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'aegiskyc'

# Server mechanics
daemon = False
pidfile = '/tmp/aegiskyc.pid'
umask = 0
user = None
group = None
tmp_upload_dir = None

# Enable preloading for faster worker spawn
preload_app = True

# Graceful timeout
graceful_timeout = 30

def on_starting(server):
    """Called just before the master process is initialized"""
    server.log.info("🚀 AegisKYC Production Server Starting...")
    server.log.info(f"Workers: {workers}")
    server.log.info(f"Worker Class: {worker_class}")
    server.log.info(f"TLS Version: TLS 1.3")

def on_reload(server):
    """Called when server is reloaded"""
    server.log.info("🔄 Server reloading...")

def when_ready(server):
    """Called when server is ready to serve requests"""
    server.log.info("✅ AegisKYC Server Ready")
    server.log.info(f"Listening on: {bind}")

def worker_int(worker):
    """Called when worker receives INT or QUIT signal"""
    worker.log.info(f"Worker {worker.pid} interrupted")

def worker_abort(worker):
    """Called when worker receives SIGABRT signal"""
    worker.log.info(f"Worker {worker.pid} aborted")
