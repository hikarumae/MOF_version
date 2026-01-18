import os
import uuid
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

search_client = SearchClient(
    endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
    index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
    credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_API_KEY")),
)

def index_chunks(chunks: list[dict]):
    docs = []
    for c in chunks:
        docs.append({
            "id": str(uuid.uuid4()),
            "content": c["text"],
            "contentVector": c["embedding"],
            "documentName": c["documentName"],
            #"documentName": os.path.basename(c["document"]),
            "blobUrl": c["blobUrl"],
            "page": int(c["page"]),
            #"chunkIndex": c["page"]
            "chunkIndex": int(c["chunk_id"])
            #"chunkIndex": f'{c["page"]}-{c["chunk_id"]}'
        })

    search_client.upload_documents(docs)


def search_chunks(question: str, k: int):
    from app.embedding import get_embedding

    vector = get_embedding(question)

    results = search_client.search(
        search_text=None,
        vector_queries=[{
            "kind": "vector",
            "vector": vector,
            "k": k,
            "fields": "contentVector"
        }],
        select=[
            "content",
            "blobUrl",
            "documentName",
            "chunkIndex"
        ]
    )
    #return list(results)

    return [
        {
            "documentName": r.get("documentName"),
            "blobUrl": r.get("blobUrl"),
            "chunkIndex": r.get("chunkIndex"),
            "content": r.get("content"),
            "score": r["@search.score"]
        }
        for r in results
    ]

