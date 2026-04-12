#flask entry point
import os
import flask
from flask import Flask
from flask_cors import CORS
from flask import request, jsonify
from flask import Blueprint
from flask import render_template

# Import routes
from routes.auth_routes import auth_bp
from routes.kyc_routes import kyc_bp
from routes.real_validation_routes import real_validation_bp
from routes.admin_routes import admin_bp
from routes.org_routes import org_bp

# Get the absolute path to the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'frontend')
STATIC_DIR = os.path.join(BASE_DIR, 'frontend')

#access home page from frontend
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR, static_url_path='')
CORS(app)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(kyc_bp)
app.register_blueprint(real_validation_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(org_bp)

@app.route('/')
def home():
    return render_template('homepage.html')

@app.route('/login')
@app.route('/login.html')
def login():
    return render_template('login.html')

@app.route('/signup')
@app.route('/signup.html')
def signup():
    return render_template('signup.html')

@app.route('/dashboard')
@app.route('/dashboard.html')
def dashboard():
    return render_template('dashboard.html')

@app.route('/kyc_complete')
@app.route('/kyc_complete.html')
def kyc_complete():
    return render_template('kyc_complete.html')

@app.route('/kyc_documents')
@app.route('/kyc_documents.html')
def kyc_documents():
    return render_template('kyc_documents.html')

@app.route('/kyc_capture')
@app.route('/kyc_capture.html')
def kyc_capture():
    return render_template('kyc_capture.html')

@app.route('/kyc_comprehensive')
@app.route('/kyc_comprehensive.html')
def kyc_comprehensive():
    return render_template('kyc_comprehensive.html')

@app.route('/document_analysis')
@app.route('/document_analysis.html')
def document_analysis():
    return render_template('document_analysis.html')

@app.route('/kyc-verification')
@app.route('/kyc-verification.html')
def kyc_verification():
    return render_template('kyc_verification.html')

@app.route('/admin')
@app.route('/admin.html')
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/org-signup')
@app.route('/org-signup.html')
def org_signup():
    return render_template('org_signup.html')

@app.route('/org-login')
@app.route('/org-login.html')
def org_login():
    return render_template('org_login.html')

@app.route('/org-dashboard')
@app.route('/org-dashboard.html')
def org_dashboard():
    return render_template('org_dashboard.html')

if __name__ == '__main__':
    app.run(debug=True)

