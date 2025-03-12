from flask import Flask, request, jsonify, render_template
import csv
import os
import time
import numpy as np
import joblib
import tensorflow as tf

app = Flask(__name__)

CSV_FILE = "sensor_data.csv"
MODEL_FILE = "health_model.h5"
SCALER_FILE = "scaler.pkl"
ENCODER_FILE = "label_encoder.pkl"

# Tải mô hình AI và scaler
model = tf.keras.models.load_model(MODEL_FILE)
scaler = joblib.load(SCALER_FILE)
label_encoder = joblib.load(ENCODER_FILE)

# Tạo file CSV nếu chưa có
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["IR_value", "BPM", "AvgBPM", "Accel_X", "Accel_Y", "Accel_Z", "A_total"])

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/get_data')
def get_data():
    data = []
    health_status = ""

    try:
        with open(CSV_FILE, mode='r', newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                data.append({
                    "IR_value": float(row["IR_value"]),
                    "BPM": float(row["BPM"]),
                    "AvgBPM": float(row["AvgBPM"]),
                    "Accel_X": float(row["Accel_X"]),
                    "Accel_Y": float(row["Accel_Y"]),
                    "Accel_Z": float(row["Accel_Z"]),
                    "A_total": float(row["A_total"])
                })
        
        # Lấy dữ liệu mới nhất để dự đoán
        if data:
            latest_data = data[-1]
            input_data = np.array([[latest_data["AvgBPM"], latest_data["A_total"]]])
            input_data = scaler.transform(input_data)  # Chuẩn hóa dữ liệu

            prediction = model.predict(input_data)
            predicted_label = np.argmax(prediction)
            health_status = label_encoder.inverse_transform([predicted_label])[0]

            print(f"Dự đoán: {health_status}")  # Debug thông tin dự đoán

    except Exception as e:
        print("Error reading file:", e)

    return jsonify({"data": data[-10:], "health_status": health_status})


@app.route('/data', methods=['POST'])
def receive_data():
    try:
        json_data = request.get_json()
        print("Received JSON:", json_data)  # Debug JSON nhận được

        if not json_data:
            return jsonify({"error": "No JSON received!"}), 400
        
        required_keys = ["IR_value", "BPM", "AvgBPM", "Accel_X", "Accel_Y", "Accel_Z", "A_total"]
        if any(key not in json_data or json_data[key] is None for key in required_keys):
            return jsonify({"error": "Invalid data received!", "data": json_data}), 400

        with open(CSV_FILE, mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([json_data[key] for key in required_keys])

        return jsonify({"message": "Data received!"}), 200

    except Exception as e:
        print("Error:", str(e))  # Debug lỗi
        return jsonify({"error": str(e)}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
