# Conformance case map

Every case of the finlight API v3 contract kit (`conformance/conformance.md`) and the pytest test that runs it.
`tests/conformance/test_case_map.py` fails when a kit case is missing here or a mapped test does not exist.
Re-sync the kit with `python scripts/sync_conformance.py --from <kit dir>`.

| Case | Title | Test |
|---|---|---|
| V-01 | Known constants equal vocab.json | `tests/conformance/test_vocab.py::test_vocab[V-01]` |
| D-01 | Full article: every include, every entitlement | `tests/conformance/test_decode.py::test_decode[D-01]` |
| D-02 | Raw skeleton (raw channel ignores include and entitlements) | `tests/conformance/test_decode.py::test_decode[D-02]` |
| D-03 | No include, every entitlement | `tests/conformance/test_decode.py::test_decode[D-03]` |
| D-04 | Every include requested, no entitlement | `tests/conformance/test_decode.py::test_decode[D-04]` |
| D-05 | events requested and entitled, companies not requested | `tests/conformance/test_decode.py::test_decode[D-05]` |
| D-06 | events and companies requested, entityAccess missing | `tests/conformance/test_decode.py::test_decode[D-06]` |
| D-07 | Legacy values delivered as they are | `tests/conformance/test_decode.py::test_decode[D-07]` |
| D-08 | Non-ASCII text | `tests/conformance/test_decode.py::test_decode[D-08]` |
| D-09 | Sentiment with a null label, event with null direction/importance/confidence, companies [] | `tests/conformance/test_decode.py::test_decode[D-09]` |
| D-10 | Decode matrix (include x entitlements x enriched/raw) | `tests/conformance/test_decode.py::test_decode_matrix[D-10.*]` |
| D-11 | Blank summary and content arrive as null | `tests/conformance/test_decode.py::test_decode[D-11]` |
| F-01 | Unknown fields at every level of the article | `tests/conformance/test_forward_compat.py::test_unknown_fields[F-01]` |
| F-02 | Unknown values in every open response enum | `tests/conformance/test_forward_compat.py::test_unknown_enum_values[F-02]` |
| F-03 | New keys on REST, webhook and WebSocket envelopes | `tests/conformance/test_forward_compat.py::test_envelope_keys[F-03]` |
| F-04 | Unknown webhook event name, unknown problem code, unknown 429 limitType | `tests/conformance/test_forward_compat.py::test_unknown_events_and_codes[F-04]` |
| R-01 | articles.search with one parameter sends exactly that parameter | `tests/conformance/test_requests.py::test_request[R-01]` |
| R-02 | articles.search with every parameter | `tests/conformance/test_requests.py::test_request[R-02]` |
| R-03 | articles.search without parameters | `tests/conformance/test_requests.py::test_request[R-03]` |
| R-04 | articles.get with include, comma-joined | `tests/conformance/test_requests.py::test_request[R-04]` |
| R-05 | articles.getByLink URL-encodes the link | `tests/conformance/test_requests.py::test_request[R-05]` |
| R-06 | companies.search with q and mic | `tests/conformance/test_requests.py::test_request[R-06]` |
| R-07 | companies.getMany joins ids with commas | `tests/conformance/test_requests.py::test_request[R-07]` |
| R-08 | companies.get returns ETag and Cache-Control | `tests/conformance/test_requests.py::test_request[R-08]` |
| R-09 | companies.get with If-None-Match answers 304 | `tests/conformance/test_requests.py::test_request[R-09]` |
| R-10 | sources.list with fullArticleAccess | `tests/conformance/test_requests.py::test_request[R-10]` |
| R-11 | sources.list without fullArticleAccess | `tests/conformance/test_requests.py::test_request[R-11]` |
| R-12 | An unknown request key is dropped silently by the server | `tests/conformance/test_requests.py::test_request[R-12]` |
| R-13 | WebSocket subscribe frame, enriched | `tests/conformance/test_ws_sessions.py::test_subscribe_enriched[R-13]` |
| R-14 | WebSocket subscribe frame, raw | `tests/conformance/test_ws_sessions.py::test_subscribe_raw[R-14]` |
| P-01 | Three-page cursor walk | `tests/conformance/test_pagination.py::test_three_pages[P-01]` |
| P-02 | limit and include may change between pages | `tests/conformance/test_pagination.py::test_page_rules[P-02]` |
| P-03 | Adding "to" on page 2 breaks the cursor | `tests/conformance/test_pagination.py::test_page_rules[P-03]` |
| P-04 | Adding the default languages ["en"] on page 2 breaks the cursor | `tests/conformance/test_pagination.py::test_page_rules[P-04]` |
| P-05 | Changing order on page 2 | `tests/conformance/test_pagination.py::test_page_rules[P-05]` |
| P-06 | Reordering list values keeps the cursor valid | `tests/conformance/test_pagination.py::test_page_rules[P-06]` |
| E-01 | Unknown enum value | `tests/conformance/test_errors.py::test_error[E-01]` |
| E-02 | Several invalid fields at once | `tests/conformance/test_errors.py::test_error[E-02]` |
| E-03 | Unknown field in the query language | `tests/conformance/test_errors.py::test_error[E-03]` |
| E-04 | Empty languages array | `tests/conformance/test_errors.py::test_error[E-04]` |
| E-05 | Unknown include value on a GET lookup | `tests/conformance/test_errors.py::test_error[E-05]` |
| E-06 | companies.search without q and ids | `tests/conformance/test_errors.py::test_error[E-06]` |
| E-07 | companies.search with q and ids | `tests/conformance/test_errors.py::test_error[E-07]` |
| E-08 | Non-integer company id in ids | `tests/conformance/test_errors.py::test_error[E-08]` |
| E-09 | Non-integer companyId in the path | `tests/conformance/test_errors.py::test_error[E-09]` |
| E-10 | Cursor that is not a cursor | `tests/conformance/test_errors.py::test_error[E-10]` |
| E-11 | Cursor of an unsupported version | `tests/conformance/test_errors.py::test_error[E-11]` |
| E-12 | No API key | `tests/conformance/test_errors.py::test_error[E-12]` |
| E-13 | Unknown API key | `tests/conformance/test_errors.py::test_error[E-13]` |
| E-14 | Company lookup without entityAccess | `tests/conformance/test_errors.py::test_error[E-14]` |
| E-15 | Unknown article id | `tests/conformance/test_errors.py::test_error[E-15]` |
| E-16 | Unknown article link | `tests/conformance/test_errors.py::test_error[E-16]` |
| E-17 | Unknown company id | `tests/conformance/test_errors.py::test_error[E-17]` |
| E-18 | Monthly token limit reached | `tests/conformance/test_errors.py::test_error[E-18]` |
| E-19 | Burst limit reached | `tests/conformance/test_errors.py::test_error[E-19]` |
| E-20 | Server failure | `tests/conformance/test_errors.py::test_error[E-20]` |
| E-21 | Malformed JSON body (NestJS fallback form) | `tests/conformance/test_errors.py::test_error[E-21]` |
| E-22 | Unknown route under /v3 (NestJS fallback form) | `tests/conformance/test_errors.py::test_error[E-22]` |
| E-23 | No X-Request-Id sent: the server generates one | `tests/conformance/test_errors.py::test_error[E-23]` |
| E-24 | Non-JSON error body | `tests/conformance/test_errors.py::test_error[E-24]` |
| E-25 | Cursor issued for another sort order | `tests/conformance/test_errors.py::test_error[E-25]` |
| W-01 | article.created, enriched, every include, non-ASCII body | `tests/conformance/test_webhooks.py::test_webhook[W-01]` |
| W-02 | article.updated with changedFields | `tests/conformance/test_webhooks.py::test_webhook[W-02]` |
| W-03 | article.updated for a plan without fullArticleAccess | `tests/conformance/test_webhooks.py::test_webhook[W-03]` |
| W-04 | article.created on a raw webhook | `tests/conformance/test_webhooks.py::test_webhook[W-04]` |
| W-05 | Dashboard test webhook (evt_test…) | `tests/conformance/test_webhooks.py::test_webhook[W-05]` |
| W-06 | v2 body is reported as wrong payload version | `tests/conformance/test_webhooks.py::test_webhook[W-06]` |
| W-07 | Body changed after signing | `tests/conformance/test_webhooks.py::test_webhook[W-07]` |
| W-08 | Timestamp older than the tolerance | `tests/conformance/test_webhooks.py::test_webhook[W-08]` |
| W-09 | Timestamp further in the future than the tolerance | `tests/conformance/test_webhooks.py::test_webhook[W-09]` |
| W-10 | Timestamp header is not ISO 8601 | `tests/conformance/test_webhooks.py::test_webhook[W-10]` |
| W-11 | Timestamp in unix seconds instead of ISO 8601 | `tests/conformance/test_webhooks.py::test_webhook[W-11]` |
| W-12 | No X-Webhook-Timestamp header | `tests/conformance/test_webhooks.py::test_webhook[W-12]` |
| W-13 | No X-Webhook-Signature header | `tests/conformance/test_webhooks.py::test_webhook[W-13]` |
| W-14 | Signature without the sha256= prefix | `tests/conformance/test_webhooks.py::test_webhook[W-14]` |
| W-15 | Signature computed with the hex-decoded secret | `tests/conformance/test_webhooks.py::test_webhook[W-15]` |
| W-16 | Case-insensitive header lookup | `tests/conformance/test_webhooks.py::test_webhook[W-16]` |
| S-01 | Ping before subscribe gets a v2 pong; after the v3 subscribe pongs are v3 | `tests/conformance/test_ws_sessions.py::test_session[S-01]` |
| S-02 | Lowercase x-api-key on the wire | `tests/conformance/test_ws_raw_bytes.py::test_lowercase_api_key_on_the_wire[S-02]` |
| S-03 | connection.admitted echoes the nonce; a re-subscribe re-admits only with the same nonce | `tests/conformance/test_ws_sessions.py::test_session[S-03]` |
| S-04 | article.created then article.updated for the same id, then an exact duplicate | `tests/conformance/test_ws_sessions.py::test_session[S-04]` |
| S-05 | An unknown event name arrives | `tests/conformance/test_ws_sessions.py::test_session[S-05]` |
| S-06 | connection.error PING_ON_DEFAULT_ROUTE | `tests/conformance/test_ws_sessions.py::test_session[S-06]` |
| S-07 | VALIDATION_FAILED for a v2 key in a v3 subscribe | `tests/conformance/test_ws_sessions.py::test_session[S-07]` |
| S-08 | VALIDATION_FAILED for include on raw | `tests/conformance/test_ws_sessions.py::test_session[S-08]` |
| S-09 | connection.preempted, reason connection_limit (another connection took over) | `tests/conformance/test_ws_sessions.py::test_session[S-09]` |
| S-10 | connection.preempted, reason quota_exceeded | `tests/conformance/test_ws_sessions.py::test_session[S-10]` |
| S-11 | Preempted before the first subscribe: the frame comes in v2 form | `tests/conformance/test_ws_sessions.py::test_session[S-11]` |
| S-12 | Error for an unreadable message comes in v2 form | `tests/conformance/test_ws_sessions.py::test_session[S-12]` |
| S-13 | connection.error HANDSHAKE_FAILED | `tests/conformance/test_ws_sessions.py::test_session[S-13]` |
| S-14 | connection.error SEARCH_FAILED | `tests/conformance/test_ws_sessions.py::test_session[S-14]` |
| S-15 | connection.error INTERNAL_ERROR | `tests/conformance/test_ws_sessions.py::test_session[S-15]` |
| S-16 | No pong for 60 s | `tests/conformance/test_ws_sessions.py::test_session[S-16]` |
| S-17 | Raw stream: admitted, no initial push, skeleton frames | `tests/conformance/test_ws_sessions.py::test_session[S-17]` |
| S-18 | Proactive rotation before the 2 h connection lifetime | `tests/conformance/test_ws_sessions.py::test_session[S-18]` |
| S-19 | Dial refused: no API key | `tests/conformance/test_ws_sessions.py::test_session[S-19]` |
| S-20 | Dial refused: invalid API key | `tests/conformance/test_ws_sessions.py::test_session[S-20]` |
| S-21 | Dial refused: API key in the wrong format | `tests/conformance/test_ws_sessions.py::test_session[S-21]` |
| S-22 | Dial refused: plan without WebSockets | `tests/conformance/test_ws_sessions.py::test_session[S-22]` |
| S-23 | Dial refused: connection limit reached, no takeover | `tests/conformance/test_ws_sessions.py::test_session[S-23]` |
| S-24 | Dial refused: WebSocket quota exhausted | `tests/conformance/test_ws_sessions.py::test_session[S-24]` |
| S-25 | Dial refused: lost the admit race | `tests/conformance/test_ws_sessions.py::test_session[S-25]` |
| S-26 | Dial refused: server error | `tests/conformance/test_ws_sessions.py::test_session[S-26]` |
