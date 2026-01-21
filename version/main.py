# 
import version_manager
import search_fetcher           # Step 1: Azure AI Searchからデータ取得
import version_manager_ai_azure # Step 2: Azure OpenAIによる判定
import file_organizer_blob      # Step 3: Blob間でのファイル移動
import time
import os
from dotenv import load_dotenv

# .envの読み込み（ローカル実行用）
load_dotenv()


def run_full_pipeline():
    # 1回だけ全工程を実行して終了する形にする
    version_manager.process_pdfs_from_blob()
    version_manager_ai_azure.run_ai_judgment()
    file_organizer_blob.organize_blobs()

if __name__ == "__main__":
    # ローカルで手動実行したい時だけ動く
    run_full_pipeline()