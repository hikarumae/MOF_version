# Azure Blob Storage 上でのファイル仕分け処理

import os
import json
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
import unicodedata
import time

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
    container_client = blob_service_client.get_container_client(CONTAINER_NEW)
    
    # 現在コンテナにあるファイル名をすべて取得しておく
    existing_blobs = [b.name for b in container_client.list_blobs()]
    
    results = data.get("results", [])
    
    print(f"{len(results)}件の判定データに基づいてBlobの仕分けを開始します...")

    for item in results:
        # AI判定時のID（正規化されている可能性がある名前）
        original_id = item.get("internal_id")
        is_latest = item.get("is_latest")
        
        # まずはそのままの名前でクライアントを作成
        source_blob = blob_service_client.get_blob_client(container=CONTAINER_NEW, blob=original_id)
        
        # もし見つからない場合は、正規化を解除した形式（NFD）なども試すロジック
        if not source_blob.exists():
            # Mac特有の形式(NFD)に変換して再試行
            nfd_name = unicodedata.normalize('NFD', original_id)
            source_blob = blob_service_client.get_blob_client(container=CONTAINER_NEW, blob=nfd_name)
            
            if not source_blob.exists():
                print(f"⚠️ スキップ: {original_id} が {CONTAINER_NEW} にどうしても見当たりません。")
                continue
            
            # 見つかった場合は、以降この nfd_name を使う
            active_file_name = nfd_name
        else:
            active_file_name = original_id

        # 移動先の決定（名前は元のIDを使用）
        target_container = CONTAINER_ALL if is_latest else CONTAINER_OLD
        dest_blob = blob_service_client.get_blob_client(container=target_container, blob=active_file_name)

        try:
            print(f"移動中: {active_file_name} -> {target_container}")
            # コピー実行
            dest_blob.start_copy_from_url(source_blob.url)
            
            # コピー完了待ち
            props = dest_blob.get_blob_properties()
            while props.copy.status == 'pending':
                time.sleep(1)
                props = dest_blob.get_blob_properties()

            if props.copy.status == 'success':
                source_blob.delete_blob()
                print(f"✅ 完了: {active_file_name}")
            else:
                print(f"❌ コピー失敗: {props.copy.status}")
                
        except Exception as e:
            print(f"エラー ({active_file_name}): {e}")
            
    print("\nすべてのBlob仕分けが完了しました！")

if __name__ == "__main__":
    organize_blobs()