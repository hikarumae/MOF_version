# 最新版は「mof2-blob-all」に移動
# バージョンが古いファイルは「mof2-blob-old」に移動
# 同名ファイル対策としてタイムスタンプを付加

import os
import json
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import time
import unicodedata

load_dotenv()

# === 設定 ===
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
SOURCE_CONTAINER = "mof2-blob-new" 
FINAL_JSON = "final_judgment.json" 

DEST_CONTAINER_LATEST = "mof2-blob-all" 
DEST_CONTAINER_OLD = "mof2-blob-old"    

def get_service_client():
    return BlobServiceClient.from_connection_string(CONNECTION_STRING)

def ensure_container_exists(blob_service_client, container_name):
    try:
        container_client = blob_service_client.get_container_client(container_name)
        if not container_client.exists():
            print(f"📦 新規コンテナ作成: {container_name}")
            container_client.create_container()
    except Exception as e:
        print(f"⚠️ コンテナ確認エラー ({container_name}): {e}")

def organize_blobs():
    if not os.path.exists(FINAL_JSON):
        print(f"エラー: {FINAL_JSON} が見つかりません。")
        return

    with open(FINAL_JSON, "r", encoding="utf-8") as f:
        results = json.load(f).get("results", [])

    blob_service_client = get_service_client()

    for c_name in [DEST_CONTAINER_LATEST, DEST_CONTAINER_OLD]:
        ensure_container_exists(blob_service_client, c_name)

    print(f"📂 {len(results)} 件のファイル移動（重複対策版）を開始します...")

    processed_files = set()
    # 現在時刻をフォーマット（秒まで含めると重複リスクがほぼゼロになります）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for item in results:
        original_id = item.get("internal_id")
        if not original_id or original_id == "unknown_filename" or original_id in processed_files:
            continue

        is_latest = item.get("is_latest", False)
        category = item.get("document_type", "未分類")
        group = item.get("group_name", "共通").replace("/", "／")

        # --- 【重要】移動後のファイル名を決定 ---
        # ファイル名の先頭にタイムスタンプを付けて上書きを防止
        new_filename = f"{timestamp}_{original_id}"

        if is_latest:
            target_container = DEST_CONTAINER_LATEST
            new_blob_path = new_filename # 直下に配置
        else:
            target_container = DEST_CONTAINER_OLD
            new_blob_path = f"{category}/{group}/{new_filename}" # フォルダ分け

        source_blob = blob_service_client.get_blob_client(SOURCE_CONTAINER, original_id)

        if not source_blob.exists():
            nfd_name = unicodedata.normalize('NFD', original_id)
            source_blob = blob_service_client.get_blob_client(SOURCE_CONTAINER, nfd_name)
            if not source_blob.exists():
                print(f"⏩ スキップ: {original_id} は存在しません。")
                processed_files.add(original_id)
                continue

        dest_blob = blob_service_client.get_blob_client(target_container, new_blob_path)

        try:
            sas_token = generate_blob_sas(
                account_name=source_blob.account_name,
                container_name=SOURCE_CONTAINER,
                blob_name=source_blob.blob_name,
                account_key=blob_service_client.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.now(timezone.utc) + timedelta(minutes=10)
            )
            source_url_with_sas = f"{source_blob.url}?{sas_token}"

            print(f"🚀 移動開始: {original_id} -> {new_blob_path}")

            dest_blob.start_copy_from_url(source_url_with_sas)

            start_wait = time.time()
            while True:
                props = dest_blob.get_blob_properties()
                status = props.copy.status
                if status == 'success':
                    source_blob.delete_blob()
                    processed_files.add(original_id)
                    print(f"   ✅ 移動完了")
                    break
                elif status in ['failed', 'aborted']:
                    print(f"   ❌ コピー失敗: {status}")
                    break
                
                if time.time() - start_wait > 60:
                    print(f"   ⏰ タイムアウト")
                    break
                time.sleep(1)

        except Exception as e:
            print(f"   ❌ 処理中にエラー: {e}")

    print(f"✨ 全てのファイル移動処理が終了しました。")

if __name__ == "__main__":
    organize_blobs()