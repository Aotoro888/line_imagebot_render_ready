from flask import Flask, request, render_template, send_from_directory
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient, ReplyMessageRequest, TextMessage, GetMessageContentRequest
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent
from dotenv import load_dotenv
import os, sqlite3, datetime, uuid

# โหลด ENV
load_dotenv()
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")

# ตั้งค่า LINE SDK V3
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
app = Flask(__name__)
handler = WebhookHandler(CHANNEL_SECRET)

# สร้างโฟลเดอร์เก็บรูป
os.makedirs("static/images", exist_ok=True)

# สร้าง DB ถ้ายังไม่มี
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        message_text TEXT,
        image_path TEXT,
        timestamp TEXT
    )''')
    conn.commit()
    conn.close()
init_db()

@app.route("/")
def index():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT user_id, message_text, image_path, timestamp FROM records ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return render_template("index.html", rows=rows)

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    print("✅ [DEBUG] Received LINE Webhook")
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400
    return "OK", 200

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):
    user_id = event.source.user_id
    text = event.message.text
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # บันทึกเฉพาะข้อความ
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("INSERT INTO records (user_id, message_text, image_path, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, text, None, timestamp))
    conn.commit()
    conn.close()

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="📩 รับข้อความแล้ว: " + text)]
            )
        )

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):
    user_id = event.source.user_id
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        content = line_bot_api.get_message_content(message_id=event.message.id)
        ext = ".jpg"
        file_name = str(uuid.uuid4()) + ext
        save_path = os.path.join("static/images", file_name)

        with open(save_path, "wb") as f:
            f.write(content)

        # บันทึก DB
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("INSERT INTO records (user_id, message_text, image_path, timestamp) VALUES (?, ?, ?, ?)",
                  (user_id, None, file_name, timestamp))
        conn.commit()
        conn.close()

        # ตอบกลับผู้ใช้
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="📷 รูปภาพถูกบันทึกเรียบร้อยแล้ว")]
            )
        )

if __name__ == "__main__":
    app.run(debug=True)
