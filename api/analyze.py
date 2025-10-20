import json
import asyncio
import os
import random
import gc
from flask import Blueprint, request, jsonify
import aiohttp

# --- Gmail API imports ---
import base64
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# --- Blueprint ---
analyze_endpoint = Blueprint('analyze_endpoint', __name__)

# --- Cấu hình ---
GOOGLE_API_KEYS_STR = os.environ.get('GOOGLE_API_KEYS')
SAFE_BROWSING_API_KEY = os.environ.get('SAFE_BROWSING_API_KEY')
if not GOOGLE_API_KEYS_STR:
    raise ValueError("Biến môi trường GOOGLE_API_KEYS là bắt buộc.")
GOOGLE_API_KEYS = [key.strip() for key in GOOGLE_API_KEYS_STR.split(',') if key.strip()]

APPS_SCRIPT_URL = os.environ.get('APPS_SCRIPT_URL')
GMAIL_TOKEN_PATH = os.environ.get('GMAIL_TOKEN_PATH', '/etc/secrets/token.json')

# --- HÀM GỬI EMAIL QUA GMAIL API ---
def send_email_gmail_api(to_email, subject, body):
    creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, ['https://www.googleapis.com/auth/gmail.send'])
    service = build('gmail', 'v1', credentials=creds)
    message = MIMEText(body)
    message['to'] = to_email
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    result = service.users().messages().send(userId='me', body={'raw': raw}).execute()
    return result

# --- HÀM HỖ TRỢ KIỂM TRA URL ---
async def check_urls_safety_optimized(urls: list):
    if not SAFE_BROWSING_API_KEY or not urls: return []
    print("➡️  [Kiểm tra URL] Bắt đầu kiểm tra URL với Google Safe Browsing...")
    safe_browsing_url = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={SAFE_BROWSING_API_KEY}"
    payload = {"threatInfo": {"threatTypes": ["MALWARE", "SOCIAL_ENGINEERING"], "platformTypes": ["ANY_PLATFORM"], "threatEntryTypes": ["URL"], "threatEntries": [{"url": url} for url in urls[:5]]}}
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(safe_browsing_url, json=payload) as resp:
                if resp.status == 200:
                    matches = (await resp.json()).get("matches", [])
                    print(f"✅ [Kiểm tra URL] Hoàn tất. Tìm thấy {len(matches)} kết quả không an toàn.")
                    return matches
                print(f"🟡 [Kiểm tra URL] API trả về trạng thái {resp.status}.")
                return []
    except Exception as e:
        print(f"🔴 [Kiểm tra URL] Thất bại: {e}")
        return []

# --- LUỒNG 1: GỌI "ĐIỆP VIÊN LEO" QUA GOOGLE APPS SCRIPT ---
async def call_gas_db_ai(text: str):
    if not APPS_SCRIPT_URL:
        print("🔴 [Leo] Lỗi: Biến môi trường APPS_SCRIPT_URL chưa được thiết lập.")
        return {"found": False, "reason": "GAS URL chưa được cấu hình."}
    payload = {"text": text}
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(APPS_SCRIPT_URL, json=payload) as resp:
                if resp.status == 200:
                    print("✅ [Leo] Nhận được phản hồi thành công từ GAS.")
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    print(f"🔴 [Leo] Lỗi từ GAS. Trạng thái: {resp.status}, Phản hồi: {error_text}")
                    return {"found": False, "reason": f"GAS trả về lỗi {resp.status}"}
    except Exception as e:
        print(f"🔴 [Leo] Lỗi kết nối đến GAS: {e}")
        return {"found": False, "reason": f"Ngoại lệ: {str(e)}"}

# --- LUỒNG 2: ANNA-AI & BỘ NÃO TĂNG CƯỜNG ---
def create_anna_ai_prompt(text: str, context_hint: str = None):
    hint_section = ""
    if context_hint:
        hint_section = f"""
---
**THÔNG TIN TÌNH BÁO BỔ SUNG (QUAN TRỌNG):**
Hệ thống Leo đã cung cấp một gợi ý về bối cảnh của tin nhắn này. Hãy ưu tiên thông tin này khi phân tích:
"{context_hint}"
---
"""
    return f"""
You are Anna, a cybersecurity analyst with high emotional intelligence, specialized in evaluating Vietnamese messages.  
Your mission is to protect users from **all deliberate and clear online threats**, including but not limited to:  
- **Scams / phishing / data theft**  
- **School violence / physical threats**  
- **Hate speech / incitement of violence / discrimination**  
- **Anti-state propaganda / harmful extremism**  
- **Other harmful behaviors with potential direct danger**  

⚠️ Golden Rule: **Default every message as SAFE** unless there is undeniable evidence of malicious intent AND a harmful action.  
Do not overflag casual jokes, memes, venting, or normal friendly chats.  

{hint_section}

Follow strictly the 3-step framework:

---
**STEP 1: NOISE FILTER**

* Core question: "Does this message contain enough content to analyze?"  
* Action: If the message is too short (<4 words), vague, or only an emoji/expression without context → **conclude SAFE immediately**.  
* Never flag as dangerous just because of one negative word without clear harmful context.  

---
**STEP 2: CONTEXT & INTENT**

* Core question: "Is this from a stranger with malicious intent, or just friends joking/venting?"  
* Default assumption: Treat all conversations as **friendly and harmless**, unless there is undeniable evidence otherwise.  
* Notice: Ignore messages related to game hacking.
* Actions:  
    * **Language:** If negative words can be used jokingly, sarcastically, or casually → treat as SAFE.  
    * **Emotion:** If it’s just venting, exaggeration, or temporary anger without targeting someone specifically → SAFE.  
    * **Action:** Only consider risky if the message **calls for a harmful action** (e.g., sending money, sharing info, meeting a stranger, physical violence, inciting hate/propaganda).  

---
**STEP 3: EVIDENCE-BASED CONCLUSION**

* Golden Rule: **Only mark DANGEROUS if there is clear malicious intent AND a specific harmful action.**  
* Actions:  
    * **DANGEROUS:** If strong evidence exists → mark true with score 1–5.  
    * **SAFE:** All other cases, or if uncertain → mark false with score 0.  

---
**Output JSON (in Vietnamese):**
- "is_dangerous": (boolean)  
- "reason": (string, giải thích ngắn gọn logic của bạn)  
- "types": (string: one of ["scam", "violence", "hate_speech", "anti_state", "other"])  
- "score": (0-5)  
- "recommend": (string)  

**TIN NHẮN CẦN PHÂN TÍCH:** "{text}"
"""

async def analyze_with_anna_ai_http(text: str, context_hint: str = None):
    api_key = random.choice(GOOGLE_API_KEYS)
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"    
    prompt = create_anna_ai_prompt(text[:3000], context_hint)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": { "temperature": 0.2, "maxOutputTokens": 400, "responseMimeType": "application/json" }
    }
    try:
        timeout = aiohttp.ClientTimeout(total=25)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            print(f"➡️  [Anna] Đang gửi yêu cầu phân tích tới Google AI...")
            async with session.post(gemini_url, json=payload) as resp:
                if resp.status == 200:
                    response_json = await resp.json()
                    if not response_json.get('candidates'):
                        print(f"🔴 [Anna] Lỗi! Phản hồi không có 'candidates'. Bị bộ lọc an toàn chặn. Chi tiết: {response_json}")
                        return {'error': 'BLOCKED_BY_GOOGLE', 'message': 'Bị bộ lọc an toàn của Google chặn.'}
                    json_text = response_json['candidates'][0]['content']['parts'][0]['text']
                    result = json.loads(json_text)
                    print("✅ [Anna] Phân tích thành công.")
                    return result
                else:
                    error_text = await resp.text()
                    print(f"🔴 [Anna] Lỗi HTTP! Trạng thái: {resp.status}, Phản hồi: {error_text}")
                    return {"error": f"Lỗi API Anna {resp.status}", "status_code": 500}
    except Exception as e:
        print(f"🔴 [Anna] Lỗi ngoại lệ khi gọi HTTP: {e}")
        return {"error": "Phân tích với Anna thất bại do có ngoại lệ.", "status_code": 500}

# --- HÀM ĐIỀU PHỐI CHÍNH ---
async def perform_full_analysis(text: str, urls: list):
    final_result = None
    is_new_case_by_anna = False
    context_hint_from_leo = None
    
    print(f"📜 [Bắt đầu] Phân tích tin nhắn: '{text[:400]}'")
    print("➡️ [Luồng 1] Bắt đầu gọi Điệp viên Leo (GAS)...")
    gas_result = await call_gas_db_ai(text)

    if gas_result and gas_result.get("found"):
        result_type = gas_result.get("type")
        if result_type == "trivial_pattern":
            print("✅ [Luồng 1] THÀNH CÔNG. Leo xác định tin nhắn là tầm thường (Trivial).")
            return {'is_dangerous': False, 'reason': 'Tin nhắn quá đơn giản để phân tích.', 'score': 0, 'types': 'Trivial'}
        elif result_type == "dangerous_pattern":
            print("✅ [Luồng 1] THÀNH CÔNG. Tìm thấy trong Sổ Đen (Blacklist) bằng AI.")
            final_result = gas_result.get("data")
        elif result_type == "context_hint":
            print("📝 [Luồng 1] Nhận được thông tin tình báo từ Leo.")
            context_hint_from_leo = gas_result.get("data")
            
    if final_result is None:
        if context_hint_from_leo:
            print(f"🟡 [Luồng 2] Bắt đầu gọi Anna-AI với thông tin tình báo: '{context_hint_from_leo}'")
        else:
            print(f"🟡 [Luồng 2] Bắt đầu gọi Anna-AI (không có thông tin tình báo).")
        final_result = await analyze_with_anna_ai_http(text, context_hint_from_leo)
        print(f"📄 [Kết quả của Anna] Phân tích AI trả về: {json.dumps(final_result, ensure_ascii=False)}")
        if 'error' in final_result:
            return final_result
        is_new_case_by_anna = True 
    
    if urls:
        url_matches = await check_urls_safety_optimized(urls)
        if url_matches:
            print(f"⚠️ [Phân tích URL] Phát hiện {len(url_matches)} URL không an toàn! Cập nhật kết quả cuối cùng.")
            final_result.update({'url_analysis': url_matches, 'is_dangerous': True, 'score': max(final_result.get('score', 0), 4), 'reason': (final_result.get('reason', '') + " + Các URL không an toàn")[:100]})

    if is_new_case_by_anna and final_result.get("is_dangerous"):
        print("➡️ [Phản hồi] Phát hiện ca nguy hiểm mới. Lên lịch gửi email bằng Gmail API...")
        try:
            send_email_gmail_api(
                to_email="duongpham18210@gmail.com",
                subject=f"[CyberShield Report] Nguy hiểm mới: {final_result.get('types', 'Không xác định')} (Điểm: {final_result.get('score', 'N/A')})",
                body=f"""Một tin nhắn mới đã được Anna-AI phân tích và gắn cờ NGUY HIỂM.
Vui lòng xem xét và bổ sung vào Google Sheets.
----------------------------------------------------------
TIN NHẮN GỐC:
{text}
----------------------------------------------------------
KẾT QUẢ PHÂN TÍCH:
{json.dumps(final_result, indent=2, ensure_ascii=False)}
"""
            )
            print("✅ [Email] Gửi email cảnh báo thành công qua Gmail API.")
        except Exception as e:
            print(f"🔴 [Email] Gửi email cảnh báo thất bại qua Gmail API: {e}")

    gc.collect()
    print(f"🏁 [Kết thúc] Phân tích hoàn tất cho tin nhắn: '{text[:50]}...'")
    return final_result

# --- ENDPOINTS ---
@analyze_endpoint.route('/analyze', methods=['POST'])
async def analyze_text():
    try:
        data = request.get_json(silent=True)
        if not data or 'text' not in data: return jsonify({'error': 'Định dạng yêu cầu không hợp lệ'}), 400
        text = data.get('text', '').strip()
        print(f"--------------------\n📬 [Đầu vào] Nhận được tin nhắn: '{text[:1000]}...'")
        if not text: return jsonify({'error': 'Không có văn bản để phân tích'}), 400
        result = await perform_full_analysis(text[:3000], data.get('urls', []))
        if 'error' in result:
            return jsonify({'error': result.get('message', 'Lỗi không xác định')}), result.get('status_code', 500)
        print("✅ [Phản hồi] Đã gửi kết quả về cho client.")
        return jsonify({'result': result})
    except Exception as e:
        print(f"🔴 [LỖI NGHIÊM TRỌNG] Lỗi server trong hàm analyze_text: {e}")
        gc.collect()
        return jsonify({'error': 'Lỗi nội bộ server'}), 500

@analyze_endpoint.route('/health', methods=['GET'])
async def health_check():

    return jsonify({'status': 'Bình thường', 'architecture': 'Trivial Filter + Blacklist (AI) + Context Hints + Anna-AI'})

