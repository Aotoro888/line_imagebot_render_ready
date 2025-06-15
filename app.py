from flask import Flask, request, render_template, abort
from dotenv import load_dotenv
import os, sqlite3, datetime, re, base64

from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.messaging.models import ReplyMessageRequest, TextMessage

# โหลด .env
load_dotenv()
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")

# LINE Config
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

app = Flask(__name__)
os.makedirs("static/images", exist_ok=True)

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    house_number TEXT,
                    month_year TEXT,
                    image_path TEXT,
                    created_at TEXT
                )''')
    conn.commit()
    conn.close()

init_db()

# --- HOME PAGE ---
@app.route("/")
def index():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT house_number, month_year, image_path, created_at FROM records ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return render_template("index.html", records=rows)

# --- LINE CALLBACK ---
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    app.logger.debug("✅ [DEBUG] Received LINE Webhook")
    try:
        handler.handle(body, signature)
    except Exception as e:
        app.logger.error("🔥 EXCEPTION OCCURRED:\n" + str(e))
        abort(500)
    return "OK"

# --- MESSAGE EVENT ---
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text.strip()
    match = re.search(r'(\d{1,4}/\d{1,4})\s*(\w+)\s*(\d{2,4})', text)
    if match:
        house_number = match.group(1)
        month_year = match.group(2) + " " + match.group(3)
        # ตอบกลับเพื่อยืนยัน
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"📌 ได้รับข้อมูล: {house_number} ({month_year})\nกรุณาส่งรูปภาพต่อไป")]
                )
            )
        # เก็บไว้ใน memory ผ่าน user_id
        user_id = event.source.user_id
        pending_users[user_id] = (house_number, month_year)

pending_users = {}

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):
    user_id = event.source.user_id
    if user_id not in pending_users:
        return  # ไม่บันทึกถ้าไม่ได้ส่งข้อความก่อน

    house_number, month_year = pending_users[user_id]
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        message_id = event.message.id
        content = line_bot_api.get_message_content(message_id)
        b64_data = base64.b64encode(content.read()).decode("utf-8")

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = f"static/images/{house_number.replace('/', '_')}_{timestamp}.jpg"

        # เซฟเป็นไฟล์
        with open(image_path, "wb") as f:
            f.write(base64.b64decode(b64_data))

        # บันทึก DB
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
        del pending_users[user_id]

if __name__ == "__main__":
    app.run(debug=True)

