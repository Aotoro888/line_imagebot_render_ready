from flask import Flask, request, abort, render_template
from dotenv import load_dotenv
import os, sqlite3, datetime, re

from linebot.v3.messaging import (
    MessagingApi,
    MessagingApiBlob,
    Configuration,
    ApiClient,
    ReplyMessageRequest,
    TextMessage,
    ContentApi
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent
from linebot.v3.exceptions import InvalidSignatureError

# โหลดตัวแปรจาก .env
load_dotenv()
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# สร้าง Flask app
app = Flask(__name__)
os.makedirs("static/images", exist_ok=True)

# สร้าง DB ถ้ายังไม่มี
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            house_number TEXT,
            month_year TEXT,
            image_path TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# index route
@app.route("/")
def index():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT * FROM records ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return render_template("index.html", records=rows)

# จัดเก็บสถานะของ user รอส่งรูป
pending_users = {}

# callback route
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    print("✅ [DEBUG] Received LINE Webhook")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("❌ Invalid signature")
        abort(400)
    except Exception as e:
        print("🔥 EXCEPTION OCCURRED:")
        print(str(e))
        abort(500)

    return "OK"

# กรณีรับข้อความ
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # ตรวจสอบรูปแบบข้อความ เช่น "39/50 พค 68"
    match = re.match(r"([\d/]+)\s+([ก-ฮA-Za-z]+\s*\d{2,4})", text)
    if match:
        house_number = match.group(1)
        month_year = match.group(2)
        pending_users[user_id] = (house_number, month_year)

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="📷 กรุณาส่งรูปภาพของคุณ")]
                )
            )
    else:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="❗️กรุณาระบุข้อมูลในรูปแบบ: บ้านเลขที่/เลขที่ เช่น 39/50 พค 68")]
                )
            )

# กรณีรับรูปภาพ
@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):
    user_id = event.source.user_id
    if user_id not in pending_users:
        return

    house_number, month_year = pending_users[user_id]

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        content_api = ContentApi(api_client)

        message_id = event.message.id
        content = content_api.get_message_content(message_id)
        data = content.read()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = f"static/images/{house_number.replace('/', '_')}_{timestamp}.jpg"
        with open(image_path, "wb") as f:
            f.write(data)

        # บันทึกลง DB
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("INSERT INTO records (house_number, month_year, image_path, created_at) VALUES (?, ?, ?, ?)",
                  (house_number, month_year, image_path, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()

        # ตอบกลับ
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="✅ บันทึกรูปภาพและข้อมูลเรียบร้อยแล้ว")]
            )
        )

        # ล้างสถานะ
        del pending_users[user_id]
