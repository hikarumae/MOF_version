import os
import json
import requests

# 設定
API_KEY = os.getenv("GOOGLE_API_KEY")
INPUT_JSON = "intermediate_data.json"
FINAL_JSON = "final_judgment.json"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

def get_available_model():
    """利用可能なGeminiモデルを自動で取得する"""
    url = f"{BASE_URL}/models?key={API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        models = response.json().get('models', [])
        # 'generateContent' に対応しているGeminiモデルを探す
        for m in models:
            if 'gemini' in m['name'] and 'generateContent' in m['supportedGenerationMethods']:
                return m['name']  # 例: 'models/gemini-1.5-flash'
    except Exception as e:
        print(f"モデルリストの取得に失敗しました: {e}")
    return "models/gemini-pro" # 最後の手段として定番名を返す

def run_ai_judgment():
    if not os.path.exists(INPUT_JSON):
        print(f"エラー: {INPUT_JSON} が見つかりません。")
        return

    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        doc_data = json.load(f)

    # 利用可能なモデルを自動特定
    target_model = get_available_model()
    print(f"使用するモデル: {target_model}")

    api_url = f"{BASE_URL}/{target_model}:generateContent?key={API_KEY}"

    prompt = f"""
    文書データを解析し、最新版を特定してください。
    回答は必ず以下のJSON形式のみで出力してください。説明文は不要です。

    {{
      "results": [
        {{
          "internal_id": "ファイル名",
          "category": "CONTRACT または REGULATION",
          "group_name": "相手方企業名 または 規則名",
          "date": "本文の日付",
          "is_latest": true または false
        }}
      ]
    }}

    【データ】
    {json.dumps(doc_data, ensure_ascii=False)}
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    print("Gemini API に接続して解析を開始します...")
    
    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        
        res_text = response.json()['candidates'][0]['content']['parts'][0]['text']
        
        # 掃除
        clean_json = res_text.strip()
        if "```" in clean_json:
            clean_json = clean_json.split("```")[1].replace("json", "").strip()
        
        # 保存
        with open(FINAL_JSON, "w", encoding="utf-8") as f:
            f.write(clean_json)
            
        print(f"成功！: {FINAL_JSON} を作成しました。")

    except Exception as e:
        print(f"エラー発生: {e}")
        if 'response' in locals():
            print(f"詳細: {response.text}")

if __name__ == "__main__":
    run_ai_judgment()