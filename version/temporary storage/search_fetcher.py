import os
import json
import time
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexerClient
from dotenv import load_dotenv

load_dotenv()

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME")
INDEXER_NAME = os.getenv("AZURE_SEARCH_INDEXER_NAME") 
OUTPUT_JSON = "intermediate_data.json"

def reset_and_run_indexer():
    if not INDEXER_NAME:
        print("⚠️ エラー: .env に INDEXER_NAME が設定されていません。")
        return

    print(f"🔄 インデクサー ({INDEXER_NAME}) の同期を開始...")
    indexer_client = SearchIndexerClient(SEARCH_ENDPOINT, AzureKeyCredential(SEARCH_KEY))

    try:
        # 1. リセット
        indexer_client.reset_indexer(INDEXER_NAME)
        # 2. 実行
        indexer_client.run_indexer(INDEXER_NAME)
        
        print("   ...スキャン実行中 (最大30秒間確認します)...")
        
        # ポーリングを最大10回（30秒）に制限。
        # スクリーンショットでAzure側が8秒前後で終わることを確認済みのため。
        for i in range(10):
            time.sleep(3)
            status = indexer_client.get_indexer_status(INDEXER_NAME)
            current_state = str(status.status).lower()
            
            # idle（待機）になれば成功
            if current_state == "idle":
                print(f"✅ インデックス同期完了。")
                return
            
            print(f"      現在ステータス: {current_state}...")

        print("⚠️ 待機時間を経過しました。最新データの取得を試みます。")
                
    except Exception as e:
        print(f"⚠️ インデクサー操作中に例外が発生（続行を試みます）: {e}")

def fetch_all_documents():
    if os.path.exists(OUTPUT_JSON):
        os.remove(OUTPUT_JSON)

    # ステップ1: インデクサーの同期（タイムアウト制限付き）
    reset_and_run_indexer()

    # ステップ2: 検索実行
    print(f"🔍 インデックス ({INDEX_NAME}) からデータを抽出中...")
    credential = AzureKeyCredential(SEARCH_KEY)
    client = SearchClient(endpoint=SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=credential)

    try:
        # 確実に全件取得するために top=1000 を指定
        results = client.search(
            search_text="*", 
            select="metadata_storage_name, content, text_head", 
            top=1000 
        )
        
        extracted_data = []
        for doc in results:
            file_name = doc.get("metadata_storage_name") or "unknown"
            # 取得できたフィールドから本文を取得
            full_text = doc.get("content") or doc.get("text_head") or ""
            
            extracted_data.append({
                "internal_id": file_name,
                "text_head": full_text[:2000],
                "text_tail": full_text[-2000:] if full_text else ""
            })

        if not extracted_data:
            print("❌ エラー: 検索結果が0件です。")
            return

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, ensure_ascii=False, indent=4)
        
        print(f"✨ Step 1 完了: {len(extracted_data)} 件の文書を取得しました。")

    except Exception as e:
        print(f"❌ 検索クエリ実行エラー: {e}")
        raise e

if __name__ == "__main__":
    fetch_all_documents()