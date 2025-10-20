import os
import requests
import json
import asyncio
import time
from flask import Blueprint, request

# Import bộ não AI
from api.analyze import perform_full_analysis

# --- Cấu hình ---
webhook_blueprint = Blueprint('webhook_blueprint', __name__)
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
CONVERSATION_DELAY = 1.5 # Độ trễ giữa các tin nhắn (tính bằng giây)

# --- Webhook Endpoints ---

@webhook_blueprint.route('/messenger_webhook', methods=['GET'])
def verify_webhook():
    """Xác thực webhook với Facebook."""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode and token and mode == 'subscribe' and token == VERIFY_TOKEN:
        print("WEBHOOK_VERIFIED")
        return challenge, 200
    return 'VERIFICATION_FAILED', 403

@webhook_blueprint.route('/messenger_webhook', methods=['POST'])
def handle_message():
    """Nhận và xử lý tin nhắn theo luồng hội thoại tự nhiên."""
    try:
        data = request.get_json(force=True)
        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                for messaging_event in entry.get('messaging', []):
                    if messaging_event.get('message'):
                        sender_id = messaging_event['sender']['id']
                        message_text = messaging_event.get('message', {}).get('text')

                        if message_text:
                            print(f'Received message: "{message_text}" from PSID: {sender_id}')
                            
                            analysis_result = asyncio.run(perform_full_analysis(message_text, []))
                            print(f"✅ Analysis result: {json.dumps(analysis_result, ensure_ascii=False)}")

                            # <<< BẮT ĐẦU LUỒNG HỘI THOẠI MỚI >>>
                            if analysis_result and analysis_result.get('is_dangerous'):
                                # --- Luồng 1: Tin nhắn NGUY HIỂM ---
                                
                                # [Tin 1] Cảnh báo đầu tiên
                                send_message(sender_id, "⚠️ Tớ phát hiện tin nhắn này có dấu hiệu không an toàn, cậu nên cẩn thận nhé.")
                                time.sleep(CONVERSATION_DELAY)

                                # [Tin 2] Lý do
                                reason = analysis_result.get('reason')
                                if reason:
                                    send_message(sender_id, f"🔎 Cụ thể là: {reason}")
                                    time.sleep(CONVERSATION_DELAY)

                                # [Tin 3] Khuyến cáo
                                recommend = analysis_result.get('recommend')
                                if recommend:
                                    send_message(sender_id, f"💡 Vì vậy, tớ gợi ý cậu nên: {recommend}")
                            
                            else:
                                # --- Luồng 2: Tin nhắn AN TOÀN ---
                                send_message(sender_id, "✅ Tớ đã quét và thấy tin nhắn này an toàn nhé.")
                            # <<< KẾT THÚC LUỒNG HỘI THOẠI >>>
                        
    except Exception as e:
        print(f"An error occurred during webhook processing: {e}")
    return 'OK', 200

# --- Hàm gửi tin nhắn thông minh (Giữ nguyên, không thay đổi) ---

def _send_single_chunk(recipient_id, chunk_text):
    """Hàm phụ: Gửi một mẩu tin nhắn duy nhất."""
    API_URL = 'https://graph.facebook.com/v23.0/me/messages'
    payload = {'recipient': {'id': recipient_id}, 'message': {'text': chunk_text}}
    headers = {'Content-Type': 'application/json'}
    try:
        r = requests.post(API_URL, params={'access_token': PAGE_ACCESS_TOKEN}, json=payload, headers=headers)
        if r.status_code != 200:
            print(f'Error sending chunk: {r.status_code} {r.text}')
            return False
        return True
    except Exception as e:
        print(f"An exception occurred while sending chunk: {e}")
        return False

def send_message(recipient_id, message_text):
    """Gửi tin nhắn, tự động chia nhỏ nếu dài hơn 2000 ký tự. KHÔNG RÚT GỌN."""
    LIMIT = 2000
    if len(message_text) <= LIMIT:
        _send_single_chunk(recipient_id, message_text)
    else:
        print(f"Message is too long ({len(message_text)} chars). Splitting into chunks.")
        chunks = [message_text[i:i + LIMIT] for i in range(0, len(message_text), LIMIT)]
        for i, chunk in enumerate(chunks):
            if not _send_single_chunk(recipient_id, chunk):
                print("Stopping sending subsequent chunks due to an error.")
                break
            time.sleep(1)
    print(f'Finished sending process to {recipient_id}.')
