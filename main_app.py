import os
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
    logging.info("🚀 AI仕分けボット起動（監視開始）")

    while True:
        # ファイルリストの取得でエラーが起きる可能性は低いため、tryの外に出すか個別にハンドリング
        try:
            blobs = list(new_container.list_blobs())
        except Exception as e:
            logging.error(f"❌ コンテナ読み込みエラー: {e}")
            time.sleep(5)
            continue

        for blob_props in blobs:
            if not blob_props.name.lower().endswith(".pdf"): continue
            
            # ★ try-except を個々のファイル処理の「内側」に移動
            try:
                logging.info(f"⚡ 処理開始: {blob_props.name}")
                source_blob = new_container.get_blob_client(blob_props.name)
                
                data = source_blob.download_blob().readall()
                text_h, text_t, img = pdf_analyzer.extract_pdf_content(data)
                info = ai_judge.get_judgment(text_h, text_t, img)
                blob_organizer.organize_files(info, blob_props.name, source_blob)
                
                logging.info(f"✅ 完了: {info.get('target_entity')} - {info.get('document_type')}")

            except Exception as e:
                # ★ 個別のファイルでエラーが起きても、全体のループは止めない
                logging.error(f"❌ {blob_props.name} の処理中にエラー: {e}")
                
                # 【重要】無限ループを防ぐため、エラーになったファイルは「new」から「error」コンテナ等へ移動させるか、
                # 名前を変更して次回の対象外にする必要があります。
                # 例: source_blobに ".error" を付与するなど。
        
        time.sleep(5) # 5秒間隔ポーリング

if __name__ == "__main__":
    main()