import cv2
import os
import subprocess
import time
import requests
from datetime import datetime
from linebot import LineBotApi
from linebot.models import TextSendMessage, ImageSendMessage

# === LINE Messaging API Configuration ===
CHANNEL_ACCESS_TOKEN = 'Cuh1ljT2/cIyTowwQ/7nMIAPHstRHXOCWL3rN9IhorMmFpCrL09JSf6ph8Y9EnaSNz+Tzc0xpcXqt14Zjpf/YiH2zlohXHYwaJPX8BUs2K9p3/1TofmWpn83p6/JBkI6CY2aUG+hQmTMpA4fq9bh7QdB04t89/1O/w1cDnyilFU='
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
USER_ID_FILE = "line_user_ids.txt"

# === GitHub Pages Configuration ===
REPO_PATH = r"C:\Users\User\Desktop\web\esp32-snapshots"
SNAPSHOT_FOLDER = os.path.join(REPO_PATH, "snapshots")
PUBLIC_URL_PREFIX = "https://teetawatchaikree.github.io/esp32-snapshots/snapshots/"
os.makedirs(SNAPSHOT_FOLDER, exist_ok=True)

# === Stream Configuration ===
STREAM_URL = 'http://192.168.1.158/stream'
COOLDOWN = 10  # seconds
RETRY_INTERVAL = 5
last_alert_time = 0

# === Utility Functions ===

def load_user_ids():
    if os.path.exists(USER_ID_FILE):
        with open(USER_ID_FILE, "r") as f:
            return list(set(line.strip() for line in f if line.strip()))
    return []

def send_text_to_all(text):
    for uid in load_user_ids():
        try:
            line_bot_api.push_message(uid, TextSendMessage(text=text))
        except Exception as e:
            print(f"Error sending message to {uid}: {e}")

def send_image_to_all(image_url):
    for uid in load_user_ids():
        try:
            image_message = ImageSendMessage(
                original_content_url=image_url,
                preview_image_url=image_url
            )
            line_bot_api.push_message(uid, image_message)
        except Exception as e:
            print(f"Error sending image to {uid}: {e}")

def git_push_and_confirm(filepath):
    try:
        subprocess.run(['git', 'add', '.'], cwd=REPO_PATH, check=True)
        subprocess.run(['git', 'commit', '-m', f"Auto snapshot {datetime.now()}"], cwd=REPO_PATH, check=True)
        subprocess.run(['git', 'push'], cwd=REPO_PATH, check=True)
        print("✅ Pushed to GitHub.")

        image_url = PUBLIC_URL_PREFIX + os.path.basename(filepath)
        for attempt in range(12):
            try:
                if requests.get(image_url).status_code == 200:
                    print(f"✅ Image is available: {image_url}")
                    return image_url
            except requests.RequestException:
                pass
            print(f"⏳ Retry {attempt + 1}: waiting for GitHub Pages...")
            time.sleep(RETRY_INTERVAL)
    except subprocess.CalledProcessError as e:
        print(f"❌ Git error: {e}")
    return None

# === Main Loop ===
print("🔁 Starting infinite motion detection loop... Press ESC in window or Ctrl+C to stop.")

try:
    while True:
        print("🎥 Connecting to video stream...")
        cap = cv2.VideoCapture(STREAM_URL)
        if not cap.isOpened():
            print("❌ Failed to open video stream. Retrying in 10s...")
            time.sleep(10)
            continue

        ret, frame1 = cap.read()
        ret2, frame2 = cap.read()
        if not ret or not ret2:
            print("❌ Failed to read initial frames. Retrying...")
            cap.release()
            time.sleep(5)
            continue

        while cap.isOpened():
            diff = cv2.absdiff(frame1, frame2)
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            _, thresh = cv2.threshold(blur, 20, 255, cv2.THRESH_BINARY)
            dilated = cv2.dilate(thresh, None, iterations=3)
            contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            motion = any(cv2.contourArea(c) > 1000 for c in contours)
            current_time = time.time()

            if motion and (current_time - last_alert_time > COOLDOWN):
                print("🚨 Motion detected!")
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                filename = f"snapshot_{timestamp}.jpg"
                filepath = os.path.join(SNAPSHOT_FOLDER, filename)

                cv2.imwrite(filepath, frame1)
                print(f"💾 Snapshot saved: {filepath}")

                image_url = git_push_and_confirm(filepath)
                if image_url:
                    send_text_to_all("📸 Motion Detected!")
                    send_image_to_all(image_url)
                else:
                    send_text_to_all("⚠️ Motion detected, but image upload failed.")

                last_alert_time = current_time

            cv2.imshow("ESP32-CAM Motion Detection", frame1)

            frame1 = frame2
            ret, frame2 = cap.read()

            if not ret or cv2.waitKey(30) == 27:
                print("⛔ ESC pressed or stream dropped.")
                break

        cap.release()
        cv2.destroyAllWindows()
        print("🔁 Restarting stream after disconnect...")
        time.sleep(5)

except KeyboardInterrupt:
    print("\n🛑 Program interrupted by user. Exiting.")
    cv2.destroyAllWindows()
