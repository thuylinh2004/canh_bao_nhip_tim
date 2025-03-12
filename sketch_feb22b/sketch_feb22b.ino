#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include "MAX30105.h"
#include "heartRate.h"
#include <Adafruit_ADXL345_U.h>

#define WIFI_SSID "hi"
#define WIFI_PASSWORD "12345678"
#define SERVER_URL "http://172.30.1.66:5000/data"

MAX30105 particleSensor;
Adafruit_ADXL345_Unified accel = Adafruit_ADXL345_Unified(12345);
SemaphoreHandle_t i2cMutex;

QueueHandle_t bpmQueue, accelQueue, irQueue;

struct BPMData {
  float bpm;
  float avgBpm;
};

struct AccelData {
  float accelX, accelY, accelZ, A_total;  // Thêm A_total
};

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);

  i2cMutex = xSemaphoreCreateMutex();

  if (!accel.begin()) {
    Serial.println("Không tìm thấy ADXL345");
    while (1)
      ;
  }

  accel.setRange(ADXL345_RANGE_16_G);          // Chuyển sang 16G để có độ phân giải cao hơn
  accel.setDataRate(ADXL345_DATARATE_100_HZ);  // Đặt tần số đo 100Hz để giảm nhiễu

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Đang kết nối WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nĐã kết nối WiFi!");

  if (!particleSensor.begin(Wire, I2C_SPEED_STANDARD)) {
    Serial.println("MAX30105 không tìm thấy!");
    while (1)
      ;
  }
  particleSensor.setup();

  bpmQueue = xQueueCreate(10, sizeof(BPMData));
  accelQueue = xQueueCreate(10, sizeof(AccelData));
  irQueue = xQueueCreate(10, sizeof(long));

  xTaskCreatePinnedToCore(readHeartRateTask, "ReadHR", 4096, NULL, 1, NULL, 1);
  xTaskCreatePinnedToCore(readAccelTask, "ReadAccel", 4096, NULL, 1, NULL, 1);
  xTaskCreatePinnedToCore(displaySensorDataTask, "DisplayData", 4096, NULL, 1, NULL, 0);
}

void readHeartRateTask(void *pvParameters) {
  byte rates[4] = { 0 };
  byte rateSpot = 0;
  long lastBeat = 0;
  float bpm = 0, avgBpm = 0;

  while (true) {
    long irValue;

    if (xSemaphoreTake(i2cMutex, portMAX_DELAY)) {
      irValue = particleSensor.getIR();
      xSemaphoreGive(i2cMutex);
    }

    xQueueSend(irQueue, &irValue, portMAX_DELAY);

    if (irValue > 50000) {
      if (checkForBeat(irValue)) {
        long delta = millis() - lastBeat;
        lastBeat = millis();
        bpm = 60 / (delta / 1000.0);

        if (bpm > 20 && bpm < 255) {
          rates[rateSpot++] = (byte)bpm;
          rateSpot %= 4;
          avgBpm = 0;
          for (byte x = 0; x < 4; x++) avgBpm += rates[x];
          avgBpm /= 4;
        }
      }
    } else {
      bpm = avgBpm = 0;
    }

    BPMData bpmData = { bpm, avgBpm };
    xQueueSend(bpmQueue, &bpmData, portMAX_DELAY);

    delay(20);
  }
}

void readAccelTask(void *pvParameters) {
  while (true) {
    sensors_event_t event;

    if (xSemaphoreTake(i2cMutex, portMAX_DELAY)) {
      accel.getEvent(&event);
      xSemaphoreGive(i2cMutex);
    }

    // Tính gia tốc tổng hợp (A_total)
    float A_total = sqrt(event.acceleration.x * event.acceleration.x + event.acceleration.y * event.acceleration.y + event.acceleration.z * event.acceleration.z);

    AccelData accelData = { event.acceleration.x, event.acceleration.y, event.acceleration.z, A_total };
    xQueueSend(accelQueue, &accelData, portMAX_DELAY);

    delay(20);
  }
}

void displaySensorDataTask(void *pvParameters) {
  BPMData bpmData;
  AccelData accelData;
  long irValue = 0;

  while (true) {
    if (xQueueReceive(bpmQueue, &bpmData, portMAX_DELAY) && xQueueReceive(accelQueue, &accelData, portMAX_DELAY) && xQueueReceive(irQueue, &irValue, portMAX_DELAY)) {

      Serial.printf("BPM: %.2f | Avg BPM: %.2f | IR: %ld | Accel X: %.2f | Accel Y: %.2f | Accel Z: %.2f | A_total: %.2f\n",
                    bpmData.bpm, bpmData.avgBpm, irValue,
                    accelData.accelX, accelData.accelY, accelData.accelZ, accelData.A_total);
    }
    delay(20);
  }
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.disconnect();
    WiFi.reconnect();
    delay(500);
    return;
  }

  BPMData bpmData;
  AccelData accelData;
  long irValue = 0;

  if (xQueueReceive(bpmQueue, &bpmData, portMAX_DELAY) && xQueueReceive(accelQueue, &accelData, portMAX_DELAY) && xQueueReceive(irQueue, &irValue, portMAX_DELAY)) {

    HTTPClient http;
    http.begin(SERVER_URL);
    http.addHeader("Content-Type", "application/json");

    String jsonData = "{\"BPM\": " + String(bpmData.bpm) + ", \"AvgBPM\": " + String(bpmData.avgBpm) + ", \"IR_value\": " + String(irValue) + ", \"Accel_X\": " + String(accelData.accelX) + ", \"Accel_Y\": " + String(accelData.accelY) + ", \"Accel_Z\": " + String(accelData.accelZ) + ", \"A_total\": " + String(accelData.A_total) + "}";
    
    int httpResponseCode = http.POST(jsonData);
    Serial.print("HTTP Response Code: ");
    Serial.println(httpResponseCode);  // Hiển thị mã phản hồi HTTP từ server

    http.end();  // Kết thúc kết nối HTTP
  }

  delay(100);
}
