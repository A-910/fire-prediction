import requests
import cv2
import numpy as np

ESP32_STREAM_URL = "http://172.20.10.5/stream"

response = requests.get(ESP32_STREAM_URL, stream=True)
if response.status_code == 200:
    print("Kết nối thành công!")
    bytes_data = b""
    for chunk in response.iter_content(chunk_size=1024):
        bytes_data += chunk
        a = bytes_data.find(b"\xff\xd8")  # JPEG start marker
        b = bytes_data.find(b"\xff\xd9")  # JPEG end marker

        if a != -1 and b != -1 and a < b:
            jpg = bytes_data[a:b + 1]
            bytes_data = bytes_data[b + 1:]
            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)

            if frame is not None:
                cv2.imshow("ESP32-CAM Stream", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
else:
    print("Không thể kết nối tới luồng MJPEG")
