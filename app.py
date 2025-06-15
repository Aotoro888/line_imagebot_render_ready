from flask import Flask, request, render_template
from dotenv import load_dotenv
import os, sqlite3, datetime, re

from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent
from linebot.v3.exceptions import InvalidSignatureError

load_dotenv()
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")

line_bot_api = MessagingApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

app = Flask(__name__)
os.makedirs("static/images", exist_ok=True)

def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            house_number TEXT,
            month_year TEXT,
            image_path TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT * FROM submissions ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()
    return render_template("index.html", data=rows)

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    print("✅ [DEBUG] Received LINE Webhook")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("❌ Invalid signature.")
        return "Invalid signature", 400

    return "OK", 200

@handler.add(MessageEvent)
def handle_message(event):
    msg_type = event.message.type
    msg_id = event.message.id

    if msg_type == "text":
        text = event.message.text
        house_number, month_year = extract_info(text)

        if house_number and month_year:
            conn = sqlite3.connect("database.db")
            c = conn.cursor()
            c.execute("INSERT INTO submissions (house_number, month_year, image_path, timestamp) VALUES (?, ?, ?, ?)",
                      (house_number, month_year, None, datetime.datetime.now().isoformat()))
            conn.commit()
            conn.close()

            reply = TextMessage(text="✅ ข้อมูลบันทึกแล้ว")
            line_bot_api.reply_message(
                ReplyMessageRequest(reply_token=event.reply_token, messages=[reply])
            )

    elif msg_type == "image":
        image_response = line_bot_api.get_message_content(msg_id)
        filename = f"{msg_id}.jpg"
        path = f"static/images/{filename}"
        with open(path, "wb") as f:
            for chunk in image_response.iter_content():
                f.write(chunk)

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("INSERT INTO submissions (house_number, month_year, image_path, timestamp) VALUES (?, ?, ?, ?)",
                  (None, None, path, datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()

def extract_info(text):
    match = re.search(r'(\d+/\d+)\s*(.+\d{2})', text)
    if match:
        return match.group(1), match.group(2)
    return None, None
