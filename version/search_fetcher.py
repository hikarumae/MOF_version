import os
import json
import time
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexerClient
from dotenv import load_dotenv

load_dotenv()

# === 設定 ===
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME")
INDEXER_NAME = os.getenv("AZURE_SEARCH_INDEXER_NAME") # .envに追加必須（例: azureblob-indexer）
OUTPUT_JSON = "intermediate_data.json"

def run_indexer_and_wait():
    """
    インデクサーを強制実行し、処理が完了するまで待機します。
    これをしないと、アップロード直後のファイルが検索に出てきません。
    """
    if not INDEXER_NAME:
        print("⚠️ 警告: AZURE_SEARCH_INDEXER_NAME が設定されていません。インデックス更新をスキップします。")
        return

    print(f"🔄 インデクサー ({INDEXER_NAME}) を実行して最新状態にします...")
    # インデクサー専用のクライアント
    indexer_client = SearchIndexerClient(SEARCH_ENDPOINT, AzureKeyCredential(SEARCH_KEY))

    try:
        # 1. インデクサーをキック（実行）
        indexer_client.run_indexer(INDEXER_NAME)
        
        # 2. 完了するまで監視ループ
        print("   ...処理中 (これには数分かかる場合があります)...")
        while True:
            status = indexer_client.get_indexer_status(INDEXER_NAME)
            last_result = status.last_result
            exec_status = status.status

            if exec_status == "running":
                print("   ...インデックス作成中...")
            elif exec_status == "error":
                print("❌ インデクサーエラー発生")
                break
            elif last_result and last_result.status == "success":
                print(f"✅ インデックス更新完了 (処理件数: {last_result.item_count})")
                break
            elif last_result and last_result.status == "inProgress":
                 print("   ...進行中...")
            else:
                # success状態でアイドル＝完了済み
                print("✅ インデクサーは待機状態です（最新）。")
                break
            
            time.sleep(5) # 5秒おきに確認
                
    except Exception as e:
        print(f"⚠️ インデクサー操作中にエラー: {e}")
        # エラーでも検索は続行させる（古いデータだけでも取るため）

def fetch_data_from_ai_search():
    # Step 0: まずインデックスを最新にする（ここが最重要）
    run_indexer_and_wait()

    print(f"🔍 Azure AI Search ({INDEX_NAME}) からデータを取得中...")
    credential = AzureKeyCredential(SEARCH_KEY)
    client = SearchClient(endpoint=SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=credential)

    try:
        # 全件取得（top指定なしでイテレータを回す）
        # ※ metadata_storage_name は必須。merged_content は本文。
        results = client.search(
            search_text="*", 
            select="metadata_storage_name, merged_content"
        )
        
        extracted_data = []
        count = 0
        
        for doc in results:
            file_name = doc.get("metadata_storage_name") or "unknown_filename"
            full_text = doc.get("merged_content") or ""
            
            # --- 強制切り出しロジック ---
            # Azure側のフィールドに頼らず、ここで必ず切り出す
            text_head = full_text[:2000]
            text_tail = full_text[-2000:] if full_text else ""
            
            print(f"  -> 取得: {file_name}")
            
            extracted_data.append({
                "internal_id": file_name,
                "text_head": text_head,
                "text_tail": text_tail
            })
            count += 1

        # JSON保存
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, ensure_ascii=False, indent=4)
            
        print(f"✅ 合計 {count} 件のデータを抽出しました。")

    except Exception as e:
        print(f"❌ エラー: {e}")

if __name__ == "__main__":
    fetch_data_from_ai_search()