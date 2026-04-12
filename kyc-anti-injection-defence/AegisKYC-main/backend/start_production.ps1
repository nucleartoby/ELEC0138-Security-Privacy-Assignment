# Windows Production Startup Script
# PowerShell script to run AegisKYC in production mode on Windows

Write-Host "🚀 Starting AegisKYC Production Server (Windows)..." -ForegroundColor Green

# Install production dependencies
Write-Host "📦 Installing production dependencies..." -ForegroundColor Yellow
pip install gunicorn gevent cryptography pyOpenSSL redis prometheus-client

# Set environment variables
$env:PORT = "8443"
$env:WORKERS = "4"
$env:FLASK_ENV = "production"

# Generate self-signed certificate for testing (Windows)
$certPath = ".\ssl\aegiskyc.crt"
$keyPath = ".\ssl\aegiskyc.key"

if (-not (Test-Path $certPath)) {
    Write-Host "🔐 Generating self-signed SSL certificate..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path "ssl" | Out-Null
    
    # Using OpenSSL on Windows (requires OpenSSL installation)
    # Alternative: Use PowerShell's New-SelfSignedCertificate for Windows
    $cert = New-SelfSignedCertificate -DnsName "localhost", "aegiskyc.local" `
        -CertStoreLocation "cert:\LocalMachine\My" `
        -KeyLength 4096 `
        -KeyAlgorithm RSA `
        -HashAlgorithm SHA256 `
        -KeyUsage DigitalSignature, KeyEncipherment `
        -NotAfter (Get-Date).AddYears(1)
    
    # Export certificate
    $pwd = ConvertTo-SecureString -String "aegiskyc2025" -Force -AsPlainText
    Export-PfxCertificate -Cert $cert -FilePath ".\ssl\aegiskyc.pfx" -Password $pwd
    
    Write-Host "✅ Certificate generated at .\ssl\aegiskyc.pfx" -ForegroundColor Green
}

Write-Host "🌐 Starting production server on https://localhost:8443..." -ForegroundColor Cyan

# For Windows, use waitress instead of gunicorn (better Windows support)
Write-Host "Installing waitress (production WSGI for Windows)..." -ForegroundColor Yellow
pip install waitress

# Start with Waitress
Write-Host "Starting Waitress server with TLS..." -ForegroundColor Green
python -c @"
from waitress import serve
from app import app
import os

# Configure for production
app.config['ENV'] = 'production'
app.config['DEBUG'] = False

print('✅ AegisKYC Production Server Ready')
print('🌐 Listening on https://localhost:8443')
print('Press CTRL+C to stop')

serve(
    app, 
    host='0.0.0.0', 
    port=8443,
    threads=8,
    channel_timeout=120,
    cleanup_interval=30,
    url_scheme='https'
)
"@
