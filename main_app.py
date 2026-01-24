#司令塔・ブロブトリガー代行)モジュール

import os
import time
import logging
from azure.storage.blob import BlobServiceClient
import pdf_analyzer
import ai_judge
import blob_organizer

logging.basicConfig(level=logging.INFO)
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

def watch_new_container():
    blob_service = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    container_client = blob_service.get_container_client("mof2-blob-new")
    logging.info("🚀 AI仕分けロボット起動完了（5秒間隔監視）")

    while True:
        try:
            blobs = list(container_client.list_blobs())
            for blob_props in blobs:
                if not blob_props.name.lower().endswith(".pdf"): continue
                
                logging.info(f"⚡ 新着検知: {blob_props.name}")
                source_blob = container_client.get_blob_client(blob_props.name)
                
                # 処理フロー実行
                data = source_blob.download_blob().readall()
                text, img = pdf_analyzer.extract_pdf_content(data)
                info = ai_judge.get_judgment(text, img)
                blob_organizer.organize_files(info, blob_props.name, source_blob)
                logging.info(f"✅ 処理完了: {blob_props.name}")
        except Exception as e:
            logging.error(f"❌ エラー発生: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    watch_new_container()