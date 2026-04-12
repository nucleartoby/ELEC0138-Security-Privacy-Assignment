"""
Simple Production Server Launcher for Windows
No PowerShell execution policy issues
"""

import os
import sys

# Add the app directory to Python path
app_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app')
sys.path.insert(0, app_dir)

# Set production environment
os.environ['FLASK_ENV'] = 'production'
os.environ['FLASK_DEBUG'] = '0'

print("=" * 60)
print("  AegisKYC Production Server (Windows)")
print("=" * 60)
print()

try:
    from waitress import serve
    from main import app
    
    HOST = "0.0.0.0"
    PORT = 8443
    THREADS = 8
    
    print(f"✅ Flask app loaded successfully")
    print(f"🚀 Starting Waitress WSGI server...")
    print(f"   Host: {HOST}")
    print(f"   Port: {PORT}")
    print(f"   Threads: {THREADS}")
    print(f"   URL: http://localhost:{PORT}")
    print()
    print("⚠️  Press Ctrl+C to stop the server")
    print()
    
    # Start Waitress (production WSGI server for Windows)
    serve(
        app,
        host=HOST,
        port=PORT,
        threads=THREADS,
        url_scheme='http',  # Use HTTP for now (HTTPS requires certificate setup)
        ident='AegisKYC/1.0',
        channel_timeout=120
    )
    
except ImportError:
    print("❌ Error: waitress not installed")
    print()
    print("Please install production dependencies:")
    print("  pip install waitress")
    print()
    sys.exit(1)
    
except KeyboardInterrupt:
    print()
    print("🛑 Server stopped by user")
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Error starting server: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
