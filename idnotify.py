# Save this as motion_multicam.py

import cv2
import os
import subprocess
import time
import requests
from datetime import datetime
from linebot import LineBotApi
from linebot.models import TextSendMessage, ImageSendMessage

CHANNEL_ACCESS_TOKEN = 'Cuh1ljT2/cIyTowwQ/7nMIAPHstRHXOCWL3rN9IhorMmFpCrL09JSf6ph8Y9EnaSNz+Tzc0xpcXqt14Zjpf/YiH2zlohXHYwaJPX8BUs2K9p3/1TofmWpn83p6/JBkI6CY2aUG+hQmTMpA4fq9bh7QdB04t89/1O/w1cDnyilFU='
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
USER_ID_FILE = "line_user_ids.txt"

REPO_PATH = r"C:\Users\User\Desktop\web\esp32-snapshots"
SNAPSHOT_FOLDER = os.path.join(REPO_PATH, "snapshots")
PUBLIC_URL_PREFIX = "https://teetawatchaikree.github.io/esp32-snapshots/snapshots/"
os.makedirs(SNAPSHOT_FOLDER, exist_ok=True)

CAM_STREAMS = {
    'CAM1': 'http://192.168.1.158/stream',
    # Add more like 'CAM2': 'http://192.168.1.xxx/stream'
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
            msg = ImageSendMessage(image_url, image_url)
            line_bot_api.push_message(uid, msg)
        except Exception as e:
            print(f"Error sending image to {uid}: {e}")

def git_push_and_confirm(filepath):
    try:
        subprocess.run(['git', 'add', '.'], cwd=REPO_PATH, check=True)
        subprocess.run(['git', 'commit', '-m', f"Auto snapshot {datetime.now()}"], cwd=REPO_PATH, check=True)
        subprocess.run(['git', 'push'], cwd=REPO_PATH, check=True)
        print("✅ Pushed to GitHub.")
        url = PUBLIC_URL_PREFIX + os.path.basename(filepath)
        for i in range(12):
            try:
                if requests.get(url).status_code == 200:
                    print(f"✅ Image available: {url}")
                    return url
            except:
                pass
            print(f"⏳ Retry {i+1}: Waiting for GitHub Pages...")
            time.sleep(RETRY_INTERVAL)
    except subprocess.CalledProcessError as e:
        print(f"❌ Git error: {e}")
    return None

def monitor_camera(name, url):
    print(f"📷 Starting monitoring for {name}")
    last_alert_time = 0

    while True:
        print(f"🎥 Connecting to {name}...")
        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            print(f"❌ Failed to open {name}. Retrying...")
            time.sleep(10)
            continue

        ret, frame1 = cap.read()
        ret2, frame2 = cap.read()
        if not ret or not ret2:
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

            motion = False
            for c in contours:
                if cv2.contourArea(c) > 1000:
                    motion = True
                    (x, y, w, h) = cv2.boundingRect(c)
                    cv2.rectangle(frame1, (x, y), (x + w, y + h), (0, 255, 0), 2)

            now = time.time()
            if motion and (now - last_alert_time > COOLDOWN):
                print(f"🚨 Motion on {name}!")
                ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                fname = f"{name}_snapshot_{ts}.jpg"
                fpath = os.path.join(SNAPSHOT_FOLDER, fname)

                cv2.imwrite(fpath, frame1)
                print(f"💾 Saved: {fpath}")

                url = git_push_and_confirm(fpath)
                if url:
                    send_text_to_all(f"📸 Motion Detected on {name}")
                    send_image_to_all(url)
                else:
                    send_text_to_all(f"⚠️ Motion on {name}, but upload failed.")

                last_alert_time = now

            frame1 = frame2
            ret, frame2 = cap.read()
            if not ret or cv2.waitKey(30) == 27:
                break

        cap.release()
        cv2.destroyAllWindows()
        time.sleep(5)

print("🔁 Starting multi-camera monitoring...")
try:
    for cam_name, cam_url in CAM_STREAMS.items():
        monitor_camera(cam_name, cam_url)
except KeyboardInterrupt:
    print("🛑 Stopped by user.")
    cv2.destroyAllWindows()
