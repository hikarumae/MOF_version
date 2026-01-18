# pip install openai を事前に実行してください

import os
import json
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY") 
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT") 
DEPLOYMENT_NAME = "gpt-4o"

INPUT_JSON = "intermediate_data.json"
FINAL_JSON = "final_judgment.json"

def run_ai_judgment():
    if not os.path.exists(INPUT_JSON):
        print(f"エラー: {INPUT_JSON} が見つかりません。")
        return

    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        doc_data = json.load(f)

    # --- 【改善策】IDのマスキング（ファイル名をAIに見せない） ---
    id_map = {}
    masked_data = []
    for i, item in enumerate(doc_data):
        dummy_id = f"doc_{i:03d}" # doc_000, doc_001... という名前に置き換え
        id_map[dummy_id] = item["internal_id"]
        masked_data.append({
            "id": dummy_id,
            "text_head": item["text_head"],
            "text_tail": item["text_tail"]
        })

    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version="2024-02-15-preview"
    )

    # プロンプトの強化
    prompt = f"""
    あなたは精密な文書管理システムです。提供された「本文」のみから各書類の「最新版」を特定してください。
    
    【厳格ルール】
    1. ID（doc_xxx）は単なる識別子であり、内容とは無関係です。
    2. 会社名、書類の種類、日付などは、すべて「text_head」または「text_tail」の本文からのみ抽出してください。
    3. ファイル名などの外部情報は一切与えられていません。

    【思考ステップ】
    1. **名寄せ**: 各文書の契約相手を特定（例：「Japan Logistics」と「ジャパン・ロジスティクス」は同一）。「たも株式会社」系列は自社なので相手方には含めない。
    2. **種別判定**: 文書が「契約書」「就業規則」「職務権限基準」等のどれに当たるか判定。
    3. **グループ化**: 【相手先 + 文書種別】でグループを作る。
    4. **日付の標準化**: 抽出した日付（締結日、施行日、改訂日等）を YYYY-MM-DD 形式に変換。和暦（令和等）は必ず西暦に変換すること。
    5. **最新判定**: 各グループ内で日付の降順（新しい順）に並べ、一番新しいものだけを is_latest: true にし、残りを false にする。

    【出力形式】
    JSON（resultsキーのリスト）で、以下の項目を正確に返してください。
    - id: 入力された dummy_id
    - document_type: 本文から判断した文書種別
    - group_name: 判定に使用した【相手先 + 種別】
    - identified_date: 本文から抽出した日付（YYYY-MM-DD）
    - is_latest: true または false
    - confidence_score: 0から100の整数
    - reason: 判定の具体的な根拠（日本語）

    【解析対象データ】
    {json.dumps(masked_data, ensure_ascii=False)}
    """

    try:
        response = client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "あなたは精密な文書管理アドバイザーです。"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"} 
        )
        
        res_text = response.choices[0].message.content
        ai_response = json.loads(res_text)
        
        # --- 【改善策】ダミーIDを元のファイル名に戻す ---
        final_results = []
        for res in ai_response.get("results", []):
            dummy_id = res.get("id")
            if dummy_id in id_map:
                res["internal_id"] = id_map[dummy_id] # 元の名前（Contract_...）を復元
                del res["id"]
                final_results.append(res)
        
        final_data = {"results": final_results}

        with open(FINAL_JSON, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
            
        print(f"成功！: {FINAL_JSON} を作成しました。")

    except Exception as e:
        print(f"エラー発生: {e}")

if __name__ == "__main__":
    run_ai_judgment()