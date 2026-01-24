import os
import json
import time
from datetime import datetime, timedelta, timezone
import unicodedata
from dotenv import load_dotenv

from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceNotFoundError

load_dotenv()

# === 設定 ===
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
SOURCE_CONTAINER = "mof2-blob-new"
DEST_CONTAINER_LATEST = "mof2-blob-all"
DEST_CONTAINER_OLD = "mof2-blob-old"
FINAL_JSON = "final_judgment.json"
TABLE_NAME = "LatestDocumentDB" # テーブル（DB）の名前

def get_clients():
    blob_service = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    table_service = TableServiceClient.from_connection_string(CONNECTION_STRING)
    return blob_service, table_service

def ensure_resources_exist(blob_service, table_service):
    # コンテナの準備
    for c_name in [DEST_CONTAINER_LATEST, DEST_CONTAINER_OLD]:
        try:
            container_client = blob_service.get_container_client(c_name)
            if not container_client.exists(): container_client.create_container()
        except: pass
    # テーブルの準備
    table_client = table_service.get_table_client(TABLE_NAME)
    try: table_service.create_table(TABLE_NAME)
    except: pass
    return table_client

def move_blob(blob_service, source_container, source_blob_name, dest_container, dest_blob_name):
    """Blobを移動する共通関数（SASトークン使用）"""
    source_blob = blob_service.get_blob_client(source_container, source_blob_name)
    if not source_blob.exists():
        return False

    dest_blob = blob_service.get_blob_client(dest_container, dest_blob_name)
    sas_token = generate_blob_sas(
        account_name=source_blob.account_name, container_name=source_container, blob_name=source_blob.blob_name,
        account_key=blob_service.credential.account_key, permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(minutes=10)
    )
    dest_blob.start_copy_from_url(f"{source_blob.url}?{sas_token}")

    # コピー完了を待って元ファイルを削除
    while True:
        status = dest_blob.get_blob_properties().copy.status
        if status == 'success':
            source_blob.delete_blob()
            return True
        elif status in ['failed', 'aborted']: return False
        time.sleep(1)

def organize_blobs():
    if not os.path.exists(FINAL_JSON): return

    with open(FINAL_JSON, "r", encoding="utf-8") as f:
        results = json.load(f).get("results", [])

    blob_service, table_service = get_clients()
    table_client = ensure_resources_exist(blob_service, table_service)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    processed_files = set()

    for item in results:
        original_id = item.get("internal_id")
        if not original_id or original_id in processed_files: continue

        category = item.get("document_type", "未分類")
        group = item.get("group_name", "共通").replace("/", "／")
        new_date_str = item.get("identified_date", "1900-01-01")

        # 重複防止の新しいファイル名
        new_filename = f"{timestamp}_{original_id}"

        # ---------------------------------------------------------
        # 🔍 Step A: DBで「過去の最新版」を検索する
        # ---------------------------------------------------------
        existing_entity = None
        try:
            # PartitionKey: 書類の種類, RowKey: 会社名
            existing_entity = table_client.get_entity(partition_key=category, row_key=group)
        except ResourceNotFoundError:
            pass # 過去データなし

        # ---------------------------------------------------------
        # ⚖️ Step B: 日付の比較と移動先の決定
        # ---------------------------------------------------------
        is_new_latest = False

        if not existing_entity:
            # 1. 過去データがない → 今回が初の最新版！
            print(f"🌟 新規登録: {group} の {category}")
            is_new_latest = True
        else:
            # 2. 過去データがある → 日付対決！
            old_date_str = existing_entity.get("LatestDate", "1900-01-01")
            if new_date_str > old_date_str:
                print(f"🔄 更新: {group} の {category} (旧:{old_date_str} -> 新:{new_date_str})")
                is_new_latest = True
                
                # 【重要】既存の最新版(all) を 旧版(old) へ追い出す
                old_filename = existing_entity["CurrentFileName"]
                old_blob_path = f"{category}/{group}/{old_filename}"
                print(f"   ↪️ 旧版を退避中: {old_filename} -> mof2-blob-old")
                move_blob(blob_service, DEST_CONTAINER_LATEST, old_filename, DEST_CONTAINER_OLD, old_blob_path)
            else:
                print(f"📉 古い版: {group} の {category} (最新:{old_date_str} のまま維持)")
                is_new_latest = False

        # ---------------------------------------------------------
        # 🚚 Step C: 新しいファイルを移動し、DBを更新
        # ---------------------------------------------------------
        if is_new_latest:
            # new -> all (直下) へ移動
            success = move_blob(blob_service, SOURCE_CONTAINER, original_id, DEST_CONTAINER_LATEST, new_filename)
            if success:
                # DBを更新 (追加または上書き)
                new_entity = {
                    "PartitionKey": category,
                    "RowKey": group,
                    "LatestDate": new_date_str,
                    "CurrentFileName": new_filename
                }
                table_client.upsert_entity(new_entity)
                processed_files.add(original_id)
        else:
            # 新しいファイルの方が古かった場合：new -> old (フォルダ分け) へ移動
            old_blob_path = f"{category}/{group}/{new_filename}"
            success = move_blob(blob_service, SOURCE_CONTAINER, original_id, DEST_CONTAINER_OLD, old_blob_path)
            if success: processed_files.add(original_id)

    print("✨ DB連携によるファイル移動処理が終了しました。")

if __name__ == "__main__":
    organize_blobs()