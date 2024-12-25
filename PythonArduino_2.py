import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Flatten
import numpy as np
import cv2
import serial
import time  # Thư viện để thêm delay

# Cấu hình Arduino Serial (đảm bảo chọn đúng cổng COM của Arduino)
arduino_port = "COM7"  # Thay bằng cổng COM tương ứng
baud_rate = 9600

# Kết nối với Arduino với xử lý lỗi
try:
    arduino = serial.Serial(arduino_port, baud_rate, timeout=1)
    time.sleep(2)  # Chờ Arduino khởi động lại
    print(f"Connected to Arduino on {arduino_port}.")
except serial.SerialException as e:
    print(f"Error connecting to Arduino: {e}")
    arduino = None  # Tiếp tục mà không có Arduino

# Kiểm tra GPU
print("GPU Available: ", "Yes" if tf.config.list_physical_devices('GPU') else "No")

# Đường dẫn nhãn
labels_path = "D:/Duan/labels.txt"

# Load nhãn
try:
    with open(labels_path, "r") as file:
        class_names = [line.strip() for line in file.readlines()]
except FileNotFoundError:
    print("Labels file not found!")
    exit()

# Tạo mô hình MobileNetV2
model = Sequential([
    MobileNetV2(weights="imagenet", include_top=False, input_shape=(224, 224, 3)),
    Flatten(),
    Dense(128, activation="relu"),
    Dense(len(class_names), activation="softmax")
])
model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
print("Model loaded.")

# Hàm tiền xử lý khung hình
def preprocess_frame(frame):
    frame = cv2.resize(frame, (224, 224))  # Resize về kích thước đầu vào của mô hình
    frame = frame.astype(np.float32) / 127.5 - 1  # Chuẩn hóa
    return np.expand_dims(frame, axis=0)  # Thêm chiều batch

# Hàm dự đoán
def predict_fire(frame, threshold=0.7):
    data = preprocess_frame(frame)
    prediction = model.predict(data, verbose=0)[0]
    confidence = np.max(prediction)
    return ("Fire Detected" if confidence >= threshold else "No Fire Detected", confidence)

# Khởi động webcam
cam = cv2.VideoCapture(0)
if not cam.isOpened():
    print("Webcam not accessible!")
    exit()

print("Press 'q' to quit.")

# Vòng lặp chính
try:
    while True:
        # Đọc khung hình
        ret, frame = cam.read()
        if not ret:
            print("Error capturing frame.")
            break

        # Dự đoán trên khung hình hiện tại
        label, confidence = predict_fire(frame)
        color = (0, 0, 255) if label == "Fire Detected" else (0, 255, 0)
        cv2.putText(frame, f"{label} ({confidence:.2f})", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

        # Gửi tín hiệu tới Arduino
        if arduino:
            try:
                if label == "Fire Detected":
                    arduino.write(b"1")  # Gửi tín hiệu "1" nếu phát hiện lửa
                else:
                    arduino.write(b"0")  # Gửi tín hiệu "0" nếu không phát hiện lửa
            except serial.SerialException as e:
                print(f"Error writing to Arduino: {e}")
                break

        # Hiển thị kết quả
        cv2.imshow("Fire Detection", frame)

        # Thoát nếu nhấn 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
finally:
    # Giải phóng tài nguyên
    cam.release()
    cv2.destroyAllWindows()
    if arduino:
        arduino.close()
        print("Arduino connection closed.")
