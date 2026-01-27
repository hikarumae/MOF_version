# main_app.py 
import os
import time
import logging
import threading  # 別スレッドで監視を動かすために必要
from flask import Flask  # Azureの生存確認に応答するために必要
from azure.storage.blob import BlobServiceClient
import pdf_analyzer
import ai_judge
import blob_organizer

# ★ 一番最初にこれが出るか確認
logging.basicConfig(level=logging.INFO)
logging.info("====================================")
logging.info("📢 プログラムの読み込みを開始しました！")
logging.info("====================================")

# 1. 生存確認用のWebサーバー設定
server = Flask(__name__)

@server.route('/')
def health_check():
    return "Bot is running!"  # Azureがここにアクセスして「生存」を確認します

# 2. 実際の監視ロジック（別スレッドで実行）
def monitor_loop():
    logging.info("🚀 監視スレッドを開始しました")
    CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not CONNECTION_STRING:
        logging.error("❌ 接続文字列が設定されていません")
        return

    blob_service = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    new_container = blob_service.get_container_client("mof2-blob-new")

    while True:
        try:
            blobs = list(new_container.list_blobs())
            if blobs:
                logging.info(f"📂 {len(blobs)} 件のファイルを検知")
                for blob_props in blobs:
                    blob_name = blob_props.name
                    if not blob_name.lower().endswith(".pdf"): continue
                    
                    try:
                        logging.info(f"⚡ 処理開始: {blob_name}")
                        source_blob = new_container.get_blob_client(blob_name)
                        data = source_blob.download_blob().readall()
                        text_h, text_t, img = pdf_analyzer.extract_pdf_content(data)
                        info = ai_judge.get_judgment(text_h, text_t, img)
                        blob_organizer.organize_files(info, blob_name, source_blob, data)
                        logging.info(f"✅ 完了: {blob_name}")
                    except Exception as e:
                        logging.error(f"⚠️ ファイルエラー: {e}")
            
            time.sleep(10)  # 監視間隔
        except Exception as system_error:
            logging.error(f"❌ システムエラー: {system_error}")
            time.sleep(10)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 監視ループをバックグラウンド（別スレッド）で起動
    worker_thread = threading.Thread(target=monitor_loop, daemon=True)
    worker_thread.start()
    
    # Webサーバーをメインスレッドで起動（Azureのポート80/8000待ち受け用）
    port = int(os.environ.get("PORT", 8000))
    server.run(host='0.0.0.0', port=port)