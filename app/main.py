#ローカル実行用
from dotenv import load_dotenv
load_dotenv()
###############

from fastapi import FastAPI, BackgroundTasks
from app.models import IndexRequest, SearchRequest
from app.blob import load_pdfs_from_blob
from app.chunk import chunk_pages
from app.embedding import get_embedding
from app.search import index_chunks, search_chunks


app = FastAPI(title="RAG API")

@app.get("/health")
def health():
    return {"status": "ok"}

def run_index(req: IndexRequest):
    pages = load_pdfs_from_blob(req.container, req.prefix)
    print("DEBUG pages[0]:", pages[0])
    print("DEBUG keys:", pages[0].keys())
    chunks = chunk_pages(pages)

    for c in chunks:
        c["embedding"] = get_embedding(c["text"])

    index_chunks(chunks)

@app.post("/index")
def index_api(req: IndexRequest, bg: BackgroundTasks):
    bg.add_task(run_index, req)
    return {"status": "accepted"}

@app.post("/search")
def search_api(req: SearchRequest):
    return search_chunks(req.question, req.k)
