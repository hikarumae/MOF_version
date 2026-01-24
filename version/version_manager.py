# バージョンを管理するためのPDFテキスト抽出ロジック

import os
import json
import time
import shutil
#import numpy as np
#import easyocr
#from pdf2image import convert_from_path
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
        try:
            shutil.rmtree(TEMP_DIR)
        except Exception:
            pass # 事前掃除で失敗しても気にせず進む
    os.makedirs(TEMP_DIR, exist_ok=True)

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
    OCRを使わず、テキストレイヤーのみを抽出する制限モード
    """
    full_text = ""
    method_used = "TextLayer (pdfminer)"

    try:
        raw_text = extract_text(file_path)
        if raw_text:
            full_text = raw_text
    except Exception as e:
        print(f"      ❌ テキスト抽出エラー: {e}")
        full_text = ""

    return full_text, method_used
    

def process_pdfs_from_blob():
    """メイン処理: ダウンロード -> ハイブリッド抽出 -> JSON保存"""
    
    # 1. ファイル準備
    pdf_files = download_blobs()
    if not pdf_files:
        print("⚠️ 処理対象のPDFが見つかりませんでした。")
        return

    # 2. OCR初期化をスキップ (Web App 標準環境用)
    print("⚙️ OCRエンジンをスキップして続行します...")
    reader = None  # 中身を空にする

    extracted_data = []
    print(f"🚀 {len(pdf_files)} 件のファイルの解析を開始します (ハイブリッドモード)...")

    for i, file_path in enumerate(pdf_files):
        file_name = os.path.basename(file_path)
        print(f"   [{i+1}/{len(pdf_files)}] Processing: {file_name} ...", end="", flush=True)
        
        start_t = time.time()
        text, method = extract_text_hybrid(file_path, reader)
        elapsed = time.time() - start_t
        
        print(f" 完了 ({elapsed:.2f}s) via {method}")

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
    
    # 4. 一時ファイル削除 (Mac/Win両対応・安全版)
    if os.path.exists(TEMP_DIR):
        try:
            time.sleep(1) # ロック解放待ち
            shutil.rmtree(TEMP_DIR)
            print("🗑️ 一時ファイルを削除しました。")
        except Exception as e:
            # 削除に失敗してもメイン処理には影響ないので続行
            print(f"⚠️ 一時フォルダの削除に失敗しましたが、処理を続行します: {e}")

if __name__ == "__main__":
    process_pdfs_from_blob()