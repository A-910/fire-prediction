import requests
import cv2
import numpy as np
from firebase_admin import credentials, initialize_app, storage
from datetime import datetime
import time

# Firebase Setup
cred = credentials.Certificate("/home/toanlybmt/serviceAccountKey.json")
initialize_app(cred, {'storageBucket': 'atmega238p-70bdc.firebasestorage.app'})
bucket = storage.bucket()

# ESP32-CAM Stream URL
ESP32_STREAM_URL = "http://34.41.46.164:80/stream"


def upload_image_to_firebase(image_data):
    """
    Upload ảnh lên Firebase Storage.
    """
    try:
        # Timestamp for unique file name
        file_name = f"images/{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        blob = bucket.blob(file_name)

        # Upload image to Firebase
        blob.upload_from_string(image_data, content_type="image/jpeg")
        blob.make_public()
        print(f"Image uploaded: {blob.public_url}")
        return blob.public_url
    except Exception as e:
        print(f"Error uploading image: {e}")
        return None


def fetch_stream():
    """
    Logic lấy stream từ ESP32-CAM và đảm bảo retry logic.
    """
    while True:
        try:
            print("Attempting connection to ESP32-CAM stream...")
            with requests.get(ESP32_STREAM_URL, stream=True, timeout=5) as response:
                if response.status_code == 200:
                    print("Connected to stream server...")
                    bytes_data = b""
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            bytes_data += chunk
                            # Tìm khung hình JPEG
                            start_idx = bytes_data.find(b'\xff\xd8')  # JPEG start
                            end_idx = bytes_data.find(b'\xff\xd9')  # JPEG end
                            if start_idx != -1 and end_idx != -1:
                                frame_data = bytes_data[start_idx:end_idx + 2]
                                bytes_data = bytes_data[end_idx + 2:]

                                # Decode khung hình
                                frame = cv2.imdecode(np.frombuffer(frame_data, np.uint8), cv2.IMREAD_COLOR)
                                if frame is not None:
                                    yield frame
                else:
                    print(f"Stream error: HTTP {response.status_code}")
        except (requests.exceptions.RequestException, ConnectionResetError) as e:
            print(f"Stream error or connection reset: {e}")
            time.sleep(2)  # Retry sau 2 giây


def main():
    """
    Logic chính.
    """
    frame_count = 0  # Dùng để hạn chế upload đến Firebase
    for frame in fetch_stream():
        try:
            # Hiển thị khung hình
            cv2.imshow("ESP32-CAM Stream", frame)

            # Giảm tốc độ upload (mỗi 5 khung hình)
            if frame_count % 5 == 0:  # Upload mỗi 5 khung hình
                _, buffer = cv2.imencode('.jpg', frame)  # Mã hóa khung hình thành byte stream
                upload_image_to_firebase(buffer.tobytes())

            frame_count += 1  # Tăng bộ đếm khung hình

            # Thoát nếu nhấn 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("User requested exit...")
                break

            time.sleep(0.1)  # Giảm tốc độ vòng lặp chính
        except Exception as e:
            print(f"Unexpected error: {e}")

    # Giải phóng tài nguyên
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
