# Azure AI Search用　

import search_fetcher           # Step 1: Azure AI Searchからデータ取得
import version_manager_ai_azure # Step 2: Azure OpenAIによる判定
import file_organizer_blob      # Step 3: Blob間でのファイル移動
import time
import os
from dotenv import load_dotenv

# .envの読み込み（ローカル実行用）
load_dotenv()

def run_full_pipeline():
    print("🚀 --- 文書管理AI自動パイプライン (AI Search版) 開始 ---")
    start_time = time.time()

    # --- [Step 1] Azure AI Search から解析済みテキストを取得 ---
    # 自前でOCRを行わず、Azure側ですでにOCR済みのデータを取得します。
    print("\n[Step 1/3] AI SearchからOCR済みテキストを取得中...")
    try:
        search_fetcher.fetch_all_documents()
    except Exception as e:
        print(f"❌ Step 1 (データ取得) でエラーが発生しました: {e}")
        return

    # --- [Step 2] Azure OpenAI による最新版・カテゴリ判定 ---
    # 取得した「前後2000文字」をAIに渡し、仕分けルールを決定します。
    print("\n[Step 2/3] Azure OpenAI による最新版判定を開始...")
    try:
        version_manager_ai_azure.run_ai_judgment()
    except Exception as e:
        print(f"❌ Step 2 (AI判定) でエラーが発生しました: {e}")
        return

    # --- [Step 3] Blobコンテナ間でのファイル仕分け移動 ---
    # AIの判定結果に基づき、適切なコンテナのフォルダへファイルを移動します。
    print("\n[Step 3/3] Blobコンテナ間でのファイル移動を開始...")
    try:
        file_organizer_blob.organize_blobs()
    except Exception as e:
        print(f"❌ Step 3 (ファイル移動) でエラーが発生しました: {e}")
        return

    # --- 終了処理 ---
    end_time = time.time()
    elapsed = end_time - start_time
    print("-" * 50)
    print(f"✨ 全行程が正常に完了しました！")
    print(f"⏱️ 合計処理時間: {elapsed:.2f}秒")
    print("-" * 50)

if __name__ == "__main__":
    # 実行前に必要なディレクトリ等があればここでチェックする記述を追加しても良いです
    run_full_pipeline()