import version_manager
import version_manager_ai_azure
import file_organizer_blob
import time
import os
from dotenv import load_dotenv

# .envの読み込み（ローカル実行用）
load_dotenv()

def run_full_pipeline():
    print("🚀 --- 文書管理AI自動パイプラインを開始します ---")
    start_time = time.time()

    # 1. OCR処理 (mof2-blob-new から取得)
    print("\n[Step 1/3] OCR処理を開始...")
    try:
        version_manager.process_pdfs_from_blob()
    except Exception as e:
        print(f"❌ Step 1 でエラーが発生しました: {e}")
        return

    # 2. Azure OpenAI による判定
    print("\n[Step 2/3] Azure OpenAI による最新版判定を開始...")
    try:
        version_manager_ai_azure.run_ai_judgment()
    except Exception as e:
        print(f"❌ Step 2 でエラーが発生しました: {e}")
        return

    # 3. Blob間でのファイル仕分け
    print("\n[Step 3/3] Blobコンテナ間でのファイル移動を開始...")
    try:
        file_organizer_blob.organize_blobs()
    except Exception as e:
        print(f"❌ Step 3 でエラーが発生しました: {e}")
        return

    end_time = time.time()
    elapsed = end_time - start_time
    print(f"\n✨ 全行程が完了しました！ (合計時間: {elapsed:.2f}秒)")

if __name__ == "__main__":
    run_full_pipeline()