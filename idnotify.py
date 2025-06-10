import cv2
import numpy as np
import os
import subprocess
import time
import requests

from linebot import LineBotApi
from linebot.models import TextSendMessage, ImageSendMessage

# LINE credentials
CHANNEL_ACCESS_TOKEN = 'YOUR_ACCESS_TOKEN'
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)

# URLs
PUBLIC_URL_PREFIX = "https://teetawatchaikree.github.io/esp32-snapshots/snapshots/"
SNAPSHOT_FOLDER = "snapshots"
STREAM_URL = 'http://192.168.1.158/stream'
REPO_PATH = r"C:\Users\User\Desktop\web\esp32-snapshots"
USER_IDS_FILE = "line_user_ids.txt"  # make sure this exists

os.makedirs(SNAPSHOT_FOLDER, exist_ok=True)

def load_user_ids():
    if not os.path.exists(USER_IDS_FILE):
        return []
    with open(USER_IDS_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]

def push_message_to_all_users(text):
    for user_id in load_user_ids():
        try:
            line_bot_api.push_message(user_id, TextSendMessage(text=text))
            print(f"Sent text to {user_id}")
        except Exception as e:
            print(f"Failed to send to {user_id}: {e}")

def push_image_to_all_users(image_url):
    for user_id in load_user_ids():
        try:
            message = ImageSendMessage(
                original_content_url=image_url,
                preview_image_url=image_url
            )
            line_bot_api.push_message(user_id, message)
            print(f"Sent image to {user_id}")
        except Exception as e:
            print(f"Failed to send image to {user_id}: {e}")

def git_push_snapshot_and_confirm(filepath):
    try:
        subprocess.run(['git', 'add', '.'], cwd=REPO_PATH, check=True)
        commit_msg = f"Auto snapshot {time.strftime('%Y-%m-%d %H:%M:%S')}"
        subprocess.run(['git', 'commit', '-m', commit_msg], cwd=REPO_PATH, check=True)
        subprocess.run(['git', 'push'], cwd=REPO_PATH, check=True)
        print("Pushed to GitHub.")

        image_url = PUBLIC_URL_PREFIX + os.path.basename(filepath)
        for attempt in range(10):
            resp = requests.get(image_url)
            if resp.status_code == 200:
                print(f"Image available at {image_url}")
                return image_url
            print(f"Retry {attempt+1}: {resp.status_code}")
            time.sleep(5)

    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}")
    return None

def detect_motion():
    print("Starting motion detection...")
    cap = cv2.VideoCapture(STREAM_URL)
    if not cap.isOpened():
        print("Stream error. Retrying...")
        return

    _, frame1 = cap.read()
    _, frame2 = cap.read()
    cooldown = 10
    last_alert = 0

    while cap.isOpened():
        diff = cv2.absdiff(frame1, frame2)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 20, 255, cv2.THRESH_BINARY)
        dilated = cv2.dilate(thresh, None, iterations=3)
        contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        motion = any(cv2.contourArea(c) > 1000 for c in contours)

        if motion and (time.time() - last_alert) > cooldown:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = f"snapshot_{timestamp}.jpg"
            filepath = os.path.join(SNAPSHOT_FOLDER, filename)
            cv2.imwrite(filepath, frame1)
            print(f"Snapshot saved to {filepath}")

            image_url = git_push_snapshot_and_confirm(filepath)
            if image_url:
                push_message_to_all_users("🚨 Motion detected!")
                push_image_to_all_users(image_url)
            else:
                push_message_to_all_users("⚠️ Motion detected, but upload failed.")

            last_alert = time.time()

        cv2.imshow("ESP32-CAM", frame1)
        frame1 = frame2
        ret, frame2 = cap.read()
        if not ret:
            break
        if cv2.waitKey(30) == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    detect_motion()
