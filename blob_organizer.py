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
    sanitized = re.sub(r'[\\/#?\u0000-\u001f\u007f-\u009f]', '', key)
    return sanitized.strip() or "Unknown"

def organize_files(info, original_blob_name, source_client, data):
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    blob_service = BlobServiceClient.from_connection_string(conn_str)
    table_client = TableClient.from_connection_string(conn_str, "LatestDocumentDB")
    
    try:
        table_client.create_table()
    except:
        pass

    # メタデータの取得
    category = sanitize_key(info.get("document_type", "その他"))
    group = sanitize_key(info.get("target_entity", "不明"))
    new_date = info.get("identified_date", "1900-01-01")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # ---------------------------------------------------------
    # 【ファイル名の定義】
    # ---------------------------------------------------------
    
    # 1. 最新版フォルダ(all)用の名前：
    #    リネームせず、元のファイル名（重複防止のタイムスタンプ付与のみ）を使用
    #unique_name = f"{timestamp}_{original_blob_name}"
    
    #デモ用に元のファイル名を使用
    unique_name = f"{original_blob_name}"
    
    # 2. 旧版フォルダ(old)へ直接保存する時用の名前：
    #    「日付_区分_対象...」の形式にリネーム
    _, ext = os.path.splitext(original_blob_name)
    safe_date = new_date.replace("/", "-") 
    formatted_rename_for_old = f"{safe_date}_{category}_{group}_{timestamp}{ext}"

    # ---------------------------------------------------------

    logging.info(f"📊 DB照合中: PK={category}, RK={group}")

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
            # --- 既存の最新ファイルを old に退避する処理 ---
            old_version_filename = existing['CurrentFileName']
            
            # 退避するときは、そのファイルが持つ過去の日付を使ってリネームする
            archive_date = existing.get("LatestDate", "1900-01-01").replace("/", "-")
            _, old_ext = os.path.splitext(old_version_filename)
            
            # 退避用ファイル名: 日付_区分_対象_退避日時_old.pdf
            formatted_archive_name = f"{archive_date}_{category}_{group}_{timestamp}_old{old_ext}"
            old_archive_path = f"{category}/{group}/{formatted_archive_name}"
            
            logging.info(f"📦 旧版をリネームして退避中: {old_archive_path}")
            
            old_blob_client = blob_service.get_blob_client("mof2-blob-all", old_version_filename)
            try:
                old_data = old_blob_client.download_blob().readall()
                blob_service.get_blob_client("mof2-blob-old", old_archive_path).upload_blob(old_data, overwrite=True)
                old_blob_client.delete_blob()
            except Exception as e:
                logging.warning(f"⚠️ 旧版の整理に失敗（無視して続行）: {e}")

        # --- 今回のファイルを all に保存する処理 ---
        # ★ここを修正: formatted_rename_for_old ではなく、unique_name (元のファイル名ベース) を使用
        logging.info(f"🚀 最新版を all に保存中: {unique_name}")
        blob_service.get_blob_client("mof2-blob-all", unique_name).upload_blob(data, overwrite=True)
        
        # DBを更新
        try:
            logging.info("📝 テーブルを更新中...")
            table_client.upsert_entity({
                "PartitionKey": category,
                "RowKey": group,
                "LatestDate": new_date,
                "CurrentFileName": unique_name  # DBには unique_name を記録
            })
            logging.info("✅ テーブル更新成功")
        except Exception as e:
            logging.error(f"❌ テーブル更新失敗: {e}")
            raise
        
    else:
        # 【旧版判定】
        # 今回のファイルがいきなり古い場合は、old に直接保存（ここはリネームする）
        old_archive_path = f"{category}/{group}/{formatted_rename_for_old}"
        logging.info(f"📁 旧版として old にリネーム保存: {old_archive_path}")
        
        blob_service.get_blob_client("mof2-blob-old", old_archive_path).upload_blob(data, overwrite=True)

    logging.info(f"🗑️ new コンテナから削除中: {original_blob_name}")
    source_client.delete_blob()
    logging.info("✨ 全工程完了")