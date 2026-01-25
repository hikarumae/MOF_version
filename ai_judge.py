# AI判定担当モジュール

import json
import os
from openai import AzureOpenAI

def get_judgment(text_head, text_tail, base64_image, company_name="たも株式会社"):
    client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version="2024-02-15-preview"
    )
    
    # プロンプト
    prompt = f"""
    あなたは精密な文書管理システムです。
    **重要ルール：以下の【解析対象データ】（テキストおよび画像）の中に記載されている情報のみを使用して判定してください。データに記載のない情報を推測したり、外部の一般知識を補完したりすることは厳禁です。**

    【自社情報】
    ・自社名：{company_name}

    【カテゴリ判定（document_type）】
    ・内容から「契約書」「就業規則」「職務権限基準」「請求書」「その他」のいずれかに分類してください。

    【日付抽出ルール（identified_date）】
    **必ず【解析対象データ】内に明記されている日付から抽出してください。**
    1. **就業規則 / 職務権限基準**:
       - 記載されている「施行日」または「改訂日」を抽出。
       - 複数ある場合は、データ内で最も新しい日付（未来に近いもの）を採用。
    2. **契約書 / 請求書**:
       - 契約書は「契約締結日」、請求書は「発行日」を抽出。
    3. **その他**:
       - 文面から読み取れる作成日や日付を抽出。
    ※和暦は西暦（YYYY-MM-DD）に変換してください。

    【取引先の特定ルール（target_entity）】
    **必ず【解析対象データ】内に明記されている名称から抽出してください。**
    1. **契約書 / 請求書**:
       - 自社（{company_name}）およびその略称**以外**の取引先名を抽出。
       - 自社と取引先の両方が記載されている場合、必ず取引先側を採用。
    2. **就業規則 / 職務権限基準**:
       - 一律で「自社」と出力。
    3.**法的実体語句（法人格）の保持と正式名称化**:
       - 抽出した名称に含まれる「株式会社」「有限会社」「合同会社」等の語句は、**削除せずに必ず含めてください**。
       - データ内で「（株）」「㈱」「(有)」などの略称が使われている場合は、省略せずに**「株式会社」「有限会社」などの正式な表記に変換**して出力してください。

    【思考ステップ】
    1. 【解析対象データ】を精査し、一切の推測を排除して記載事実のみを確認する。
    2. データ内の記述に基づき「document_type」を決定する。
    3. データ内に存在する日付の中から、カテゴリに応じた最適な日付を特定する。
    4. データ内に存在する組織名から、自社を除外して「target_entity」を特定する。

    【出力要件】
    以下のJSON形式で出力してください。データから情報を特定できない項目がある場合は、空文字 "" を返してください。
    {{
        "document_type": "契約書 / 就業規則 / 職務権限基準 / 請求書 / その他 のいずれか",
        "target_entity": "抽出した取引先名 または 自社",
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