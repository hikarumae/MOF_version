#仕分け・DB担当モジュール

import os
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableClient

def organize_files(info, blob_name, source_client):
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    blob_service = BlobServiceClient.from_connection_string(conn_str)
    # Table名: LatestDocumentDB
    table_client = TableClient.from_connection_string(conn_str, "LatestDocumentDB")

    pk = info.get("書類種別", "その他")
    rk = info.get("会社名", "不明")
    new_date = info.get("日付", "1900-01-01")

    try:
        existing = table_client.get_entity(pk, rk)
        old_date = existing["LatestDate"]
    except:
        existing, old_date = None, "1900-01-01"

    if new_date >= old_date:
        # 最新版：既存をoldへ退避、今回をallへ
        if existing:
            old_path = f"{pk}/{rk}/{existing['CurrentFileName']}"
            blob_service.get_blob_client("mof2-blob-old", old_path).start_copy_from_url(
                blob_service.get_blob_client("mof2-blob-all", existing["CurrentFileName"]).url
            )
        blob_service.get_blob_client("mof2-blob-all", blob_name).start_copy_from_url(source_client.url)
        table_client.upsert_entity({"PartitionKey": pk, "RowKey": rk, "LatestDate": new_date, "CurrentFileName": blob_name})
    else:
        # 旧版：oldへ階層移動
        old_path = f"{pk}/{rk}/{new_date}_{blob_name}"
        blob_service.get_blob_client("mof2-blob-old", old_path).start_copy_from_url(source_client.url)

    source_client.delete_blob()