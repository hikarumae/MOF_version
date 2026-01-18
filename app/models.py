from pydantic import BaseModel

class IndexRequest(BaseModel):
    container: str
    prefix: str | None = None

class SearchRequest(BaseModel):
    question: str
    k: int = 5
