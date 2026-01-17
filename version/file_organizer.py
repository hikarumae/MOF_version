# Azure Blob Storage 上でのファイル仕分け処理

import os
import json
from azure.storage.blob import BlobServiceClient

# App Serviceの環境変数に設定した接続文字列を読み込む
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)

# コンテナ名の設定
CONTAINER_NEW = "mof2-blob-new"
CONTAINER_ALL = "mof2-blob-all"
CONTAINER_OLD = "mof2-blob-old"

def organize_on_blob():
    # 判定結果(final_judgment.json)を読み込む
    with open("final_judgment.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data.get("results", []):
        file_name = item.get("internal_id")
        is_latest = item.get("is_latest")
        
        # 移動元のblob（mof2-blob-new）
        source_blob = blob_service_client.get_blob_client(container=CONTAINER_NEW, blob=file_name)
        
        # 判定に基づいて移動先を決定
        target_container = CONTAINER_ALL if is_latest else CONTAINER_OLD
        dest_blob = blob_service_client.get_blob_client(container=target_container, blob=file_name)

        # リソースB内での「移動」処理（コピーして消す）
        print(f"移動中: {file_name} -> {target_container}")
        dest_blob.start_copy_from_url(source_blob.url)
        source_blob.delete_blob()

    print("すべてのBlob仕分けが完了しました！")