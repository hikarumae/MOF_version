#仕分け・DB担当モジュール
import os
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableClient

def organize_files(info, original_blob_name, source_client):
    """
    情報を元にファイルを仕分け。
    ファイル名にタイムスタンプを付与し、一意の名称で保存する。
    """
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    blob_service = BlobServiceClient.from_connection_string(conn_str)
    table_client = TableClient.from_connection_string(conn_str, "LatestDocumentDB")

    category = info.get("document_type", "その他")
    group = info.get("target_entity", "不明").replace("/", "／")
    new_date = info.get("identified_date", "1900-01-01")

    # 一意にするためのタイムスタンプ作成 (例: 20260124_173045)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_name = f"{timestamp}_{original_blob_name}"

    # DBで現在の最新版情報をチェック
    try:
        existing = table_client.get_entity(partition_key=category, row_key=group)
        old_date = existing.get("LatestDate", "1900-01-01")
    except:
        existing, old_date = None, "1900-01-01"

    if new_date >= old_date:
        # 【最新版判定】
        # 1. もし既存の「旧・最新版」があれば、それを old コンテナへ退避
        if existing:
            old_version_filename = existing['CurrentFileName']
            # oldコンテナ内は 会社名/書類種別/ファイル名 の階層構造にする
            old_archive_path = f"{category}/{group}/{old_version_filename}"
            
            # allコンテナからoldコンテナへコピー
            old_blob_url = blob_service.get_blob_client("mof2-blob-all", old_version_filename).url
            blob_service.get_blob_client("mof2-blob-old", old_archive_path).start_copy_from_url(old_blob_url)

        # 2. 今回のファイルを all コンテナのルートへ保存 (一意の名前)
        blob_service.get_blob_client("mof2-blob-all", unique_name).start_copy_from_url(source_client.url)
        
        # 3. DBを更新 (最新の日付と、一意になったファイル名を記録)
        table_client.upsert_entity({
            "PartitionKey": category,
            "RowKey": group,
            "LatestDate": new_date,
            "CurrentFileName": unique_name
        })
        
    else:
        # 【旧版判定】
        # 直接 old コンテナの階層フォルダへ保存 (一意の名前)
        old_archive_path = f"{category}/{group}/{unique_name}"
        blob_service.get_blob_client("mof2-blob-old", old_archive_path).start_copy_from_url(source_client.url)

    # 処理が終わったので new コンテナから削除
    source_client.delete_blob()