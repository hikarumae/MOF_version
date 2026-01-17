

import os
import json
from openai import OpenAI

# 環境変数 OPENAI_API_KEY から読み込み
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

INPUT_JSON = "intermediate_data.json" # 前処理（version_manager.py）で作ったデータの場所
FINAL_JSON = "final_judgment.json" # AIが下した最終判定の保存先


def run_ai_judgment():
    # 前処理データが存在するかチェック。未実行ならエラーを出して終了
    if not os.path.exists(INPUT_JSON):
        print(f"エラー: {INPUT_JSON} が見つかりません。先に前処理を実行してください。")
        return

    # 前処理で抽出したテキスト（冒頭と末尾の2000文字分）を読み込みます
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        doc_data = json.load(f)


    #======= AIに渡すシステムプロンプトを定義 =======#
    system_prompt = """
    あなたは高度な文書管理専門のAIです。
    各データの `text_content` のみを分析し、以下のタスクを遂行してください。
    ※ `internal_id` はファイル名ですが、内容の判定には一切使用しないでください。

    1. 分類 (Category): 
       - 本文に「第1条(売買契約)」や「甲・乙」の定義があれば「CONTRACT（契約書）」。
       - 「就業規則」「職務権限」「規定」などの表題や条文があれば「REGULATION（社内規程）」。
    2. グルーピング (Group Name):
       - CONTRACT: 本文内の当事者（例：たも株式会社と相手方企業）の組み合わせで名寄せ。
       - REGULATION: 本文内の文書タイトル（例：就業規則）で名寄せ。
    3. 最新判定 (Version Control):
       - 本文内の「契約締結日」「施行日」「改訂日」を抽出し、比較。
       - 各グループ内で、日付が最も新しいものに is_latest: true を付与。

    【出力形式】
    JSON: { "results": [ { "internal_id", "category", "group_name", "date", "is_latest" } ] }
    """

    print("AIによる解析を開始します...")
    try:
        # AIにリクエストを送信
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"解析対象データ:\n{json.dumps(doc_data, ensure_ascii=False)}"}
            ],
            response_format={ "type": "json_object" }# 答えをJSON形式で受け取る設定
        )

        # AIの回答をファイルに書き込み
        with open(FINAL_JSON, "w", encoding="utf-8") as f:
            f.write(response.choices[0].message.content)
        print(f"判定完了: {FINAL_JSON} に結果を保存しました。")
    except Exception as e:
        print(f"AI解析中にエラーが発生しました: {e}")

if __name__ == "__main__":
    run_ai_judgment()
    
# AIの回答を確認
print("\n=== AIの回答内容 ===")
with open(FINAL_JSON, "r", encoding="utf-8") as f:
    print(f.read())