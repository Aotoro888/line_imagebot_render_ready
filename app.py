from flask import Flask, request, render_template
from dotenv import load_dotenv
import os, sqlite3, datetime

from linebot.v3.messaging import (
    MessagingApi,
    MessagingApiBlob,
    Configuration,
    ApiClient,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent
from linebot.v3.exceptions import InvalidSignatureError

# โหลด .env
load_dotenv()
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")

# LINE Bot SDK
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)
line_bot_blob = MessagingApiBlob(api_client)
handler = WebhookHandler(CHANNEL_SECRET)

# Flask App
app = Flask(__name__)
os.makedirs("static/images", exist_ok=True)

# DB Init
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        text TEXT,
        image_path TEXT,
        timestamp TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT * FROM records ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return render_template("index.html", rows=rows)

@app.route('/callback', methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return 'Invalid signature', 400
    except Exception as e:
        print(f"🔥 Error: {e}")
        return 'Error', 500

    return 'OK', 200

@handler.add(MessageEvent)
def handle_message(event):
    user_id = event.source.user_id
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(event.message, TextMessageContent):
        text = event.message.text.strip()
        save_to_db(user_id, text, None, timestamp)
        reply = TextMessage(text="✅ ข้อความถูกบันทึกแล้ว")
        line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply]))

    elif isinstance(event.message, ImageMessageContent):
        msg_id = event.message.id
        image_data = line_bot_blob.get_message_content(msg_id)
        filename = f"static/images/{user_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"

        with open(filename, 'wb') as f:
            for chunk in image_data:
                f.write(chunk)

        save_to_db(user_id, None, filename, timestamp)
        reply = TextMessage(text="📷 รูปภาพถูกบันทึกเรียบร้อย")
        line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply]))

def save_to_db(user_id, text, image_path, timestamp):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("INSERT INTO records (user_id, text, image_path, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, text, image_path, timestamp))
    conn.commit()
    conn.close()
