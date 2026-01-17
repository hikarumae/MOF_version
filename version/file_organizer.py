import os
import json
import shutil

# スクリプトがある場所（app/version）を取得
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 2つ上の階層（プロジェクトルート）を取得
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# パスの設定を修正
FINAL_JSON = os.path.join(CURRENT_DIR, "final_judgment.json")
INPUT_DIR = os.path.join(BASE_DIR, "test")
LATEST_DIR = os.path.join(CURRENT_DIR, "latest_docs")
ARCHIVE_DIR = os.path.join(CURRENT_DIR, "archive")

def organize_files():
    print(f"探索中のPDFディレクトリ: {os.path.abspath(INPUT_DIR)}")
    
    if not os.path.exists(FINAL_JSON):
        print(f"エラー: {FINAL_JSON} が見つかりません。先にAI解析を実行してください。")
        return

    if not os.path.exists(INPUT_DIR):
        print(f"エラー: PDFが入っている {INPUT_DIR} フォルダが見つかりません。パスを確認してください。")
        return

    with open(FINAL_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    os.makedirs(LATEST_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    results = data.get("results", [])
    print(f"{len(results)}件の判定データに基づいて処理を開始します...")

    for item in results:
        file_name = item.get("internal_id")
        is_latest = item.get("is_latest")
        
        src_path = os.path.join(INPUT_DIR, file_name)
        
        if not os.path.exists(src_path):
            print(f"スキップ: {file_name} が見つかりません（検索先: {src_path}）")
            continue

        if is_latest:
            dest_path = os.path.join(LATEST_DIR, file_name)
            shutil.copy2(src_path, dest_path)
            print(f"【最新】をコピー: {file_name}")
        else:
            dest_path = os.path.join(ARCHIVE_DIR, file_name)
            # archiveフォルダへ移動
            shutil.move(src_path, dest_path)
            print(f"【旧版】をアーカイブへ移動: {file_name}")

    print("\nすべての仕分けが完了しました！")

if __name__ == "__main__":
    organize_files()