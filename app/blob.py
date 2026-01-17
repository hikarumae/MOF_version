import os
from azure.storage.blob import BlobServiceClient
from pypdf import PdfReader
import io

blob_service = BlobServiceClient.from_connection_string(
    os.getenv("AZURE_STORAGE_CONNECTION_STRING")
)

def load_pdfs_from_blob(container_name: str, prefix: str | None):
    container = blob_service.get_container_client(container_name)
    pages = []

    for blob in container.list_blobs(name_starts_with=prefix):
        if not blob.name.lower().endswith(".pdf"):
            continue

        data = container.download_blob(blob.name).readall()
        reader = PdfReader(io.BytesIO(data))
        file_name = os.path.basename(blob.name) 

        for i, page in enumerate(reader.pages):
            pages.append({
            "documentName": file_name,
            "blobUrl": container.get_blob_client(blob.name).url,
            "page": i + 1,
            "text": page.extract_text()
            })
            """
            pages.append({
                "document": blob.name,
                "page": i + 1,
                "text": page.extract_text()
            })
"""
    return pages
