from flask import Flask, request, jsonify, render_template
import csv
import os
import time

app = Flask(__name__)

CSV_FILE = "sensor_data.csv"
ALERT_THRESHOLD_HIGH = 120
ALERT_THRESHOLD_LOW = 50
ALERT_DURATION = 10  # Thời gian liên tục để kích hoạt cảnh báo (giây)
alert_active = False
alert_start_time = None
alert_type = ""

# Tạo file CSV nếu chưa có
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["IR_value", "BPM", "AvgBPM"])

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/get_data')
def get_data():
    global alert_active, alert_start_time, alert_type
    data = []
    try:
        with open(CSV_FILE, mode='r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                data.append({
                    "IR_value": row["IR_value"],
                    "BPM": row["BPM"],
                    "AvgBPM": row["AvgBPM"]
                })
        
        if len(data) > 10:
            recent_data = [float(d["AvgBPM"]) for d in data[-10:] if d["AvgBPM"]]
            if all(bpm > ALERT_THRESHOLD_HIGH for bpm in recent_data):
                if not alert_active:
                    alert_active = True
                    alert_start_time = time.time()
                    alert_type = "Nhịp tim quá cao!"
                elif time.time() - alert_start_time >= ALERT_DURATION:
                    return jsonify(data + [{"alert": alert_type}])
            elif all(bpm < ALERT_THRESHOLD_LOW for bpm in recent_data):
                if not alert_active:
                    alert_active = True
                    alert_start_time = time.time()
                    alert_type = "Nhịp tim quá thấp!"
                elif time.time() - alert_start_time >= ALERT_DURATION:
                    return jsonify(data + [{"alert": alert_type}])
            else:
                alert_active = False
                alert_start_time = None
                alert_type = ""
    except Exception as e:
        print("Error reading file:", e)

    return jsonify(data)

@app.route('/data', methods=['POST'])
def receive_data():
    try:
        json_data = request.get_json()

        ir_value = json_data.get("IR_value")
        bpm = json_data.get("BPM")
        avg_bpm = json_data.get("AvgBPM")

        # Kiểm tra nếu dữ liệu hợp lệ (không None, không phải 0 nếu không hợp lý)
        if ir_value and bpm and avg_bpm:
            with open(CSV_FILE, mode="a", newline="") as file:
                writer = csv.writer(file)
                writer.writerow([ir_value, bpm, avg_bpm])

            return jsonify({"message": "Data received!"}), 200
        else:
            return jsonify({"error": "Invalid data received!"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
