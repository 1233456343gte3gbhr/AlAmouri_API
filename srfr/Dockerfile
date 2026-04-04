FROM python:3.11-slim

WORKDIR /app

# تثبيت المتطلبات النظام
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# نسخ requirements.txt
COPY requirements.txt .

# تثبيت المكتبات
RUN pip install --no-cache-dir -r requirements.txt

# نسخ الملفات
COPY . .

# تشغيل التطبيق
CMD ["python", "main.py"]
