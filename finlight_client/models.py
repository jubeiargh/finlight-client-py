from typing import List, Optional
from pydantic import BaseModel


class BasicArticle(BaseModel):
    link: str
    title: str
    publish_date: str
    authors: str
    source: str
    language: str
    sentiment: Optional[str] = None
    confidence: Optional[float] = None


class Article(BasicArticle):
    content: str
    summary: Optional[str] = None


class ApiResponse(BaseModel):
    status: str
    total_results: int
    page: int
    page_size: int
    articles: List[BasicArticle]
