# pip install easyocr を事前に実行してください
# pip install pdf2image を事前に実行してください

import os
import json
import easyocr
import numpy as np
from pdf2image import convert_from_path

# PDFが格納されているディレクトリ
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test")

# AIに渡すための中間データのファイル名
OUTPUT_JSON = "intermediate_data.json"

def process_pdfs():
    # OCRエンジンを初期化。日本語('ja')と英語('en')を読み取り対象に設定
    reader = easyocr.Reader(['ja', 'en'])
    # 解析結果を一時的に溜めておくためのリスト
    extracted_data = []
    
    # デバッグ用: 処理対象のディレクトリを表示
    print(f"探索中のディレクトリ: {INPUT_DIR}")
    
    # 指定したフォルダが存在しない場合のエラーチェック
    if not os.path.exists(INPUT_DIR):
        print(f"エラー: ディレクトリ {INPUT_DIR} が見つかりません。")
        return
    
    # デバック用：フォルダ内の全ファイルをリストアップして表示
    all_files = os.listdir(INPUT_DIR)
    print(f"見つかったファイル数: {len(all_files)}")
    
    # フォルダ内のファイルを一つずつ取り出して処理
    for file_name in all_files:
        # PDFファイル以外（隠しファイルなど）は無視してスキップ
        if not file_name.lower().endswith('.pdf'):
            continue
        
        # ファイルのフルパスを作成
        path = os.path.join(INPUT_DIR, file_name)
        print(f"PDF解析中: {file_name}")
        
        
        
        #===== OCR処理 =====#
        try:
            # 判定に必要な冒頭（第1条等）と末尾（署名日等）を重点的に取得
            images = convert_from_path(path)
            # 最初と最後のページのみを結合（タイトルや第1条があるため）
            target_pages = [images[0]]
            # 2ページ以上ある場合は、最後（署名欄があるページ）も対象に追加
            if len(images) > 1:
                target_pages.append(images[-1])
            
            combined_text = ""
            for img in target_pages:
                # OCR実行
                img_array = np.array(img)
                # 読み取った単語をスペースで繋いで一つの文章にまとめる
                result = reader.readtext(img_array, detail=0)
                combined_text += " ".join(result) + " "

            #===== データの格納 =====#
            # AIが「中身」で判断できるように、抽出したテキストを保存
            extracted_data.append({
                # ファイル名はAIには教えず、後でどのファイルか特定するためのIDとして保持
                "internal_id": file_name,
                # 冒頭と末尾の主要情報をカバーする2000文字をAIに渡すデータにして格納
                "text_content": combined_text[:2000] 
            })
            
        except Exception as e:
            # OCRやPDF変換でエラーが起きても止まらないように、エラー内容を表示して次へ進みます
            print(f"ファイル {file_name} の処理中にエラーが発生しました: {e}")

    # 抽出したデータをJSONファイルに保存
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        # 日本語が化けないようにし、見やすいように字下げ（indent=4）を付けて保存
        json.dump(extracted_data, f, ensure_ascii=False, indent=4)
    print(f"完了: {OUTPUT_JSON} を作成しました。({len(extracted_data)}件のデータを格納)")

if __name__ == "__main__":
    process_pdfs()
    
#作成したJSONファイルの内容を確認
print("\n=== 抽出された中間データ ===")
with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
    print(f.read())