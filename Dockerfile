# ===== ベース =====
FROM python:3.10-slim

# ===== 必要なパッケージ =====
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ===== 作業ディレクトリ =====
WORKDIR /app

# ===== 先にrequirementsをコピー（キャッシュ効かせる）=====
COPY requirements.txt .

# ===== Pythonライブラリ =====
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ===== アプリ本体コピー =====
COPY . .

# ===== ポート設定 =====
ENV PORT=10000

# ===== 起動 =====
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:$PORT"]
