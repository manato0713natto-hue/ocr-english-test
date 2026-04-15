FROM python:3.10-slim

# 必要パッケージ
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:$PORT"]
