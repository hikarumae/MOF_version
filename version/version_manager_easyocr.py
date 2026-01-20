import os
import json
import easyocr
import numpy as np
from pdf2image import convert_from_path
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
import unicodedata


load_dotenv()

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
        # Blobから取得した名前をNFCに正規化
        file_name = unicodedata.normalize('NFC', blob.name)
        
        if not file_name.lower().endswith('.pdf'):
            continue
            
        print(f"解析開始: {file_name}")
        # local_path も正規化後の名前で作成
        local_path = os.path.join(TEMP_DIR, file_name) 
        
        # 3. リソースBから一時的にダウンロード
        # ※Azure上のファイルを探す時は、元の blob.name を使う必要がある
        blob_client = container_client.get_blob_client(blob.name) 
        with open(local_path, "wb") as file:
            file.write(blob_client.download_blob().readall())

        # 4. OCR処理
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
            
            # 抽出したデータの格納
            extracted_data.append({
                # ここを正規化後の file_name にすることで、Step 3 の仕分けプログラムと一致させます
                "internal_id": file_name, 
                "text_head": combined_text[:2000],  # 最初の1000文字
                "text_tail": combined_text[-2000:] # 最後の1000文字 
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