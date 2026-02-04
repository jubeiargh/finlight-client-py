from datetime import datetime
from typing import Callable, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field
from dataclasses import dataclass


@dataclass
class ApiConfig:
    base_url: str = "https://api.finlight.me"
    timeout: int = 5000
    retry_count: int = 3
    api_key: str = ""
    wss_url: str = "wss://wss.finlight.me"


class GetArticlesParams(BaseModel):
    query: Optional[str] = Field(default=None, description="Search query")

    source: Optional[str] = Field(
        default=None, description="@deprecated => use sources\nsource of the articles"
    )

    sources: Optional[List[str]] = Field(
        default=None,
        description="Source of the articles, accepts multiple.\n"
        "If you select sources then 'includeAllSources' is not necessary",
    )

    excludeSources: Optional[List[str]] = Field(
        default=None, description="Exclude specific sources, accepts multiple.\n"
    )

    optInSources: Optional[List[str]] = Field(
        default=None, description="Optional list of non default article sources to include"
    )

    from_: Optional[str] = Field(
        default=None, alias="from", description="Start date in (YYYY-MM-DD) or ISO Date string"
    )

    to: Optional[str] = Field(
        default=None, description="End date in (YYYY-MM-DD) or ISO Date string"
    )

    language: Optional[str] = Field(default=None, description='Language, default is "en"')

    tickers: Optional[List[str]] = Field(
        default=None, description="List of tickers to search for"
    )
    includeEntities: bool = Field(
        default=False, description="Include tagged companies in the result"
    )
    excludeEmptyContent: bool = Field(
        default=False, description="Only return results that have content"
    )

    includeContent: bool = Field(
        default=False, description="Whether to return full article details"
    )

    orderBy: Optional[Literal["publishDate", "createdAt"]] = Field(
        default=None, description="Order by"
    )

    order: Optional[Literal["ASC", "DESC"]] = Field(default=None, description="Sort order")

    pageSize: Optional[int] = Field(
        default=None, ge=1, le=1000, description="Results per page (1-1000)"
    )

    page: Optional[int] = Field(default=None, ge=1, description="Page number")

    countries: Optional[List[str]] = Field(
        default=None, description="List of ISO 3166-1 alpha-2 country codes to filter articles"
    )

    model_config = ConfigDict(populate_by_name=True)


class GetArticlesWebSocketParams(BaseModel):
    query: Optional[str] = Field(default=None, description="Search query string")
    sources: Optional[List[str]] = Field(
        default=None, description="Optional list of article sources"
    )
    excludeSources: Optional[List[str]] = Field(
        default=None, description="Optional list of article sources to exclude"
    )
    optInSources: Optional[List[str]] = Field(
        default=None, description="Optional list of non default article sources to include"
    )
    language: Optional[str] = Field(
        default=None, description="Language filter, e.g., 'en', 'de'"
    )
    extended: bool = Field(default=False, description="Whether to return full article details")
    tickers: Optional[List[str]] = Field(
        default=None, description="List of tickers to search for"
    )
    includeEntities: bool = Field(
        default=False, description="Include tagged companies in the result"
    )
    excludeEmptyContent: bool = Field(
        default=False, description="Only return results that have content"
    )
    countries: Optional[List[str]] = Field(
        default=None, description="List of ISO 3166-1 alpha-2 country codes to filter articles"
    )


class GetRawArticlesWebSocketParams(BaseModel):
    query: Optional[str] = Field(default=None, description="Search query string")
    sources: Optional[List[str]] = Field(
        default=None, description="Optional list of article sources"
    )
    excludeSources: Optional[List[str]] = Field(
        default=None, description="Optional list of article sources to exclude"
    )
    optInSources: Optional[List[str]] = Field(
        default=None, description="Optional list of non default article sources to include"
    )
    language: Optional[str] = Field(
        default=None, description="Language filter, e.g., 'en', 'de'"
    )


class Listing(BaseModel):
    ticker: str
    exchangeCode: str
    exchangeCountry: str


class Company(BaseModel):
    companyId: int
    confidence: Optional[float] = None
    country: Optional[str] = None
    exchange: Optional[str] = None
    industry: Optional[str] = None
    sector: Optional[str] = None
    name: str
    ticker: str
    isin: Optional[str] = None
    openfigi: Optional[str] = None
    primaryListing: Optional[Listing] = None
    isins: Optional[List[str]] = None
    otherListings: Optional[List[Listing]] = None


class Article(BaseModel):
    link: str
    title: str
    publishDate: datetime
    source: str
    language: str
    sentiment: Optional[str] = None
    confidence: Optional[float] = None
    summary: Optional[str] = None
    images: Optional[List[str]] = None
    content: Optional[str] = None
    companies: Optional[List[Company]] = None
    createdAt: Optional[datetime] = None


class RawArticle(BaseModel):
    link: str
    title: str
    publishDate: datetime
    source: str
    language: str
    summary: Optional[str] = None
    images: Optional[List[str]] = None
    createdAt: Optional[datetime] = None


class ArticleResponse(BaseModel):
    status: str
    page: int
    pageSize: int
    articles: List[Article]


class Source(BaseModel):
    domain: str
    isContentAvailable: bool
    isDefaultSource: bool


@dataclass
class WebSocketOptions:
    ping_interval: int = 25
    pong_timeout: int = 60
    base_reconnect_delay: float = 0.5
    max_reconnect_delay: float = 10.0
    connection_lifetime: int = 115 * 60
    takeover: bool = False
    on_close: Optional[Callable[[int, str], None]] = None


@dataclass
class RawWebSocketOptions:
    ping_interval: int = 25
    pong_timeout: int = 60
    base_reconnect_delay: float = 0.5
    max_reconnect_delay: float = 10.0
    connection_lifetime: int = 115 * 60
    takeover: bool = False
    on_close: Optional[Callable[[int, str], None]] = None
