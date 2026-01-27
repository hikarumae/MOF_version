import re

def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def chunk_text(text: str, size=500, overlap=100):
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks

def chunk_pages(pages: list[dict]):
    chunks = []
    for p in pages:
        required = {"documentName", "blobUrl", "page", "text"}
        missing = required - p.keys()
        if missing:
            raise ValueError(f"Invalid page structure: missing {missing}")
        text = normalize_text(p["text"])
        for i, c in enumerate(chunk_text(text)):
            chunks.append({
            # "document": p["document"],
                "document": p["documentName"],
                "documentName": p["documentName"],  # 検索表示用
                "blobUrl": p["blobUrl"],
                #"page": p["page"],
                "page": int(p["page"]), 
                "chunk_id": i,
                "text": c
            })
    return chunks
