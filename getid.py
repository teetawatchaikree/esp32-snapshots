from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import FollowEvent, TextSendMessage

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = 'Cuh1ljT2/cIyTowwQ/7nMIAPHstRHXOCWL3rN9IhorMmFpCrL09JSf6ph8Y9EnaSNz+Tzc0xpcXqt14Zjpf/YiH2zlohXHYwaJPX8BUs2K9p3/1TofmWpn83p6/JBkI6CY2aUG+hQmTMpA4fq9bh7QdB04t89/1O/w1cDnyilFU='
CHANNEL_SECRET = 'a768db5a4d651536fd368075d5c8c448'

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# Store user IDs in a file or in-memory set (simple example)
user_ids_file = "line_user_ids.txt"

def add_user_id(user_id):
    with open(user_ids_file, "a+") as f:
        f.seek(0)
        user_ids = f.read().splitlines()
        if user_id not in user_ids:
            f.write(user_id + "\n")
            print(f"Added new user ID: {user_id}")

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id
    print(f"New user followed: {user_id}")
    
    # Save user ID
    add_user_id(user_id)

    # Send welcome message
    line_bot_api.push_message(user_id, TextSendMessage(text="Welcome! Thanks for adding me."))

if __name__ == "__main__":
    app.run(port=5000)
