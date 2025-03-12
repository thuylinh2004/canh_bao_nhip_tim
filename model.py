import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow import keras
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.utils.class_weight import compute_class_weight
import joblib

# Bước 1: Đọc dữ liệu
file_path = "sensor_data.csv"
df = pd.read_csv(file_path)

# Bước 2: Xử lý dữ liệu
# Chuyển đổi giá trị thành số thực
df = df.astype(float)

# Xây dựng nhãn theo quy tắc phức tạp hơn
def classify_health_state(avg_bpm, a_total):
    # Trường hợp BPM trong khoảng 60-110
    if 60 <= avg_bpm <= 110:
        if a_total < 12:
            return "Bình thường"
        elif 12 <= a_total < 20:
            return "Hoạt động nhẹ"
        elif 20 <= a_total < 35:
            return "Hoạt động trung bình"
        else:
            return "Hoạt động mạnh"

    # Trường hợp BPM quá thấp hoặc quá cao
    if avg_bpm < 60:
        if a_total < 12:
            return "Cảnh báo sức khoẻ không ổn định"
        elif a_total >= 35:
            return "Hoạt động mạnh bất thường"

    if avg_bpm > 110:
        if a_total < 12:
            return "Nhịp tim cao bất thường"
        elif 12 <= a_total < 35:
            return "Hoạt động thể chất mạnh"
        else:
            return "Hoạt động cực độ"

    # Trường hợp đặc biệt sức khỏe tốt hoặc rất xấu
    if avg_bpm < 50 and a_total < 12:
        return "Sức khỏe siêu tốt"

    if avg_bpm > 150 and a_total > 35:
        return "Cảnh báo nguy hiểm"

    return "Không xác định"

# Tạo cột nhãn
df["label"] = df.apply(lambda row: classify_health_state(row["AvgBPM"], row["A_total"]), axis=1)

# Xóa dữ liệu không xác định
df = df[df["label"] != "Không xác định"]


# Chuyển nhãn thành số
label_encoder = LabelEncoder()
df["label"] = label_encoder.fit_transform(df["label"])

# Lưu encoder
joblib.dump(label_encoder, "label_encoder.pkl")

# Chọn đặc trưng đầu vào
X = df[["AvgBPM", "A_total"]].values
y = df["label"].values

# Chuẩn hóa dữ liệu
scaler = StandardScaler()
X = scaler.fit_transform(X)

# Lưu scaler
joblib.dump(scaler, "scaler.pkl")

# Chia dữ liệu train/test
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Kiểm tra sự mất cân bằng dữ liệu
class_weights = compute_class_weight('balanced', classes=np.unique(y), y=y_train)
class_weight_dict = dict(enumerate(class_weights))

# Bước 3: Xây dựng mô hình
model = keras.Sequential([
    keras.layers.Dense(32, activation='relu', input_shape=(2,)),
    keras.layers.BatchNormalization(),
    keras.layers.Dense(16, activation='relu'),
    keras.layers.Dropout(0.2),
    keras.layers.Dense(8, activation='relu'),
    keras.layers.Dense(len(np.unique(y)), activation='softmax')
])

model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])

# Bước 4: Huấn luyện mô hình với EarlyStopping
early_stopping = keras.callbacks.EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)

model.fit(X_train, y_train, epochs=100, batch_size=16, validation_data=(X_test, y_test),
          callbacks=[early_stopping], class_weight=class_weight_dict)

# Bước 5: Lưu mô hình
model.save("health_model.h5")
print("Mô hình đã được lưu thành công!")

# Kiểm tra độ chính xác trên tập test
test_loss, test_acc = model.evaluate(X_test, y_test)
print(f"Độ chính xác trên tập test: {test_acc:.4f}")
