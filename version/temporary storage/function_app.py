import azure.functions as func
import logging
import os
import time
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import HttpResponseError, ResourceExistsError

# 既存のロジックをインポート
import version_manager          # Step 1: OCR処理
import version_manager_ai_azure # Step 2: AI判定
import file_organizer_blob      # Step 3: ファイル移動

# === 設定 (環境変数から取得) ===
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
SOURCE_CONTAINER = "mof2-blob-new"
LOCK_CONTAINER = "sys-lock"       # ロック用コンテナ
LOCK_BLOB_NAME = "leader_lock"    # ロック用ファイル

app = func.FunctionApp()

def get_leader_lease(blob_service_client):
    """
    リーダー権限（リース）の取得を試みる関数
    """
    try:
        container_client = blob_service_client.get_container_client(LOCK_CONTAINER)
        if not container_client.exists():
            container_client.create_container()
        
        blob_client = container_client.get_blob_client(LOCK_BLOB_NAME)
        if not blob_client.exists():
            blob_client.upload_blob(b"LEADER_LOCK", overwrite=True)
            
        # 60秒間の独占権を取得
        lease = blob_client.acquire_lease(lease_duration=60)
        return lease
    except (HttpResponseError, ResourceExistsError):
        # 誰かがすでに取得している場合は None を返す
        return None

@app.blob_trigger(arg_name="myblob", path=f"{SOURCE_CONTAINER}/{{name}}", connection="AzureWebJobsStorage")
def mof_coordinator_trigger(myblob: func.InputStream):
    trigger_file = myblob.name
    logging.info(f"🔔 トリガー検知: {trigger_file}")

    # 1. Blobサービスへの接続
    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    
    # 2. リーダー立候補
    lease = get_leader_lease(blob_service_client)
    
    if not lease:
        # 他のプロセスがすでにリーダーとして動いている場合は終了
        logging.info(f"⏩ {trigger_file}: リーダーが他にいるため、このプロセスは終了します。")
        return

    # 3. リーダーとしての処理（全件一括処理ループ）
    logging.info(f"👑 リーダー権限を取得しました。一括処理を開始します。")
    try:
        source_container_client = blob_service_client.get_container_client(SOURCE_CONTAINER)
        
        while True:
            # 今あるPDFファイルをリストアップ
            blobs = list(source_container_client.list_blobs())
            target_files = [b.name for b in blobs if b.name.lower().endswith(".pdf")]
            
            if not target_files:
                logging.info("🧹 処理待ちのファイルがなくなりました。")
                break
                
            logging.info(f"📋 現在の処理対象: {len(target_files)}件")

            # 全体ではなく、1サイクルごとに例外をキャッチする ###
            try:
                logging.info(f"📋 現在の処理対象: {len(target_files)}件")
                lease.renew()

                logging.info("1️⃣ [Step 1] OCR処理を開始...")
                version_manager.process_pdfs_from_blob()
                
                logging.info("2️⃣ [Step 2] AIによる判定を開始...")
                version_manager_ai_azure.run_ai_judgment()
                
                logging.info("3️⃣ [Step 3] ファイルの仕分け移動を開始...")
                file_organizer_blob.organize_blobs()
                
            except Exception as single_error:
                # ここでエラーが起きた場合、ファイルが 'new' に残っていると
                # 次のループでまた同じファイルを処理して無限ループになります。
                logging.error(f"⚠️ 処理サイクル中にエラーが発生しました: {single_error}")
                
                # ### エラーファイルを隔離する (重要) ###
                # ここで target_files にあるファイルを 'error-folder' 等へ移動させる
                # 処理を入れるか、手動で削除するまでループを抜ける等の対策が必要です。
                # 今回は安全のため、一度エラーが出たらループを抜けるようにします。
                logging.error("無限ループ防止のため、このサイクルの処理を中断します。手動でファイルを確認してください。")
                break

            # 処理が1セット終わったら、もう一度 while の先頭に戻り、
            # 処理中に新しくアップロードされたファイルがないか確認します。
            logging.info("♻️ 再チェック中...")
            time.sleep(1) # 無限ループの負荷を抑えるための微小待機

    except Exception as e:
        logging.error(f"❌ リーダー処理中に重大なエラーが発生しました: {e}")
    finally:
        # 最後に必ずリーダー権限を返上する
        lease.release()
        logging.info("👋 リーダー権限を解放しました。")
        
        
        ##　func startで起動＃