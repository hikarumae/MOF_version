# AI判定担当モジュール

import json
import os
from openai import AzureOpenAI

def get_judgment(text_head, text_tail, base64_image):
    client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_KEY"),
        api_version="2024-02-15-preview"
    )
    
    # 以前のプロンプトをそのまま活用
    prompt = f"""
    あなたは精密な文書管理システムです。以下の【厳格ルール】と【思考ステップ】を遵守し、提供されたデータから情報を抽出してください。

    【厳格ルール】
    1. 会社名、書類の種類、日付などは、すべて「text_head」「text_tail」または「画像」からのみ抽出してください。
    2. ファイル名などの外部情報は一切与えられていません。

    【思考ステップ】
    1. **名寄せ**: 各文書の契約相手や規定名を特定（例：「Japan Logistics」と「ジャパン・ロジスティクス」は同一）。「たも株式会社」系列は自社なので相手方には含めない。「会社名から『株式会社』や『有限会社』を削除して比較してください」。
    2. **種別判定**: 文書が「契約書」「就業規則」「職務権限基準」等のどれに当たるか判定。※売買契約書や覚書は「契約書」に統一。
    3. **グループ化**: 【相手先(または規定名) + 文書種別】で判定。
    4. **日付の標準化**: 抽出した日付を YYYY-MM-DD 形式に変換。和暦は必ず西暦に変換すること。

    【出力要件】
    以下のJSON形式で出力してください。
    {{
        "document_type": "文書種別",
        "target_entity": "相手先会社名 または 規定名",
        "identified_date": "YYYY-MM-DD"
    }}

    【解析対象データ】
    text_head: {text_head}
    text_tail: {text_tail}
    """

    content = [{"type": "text", "text": prompt}]
    if base64_image:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}})

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": content}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)