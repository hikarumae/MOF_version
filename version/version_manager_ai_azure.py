import os
import json
import time
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY") 
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT") 
DEPLOYMENT_NAME = "gpt-4o"

INPUT_JSON = "intermediate_data.json"
FINAL_JSON = "final_judgment.json"
BATCH_SIZE = 5

def normalize_doc_type(doc_type):
    """
    表記ゆれを防ぐための正規化ロジック
    「売買契約書」と「契約書」が別グループになると比較できないため、
    比較用キーとしては「契約書」に統一する。
    """
    if not doc_type: return "不明"
    
    # "契約書" という文字が含まれていれば、すべて "契約書" グループとして扱う
    if "契約書" in doc_type:
        return "契約書"
    
    # その他の文書はそのまま（例：請求書、就業規則など）
    return doc_type

def run_ai_judgment():
    if not os.path.exists(INPUT_JSON) or os.path.getsize(INPUT_JSON) == 0:
        print(f"⚠️ エラー: {INPUT_JSON} が見つかりません。")
        return

    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        doc_data = json.load(f)
    
    if not doc_data:
        print("⚠️ データがありません。")
        return

    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version="2024-02-15-preview"
    )

    all_ai_results = []
    print(f"📋 全 {len(doc_data)} 件の文書を解析します...")

    # --- バッチ処理 ---
    for i in range(0, len(doc_data), BATCH_SIZE):
        batch = doc_data[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        print(f"   Running Batch {batch_num} ({len(batch)} items)...")

        # IDマッピング
        id_map = {}
        masked_batch = []
        for j, item in enumerate(batch):
            dummy_id = f"b{batch_num}_doc_{j:03d}"
            id_map[dummy_id] = item["internal_id"]
            masked_batch.append({
                "id": dummy_id,
                "text_head": item["text_head"],
                "text_tail": item["text_tail"]
            })

        # === 厳格ルールと思考ステップを含んだプロンプト ===
        prompt = f"""
        あなたは精密な文書管理システムです。以下の【厳格ルール】と【思考ステップ】を遵守し、提供されたデータから情報を抽出してください。

        【厳格ルール】
        1. ID（doc_xxx）は単なる識別子であり、内容とは無関係です。
        2. 会社名、書類の種類、日付などは、すべて「text_head」または「text_tail」の本文からのみ抽出してください。
        3. ファイル名などの外部情報は一切与えられていません。

        【思考ステップ】
        1. **名寄せ**: 各文書の契約相手を特定（例：「Japan Logistics」と「ジャパン・ロジスティクス」は同一）。「たも株式会社」系列は自社なので相手方には含めない。
        2. **種別判定**: 文書が「契約書」「就業規則」「職務権限基準」等のどれに当たるか判定。
        3. **グループ化**: 【相手先(または規定名) + 文書種別】でグループを作る。
        4. **日付の標準化**: 抽出した日付（締結日、施行日、改訂日等）を YYYY-MM-DD 形式に変換。和暦（令和等）は必ず西暦に変換すること。
        5. **最新判定**: 各グループ内で日付の降順（新しい順）に並べ、一番新しいものだけを is_latest: true にし、残りを false にする。

        【出力要件】
        以下のJSON形式（リスト）で出力してください。入力された **全てのID** について必ず出力を含めること。
        {{
            "results": [
                {{
                    "id": "入力されたID",
                    "document_type": "文書種別(例: 売買契約書)",
                    "target_entity": "相手先会社名 または 規定名",
                    "identified_date": "YYYY-MM-DD",
                    "is_latest": true/false
                }}
            ]
        }}

        【解析対象データ】
        {json.dumps(masked_batch, ensure_ascii=False)}
        """

        # --- リトライ機能（判定漏れ防止） ---
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=DEPLOYMENT_NAME,
                    messages=[
                        {"role": "system", "content": "あなたはJSON出力マシンです。"},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                res_content = response.choices[0].message.content
                batch_results = json.loads(res_content).get("results", [])

                # 件数チェック
                if len(batch_results) < len(batch):
                    print(f"      ⚠️ 件数不足 (期待:{len(batch)}, 実際:{len(batch_results)}) - リトライします")
                    time.sleep(1)
                    continue
                
                # 成功したらID復元して追加
                for res in batch_results:
                    res["internal_id"] = id_map.get(res.get("id"))
                    all_ai_results.append(res)
                break # 成功したらリトライループを抜ける

            except Exception as e:
                print(f"      ❌ エラー ({attempt+1}/{max_retries}): {e}")
                time.sleep(2)
        else:
            print(f"   ❌ Batch {batch_num} は完全に失敗しました。スキップします。")


    # --- Pythonによる最終集計と正規化（ここが改善点） ---
    print(f"📊 集計と最終判定を開始します ({len(all_ai_results)}/{len(doc_data)}件)...")

    groups = {}
    for res in all_ai_results:
        if not res.get("internal_id"): continue

        # 1. 文書種別の正規化（「売買契約書」->「契約書」へ統合）
        raw_type = res.get("document_type") or "不明"
        norm_type = normalize_doc_type(raw_type)
        
        entity = res.get("target_entity") or "不明"
        
        # 2. グループ化キー: 正規化された種別_相手先
        # これにより、「東京メディカル」の「売買契約書」と「契約書」は同じグループになります
        key = f"{norm_type}_{entity}"
        
        if key not in groups:
            groups[key] = []
        groups[key].append(res)

    final_results = []
    for key, docs in groups.items():
        # 3. 日付順ソート（日付判定ミスをPythonで修正）
        docs.sort(key=lambda x: x.get("identified_date") or "1900-01-01", reverse=True)
        
        for idx, doc in enumerate(docs):
            # 先頭のみTrue
            doc["is_latest"] = (idx == 0)
            
            # フォルダ分け用に、グループ名（相手先）をセット
            doc["group_name"] = doc.get("target_entity")
            
            # 念のため正規化前の種別を保持しておく（ファイル移動の際のフォルダ名に使用するため）
            # もしフォルダ名も「契約書」に統一したい場合は norm_type を使ってください
            final_results.append(doc)

    with open(FINAL_JSON, "w", encoding="utf-8") as f:
        json.dump({"results": final_results}, f, ensure_ascii=False, indent=4)
        
    print(f"✅ 判定完了: {FINAL_JSON} を作成しました。")

if __name__ == "__main__":
    run_ai_judgment()