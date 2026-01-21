# 「常時監視型（ポーリング）」に変更
# Dockerfileと組み合わせる

import time
import os
import sys
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

# 各処理モジュールのインポート
import version_manager          # Step 1: 自前OCR (EasyOCR)
import version_manager_ai_azure # Step 2: Azure OpenAI判定
import file_organizer_blob      # Step 3: Blob移動 & 整理

# .envの読み込み
load_dotenv()

# 設定
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
SOURCE_CONTAINER = "mof2-blob-new"
CHECK_INTERVAL = 5  # 監視間隔（秒）

def has_new_files():
    """
    コンテナ内に処理すべきPDFがあるか、軽量にチェックする関数。
    (毎回OCR処理を走らせないための事前確認用)
    """
    try:
        service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
        container_client = service_client.get_container_client(SOURCE_CONTAINER)
        
        # コンテナが存在しない場合はまだファイルもない
        if not container_client.exists():
            return False

        # ファイルを1つだけ探してみる (リスト全体を取得せず負荷を下げる)
        # name_starts_withなどが必要なら引数に追加可能
        blob_iterator = container_client.list_blobs(results_per_page=1)
        for blob in blob_iterator:
            if blob.name.lower().endswith(".pdf"):
                return True
        
        return False
    except Exception as e:
        print(f"⚠️ 接続チェックエラー: {e}")
        return False

def run_full_pipeline():
    """
    1回分の処理フローを実行する関数
    (OCR -> AI判定 -> 移動)
    """
    print("\n🚀 --- 新規ファイルを検知！処理を開始します ---")
    start_time = time.time()

    # --- [Step 1] PDFダウンロード & ローカルOCR ---
    print("1️⃣ [Step 1] OCR処理を実行中...")
    try:
        version_manager.process_pdfs_from_blob()
    except Exception as e:
        print(f"❌ Step 1 (OCR) エラー: {e}")
        return # ここで失敗したら中断

    # --- [Step 2] Azure OpenAI による判定 ---
    print("2️⃣ [Step 2] AIによる判定を実行中...")
    try:
        version_manager_ai_azure.run_ai_judgment()
    except Exception as e:
        print(f"❌ Step 2 (AI) エラー: {e}")
        return

    # --- [Step 3] Blobコンテナ間での移動 ---
    print("3️⃣ [Step 3] ファイル移動を実行中...")
    try:
        file_organizer_blob.organize_blobs()
    except Exception as e:
        print(f"❌ Step 3 (移動) エラー: {e}")
        return

    elapsed = time.time() - start_time
    print(f"✨ 処理完了 (所要時間: {elapsed:.2f}秒)")
    print("-" * 50)

def watch_loop():
    """
    無限ループでコンテナを監視するメイン関数
    """
    print(f"👀 監視を開始しました: コンテナ '{SOURCE_CONTAINER}'")
    print(f"⏱️ 確認間隔: {CHECK_INTERVAL}秒")
    print("--------------------------------------------------")

    while True:
        try:
            # 1. ファイルがあるかチラ見する
            if has_new_files():
                # 2. あれば処理を実行
                run_full_pipeline()
            else:
                # 3. なければログを出して待機（ログが流れすぎないようprintは控えめにしてもOK）
                # print(f"💤 ファイル待ち... ({datetime.now().strftime('%H:%M:%S')})", end="\r")
                pass

        except KeyboardInterrupt:
            print("\n🛑 監視を手動で停止しました。")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ 予期せぬエラーが発生しました（監視は継続します）: {e}")
            time.sleep(5) # エラー連打を防ぐための待機

        # 指定時間待機
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    # Dockerコンテナが起動すると、この関数が呼ばれ続ける
    watch_loop()