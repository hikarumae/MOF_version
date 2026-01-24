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
    1. 会社名、書類の種類、日付などは、すべて「text_head」「text_tail」または「画像」からのみ抽出してください。
    2. **最新日付の採用**: 複数の日付がある場合は、最も新しい（未来に近い）日付を採用してください。
    3. **法的実体語句の除去**: 「target_entity」から「株式会社」等の語句を必ず削除してください。
    4. **カテゴリの強制統一**: 「document_type」は、以下のいずれかに完全に一致させてください。
       - **「契約書」**: 売買契約書、業務委託契約書、秘密保持契約書など、あらゆる契約書類は一律で「契約書」とすること。
       - **「就業規則」**
       - **「職務権限基準」**
       - これら以外は「その他」とすること。

    【思考ステップ】
    1. **名寄せ**: 相手先会社名を特定し、法的実体（株式会社等）を完全に除去して名前を正規化します。
    2. **種別判定**: 文書の内容から、上記の4つの統一カテゴリのいずれかに分類します。
    3. **グループ化**: 【正規化した名前（target_entity） + 統一カテゴリ（document_type）】を一つの管理単位として特定します。
    4. **日付の標準化**: 文書内の最新の日付を特定し、YYYY-MM-DD 形式に変換。和暦（令和8年など）は西暦（2026年）に正確に変換してください。

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