import os
import json
import time
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexerClient
from dotenv import load_dotenv

load_dotenv()

# .envの設定読み込み
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME")
# スクリーンショットのお名前に合わせました
INDEXER_NAME = os.getenv("AZURE_SEARCH_INDEXER_NAME") 
OUTPUT_JSON = "intermediate_data.json"

def reset_and_run_indexer():
    """
    インデクサーを「リセット」して「実行」し、完了を待ちます。
    これにより、新しいファイル（27件目）も確実に認識させます。
    """
    if not INDEXER_NAME:
        print("⚠️ エラー: .env に AZURE_SEARCH_INDEXER_NAME が設定されていません。")
        return

    print(f"🔄 インデクサー ({INDEXER_NAME}) をリセットして強制再スキャンします...")
    indexer_client = SearchIndexerClient(SEARCH_ENDPOINT, AzureKeyCredential(SEARCH_KEY))

    try:
        # 1. リセット（履歴消去）
        indexer_client.reset_indexer(INDEXER_NAME)
        
        # 2. 実行（スキャン開始）
        indexer_client.run_indexer(INDEXER_NAME)
        
        # 3. 完了待機ループ
        print("   ...インデックス更新中 (完了まで待機します)...")
        while True:
            status = indexer_client.get_indexer_status(INDEXER_NAME)
            last_result = status.last_result
            
            if status.status == "error":
                print("❌ インデクサーエラー発生")
                if last_result and last_result.errors:
                    print(f"   詳細: {last_result.errors[0].message}")
                break
            
            # 実行中でなければ完了とみなす
            if status.status != "running":
                if last_result and last_result.status == "success":
                    print(f"✅ インデックス更新完了 (処理件数: {last_result.item_count})")
                else:
                    print(f"⚠️ インデクサー停止 (ステータス: {last_result.status if last_result else '不明'})")
                break
            
            time.sleep(5)
                
    except Exception as e:
        print(f"⚠️ インデクサー操作エラー: {e}")

def fetch_all_documents():
    # Step 0: まずインデクサーを動かして、データを最新（27件）にする
    reset_and_run_indexer()

    # Step 1: 検索クライアントの準備
    print(f"🔍 インデックス ({INDEX_NAME}) から全件取得を開始します...")
    credential = AzureKeyCredential(SEARCH_KEY)
    client = SearchClient(endpoint=SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=credential)

    try:
        # Step 2: 全件取得 (top=1000)
        # ※ content が取得できない場合は text_head を見る安全策付き
        results = client.search(
            search_text="*", 
            select="metadata_storage_name, content, text_head", 
            top=1000 
        )
        
        extracted_data = []
        for doc in results:
            file_name = doc.get("metadata_storage_name") or "unknown"
            # content（全文）優先、なければ text_head
            full_text = doc.get("content") or doc.get("text_head") or ""
            
            extracted_data.append({
                "internal_id": file_name,
                "text_head": full_text[:2000],
                "text_tail": full_text[-2000:] if full_text else ""
            })

        # データが空ならエラーにする
        if not extracted_data:
            print("❌ エラー: ドキュメントが1件も取得できませんでした。")
            return

        # 保存
        if os.path.exists(OUTPUT_JSON):
            os.remove(OUTPUT_JSON)
            
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, ensure_ascii=False, indent=4)
        
        print(f"✨ 取得完了: {len(extracted_data)} 件を保存しました。")

    except Exception as e:
        print(f"❌ 取得エラー: {e}")
        # 後続処理を止めるためにエラーを投げる
        raise e

if __name__ == "__main__":
    fetch_all_documents()