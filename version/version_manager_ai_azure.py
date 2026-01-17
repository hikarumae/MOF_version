# pip install openai を事前に実行してください

import os
import json
from openai import AzureOpenAI

# === Azure OpenAI 設定（環境変数） ===
# Azure ポータルの「キーとエンドポイント」から取得した値を設定してください
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY") 
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT") # 例: https://xxx.openai.azure.com/
DEPLOYMENT_NAME = "gpt-4o" # Azureでデプロイした際の名前

INPUT_JSON = "intermediate_data.json"
FINAL_JSON = "final_judgment.json"

def run_ai_judgment():
    # 1. 入力データの確認
    if not os.path.exists(INPUT_JSON):
        print(f"エラー: {INPUT_JSON} が見つかりません。")
        return

    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        doc_data = json.load(f)

    # 2. Azure OpenAI クライアントの初期化
    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        api_version="2024-02-15-preview" # または最新のバージョン
    )

    # 3. プロンプトの作成
    # JSONモードを有効にするため、システムプロンプトに「JSONで出力する」旨を含めるのが必須です
    prompt = f"""
    文書データを解析し、最新版を特定してください。
    
    【ルール】
    - 同じ相手方企業名や規則名（group_name）の中で、最も日付が新しいものを is_latest: true としてください。
    - 日付が不明な場合は、他の情報から判断するか、is_latest: false としてください。

    【データ】
    {json.dumps(doc_data, ensure_ascii=False)}
    """

    print(f"Azure OpenAI ({DEPLOYMENT_NAME}) に接続して解析を開始します...")
    
    try:
        # 4. Chat Completion の実行
        response = client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=[
                {
                    "role": "system", 
                    "content": "あなたは文書管理の専門家です。回答は必ず指定されたJSON形式（resultsをキーとしたリスト）で出力してください。"
                },
                {"role": "user", "content": prompt}
            ],
            # JSONモードの指定
            response_format={"type": "json_object"} 
        )
        
        # 5. 結果の取得と整形
        res_text = response.choices[0].message.content
        
        # 文字列として返ってくるので、一度JSONとしてロードして検証
        final_data = json.loads(res_text)
        
        # 6. 保存
        with open(FINAL_JSON, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
            
        print(f"成功！: {FINAL_JSON} を作成しました。")

    except Exception as e:
        print(f"エラー発生: {e}")

if __name__ == "__main__":
    run_ai_judgment()