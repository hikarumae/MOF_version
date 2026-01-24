# main_app.py 
import time
import logging
from azure.storage.blob import BlobServiceClient
import pdf_analyzer
import ai_judge
import blob_organizer

logging.basicConfig(level=logging.INFO)
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

def main():
    blob_service = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    new_container = blob_service.get_container_client("mof2-blob-new")
    logging.info("🚀 AI仕分けボット起動（高耐久・一括処理モード）")

    while True:
        try:
            blobs = list(new_container.list_blobs())
            if not blobs:
                time.sleep(5)
                continue

            logging.info(f"📂 {len(blobs)} 件のファイルを検知しました。処理を開始します。")

            for blob_props in blobs:
                blob_name = blob_props.name
                if not blob_name.lower().endswith(".pdf"): continue
                
                # ★ 各ファイルごとに個別の try-except を配置（重要）
                try:
                    logging.info(f"⚡ 処理開始: {blob_name}")
                    source_blob = new_container.get_blob_client(blob_name)
                    
                    data = source_blob.download_blob().readall()
                    text_h, text_t, img = pdf_analyzer.extract_pdf_content(data)
                    info = ai_judge.get_judgment(text_h, text_t, img)
                    blob_organizer.organize_files(info, blob_name, source_blob, data)
                    
                    logging.info(f"✅ 完了: {blob_name} -> {info.get('target_entity')} ({info.get('identified_date')})")

                except Exception as file_error:
                    # 特定のファイルが失敗しても、エラーを記録して「次のファイル」へ進む
                    logging.error(f"⚠️ ファイル「{blob_name}」でエラーが発生（スキップ）: {file_error}")
                    continue
        
        except Exception as system_error:
            logging.error(f"❌ システムエラー（5秒後に再試行）: {system_error}")
        
        time.sleep(5)

if __name__ == "__main__":
    main()