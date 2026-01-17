# Azure Blob Storage 上でのファイル仕分け処理

import os
import json
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

# .envファイルから接続情報を読み込む
load_dotenv()

# === 設定 ===
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NEW = "mof2-blob-new"
CONTAINER_ALL = "mof2-blob-all"
CONTAINER_OLD = "mof2-blob-old"
FINAL_JSON = "final_judgment.json"

def organize_blobs():
    # 1. AIの判定結果ファイルを読み込む
    if not os.path.exists(FINAL_JSON):
        print(f"エラー: {FINAL_JSON} が見つかりません。先にAI解析を実行してください。")
        return

    with open(FINAL_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 2. Blobサービスへの接続準備
    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    results = data.get("results", [])
    
    print(f"{len(results)}件の判定データに基づいてBlobの仕分けを開始します...")

    for item in results:
        file_name = item.get("internal_id")
        is_latest = item.get("is_latest")
        
        # 移動元のBlobクライアント
        source_blob = blob_service_client.get_blob_client(container=CONTAINER_NEW, blob=file_name)
        
        # 判定に基づいて移動先のコンテナを決定
        target_container = CONTAINER_ALL if is_latest else CONTAINER_OLD
        dest_blob = blob_service_client.get_blob_client(container=target_container, blob=file_name)

        try:
            # 3. ファイルのコピーを実行
            # start_copy_from_url を使うと、Azureのネットワーク内で高速にコピーされます
            print(f"移動中: {file_name} -> {target_container}")
            dest_blob.start_copy_from_url(source_blob.url)
            
            # 4. コピーが完了したら元データを削除（これで「移動」が完了）
            source_blob.delete_blob()
            
        except Exception as e:
            print(f"エラー ({file_name}): {e}")

    print("\nすべてのBlob仕分けが完了しました！")

if __name__ == "__main__":
    organize_blobs()