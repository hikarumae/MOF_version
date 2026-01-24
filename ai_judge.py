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
    
    # 既存の構造を維持しつつ、最新日付への対応と名寄せを強化
    prompt = f"""
    あなたは精密な文書管理システムです。以下の【厳格ルール】と【思考ステップ】を遵守し、提供されたデータから情報を抽出してください。

    【厳格ルール】
    1. 会社名、書類の種類、日付などは、すべて「text_head」「text_tail」または「画像」からのみ抽出してください 。
    2. ファイル名などの外部情報は一切与えられていません 。
    3. **日付の選択基準**: 文書内に複数の日付（施行日、改訂日など）がある場合は、**最も新しい（未来に近い）日付**を「identified_date」として採用してください 。
    4. **名寄せの徹底**: 「target_entity」からは「株式会社」「有限会社」「合同会社」等の法的実体を示す語句を**必ず削除**してください（例：「株式会社サンプル」→「サンプル」） 。

    【思考ステップ】
    1. **名寄せ**: 各文書の契約相手や規定名を特定（例：「Japan Logistics」と「ジャパン・ロジスティクス」は同一）。「たも株式会社」系列は自社なので相手方には含めない 。
    2. **種別判定**: 文書が「契約書」「就業規則」「職務権限基準」等のどれに当たるか判定 。
    3. **グループ化**: 【相手先(または規定名) + 文書種別】で判定 。
    4. **日付の標準化**: 抽出した**最新の日付**を YYYY-MM-DD 形式に変換。和暦（令和8年など）は必ず正確な西暦（2026年）に計算して変換すること [cite: 1, 2]。

    【出力要件】
    以下のJSON形式で出力してください 。
    {{
        "document_type": "文書種別",
        "target_entity": "法的実体語句を除いた名前",
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