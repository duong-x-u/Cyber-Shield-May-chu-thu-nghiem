from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import logging
from api.analyze import analyze_endpoint
from webhook import webhook_blueprint
from werkzeug.exceptions import NotFound # Thêm import này

# Gmail API imports (sử dụng cho gửi email cảnh báo)
import base64
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Gmail API token path từ biến môi trường
GMAIL_TOKEN_PATH = os.getenv('GMAIL_TOKEN_PATH', '/etc/secrets/token.json')

# Hàm gửi email bằng Gmail API (cần dùng ở api/analyze.py)
def send_email_gmail_api(to, subject, body):
    creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, ['https://www.googleapis.com/auth/gmail.send'])
    service = build('gmail', 'v1', credentials=creds)
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    result = service.users().messages().send(userId='me', body={'raw': raw}).execute()
    return result

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Register blueprints
app.register_blueprint(analyze_endpoint, url_prefix='/api')
app.register_blueprint(webhook_blueprint, url_prefix='/messenger')

@app.route('/')
def home():
    #"""Home endpoint - cyberpunk gaming vibe"""
    #return jsonify({
    #    'banner': '⚡ WELCOME TO ARENA OF CYBERSHIELD ⚡',
    #    'status': '🟢 Sẵn Sàng',
    #    'version': '1.0.0',
    #    'server': '0xCyb3r-Sh13ld',
    #    'message': [
    #        "Chào mừng đến với Server của Cyber Shield",
    #        "Kẻ địch sẽ xuất trận sau 5 giây"
    #    ]
    #})
    return render_template('index.html')



@app.route('/health')
def health_check():
    return jsonify({
        'status': '🟢 Systems Nominal',
        'hp': '100/100',
        'mana': '∞',
        'latency_ms': 5,
        'service': 'cybershield-backend',
        'note': 'Tế đàn còn ổn'
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': '❌ 404: Page Not Found ://'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {str(error)}")
    return jsonify({'error': '💥 500: Quay về phòng thủ. Tế đàn bị tấn công'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)