from pydantic import BaseModel
from typing import Optional

class IndexRequest(BaseModel):
    container: str
    prefix: str = None

class SearchRequest(BaseModel):
    question: str
    k: int = 5
