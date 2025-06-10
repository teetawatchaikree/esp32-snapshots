import cv2
import numpy as np
import os
import subprocess
from linebot import LineBotApi
from linebot.models import TextSendMessage, ImageSendMessage
import time
import requests

# === Replace these with your actual LINE Channel Access Token and User ID ===
CHANNEL_ACCESS_TOKEN = 'Cuh1ljT2/cIyTowwQ/7nMIAPHstRHXOCWL3rN9IhorMmFpCrL09JSf6ph8Y9EnaSNz+Tzc0xpcXqt14Zjpf/YiH2zlohXHYwaJPX8BUs2K9p3/1TofmWpn83p6/JBkI6CY2aUG+hQmTMpA4fq9bh7QdB04t89/1O/w1cDnyilFU='
USER_ID = ' Ub57a382de5af92d005c615f4e662d91b'

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)

def push_message(user_id, text):
    try:
        line_bot_api.push_message(user_id, TextSendMessage(text=text))
        print("LINE text message sent.")
    except Exception as e:
        print("LINE message error:", e)

def push_image_message(user_id, image_url):
    try:
        message = ImageSendMessage(
            original_content_url=image_url,
            preview_image_url=image_url
        )
        line_bot_api.push_message(user_id, message)
        print("LINE image message sent.")
    except Exception as e:
        print("LINE image message error:", e)

def git_push_snapshot_and_confirm(filename):
    repo_path = r"C:\Users\User\Desktop\web\esp32-snapshots"
    public_url_prefix = "https://teetawatchaikree.github.io/esp32-snapshots/snapshots/"
    max_retries = 10
    wait_seconds = 5

    try:
        # Add all changes in repo (better to add '.' in case multiple files)
        subprocess.run(['git', 'add', '.'], cwd=repo_path, check=True)

        commit_message = f"Auto snapshot commit {time.strftime('%Y-%m-%d %H:%M:%S')}"
        result = subprocess.run(['git', 'commit', '-m', commit_message], cwd=repo_path, capture_output=True, text=True)

        if result.returncode != 0:
            if "nothing to commit" in result.stderr.lower():
                print("No new changes to commit.")
            else:
                print("Git commit error:", result.stderr)
                return None
        else:
            print("Committed snapshot.")

        subprocess.run(['git', 'push'], cwd=repo_path, check=True)
        print("Pushed to GitHub.")

        image_url = public_url_prefix + os.path.basename(filename)
        print(f"Checking upload status: {image_url}")

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(image_url, timeout=5)
                if response.status_code == 200:
                    print(f"✅ Image is now available at: {image_url}")
                    return image_url
                else:
                    print(f"❌ Attempt {attempt}: Not available yet (status {response.status_code})")
            except Exception as req_err:
                print(f"Request error on attempt {attempt}: {req_err}")
            time.sleep(wait_seconds)

        print("❌ Image did not become available after retries.")
        return None

    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}")
        return None

# ESP32-CAM stream URL
stream_url = 'http://192.168.1.158/stream'

# Folder to save snapshots locally
SNAPSHOT_FOLDER = "snapshots"
os.makedirs(SNAPSHOT_FOLDER, exist_ok=True)

cooldown = 10  # seconds between alerts
last_alert_time = 0

print("Starting motion detection... Press ESC to exit.")

while True:
    print("Opening video stream...")
    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        print("Error opening video stream. Retrying in 5 seconds...")
        time.sleep(5)
        continue

    ret, frame1 = cap.read()
    ret2, frame2 = cap.read()
    if not ret or not ret2:
        print("Error reading initial frames. Retrying in 5 seconds...")
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
        for contour in contours:
            if cv2.contourArea(contour) < 1000:
                continue
            motion = True
            (x, y, w, h) = cv2.boundingRect(contour)
            cv2.rectangle(frame1, (x, y), (x + w, y + h), (0, 255, 0), 2)

        current_time = time.time()

        if motion and (current_time - last_alert_time) > cooldown:
            print("Motion detected!")
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = f"snapshot_{timestamp}.jpg"
            filepath = os.path.join(SNAPSHOT_FOLDER, filename)

            cv2.imwrite(filepath, frame1)
            print(f"Snapshot saved to {filepath}")

            # Push snapshot and confirm upload
            image_url = git_push_snapshot_and_confirm(filepath)
            if image_url:
                push_message(USER_ID, "Motion Detected")
                push_image_message(USER_ID, image_url)
            else:
                push_message(USER_ID, "Motion detected but failed to upload image.")

            last_alert_time = current_time
            motion = False

        cv2.imshow("ESP32-CAM Motion Detection", frame1)

        frame1 = frame2
        ret, frame2 = cap.read()
        if not ret:
            print("Stream disconnected, reconnecting...")
            break

        if cv2.waitKey(30) == 27:  # ESC to exit
            print("Exiting...")
            cap.release()
            cv2.destroyAllWindows()
            exit()

    cap.release()
    cv2.destroyAllWindows()
    time.sleep(5)


