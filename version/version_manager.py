# 
#

import os
import json
import time
import shutil
import numpy as np
import easyocr
from pdf2image import convert_from_path
from pdfminer.high_level import extract_text
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

# === 設定 ===
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
SOURCE_CONTAINER = "mof2-blob-new"  # 読み取り元のコンテナ名
OUTPUT_JSON = "intermediate_data.json"
TEMP_DIR = "temp_pdfs"

def download_blobs():
    """BlobストレージからPDFファイルを一時フォルダにダウンロードする"""
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)

    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(SOURCE_CONTAINER)

    downloaded_files = []
    print(f"📥 Blobコンテナ '{SOURCE_CONTAINER}' からファイルをダウンロード中...")

    blob_list = container_client.list_blobs()
    for blob in blob_list:
        if blob.name.lower().endswith(".pdf"):
            local_path = os.path.join(TEMP_DIR, blob.name)
            # フォルダ階層がある場合はディレクトリを作成
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            with open(local_path, "wb") as f:
                data = container_client.download_blob(blob.name).readall()
                f.write(data)
            downloaded_files.append(local_path)
    
    print(f"   -> {len(downloaded_files)} 件のPDFをダウンロードしました。")
    return downloaded_files

def extract_text_hybrid(file_path, reader):
    """
    ハイブリッド抽出ロジック:
    1. pdfminer でテキストレイヤーの抽出を試みる (高速・高精度)
    2. 抽出できた文字数が少なければ、画像化して EasyOCR をかける (低速・最終手段)
    """
    full_text = ""
    method_used = ""

    # --- Step 1: テキストレイヤーからの抽出 (pdfminer) ---
    try:
        raw_text = extract_text(file_path)
        # 空白除去して50文字以上あれば「読み取り成功」とみなす
        if raw_text and len(raw_text.strip()) > 50:
            full_text = raw_text
            method_used = "TextLayer (pdfminer)"
    except Exception as e:
        print(f"      [Info] テキスト抽出スキップ: {e}")

    # --- Step 2: 失敗時のみ OCR 実行 (EasyOCR) ---
    if not full_text:
        method_used = "OCR (EasyOCR)"
        try:
            # 全ページやると遅すぎるため、最初と最後のページのみ対象にする等の工夫も可能
            # ここでは精度重視で全ページ処理するが、必要に応じて調整してください
            images = convert_from_path(file_path)
            
            ocr_text_parts = []
            # 処理時間の短縮：最大5ページまでとする場合
            # target_images = images[:5] 
            target_images = images 

            for img in target_images:
                img_array = np.array(img)
                # detail=0 でテキストのみリストで返る
                result = reader.readtext(img_array, detail=0) 
                ocr_text_parts.append(" ".join(result))
            
            full_text = "\n".join(ocr_text_parts)
        except Exception as e:
            print(f"      ❌ OCRエラー: {e}")
            full_text = ""

    return full_text, method_used

def process_pdfs_from_blob():
    """メイン処理: ダウンロード -> ハイブリッド抽出 -> JSON保存"""
    
    # 1. ファイル準備
    pdf_files = download_blobs()
    if not pdf_files:
        print("⚠️ 処理対象のPDFが見つかりませんでした。")
        return

    # 2. EasyOCRの初期化 (GPUがあれば自動で使用)
    print("⚙️ OCRエンジン (EasyOCR) を初期化中...")
    # 対応言語: 日本語(ja)と英語(en)
    reader = easyocr.Reader(['ja', 'en']) 

    extracted_data = []
    print(f"🚀 {len(pdf_files)} 件のファイルの解析を開始します (ハイブリッドモード)...")

    for i, file_path in enumerate(pdf_files):
        file_name = os.path.basename(file_path)
        print(f"   [{i+1}/{len(pdf_files)}] Processing: {file_name} ...", end="", flush=True)
        
        start_t = time.time()
        text, method = extract_text_hybrid(file_path, reader)
        elapsed = time.time() - start_t
        
        print(f" 完了 ({elapsed:.2f}s) via {method}")

        # 前後2000文字を抽出（AIへ渡す用）
        text_head = text[:2000] if text else ""
        text_tail = text[-2000:] if text else ""

        extracted_data.append({
            "internal_id": file_name,
            "text_head": text_head,
            "text_tail": text_tail
        })

    # 3. JSON保存
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=4)

    print(f"✅ 解析完了: {OUTPUT_JSON} を作成しました。")
    
    # 4. 一時ファイル削除
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
        print("🗑️ 一時ファイルを削除しました。")

if __name__ == "__main__":
    process_pdfs_from_blob()