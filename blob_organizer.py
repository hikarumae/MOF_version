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

def organize_files(info, original_blob_name, source_client, data):
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    blob_service = BlobServiceClient.from_connection_string(conn_str)
    table_client = TableClient.from_connection_string(conn_str, "LatestDocumentDB")
    
    # 1. テーブルの自動作成
    try:
        table_client.create_table()
    except:
        pass

    # 2. AI判定結果のクレンジング
    category = sanitize_key(info.get("document_type", "その他"))
    group = sanitize_key(info.get("target_entity", "不明"))
    new_date = info.get("identified_date", "1900-01-01")

    # タイムスタンプ生成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # ★追加: 元のファイル名から拡張子だけ取得 (.pdfなど)
    _, ext = os.path.splitext(original_blob_name)
    
    # ★修正: 今回のファイル用のリネーム名を作成 (例: 2023-10-01_請求書_株式会社A_20240128_120000.pdf)
    # ファイル名に使えない文字対策としてここでもsanitize_keyを通すか、単純な置換を行うのが安全です
    safe_date = new_date.replace("/", "-") 
    formatted_new_filename = f"{safe_date}_{category}_{group}_{timestamp}{ext}"

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
        # 【最新版判定】 -> 既存のファイルを old に退避する必要がある
        if existing:
            old_version_filename = existing['CurrentFileName']
            
            # ★修正: 退避するファイルの情報をDBから取得して、綺麗な名前にリネームする
            # 退避ファイルの元の日付を使用
            archive_date = existing.get("LatestDate", "1900-01-01").replace("/", "-")
            # 拡張子の取得（DB上のファイル名から）
            _, old_ext = os.path.splitext(old_version_filename)
            
            # 退避用ファイル名: 日付_区分_対象_退避日時.pdf
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

        # 今回のファイルを all コンテナへ保存
        # (ここも formatted_new_filename を使うと、allフォルダの中身も綺麗になります)
        logging.info(f"🚀 最新版を all に保存中: {formatted_new_filename}")
        blob_service.get_blob_client("mof2-blob-all", formatted_new_filename).upload_blob(data, overwrite=True)
        
        # DBを更新
        try:
            logging.info("📝 テーブルを更新中...")
            table_client.upsert_entity({
                "PartitionKey": category,
                "RowKey": group,
                "LatestDate": new_date,
                "CurrentFileName": formatted_new_filename # DBにも綺麗な名前を登録
            })
            logging.info("✅ テーブル更新成功")
        except Exception as e:
            logging.error(f"❌ テーブル更新失敗: {e}")
            raise
        
    else:
        # 【旧版判定】 -> 今回のファイルを直接 old に保存
        # ★修正: ここで formatted_new_filename を使用してリネーム保存
        old_archive_path = f"{category}/{group}/{formatted_new_filename}"
        logging.info(f"📁 旧版として old にリネーム保存: {old_archive_path}")
        
        blob_service.get_blob_client("mof2-blob-old", old_archive_path).upload_blob(data, overwrite=True)

    # 4. 全ての処理が成功した時だけ、new コンテナから削除
    logging.info(f"🗑️ new コンテナから削除中: {original_blob_name}")
    source_client.delete_blob()
    logging.info("✨ 全工程完了")