# 1. ベースイメージの指定
FROM python:3.11-slim

# 2. ログをリアルタイムで出す設定
ENV PYTHONUNBUFFERED=1

# 3. EasyOCRやpdf2imageに必要なOSライブラリをインストール
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    poppler-utils \
    g++ \
    && apt-get clean

WORKDIR /app

# 4. 依存ライブラリのインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. ソースコードのコピー（versionフォルダの中身を直下に配置）
COPY version/ .

# 6. アプリの起動（main_app.pyを実行）
CMD ["python", "main_app.py"]