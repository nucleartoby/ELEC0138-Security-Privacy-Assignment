"""Simple server starter without debug/reloader for testing"""
import os
import sys

# Ensure app directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app

if __name__ == '__main__':
    print("Starting AegisKYC server on http://127.0.0.1:5000")
    print("Press CTRL+C to quit")
    try:
        from waitress import serve
        print("Using Waitress WSGI server...")
        serve(app, host='127.0.0.1', port=5000, threads=4)
    except ImportError:
        print("Waitress not available, using Flask dev server...")
        app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False, threaded=True)
