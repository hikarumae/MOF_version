import version_manager          # Step 1: 自前OCR (EasyOCR) でデータ取得
import version_manager_ai_azure # Step 2: Azure OpenAIによる判定
import file_organizer_blob      # Step 3: Blob間でのファイル移動
import time
import os
from dotenv import load_dotenv

# .envの読み込み
load_dotenv()

def run_full_pipeline():
    print("🚀 --- 文書管理AI自動パイプライン (自前OCR版) 開始 ---")
    start_time = time.time()

    # --- [Step 1] PDFダウンロード & ローカルOCR ---
    # Azure AI Searchを使わず、Pythonスクリプトで直接OCRします。
    print("\n[Step 1/3] BlobからPDFを取得し、OCR処理を実行中...")
    try:
        # ここを search_fetcher から version_manager に戻しました
        version_manager.process_pdfs_from_blob()
    except Exception as e:
        print(f"❌ Step 1 (OCR処理) でエラーが発生しました: {e}")
        return

    # --- [Step 2] Azure OpenAI による最新版・カテゴリ判定 ---
    print("\n[Step 2/3] Azure OpenAI による最新版判定を開始...")
    try:
        version_manager_ai_azure.run_ai_judgment()
    except Exception as e:
        print(f"❌ Step 2 (AI判定) でエラーが発生しました: {e}")
        return

    # --- [Step 3] Blobコンテナ間でのファイル仕分け移動 ---
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
    run_full_pipeline()