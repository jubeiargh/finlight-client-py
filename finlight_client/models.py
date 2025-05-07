from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, AnyHttpUrl
from typing import List, Optional, Literal
from dataclasses import dataclass


@dataclass
class ApiConfig:
    base_url: AnyHttpUrl = "https://api.finlight.me"
    timeout: int = 5000
    retry_count: int = 3
    api_key: str = ""
    wss_url: AnyHttpUrl = "wss://wss.finlight.me"


class GetArticlesParams(BaseModel):
    query: str = Field(..., description="Search query")

    source: Optional[str] = Field(
        None, description="@deprecated => use sources\nsource of the articles"
    )

    sources: Optional[List[str]] = Field(
        None,
        description="Source of the articles, accepts multiple.\n"
        "If you select sources then 'includeAllSources' is not necessary",
    )

    excludeSources: Optional[List[str]] = Field(
        None, description="Exclude specific sources, accepts multiple.\n"
    )

    from_: Optional[str] = Field(
        None, alias="from", description="Start date in (YYYY-MM-DD) or ISO Date string"
    )

    to: Optional[str] = Field(
        None, description="End date in (YYYY-MM-DD) or ISO Date string"
    )

    language: Optional[str] = Field(None, description='Language, default is "en"')

    order: Optional[Literal["ASC", "DESC"]] = Field(None, description="Sort order")

    pageSize: Optional[int] = Field(
        None, ge=1, le=1000, description="Results per page (1-1000)"
    )

    page: Optional[int] = Field(None, ge=1, description="Page number")

    class Config:
        populate_by_name = True


class GetArticlesWebSocketParams(BaseModel):
    query: Optional[str] = Field(None, description="Search query string")
    sources: Optional[List[str]] = Field(
        None, description="Optional list of article sources"
    )
    excludeSources: Optional[List[str]] = Field(
        None, description="Optional list of article sources to exclude"
    )
    language: Optional[str] = Field(
        None, description="Language filter, e.g., 'en', 'de'"
    )
    extended: bool = Field(False, description="Whether to return full article details")


class BasicArticle(BaseModel):
    link: str
    title: str
    publishDate: datetime
    source: str
    language: str
    sentiment: Optional[str] = None
    confidence: Optional[float] = None
    summary: Optional[str] = None


class Article(BasicArticle):
    content: Optional[str] = None


class BasicArticleResponse(BaseModel):
    status: str
    page: int
    pageSize: int
    articles: List[BasicArticle]


class ArticleResponse(BaseModel):
    status: str
    page: int
    pageSize: int
    articles: List[Article]
