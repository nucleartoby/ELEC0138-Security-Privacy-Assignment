#!/bin/bash
# Production Deployment Script for AegisKYC

echo "🚀 Starting AegisKYC Production Deployment..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  Please run as root for SSL certificate setup"
fi

# Install production dependencies
echo "📦 Installing production dependencies..."
pip install -r requirements_production.txt

# Generate self-signed certificate if not exists (for testing)
# In production, use Let's Encrypt or commercial CA
if [ ! -f /etc/ssl/private/aegiskyc.key ]; then
    echo "🔐 Generating self-signed SSL certificate..."
    mkdir -p /etc/ssl/private
    openssl req -x509 -nodes -days 365 -newkey rsa:4096 \
        -keyout /etc/ssl/private/aegiskyc.key \
        -out /etc/ssl/certs/aegiskyc.crt \
        -subj "/C=IN/ST=Maharashtra/L=Mumbai/O=AegisKYC/CN=aegiskyc.com"
    chmod 600 /etc/ssl/private/aegiskyc.key
fi

# Set environment variables
export PORT=8443
export WORKERS=4
export SSL_KEY_FILE=/etc/ssl/private/aegiskyc.key
export SSL_CERT_FILE=/etc/ssl/certs/aegiskyc.crt

# Start production server with Gunicorn
echo "🌐 Starting Gunicorn with TLS 1.3..."
gunicorn \
    --config gunicorn_config.py \
    --bind 0.0.0.0:8443 \
    --certfile=/etc/ssl/certs/aegiskyc.crt \
    --keyfile=/etc/ssl/private/aegiskyc.key \
    --ssl-version=5 \
    --workers=4 \
    --worker-class=gevent \
    --access-logfile=- \
    --error-logfile=- \
    app:app

echo "✅ AegisKYC Production Server running on https://0.0.0.0:8443"
