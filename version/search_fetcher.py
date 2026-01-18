import os
import json
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from dotenv import load_dotenv

load_dotenv()

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME")
OUTPUT_JSON = "intermediate_data.json"

def fetch_all_documents():
    # 古い中間データを削除して、確実に最新を取得するようにする
    if os.path.exists(OUTPUT_JSON):
        os.remove(OUTPUT_JSON)

    print(f"🔄 インデックス ({INDEX_NAME}) から全件取得を開始します...")
    credential = AzureKeyCredential(SEARCH_KEY)
    client = SearchClient(endpoint=SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=credential)

    try:
        # top=1000で全件取得
        # contentが取得できない場合は text_head を優先的に試みる
        results = client.search(
            search_text="*", 
            select="metadata_storage_name, content, text_head", 
            top=1000 
        )
        
        extracted_data = []
        for doc in results:
            file_name = doc.get("metadata_storage_name") or "unknown"
            # content（全文）が取れない場合は text_head を使用
            full_text = doc.get("content") or doc.get("text_head") or ""
            
            extracted_data.append({
                "internal_id": file_name,
                "text_head": full_text[:2000],
                "text_tail": full_text[-2000:] if full_text else ""
            })

        if not extracted_data:
            raise Exception("取得できたドキュメントが0件です。インデックスを確認してください。")

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, ensure_ascii=False, indent=4)
        
        print(f"✨ 取得完了: {len(extracted_data)} 件を保存しました。")

    except Exception as e:
        print(f"❌ 取得エラー: {e}")
        # Step 2に進ませないために、ここで明示的に例外を投げる
        raise e

if __name__ == "__main__":
    fetch_all_documents()