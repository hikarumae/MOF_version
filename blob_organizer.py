#仕分け・DB担当モジュール
import os
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableClient
from azure.core.exceptions import ResourceNotFoundError

def organize_files(info, original_blob_name, source_client):
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    blob_service = BlobServiceClient.from_connection_string(conn_str)
    
    # 1. テーブルの準備
    table_client = TableClient.from_connection_string(conn_str, "LatestDocumentDB")
    try:
        table_client.create_table() # なければ作成
    except:
        pass

    category = info.get("document_type", "その他")
    group = info.get("target_entity", "不明").replace("/", "／")
    new_date = info.get("identified_date", "1900-01-01")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_name = f"{timestamp}_{original_blob_name}"

    # 2. DBで現在の最新版情報をチェック
    try:
        existing = table_client.get_entity(partition_key=category, row_key=group)
        old_date = existing.get("LatestDate", "1900-01-01")
    except ResourceNotFoundError:
        existing, old_date = None, "1900-01-01"

    if new_date >= old_date:
        # 【最新版判定】
        if existing:
            old_version_filename = existing['CurrentFileName']
            old_archive_path = f"{category}/{group}/{old_version_filename}"
            
            # 以前の最新版を old へ退避
            old_blob_client = blob_service.get_blob_client("mof2-blob-all", old_version_filename)
            blob_service.get_blob_client("mof2-blob-old", old_archive_path).start_copy_from_url(old_blob_client.url)
            
            # --- 重要：コピーが終わったら all コンテナから削除する ---
            old_blob_client.delete_blob()

        # 今回のファイルを all コンテナへ保存
        blob_service.get_blob_client("mof2-blob-all", unique_name).start_copy_from_url(source_client.url)
        
        # DBを更新（ここでデータが保存されます）
        table_client.upsert_entity({
            "PartitionKey": category,
            "RowKey": group,
            "LatestDate": new_date,
            "CurrentFileName": unique_name
        })
        
    else:
        # 【旧版判定】
        old_archive_path = f"{category}/{group}/{unique_name}"
        blob_service.get_blob_client("mof2-blob-old", old_archive_path).start_copy_from_url(source_client.url)

    # 処理完了：new コンテナから削除
    source_client.delete_blob()