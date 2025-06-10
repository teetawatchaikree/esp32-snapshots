import cv2
import os
import subprocess
import time
import requests
from datetime import datetime
from linebot import LineBotApi
from linebot.models import TextSendMessage, ImageSendMessage
from threading import Thread

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
CAM_STREAMS = {
    'CAM1': 'http://192.168.1.158/stream',
    # Add more cameras if needed
}
COOLDOWN = 10
RETRY_INTERVAL = 5

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
                    print(f"✅ Image available: {image_url}")
                    return image_url
            except:
                pass
            print(f"⏳ Retry {attempt+1} for {image_url}")
            time.sleep(RETRY_INTERVAL)
    except subprocess.CalledProcessError as e:
        print(f"❌ Git error: {e}")
    return None

def monitor_camera(name, url):
    print(f"📡 Starting camera monitor: {name}")
    last_alert_time = 0

    while True:
        print(f"🎥 Connecting to {name}...")
        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            print(f"❌ {name} stream offline. Retrying in 10s...")
            time.sleep(10)
            continue

        ret, frame1 = cap.read()
        ret2, frame2 = cap.read()
        if not ret or not ret2:
            print(f"❌ {name}: Failed to read initial frames. Reconnecting...")
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

            motion_detected = False
            for contour in contours:
                if cv2.contourArea(contour) > 1000:
                    motion_detected = True
                    (x, y, w, h) = cv2.boundingRect(contour)
                    cv2.rectangle(frame1, (x, y), (x + w, y + h), (0, 255, 0), 2)

            current_time = time.time()
            if motion_detected and (current_time - last_alert_time) > COOLDOWN:
                print(f"🚨 Motion detected on {name}!")
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                filename = f"{name}_snapshot_{timestamp}.jpg"
                filepath = os.path.join(SNAPSHOT_FOLDER, filename)

                cv2.imwrite(filepath, frame1)
                print(f"💾 {name}: Snapshot saved to {filepath}")

                image_url = git_push_and_confirm(filepath)
                if image_url:
                    send_text_to_all(f"📸 Motion Detected on {name}")
                    send_image_to_all(image_url)
                else:
                    send_text_to_all(f"⚠️ Motion detected on {name}, but image upload failed.")

                last_alert_time = current_time

            frame1 = frame2
            ret, frame2 = cap.read()
            if not ret:
                print(f"🔌 {name} stream dropped. Reconnecting...")
                break

        cap.release()
        time.sleep(5)

# === Start Threads for Each Camera ===
print("🔁 Launching camera threads...")
for cam_name, stream_url in CAM_STREAMS.items():
    Thread(target=monitor_camera, args=(cam_name, stream_url), daemon=True).start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Stopping camera monitoring.")
    cv2.destroyAllWindows()

