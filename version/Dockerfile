# OCRが動くようにOSレベルの設定が含まれたベースイメージ
FROM python:3.9-slim

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

# ひとまず起動し続けるための設定（Webサーバーとして動かす場合はここを書き換え）
CMD ["python", "version_manager.py"]