# AI判定担当モジュール

import json
import os
from openai import AzureOpenAI

def get_judgment(text, base64_image):
    client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_KEY"),
        api_version="2024-02-15-preview"
    )
    
    content = [{"type": "text", "text": "提供されたテキストの【Document Head】(冒頭)と【Document Tail】(末尾)、および画像から、書類情報を抽出してください。"}]

    content.append({"type": "text", "text": f"テキスト: {text}"})
    if base64_image:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}})

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": content}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)