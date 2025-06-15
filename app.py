from flask import Flask, request, abort, render_template
from dotenv import load_dotenv
import os, sqlite3, datetime, traceback

from linebot.v3.messaging import (
    MessagingApi, ReplyMessageRequest, TextMessage as V3TextMessage,
    Configuration, ApiClient
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent

load_dotenv()
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
line_bot_api = MessagingApi(ApiClient(configuration))
handler = WebhookHandler(CHANNEL_SECRET)

app = Flask(__name__)
os.makedirs("static/images", exist_ok=True)

def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT,
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
    c.execute("SELECT * FROM data ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()
    return render_template("index.html", rows=rows)

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    print("✅ [DEBUG] Received LINE Webhook")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("❌ Invalid signature!")
        abort(400)
    except Exception:
        print("🔥 EXCEPTION OCCURRED:")
        print(traceback.format_exc())
        abort(500)

    return "OK"

@handler.add(MessageEvent)
def handle_message(event):
    text = None

    if isinstance(event.message, TextMessageContent):
        text = event.message.text
        reply = V3TextMessage(text=f"✅ รับข้อความแล้ว: {text}")
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[reply]
            )
        )

    if text:
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("INSERT INTO data (text, image_path, timestamp) VALUES (?, ?, ?)", (
            text,
            None,
            datetime.datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()

if __name__ == "__main__":
    app.run(debug=True)
