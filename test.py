import firebase_admin
from firebase_admin import credentials, db, storage
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Flatten
import numpy as np
import cv2
import time

# Firebase setup
cred = credentials.Certificate("D:\download\duan\serviceAccountKey.json")  # Đường dẫn đến ServiceAccountKey.json
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://atmega238p-70bdc-default-rtdb.firebaseio.com/',
    'storageBucket': 'atmega238p-70bdc.firebasestorage.app'
})

# Load labels
labels_path = "D:/Duan/labels.txt"
try:
    with open(labels_path, "r") as file:
        class_names = [line.strip() for line in file.readlines()]
except FileNotFoundError:
    print("Labels file not found!")
    exit()

# Load ML Model
base_model = MobileNetV2(weights="imagenet", include_top=False, input_shape=(224, 224, 3))
base_model.trainable = False  # Freeze base model during transfer learning
model = tf.keras.Sequential([
    base_model,
    tf.keras.layers.Flatten(),
    tf.keras.layers.Dense(128, activation="relu"),
    tf.keras.layers.Dense(len(class_names), activation="softmax")
])
model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
print("Model loaded successfully.")


# Function to download the latest image from Firebase Storage
def download_latest_image_from_firebase(local_path):
    """Download the latest image file from Firebase Storage."""
    try:
        bucket = firebase_admin.storage.bucket()
        blobs = list(bucket.list_blobs(prefix="images/"))  # Lấy danh sách ảnh từ Firebase Storage

        if not blobs:
            print("No images found in Firebase Storage.")
            return None

        latest_blob = max(blobs, key=lambda b: b.updated)
        latest_blob.download_to_filename(local_path)
        print(f"Downloaded image: {latest_blob.name}")
        return local_path

    except Exception as e:
        print(f"Error accessing Firebase Storage: {e}")
        return None


# Function to predict fire from the image
def predict_fire(frame):
    """Run the image through the ML model to predict fire."""
    try:
        resized_frame = cv2.resize(frame, (224, 224))
        normalized_frame = resized_frame / 255.0
        input_data = np.expand_dims(normalized_frame, axis=0)

        predictions = model.predict(input_data)
        predicted_index = np.argmax(predictions)
        confidence = predictions[0][predicted_index]
        label = class_names[predicted_index]

        print(f"Prediction: {label} with confidence {confidence:.2f}")
        return label, confidence
    except Exception as e:
        print(f"Error during prediction: {e}")
        return "Unknown", 0


# Function to send results to Firebase Realtime Database
def send_to_firebase(result):
    """Send the fire detection result to Firebase Realtime Database."""
    try:
        ref = db.reference("fire_detection")  # Giao tiếp với Firebase Database
        ref.set({"result": result})
        print(f"Sent result '{result}' to Firebase Database.")
    except Exception as e:
        print(f"Error sending result to Firebase Database: {e}")


# Main loop for prediction and database communication
try:
    while True:
        # Download latest image from Firebase Storage
        local_image_path = "D:/Duan/imagefile/latest_image.jpg"
        firebase_image_path = download_latest_image_from_firebase(local_image_path)

        if not firebase_image_path:
            print("Retrying image download...")
            time.sleep(5)
            continue

        # Read the downloaded image
        frame = cv2.imread(local_image_path)
        if frame is not None:
            # Make prediction
            label, confidence = predict_fire(frame)

            # Determine the result to send to Firebase Database
            if "Fire" in label and confidence > 0.7:  # Ngưỡng phát hiện lửa
                send_to_firebase(1)  # Fire detected
            else:
                send_to_firebase(0)  # No fire detected

            # Wait to prevent spamming Firebase
            time.sleep(5)
        else:
            print("Error reading image file.")

finally:
    cv2.destroyAllWindows()
    print("Cleanup complete.")
