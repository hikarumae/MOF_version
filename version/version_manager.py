import os
import json
import easyocr
import numpy as np
from pdf2image import convert_from_path
from azure.storage.blob import BlobServiceClient

# === 設定 ===
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
SOURCE_CONTAINER = "mof2-blob-new"
TEMP_DIR = "temp_pdf" # 一時保存用フォルダ
OUTPUT_JSON = "intermediate_data.json"

def process_pdfs_from_blob():
    # 1. 準備
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
    
    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(SOURCE_CONTAINER)
    reader = easyocr.Reader(['ja', 'en'])
    extracted_data = []

    # 2. mof2-blob-new コンテナ内のファイル一覧を取得
    print(f"'{SOURCE_CONTAINER}' 内のファイルをチェック中...")
    blob_list = container_client.list_blobs()
    
    for blob in blob_list:
        if not blob.name.lower().endswith('.pdf'):
            continue
            
        print(f"解析開始: {blob.name}")
        local_path = os.path.join(TEMP_DIR, blob.name)
        
        # 3. リソースBから一時的にダウンロード
        blob_client = container_client.get_blob_client(blob.name)
        with open(local_path, "wb") as file:
            file.write(blob_client.download_blob().readall())

        # 4. OCR処理 (以前のロジックと同じ)
        try:
            images = convert_from_path(local_path)
            target_pages = [images[0]]
            if len(images) > 1:
                target_pages.append(images[-1])
            
            combined_text = ""
            for img in target_pages:
                img_array = np.array(img)
                result = reader.readtext(img_array, detail=0)
                combined_text += " ".join(result) + " "

            extracted_data.append({
                "internal_id": blob.name,
                "text_content": combined_text[:2000] 
            })
            
            # 5. 使い終わった一時ファイルを削除
            os.remove(local_path)
            
        except Exception as e:
            print(f"エラー ({blob.name}): {e}")

    # 6. 中間データを保存
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=4)
    print(f"完了: {OUTPUT_JSON} を作成しました。({len(extracted_data)}件)")

if __name__ == "__main__":
    process_pdfs_from_blob()