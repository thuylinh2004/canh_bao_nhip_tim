#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include "MAX30105.h"
#include "heartRate.h"

#define WIFI_SSID "hi"
#define WIFI_PASSWORD "12345678"
#define SERVER_URL "http://192.168.165.193:5000/data"  // Thay bằng IP Flask server

MAX30105 particleSensor;
const byte RATE_SIZE = 4;
byte rates[RATE_SIZE];
byte rateSpot = 0;
long lastBeat = 0;
float beatsPerMinute = 0;
int beatAvg = 0;

void setup() {
  Serial.begin(115200);
  Serial.println("Initializing...");

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi!");
  Serial.print("ESP32 IP Address: ");
  Serial.println(WiFi.localIP());

  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("MAX30105 not found. Please check wiring!");
    while (1);
  }
  Serial.println("Place your index finger on the sensor.");

  particleSensor.setup();
  particleSensor.setPulseAmplitudeRed(0x0A);
  particleSensor.setPulseAmplitudeGreen(0);

  xTaskCreatePinnedToCore(
    readSensorTask,  // Task function
    "ReadSensor",    // Tên task
    4096,            // Dung lượng stack
    NULL,            // Tham số task
    1,               // Độ ưu tiên
    NULL,            // Handle task
    0                // Chạy trên Core 0
  );
}

// Task đọc cảm biến (chạy trên Core 0)
void readSensorTask(void *pvParameters) {
  while (true) {
    long irValue = particleSensor.getIR();

    if (irValue < 50000) {  // Nếu không có ngón tay
      Serial.println("No finger detected! Skipping calculations.");
      beatsPerMinute = 0;
      beatAvg = 0;
    } else {
      if (checkForBeat(irValue)) {
        long delta = millis() - lastBeat;
        lastBeat = millis();
        beatsPerMinute = 60 / (delta / 1000.0);

        if (beatsPerMinute < 255 && beatsPerMinute > 20) {
          rates[rateSpot++] = (byte)beatsPerMinute;
          rateSpot %= RATE_SIZE;

          beatAvg = 0;
          for (byte x = 0; x < RATE_SIZE; x++)
            beatAvg += rates[x];
          beatAvg /= RATE_SIZE;
        }
      }
    }

    Serial.print("IR=");
    Serial.print(irValue);
    Serial.print(", BPM=");
    Serial.print(beatsPerMinute);
    Serial.print(", Avg BPM=");
    Serial.print(beatAvg);
    
    if (irValue < 50000) Serial.print(" No finger?");
    Serial.println();

    delay(10);
  }
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    if (beatsPerMinute > 0 && beatAvg > 0) {  // Chỉ gửi khi có dữ liệu hợp lệ
      HTTPClient http;
      http.begin(SERVER_URL);
      http.addHeader("Content-Type", "application/json");

      String jsonData = "{\"IR_value\": " + String(particleSensor.getIR()) + 
                        ", \"BPM\": " + String(beatsPerMinute) + 
                        ", \"AvgBPM\": " + String(beatAvg) + "}";

      int httpResponseCode = http.POST(jsonData);

      http.end();
    } else {
      Serial.println("No valid heart rate data, skipping upload.");
    }
  } else {
    Serial.println("WiFi not connected!");
  }

  delay(1000);  // Gửi dữ liệu mỗi giây
}
