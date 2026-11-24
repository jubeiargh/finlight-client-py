"""``client.companies``: search, get_many, get (needs ``entityAccess``).

Every call costs 1 credit (same monthly quota and burst limit as articles;
``get_many`` costs 1 per call, not per company). A 304 answer to an ETag
revalidation and errors cost 1 credit too.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Sequence
from typing import Any, Optional, overload

from ._http import HttpTransport
from ._params import company_ids
from .errors import FinlightDecodeError, FinlightValidationError
from .models import CacheInfo, CompanyRecord, cache_info, decode_company_record, decode_list

__all__ = ["CompaniesService", "CompanyList"]


class CompanyList(list):  # type: ignore[type-arg]
    """A list of :class:`CompanyRecord`. ``skipped`` holds entries that could not be read."""

    def __init__(self, items: Sequence[CompanyRecord], skipped: list[Any]) -> None:
        super().__init__(items)
        self.skipped = skipped


class _EtagCache:
    def __init__(self, size: int) -> None:
        self._size = size
        self._items: OrderedDict[int, CompanyRecord] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: int) -> Optional[CompanyRecord]:
        if self._size <= 0:
            return None
        with self._lock:
            item = self._items.get(key)
            if item is not None:
                self._items.move_to_end(key)
            return item

    def put(self, key: int, record: CompanyRecord) -> None:
        if self._size <= 0:
            return
        with self._lock:
            self._items[key] = record
            self._items.move_to_end(key)
            while len(self._items) > self._size:
                self._items.popitem(last=False)


class CompaniesService:
    def __init__(self, http: HttpTransport, cache_size: int = 256) -> None:
        self._http = http
        self._cache = _EtagCache(cache_size)

    def search(self, q: str, *, mic: Optional[str] = None) -> CompanyList:
        """Resolve a ticker, name, ISIN or vendor notation (at most 10 results, no pages).

        Costs 1 credit per call, errors included.
        """
        if not isinstance(q, str):
            raise FinlightValidationError("q must be a string", param="q")
        if len(q) > 200:
            raise FinlightValidationError("q takes at most 200 characters", param="q")
        query = [("q", q)]
        if mic is not None:
            if not isinstance(mic, str):
                raise FinlightValidationError("mic must be a string", param="mic")
            if len(mic) > 32:
                raise FinlightValidationError("mic takes at most 32 characters", param="mic")
            query.append(("mic", mic))
        resp = self._http.call("GET", "/v3/companies", query=query)
        return _company_list(resp.json())

    def get_many(self, ids: Sequence[int]) -> CompanyList:
        """Resolve 1 to 10 company ids. Unknown ids are left out; order is not guaranteed.

        Costs 1 credit per call, however many ids, errors included.
        """
        checked = company_ids(ids)
        resp = self._http.call("GET", "/v3/companies", query=[("ids", ",".join(str(i) for i in checked))])
        return _company_list(resp.json())

    @overload
    def get(self, company_id: int) -> CompanyRecord: ...

    @overload
    def get(self, company_id: int, *, if_none_match: str) -> Optional[CompanyRecord]: ...

    def get(self, company_id: int, *, if_none_match: Optional[str] = None) -> Optional[CompanyRecord]:
        """``GET /v3/companies/{companyId}``. A miss raises ``NotFoundError``.

        Without ``if_none_match`` the client keeps the last records (``company_cache_size``,
        default 256, 0 turns it off) and revalidates them with their ``ETag``; a 304 answer
        returns the kept record. With ``if_none_match`` you manage the cache: a 304 answer
        returns ``None`` ("not modified"). ``cache_info(record)`` gives the ETag and
        Cache-Control of a record.

        Every call costs 1 credit: a 200, a 304 answer (revalidation) and errors alike.
        """
        if isinstance(company_id, bool) or not isinstance(company_id, int):
            raise FinlightValidationError("company_id must be an integer", param="company_id")
        cached = None
        headers = {}
        if if_none_match is not None:
            if not isinstance(if_none_match, str):
                raise FinlightValidationError("if_none_match must be a string", param="if_none_match")
            headers["If-None-Match"] = if_none_match
        else:
            cached = self._cache.get(company_id)
            info = cache_info(cached) if cached is not None else None
            if info is not None and info.etag:
                headers["If-None-Match"] = info.etag
        resp = self._http.call(
            "GET", f"/v3/companies/{company_id}", headers=headers, ok_statuses=(200, 304)
        )
        if resp.status == 304:
            if cached is None:
                return None
            old = cache_info(cached)
            cached._cache_info = CacheInfo(
                etag=resp.headers.get("etag") or (old.etag if old else None),
                cache_control=resp.headers.get("cache-control") or (old.cache_control if old else None),
                not_modified=True,
            )
            return cached
        body = resp.json()
        if not isinstance(body, dict) or "company" not in body:
            raise FinlightDecodeError("response has no 'company' object", raw=body)
        record = decode_company_record(body["company"])
        record._cache_info = CacheInfo(
            etag=resp.headers.get("etag"), cache_control=resp.headers.get("cache-control"), not_modified=False
        )
        if record._cache_info.etag:
            self._cache.put(company_id, record)
        return record


def _company_list(body: Any) -> CompanyList:
    if not isinstance(body, dict):
        raise FinlightDecodeError("companies response is not a JSON object", raw=body)
    items, skipped = decode_list(body.get("companies"), CompanyRecord, "company")
    return CompanyList(items, skipped)
