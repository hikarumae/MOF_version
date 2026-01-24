#仕分け・DB担当モジュール


import os
import re
import logging
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableClient
from azure.core.exceptions import ResourceNotFoundError

def sanitize_key(key):
    """Table Storageで使用禁止の文字を排除する"""
    if not key:
        return "Unknown"
    # 使用禁止文字 / \ # ? と 改行・タブ を排除
    sanitized = re.sub(r'[\\/#?\u0000-\u001f\u007f-\u009f]', '', key)
    return sanitized.strip() or "Unknown"

# ★修正ポイント1: 引数に「data（PDFの中身）」を追加
def organize_files(info, original_blob_name, source_client, data):
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    blob_service = BlobServiceClient.from_connection_string(conn_str)
    table_client = TableClient.from_connection_string(conn_str, "LatestDocumentDB")
    
    # 1. テーブルの自動作成（念のため）
    try:
        table_client.create_table()
    except:
        pass

    # 2. AI判定結果のクレンジング
    category = sanitize_key(info.get("document_type", "その他"))
    group = sanitize_key(info.get("target_entity", "不明"))
    new_date = info.get("identified_date", "1900-01-01")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_name = f"{timestamp}_{original_blob_name}"

    logging.info(f"📊 DB照合中: PK={category}, RK={group}")

    # 3. DBで現在の最新版情報をチェック
    try:
        existing = table_client.get_entity(partition_key=category, row_key=group)
        old_date = existing.get("LatestDate", "1900-01-01")
        logging.info(f"🔎 既存データあり: {old_date}")
    except ResourceNotFoundError:
        existing, old_date = None, "1900-01-01"
        logging.info("🆕 新規データとして処理します")

    if new_date >= old_date:
        # 【最新版判定】
        if existing:
            old_version_filename = existing['CurrentFileName']
            old_archive_path = f"{category}/{group}/{old_version_filename}"
            logging.info(f"📦 旧版を退避中: {old_archive_path}")
            
            old_blob_client = blob_service.get_blob_client("mof2-blob-all", old_version_filename)
            try:
                # ★修正ポイント2: 旧版の移動もURLコピーではなく、安全にダウンロード→アップロードに変更
                old_data = old_blob_client.download_blob().readall()
                blob_service.get_blob_client("mof2-blob-old", old_archive_path).upload_blob(old_data, overwrite=True)
                old_blob_client.delete_blob()
            except Exception as e:
                logging.warning(f"⚠️ 旧版の整理に失敗（無視して続行）: {e}")

        # 今回のファイルを all コンテナへ保存
        logging.info(f"🚀 最新版を all に保存中: {unique_name}")
        # ★修正ポイント3: URLからのコピーではなく、引数のdataを直接アップロード
        blob_service.get_blob_client("mof2-blob-all", unique_name).upload_blob(data, overwrite=True)
        
        # DBを更新
        try:
            logging.info("📝 テーブルを更新中...")
            table_client.upsert_entity({
                "PartitionKey": category,
                "RowKey": group,
                "LatestDate": new_date,
                "CurrentFileName": unique_name
            })
            logging.info("✅ テーブル更新成功")
        except Exception as e:
            logging.error(f"❌ テーブル更新失敗: {e}")
            raise  # ここで失敗したら削除させない
        
    else:
        # 【旧版判定】
        old_archive_path = f"{category}/{group}/{unique_name}"
        logging.info(f"📁 旧版として old に直接保存: {old_archive_path}")
        # ★修正ポイント4: 同様にdataを直接アップロード
        blob_service.get_blob_client("mof2-blob-old", old_archive_path).upload_blob(data, overwrite=True)

    # 4. 全ての処理が成功した時だけ、new コンテナから削除
    logging.info(f"🗑️ new コンテナから削除中: {original_blob_name}")
    source_client.delete_blob()
    logging.info("✨ 全工程完了")