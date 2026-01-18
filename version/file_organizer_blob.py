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
ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME") # .envに追加推奨、なければ接続文字列から解析も可
ACCOUNT_KEY = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")   # .envに追加推奨

# コンテナ設定
CONTAINER_MAP = {
    "売買契約書": "container-contracts",
    "契約書": "container-contracts",
    "社内規定": "container-rules",
    "就業規則": "container-rules",
    "職務権限基準": "container-rules",
    "請求書": "container-invoices",
    "その他": "container-others"
}

def get_service_client():
    return BlobServiceClient.from_connection_string(CONNECTION_STRING)

def ensure_container_exists(blob_service_client, container_name):
    """移動先コンテナが存在しない場合、自動で作成する"""
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

    # --- 移動先コンテナを事前に全て作っておく ---
    unique_containers = set(CONTAINER_MAP.values())
    unique_containers.add("container-others")
    for c_name in unique_containers:
        ensure_container_exists(blob_service_client, c_name)

    print(f"📂 {len(results)} 件のファイル移動を開始します...")

    for item in results:
        original_id = item.get("internal_id")
        if not original_id or original_id == "unknown_filename":
            continue

        is_latest = item.get("is_latest", False)
        category = item.get("document_type", "未分類")
        group = item.get("group_name", "共通").replace("/", "／")
        version_status = "new" if is_latest else "old"

        # 移動先決定
        target_container = CONTAINER_MAP.get(category, CONTAINER_MAP["その他"])
        new_blob_path = f"{category}/{group}/{version_status}/{original_id}"

        # クライアント取得
        source_blob = blob_service_client.get_blob_client(SOURCE_CONTAINER, original_id)

        # 文字コード対策 (NFD -> NFC)
        if not source_blob.exists():
            nfd_name = unicodedata.normalize('NFD', original_id)
            source_blob = blob_service_client.get_blob_client(SOURCE_CONTAINER, nfd_name)
            if not source_blob.exists():
                print(f"⚠️ スキップ: {original_id} (ファイル実体が見つかりません)")
                continue

        dest_blob = blob_service_client.get_blob_client(target_container, new_blob_path)

        try:
            # --- 【重要】SASトークン（一時的なアクセス権）付きURLを生成 ---
            # これがないと、Azure内コピーでも「権限不足」で失敗することが多いです
            sas_token = generate_blob_sas(
                account_name=source_blob.account_name,
                container_name=SOURCE_CONTAINER,
                blob_name=source_blob.blob_name,
                account_key=blob_service_client.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.now(timezone.utc) + timedelta(minutes=10) # 10分間だけ有効
            )
            source_url_with_sas = f"{source_blob.url}?{sas_token}"

            print(f"🚀 移動中: {original_id}")
            print(f"   -> {target_container}/{new_blob_path}")

            # コピー開始
            dest_blob.start_copy_from_url(source_url_with_sas)

            # 完了待機
            start_wait = time.time()
            while True:
                props = dest_blob.get_blob_properties()
                status = props.copy.status
                if status == 'success':
                    # コピー成功後に削除
                    source_blob.delete_blob()
                    print(f"   ✅ 完了")
                    break
                elif status == 'failed' or status == 'aborted':
                    print(f"   ❌ コピー失敗: {status}")
                    break
                
                if time.time() - start_wait > 60: # 60秒でタイムアウト
                    print(f"   ⏰ タイムアウト")
                    break
                time.sleep(0.5)

        except Exception as e:
            print(f"   ❌ エラー: {e}")

if __name__ == "__main__":
    organize_blobs()