import requests
import cv2
import numpy as np
from firebase_admin import credentials, initialize_app, storage
from datetime import datetime
import time
import subprocess
import re


# Firebase Setup
cred = credentials.Certificate("D:/download/duan/serviceAccountKey.json")
initialize_app(cred, {'storageBucket': 'atmega238p-70bdc.firebasestorage.app'})
bucket = storage.bucket()


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


def get_esp32_ip():
    """
    Thực hiện quét mạng bằng lệnh nmap thông qua subprocess và regex.
    """
    try:
        print("Scanning network for ESP32...")
        # Thêm đường dẫn đầy đủ tới nmap.exe
        result = subprocess.run(
            [r"C:\Program Files (x86)\Nmap\nmap.exe", "-sn", "192.168.0.0/24"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Kiểm tra đầu ra của lệnh
        output = result.stdout
        # Tìm IP ESP32 thông qua regex
        match = re.search(r"(\d+\.\d+\.\d+\.\d+)", output)
        if match:
            esp32_ip = match.group(1)
            print(f"Found ESP32 at IP: {esp32_ip}")
            return esp32_ip
        else:
            print("Không tìm thấy ESP32 qua Nmap.")
            return None
    except Exception as e:
        print(f"Lỗi trong quá trình quét IP ESP32: {e}")
        return None


def fetch_stream(stream_url):
    """
    Logic lấy stream từ ESP32-CAM và retry nếu gặp lỗi.
    """
    while True:
        try:
            print("Attempting connection to ESP32-CAM stream...")
            with requests.get(stream_url, stream=True, timeout=5) as response:
                if response.status_code == 200:
                    print("Connected to stream server...")
                    bytes_data = b""
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            bytes_data += chunk
                            # Tìm khung hình JPEG
                            start_idx = bytes_data.find(b'\xff\xd8')
                            end_idx = bytes_data.find(b'\xff\xd9')
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
            print(f"Stream error: {e}")
            time.sleep(2)  # Retry sau 2 giây


def main():
    """
    Logic chính, thực hiện dò tìm và kết nối stream từ ESP32.
    """
    esp32_ip = None
    # Thử dò IP động từ ESP32 trong mạng LAN
    while esp32_ip is None:
        try:
            esp32_ip = get_esp32_ip()
            if esp32_ip is None:
                print("Không tìm thấy ESP32, thử lại sau 2 giây...")
                time.sleep(2)
        except Exception as e:
            print(f"Lỗi trong quá trình dò tìm ESP32: {e}")
            time.sleep(2)

    # Thêm URL vào sau khi đã tìm thấy IP động
    stream_url = f"http://{esp32_ip}:80/stream"
    print(f"Stream URL: {stream_url}")

    frame_count = 0  # Dùng để hạn chế upload đến Firebase
    try:
        for frame in fetch_stream(stream_url):
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
    except Exception as e:
        print(f"Lỗi trong quá trình stream từ ESP32: {e}")
    finally:
        # Giải phóng tài nguyên
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
