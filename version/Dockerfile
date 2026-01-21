# OCRが動くようにOSレベルの設定が含まれたベースイメージ
FROM python:3.9-slim

# ログをバッファせず即時出力させる設定
ENV PYTHONUNBUFFERED=1

# OSのライブラリ（OCRやPDF変換に必要）をインストール
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    poppler-utils \
    && apt-get clean

WORKDIR /app
COPY . .

# ライブラリのインストール
RUN pip install --no-cache-dir -r requirements.txt

# 全体を統括する main.py を実行するようにします
CMD ["python", "main.py"]