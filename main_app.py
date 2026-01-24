# 司令塔・ブロブトリガー代行)モジュール 

import os
import time
import logging
from azure.storage.blob import BlobServiceClient
import pdf_analyzer
import ai_judge
import blob_organizer

logging.basicConfig(level=logging.INFO)
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

def main():
    blob_service = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    new_container = blob_service.get_container_client("mof2-blob-new")
    logging.info("🚀 AI仕分けボット起動")

    while True:
        try:
            # 1. 処理対象のファイルをリストアップ
            blobs = list(new_container.list_blobs())
            if not blobs:
                # ファイルがない時は静かに待機
                time.sleep(5)
                continue

            logging.info(f"📂 {len(blobs)} 件のファイルを検知しました。順次処理を開始します。")

            for blob_props in blobs:
                blob_name = blob_props.name
                if not blob_name.lower().endswith(".pdf"):
                    continue
                
                # ★ 個別のファイル処理を try-except で囲む（重要！）
                # これにより、1つのファイルでエラーが起きてもループが止まりません
                try:
                    logging.info(f"⚡ 処理開始: {blob_name}")
                    source_blob = new_container.get_blob_client(blob_name)
                    
                    # データの読み込み
                    data = source_blob.download_blob().readall()
                    
                    # 解析・判定・整理（前回修正した引数dataを渡す形）
                    text_h, text_t, img = pdf_analyzer.extract_pdf_content(data)
                    info = ai_judge.get_judgment(text_h, text_t, img)
                    blob_organizer.organize_files(info, blob_name, source_blob, data)
                    
                    logging.info(f"✅ 完了: {blob_name} -> {info.get('target_entity')}")

                except Exception as file_error:
                    # 特定のファイルでエラーが起きた場合、ログを出して次のファイルへ
                    logging.error(f"❌ ファイル「{blob_name}」の処理中にエラーが発生しました。スキップします: {file_error}")
                    continue

        except Exception as system_error:
            # コンテナへの接続自体が失敗した場合などの致命的なエラー
            logging.error(f"⚠️ システムエラー（監視を再開します）: {system_error}")
        
        time.sleep(5) # 1サイクル終わったら5秒待機

if __name__ == "__main__":
    main()