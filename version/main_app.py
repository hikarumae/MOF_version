import logging
import os
import time
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import HttpResponseError, ResourceExistsError

# あなたが作ったロジックをインポート
import version_manager
import version_manager_ai_azure
import file_organizer_blob

# 設定 (App Serviceの「環境変数」から取得されます)
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
SOURCE_CONTAINER = "mof2-blob-new"
LOCK_CONTAINER = "sys-lock"
LOCK_BLOB_NAME = "leader_lock"

# ロギングの設定 (App Serviceのログに表示するため)
logging.basicConfig(level=logging.INFO)

def get_leader_lease(blob_service_client):
    try:
        container_client = blob_service_client.get_container_client(LOCK_CONTAINER)
        if not container_client.exists():
            container_client.create_container()
        blob_client = container_client.get_blob_client(LOCK_BLOB_NAME)
        if not blob_client.exists():
            blob_client.upload_blob(b"LEADER_LOCK", overwrite=True)
        lease = blob_client.acquire_lease(lease_duration=60)
        return lease
    except Exception:
        return None

def run_loop():
    """常駐監視メインループ"""
    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    logging.info("🚀 AI仕分けロボット起動完了...")

    while True:
        lease = get_leader_lease(blob_service_client)
        if lease:
            try:
                source_container_client = blob_service_client.get_container_client(SOURCE_CONTAINER)
                blobs = list(source_container_client.list_blobs())
                target_files = [b.name for b in blobs if b.name.lower().endswith(".pdf")]

                if target_files:
                    logging.info(f"📋 {len(target_files)}件の処理を開始します...")
                    lease.renew()
                    
                    version_manager.process_pdfs_from_blob()
                    version_manager_ai_azure.run_ai_judgment()
                    file_organizer_blob.organize_blobs()
                
                else:
                    logging.info("💤 待機中...")

            except Exception as e:
                logging.error(f"❌ エラー発生: {e}")
            finally:
                lease.release()
        
        # 監視間隔 (例: 30秒ごとにチェック)
        time.sleep(30)

if __name__ == "__main__":
    run_loop()