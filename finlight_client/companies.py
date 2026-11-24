"""``client.companies``: search, get_many, get (needs ``entityAccess``).

Every call costs 1 credit (same monthly quota and burst limit as articles;
``get_many`` costs 1 per call, not per company). A 304 answer to an ETag
revalidation and errors cost 1 credit too. The SDK keeps no cache of company
records; see :meth:`CompaniesService.get`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Optional, overload

from ._http import HttpTransport
from ._params import company_ids
from .errors import FinlightDecodeError, FinlightValidationError
from .models import CacheInfo, CompanyRecord, decode_company_record, decode_list

__all__ = ["CompaniesService", "CompanyList"]


class CompanyList(list):  # type: ignore[type-arg]
    """A list of :class:`CompanyRecord`. ``skipped`` holds entries that could not be read."""

    def __init__(self, items: Sequence[CompanyRecord], skipped: list[Any]) -> None:
        super().__init__(items)
        self.skipped = skipped


class CompaniesService:
    def __init__(self, http: HttpTransport) -> None:
        self._http = http

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

        The SDK keeps no cache of company records: every call goes to the server and
        costs 1 credit, a 200, a 304 answer and errors alike. To save credits, keep the
        records yourself and do not call again within the ``max-age`` of their
        Cache-Control. ``cache_info(record)`` gives the ETag and Cache-Control of a record.
        Pass that ETag back as ``if_none_match`` to revalidate: the SDK sends it as
        ``If-None-Match`` and a 304 answer returns ``None`` ("not modified"). That saves
        the download, not the credit. Without ``if_none_match`` no ``If-None-Match`` is sent.
        """
        if isinstance(company_id, bool) or not isinstance(company_id, int):
            raise FinlightValidationError("company_id must be an integer", param="company_id")
        headers = {}
        if if_none_match is not None:
            if not isinstance(if_none_match, str):
                raise FinlightValidationError("if_none_match must be a string", param="if_none_match")
            headers["If-None-Match"] = if_none_match
        resp = self._http.call(
            "GET", f"/v3/companies/{company_id}", headers=headers, ok_statuses=(200, 304)
        )
        if resp.status == 304:
            return None
        body = resp.json()
        if not isinstance(body, dict) or "company" not in body:
            raise FinlightDecodeError("response has no 'company' object", raw=body)
        record = decode_company_record(body["company"])
        record._cache_info = CacheInfo(etag=resp.headers.get("etag"), cache_control=resp.headers.get("cache-control"))
        return record


def _company_list(body: Any) -> CompanyList:
    if not isinstance(body, dict):
        raise FinlightDecodeError("companies response is not a JSON object", raw=body)
    items, skipped = decode_list(body.get("companies"), CompanyRecord, "company")
    return CompanyList(items, skipped)
