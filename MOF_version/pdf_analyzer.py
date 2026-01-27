#解析担当  モジュール

import fitz  # PyMuPDF
import base64

def extract_pdf_content(blob_data):
    """1ページ目冒頭2000文字 + 最終ページ末尾2000文字 + 1ページ目画像を抽出"""
    doc = fitz.open(stream=blob_data, filetype="pdf")
    page_count = doc.page_count
    
    text_head = ""
    text_tail = ""
    base64_image = None

    if page_count > 0:
        # 1ページ目の処理
        first_page = doc[0]
        text_head = first_page.get_text()[:2000]
        
        # 1ページ目を画像化 (OCRの代わり)
        pix = first_page.get_pixmap(matrix=fitz.Matrix(2, 2))
        base64_image = base64.b64encode(pix.tobytes("png")).decode("utf-8")

        # 最終ページの処理
        last_page = doc[page_count - 1]
        full_last_text = last_page.get_text()
        text_tail = full_last_text[-2000:] if len(full_last_text) > 2000 else full_last_text

    doc.close()
    return text_head, text_tail, base64_image