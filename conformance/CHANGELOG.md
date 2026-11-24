# Contract kit changelog

## 3.0.0-rc.6 (2026-11-25)

- Clients keep no cache of company records. The config option for its size (`companyCacheSize` and its
  per-language names) is gone, and a 304 is never answered with a stored record.
- `companies.get` sends `If-None-Match` only with the caller's `ifNoneMatch`; a 304 returns "not modified"
  (the language null). `cacheInfo(record)` still exposes `ETag` and `Cache-Control`, so callers can cache
  the records themselves.
- R-08: without a caller `ifNoneMatch` no `If-None-Match` header is sent.
- R-09: the clause "when the SDK revalidates its own cached copy it returns that record" is removed.
- contract.md 2.6: states that clients do not cache and that a 304 also costs 1 credit.

## 3.0.0-rc.5 (2026-11-24)

- Every lookup request (`/v3/companies`, `/v3/companies/{companyId}`, `/v3/sources`) costs 1 credit,
  a 304 and error answers included.
