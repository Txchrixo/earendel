"""HAR analyzer — turns a HAR capture into scored endpoint candidates.

This is the heart of Earendel's technical moat (Option B). Instead of
clicking through a portal with a browser, we replay the internal XHR/fetch
endpoints the portal itself was calling. The analyzer:

  1. Filters out non-business noise (static assets, analytics beacons).
  2. Clusters the remaining requests by ``(method, normalized_path)`` so
     ``POST /api/invoices/INV-123`` and ``POST /api/invoices/INV-456``
     collapse into one ``POST /api/invoices/{id}`` cluster.
  3. Scores each cluster by "business relevance" — mutations, JSON
     responses, action-name keyword hits, etc.
  4. For the top clusters, infers:
       - ``field_mapping`` (response JSON key -> contract output field,
         fuzzy-matched snake_case <-> camelCase + synonyms).
       - ``body_template`` (request body with actual values replaced by
         ``{inputKey}`` placeholders).
       - ``cookie_env_var`` (derived from the request's domain).
       - ``response_shape`` (top-level keys of the response JSON).

The result is a list of :class:`DiscoveredEndpointCandidate` (top 3 by
score) that the ``endpoint_store`` persists to the ``DiscoveredEndpoint``
table, and the ``internal_route`` adapter replays at runtime.

The analyzer is **pure** — no IO, no DB. It degrades gracefully: a
malformed/empty HAR returns an empty candidate list rather than raising.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Static asset extensions — these requests are NEVER business-relevant.
_STATIC_ASSET_EXTENSIONS: frozenset[str] = frozenset({
    ".js", ".mjs", ".css", ".map",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".bmp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".mp3", ".webm", ".ogg",
    ".pdf",  # PDF *downloads* are usually the *result*, but the request that
             # returned a PDF blob is not an API endpoint — it's a direct file
             # fetch. The business endpoint is the one that *returns the URL*.
    ".zip", ".tar", ".gz",
})

# Analytics / telemetry domains — filtered out before clustering.
_ANALYTICS_DOMAINS: frozenset[str] = frozenset({
    "google-analytics.com",
    "www.google-analytics.com",
    "ssl.google-analytics.com",
    "doubleclick.net",
    "stats.g.doubleclick.net",
    "segment.io",
    "cdn.segment.io",
    "mixpanel.com",
    "api.mixpanel.com",
    "hotjar.com",
    "sentry.io",
    "browser-intake-datadoghq.com",
    "rum.browser-intake-datadoghq.com",
    "fullstory.com",
    "fbcdn.net",
    "connect.facebook.net",
    "www.facebook.com",
    "bat.bing.com",
    "analytics.tiktok.com",
    "sentry.io",
})

# Action name -> keywords that mark a response as business-relevant.
_BUSINESS_KEYWORDS: dict[str, list[str]] = {
    "downloadInvoice": ["invoice", "pdf", "supplier", "amount", "total", "payment"],
    "trackShipment": ["shipment", "tracking", "delivery", "carrier", "eta", "pod"],
    "checkClaimStatus": ["claim", "patient", "denial", "coverage", "next_step"],
    "downloadMarketplaceReport": ["report", "marketplace", "settlement", "sales", "rows"],
    "exportNewCandidates": ["candidate", "applicant", "resume", "dedup", "match"],
    "fillSecurityQuestionnaire": ["questionnaire", "evidence", "review", "draft", "answer"],
}

# Action name -> list of contract output field names (camelCase).
# Used to infer the field_mapping. Kept in sync with seed.py contracts.
_KNOWN_CONTRACT_OUTPUTS: dict[str, list[str]] = {
    "downloadInvoice": [
        "invoiceNumber", "pdfUrl", "supplierName", "amount", "status",
    ],
    "trackShipment": [
        "status", "eta", "currentLocation", "proofOfDeliveryUrl",
    ],
    "checkClaimStatus": [
        "status", "denialReason", "nextStep", "lastUpdated",
    ],
    "downloadMarketplaceReport": [
        "reportUrl", "rows", "periodStart", "periodEnd", "currency",
    ],
    "exportNewCandidates": [
        "candidates", "count", "duplicatesRemoved", "topMatchScore",
    ],
    "fillSecurityQuestionnaire": [
        "filledFields", "needsReview", "evidenceRefs", "status",
    ],
}

# Action name -> sample inputs used by the demo HAR synthesizer + by the
# body_template inference (so we know which values to replace with placeholders).
_KNOWN_INPUT_KEYS: dict[str, list[str]] = {
    "downloadInvoice": ["invoiceId"],
    "trackShipment": ["carrier", "trackingNumber"],
    "checkClaimStatus": ["patientId", "claimId"],
    "downloadMarketplaceReport": ["marketplace", "reportType", "dateRange"],
    "exportNewCandidates": ["jobId", "source"],
    "fillSecurityQuestionnaire": ["portalUrl", "knowledgeBaseId"],
}

# Synonyms for fuzzy field-mapping: contract_output_field -> list of
# response-key aliases (snake_case form). Tried when direct snake/camel
# conversion does not produce a hit.
_FIELD_SYNONYMS: dict[str, list[str]] = {
    "invoiceNumber": ["invoice_number", "invoice_id", "number", "inv_num"],
    "pdfUrl": ["download_url", "pdf_url", "file_url", "pdf", "file"],
    "supplierName": ["supplier_name", "vendor_name", "seller_name", "supplier"],
    "amount": ["total", "amount", "value", "sum", "grand_total", "amount_due"],
    "status": ["payment_status", "claim_status", "state", "status", "shipment_status"],
    "eta": ["eta", "estimated_arrival", "arrival_date", "delivery_date", "expected_delivery"],
    "currentLocation": ["current_location", "location", "last_location", "current_city"],
    "proofOfDeliveryUrl": ["pod_url", "proof_of_delivery", "delivery_url", "pod"],
    "denialReason": ["denial_reason", "denied_reason", "rejection_reason", "denied"],
    "nextStep": ["next_step", "action_required", "recommended_action", "next_action"],
    "lastUpdated": ["last_updated", "updated_at", "modified_at", "last_modified"],
    "reportUrl": ["report_url", "download_url", "file_url", "report_link"],
    "rows": ["row_count", "count", "total_count", "rows", "num_rows"],
    "periodStart": ["period_start", "start_date", "from_date", "date_from"],
    "periodEnd": ["period_end", "end_date", "to_date", "date_to"],
    "currency": ["currency", "curr", "currency_code"],
    "candidates": ["candidates", "applicants", "profiles", "resume_urls"],
    "count": ["count", "total_count", "num_candidates", "candidate_count"],
    "duplicatesRemoved": ["duplicates_removed", "dedup_count", "dedupe", "duplicates"],
    "topMatchScore": ["top_match_score", "best_score", "match_score", "top_score"],
    "filledFields": ["filled_fields", "fields_filled", "answers_filled", "answered"],
    "needsReview": ["needs_review", "review_needed", "pending_review", "unanswered"],
    "evidenceRefs": ["evidence_refs", "evidence_bundle", "evidence", "evidence_url"],
}

# Regex patterns for ID-like path segments.
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_NUMERIC_RE = re.compile(r"^\d+$")
# Patterns like INV-123, MAEU-8842, PAT-1, ORD-2024-001.
_ID_LIKE_RE = re.compile(r"^[A-Za-z]+-\d+$")
_LONG_HASH_RE = re.compile(r"^[A-Za-z0-9_\-]{16,}$")


# ---------------------------------------------------------------------------
# Candidate dataclass
# ---------------------------------------------------------------------------


@dataclass
class DiscoveredEndpointCandidate:
    """A scored, clustered endpoint ready to be persisted.

    The structured fields (``body_template``, ``field_mapping``,
    ``response_shape``, ``headers_template``) are kept as Python dicts here;
    the :mod:`endpoint_store` serializes them to JSON strings before
    writing to the ``DiscoveredEndpoint`` table.
    """

    action_name: str
    method: str
    url: str
    url_pattern: str
    business_score: float
    cluster_size: int
    body_template: dict[str, Any] = field(default_factory=dict)
    headers_template: dict[str, Any] = field(default_factory=dict)
    cookie_env_var: str = ""
    field_mapping: dict[str, str] = field(default_factory=dict)
    response_shape: dict[str, str] = field(default_factory=dict)
    connector_id: str | None = None
    discovered_from: str = "har"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_path(url: str) -> str:
    """Extract the path and replace ID-like segments with ``{id}``.

    Examples::

        /api/invoices/INV-123            -> /api/invoices/{id}
        /api/invoices/550e8400-...       -> /api/invoices/{id}
        /v2/users/12345                  -> /v2/users/{id}
        /api/invoices/download           -> /api/invoices/download  (unchanged)
    """
    try:
        path = urlparse(url).path or "/"
    except Exception:
        return "/"
    if not path:
        return "/"
    segments = path.split("/")
    normalized: list[str] = []
    for seg in segments:
        if not seg:
            normalized.append("")
            continue
        if _UUID_RE.match(seg) or _NUMERIC_RE.match(seg) \
                or _ID_LIKE_RE.match(seg) or _LONG_HASH_RE.match(seg):
            normalized.append("{id}")
        else:
            normalized.append(seg)
    return "/".join(normalized)


def _get_domain(url: str) -> str:
    """Extract the hostname (lowercased) from a URL, or "" if unparseable."""
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _is_static_asset(url: str) -> bool:
    """True if the URL targets a static asset (js/css/png/svg/woff/pdf/...)."""
    try:
        path = urlparse(url).path.lower()
    except Exception:
        return False
    for ext in _STATIC_ASSET_EXTENSIONS:
        if path.endswith(ext):
            return True
    if path.endswith("/favicon") or path.endswith("/favicon.ico"):
        return True
    return False


def _is_analytics(url: str) -> bool:
    """True if the URL targets a known analytics / telemetry domain."""
    host = _get_domain(url)
    if not host:
        return False
    for dom in _ANALYTICS_DOMAINS:
        if host == dom or host.endswith("." + dom):
            return True
    return False


def _is_business_request(url: str) -> bool:
    """Keep the request if it's not a static asset and not analytics."""
    return not _is_static_asset(url) and not _is_analytics(url)


def _to_snake(s: str) -> str:
    """Convert camelCase / PascalCase / kebab-case to lower snake_case."""
    out = re.sub(r"[\- ]+", "_", s)
    out = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", out)
    return out.lower()


def _normalize_key(s: str) -> str:
    """Aggressively normalize a key for fuzzy matching.

    Lowercases, strips underscores/dashes/dots/spaces — so ``invoiceNumber``,
    ``invoice_number``, ``InvoiceNumber``, ``invoice-number`` all collapse
    to ``invoicenumber``.
    """
    return re.sub(r"[_\-\.\s]+", "", s.lower())


def _infer_field_mapping(
    response_keys: list[str],
    contract_output_fields: list[str],
) -> dict[str, str]:
    """Fuzzy-match response keys to contract output fields.

    Returns a ``{contract_field: response_key}`` dict (the same shape the
    internal_route adapter expects).

    Matching order:
      1. Exact case-insensitive match (``Status`` == ``status``).
      2. Snake-case normalized match (``invoiceNumber`` == ``invoice_number``).
      3. Aggressive normalized match (strip all separators).
      4. Synonym match (``amount`` <-> ``total`` via ``_FIELD_SYNONYMS``).
      5. Substring match (``invoice`` in ``invoice_number``).
    """
    mapping: dict[str, str] = {}
    if not response_keys or not contract_output_fields:
        return mapping

    # Index response keys by their normalized forms for O(1) lookup.
    by_lower: dict[str, str] = {}
    by_snake: dict[str, str] = {}
    by_norm: dict[str, str] = {}
    for rk in response_keys:
        by_lower.setdefault(rk.lower(), rk)
        by_snake.setdefault(_to_snake(rk), rk)
        by_norm.setdefault(_normalize_key(rk), rk)

    for cf in contract_output_fields:
        # 1. Exact case-insensitive.
        if cf.lower() in by_lower:
            mapping[cf] = by_lower[cf.lower()]
            continue
        # 2. Snake-case normalized (camelCase -> snake_case).
        cf_snake = _to_snake(cf)
        if cf_snake in by_snake:
            mapping[cf] = by_snake[cf_snake]
            continue
        # 3. Aggressive normalized.
        cf_norm = _normalize_key(cf)
        if cf_norm in by_norm:
            mapping[cf] = by_norm[cf_norm]
            continue
        # 4. Synonyms.
        matched = False
        for syn in _FIELD_SYNONYMS.get(cf, []):
            if syn in by_lower or _to_snake(syn) in by_snake \
                    or _normalize_key(syn) in by_norm:
                mapping[cf] = by_lower.get(syn) or by_snake.get(_to_snake(syn)) \
                    or by_norm.get(_normalize_key(syn))
                matched = True
                break
        if matched:
            continue
        # 5. Substring (one contains the other) — last resort.
        for rk in response_keys:
            rk_norm = _normalize_key(rk)
            if cf_norm and rk_norm and (cf_norm in rk_norm or rk_norm in cf_norm):
                mapping[cf] = rk
                break

    return mapping


def _infer_cookie_env_var(url: str) -> str:
    """Derive an env-var name for the session cookie from the URL's domain.

    ``acme.com`` -> ``ACME_SESSION_COOKIE``
    ``supplier-portal.acme.com`` -> ``ACME_SESSION_COOKIE``
    ``bluecross.co.uk`` -> ``BLUECROSS_SESSION_COOKIE``
    """
    host = _get_domain(url)
    if not host:
        return "SESSION_COOKIE"
    parts = host.split(".")
    # Take the second-level domain. For multi-part TLDs like ``.co.uk`` the
    # SLD is ``parts[-3]``; for normal TLDs it's ``parts[-2]``.
    sld = ""
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in (
            "co", "com", "org", "net", "ac", "gov", "edu"):
        sld = parts[-3]
    elif len(parts) >= 2:
        sld = parts[-2]
    else:
        sld = parts[0]
    # Strip non-alphanumeric.
    sld = re.sub(r"[^A-Za-z0-9]", "", sld).upper()
    if not sld:
        sld = re.sub(r"[^A-Za-z0-9]", "", host.replace(".", "")).upper() or "APP"
    return f"{sld}_SESSION_COOKIE"


def _build_body_template(
    post_data: dict | None,
    inputs_sample: dict[str, Any],
) -> dict[str, Any]:
    """Extract a body template, replacing actual values with ``{inputKey}`` placeholders.

    ``post_data`` is the HAR ``postData`` object — either
    ``{"text": "<json>"}`` or ``{"params": [{"name":..,"value":..}, ..]}``.

    The template maps each top-level body key to either ``{inputKey}`` (when
    the value matches one of the sample inputs OR the body key matches an
    input key via fuzzy snake_case<->camelCase matching) or to the literal
    value (so subsequent replays can use it as-is).
    """
    if not post_data:
        return {}
    # Parse the JSON body if it's a text field.
    body_obj: Any = None
    text = post_data.get("text")
    if isinstance(text, str) and text.strip():
        try:
            body_obj = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            body_obj = None
    if body_obj is None and "params" in post_data:
        # Convert form params to a dict.
        try:
            body_obj = {p["name"]: p.get("value", "") for p in post_data["params"]}
        except (KeyError, TypeError):
            body_obj = None
    if not isinstance(body_obj, dict):
        return {}

    # Build lookups for two matching strategies:
    # 1. value -> input_key   (body value matches a known input value)
    value_to_key: dict[str, str] = {}
    for k, v in inputs_sample.items():
        if v is not None:
            value_to_key[str(v)] = k
    # 2. normalized_input_key -> input_key  (body key matches an input key
    #    after snake_case<->camelCase normalization)
    known_input_keys_normalized: dict[str, str] = {
        _normalize_key(k): k for k in inputs_sample
    }

    template: dict[str, Any] = {}
    for key, value in body_obj.items():
        # 1. Value match.
        if isinstance(value, str) and value in value_to_key:
            template[key] = "{" + value_to_key[value] + "}"
            continue
        # 2. Key match (fuzzy).
        key_norm = _normalize_key(key)
        if key_norm in known_input_keys_normalized:
            input_key = known_input_keys_normalized[key_norm]
            template[key] = "{" + input_key + "}"
            continue
        # 3. Leave as literal — the adapter's _build_body passes non-placeholder
        #    values through verbatim.
        template[key] = value
    return template


def _extract_response_json(entry: dict) -> dict | None:
    """Extract the JSON object from a HAR entry's response body, if possible."""
    try:
        content = entry.get("response", {}).get("content", {}) or {}
    except AttributeError:
        return None
    mime = (content.get("mimeType") or "").lower()
    text = content.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    # Be lenient about charset suffixes etc.
    if "json" not in mime and not text.lstrip().startswith(("{", "[")):
        return None
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _response_text(entry: dict) -> str:
    """Get the raw response body text (lowercased) for keyword matching."""
    try:
        text = entry.get("response", {}).get("content", {}).get("text")
    except AttributeError:
        return ""
    return (text or "").lower()


def _response_mime(entry: dict) -> str:
    try:
        return (entry.get("response", {}).get("content", {}).get("mimeType")
                or "").lower()
    except AttributeError:
        return ""


def _response_status(entry: dict) -> int:
    try:
        return int(entry.get("response", {}).get("status", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _request_method(entry: dict) -> str:
    try:
        return (entry.get("request", {}).get("method") or "GET").upper()
    except AttributeError:
        return "GET"


def _request_url(entry: dict) -> str:
    try:
        return entry.get("request", {}).get("url") or ""
    except AttributeError:
        return ""


def _request_post_data(entry: dict) -> dict | None:
    try:
        pd = entry.get("request", {}).get("postData")
        return pd if isinstance(pd, dict) else None
    except AttributeError:
        return None


def _has_api_segment(path: str) -> bool:
    """True if the path looks like an API endpoint (/api/, /v1/, /internal/, ...)."""
    p = path.lower()
    return (
        "/api/" in p or p.startswith("/api")
        or "/internal/" in p or p.startswith("/internal")
        or "/v1/" in p or "/v2/" in p or "/v3/" in p
        or "/graphql" in p or "/rpc/" in p
    )


def _json_type_name(v: Any) -> str:
    """Return a JSON-ish type name for a value (``null`` for None)."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return type(v).__name__


def _compute_business_score(
    method: str,
    response_mime: str,
    response_status: int,
    response_text: str,
    path: str,
    has_body: bool,
    action_name: str,
) -> float:
    """Compute a 0..1 business-relevance score for a cluster.

    Weights (additive, capped at 1.0):
      +0.30  method is POST/PUT/PATCH (mutations are business-relevant)
      +0.20  response is JSON
      +0.20  response body contains an action-name keyword
      +0.15  response status is 200
      +0.10  URL has an API-like path segment (/api/, /v1/, /internal/, ...)
      +0.05  request has a body (postData)
    """
    score = 0.0
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        score += 0.30
    if "json" in response_mime:
        score += 0.20
    keywords = _BUSINESS_KEYWORDS.get(action_name, [])
    if keywords and any(kw in response_text for kw in keywords):
        score += 0.20
    if response_status == 200:
        score += 0.15
    if _has_api_segment(path):
        score += 0.10
    if has_body:
        score += 0.05
    return min(score, 1.0)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def analyze_har(
    har_json: dict | None,
    action_name: str,
    connector_id: str | None = None,
) -> list[DiscoveredEndpointCandidate]:
    """Analyze a HAR capture and return scored endpoint candidates.

    Args:
        har_json: A HAR object in the standard format
            ``{log: {entries: [{request, response}, ...]}}``.
        action_name: The action this HAR was recorded for (used for
            keyword scoring and contract-output-field lookup).
        connector_id: Optional connector id to stamp on every candidate.

    Returns:
        Up to 3 :class:`DiscoveredEndpointCandidate` instances, sorted by
        descending business_score. Returns an empty list for malformed /
        empty HAR.
    """
    if not isinstance(har_json, dict):
        return []
    try:
        entries = (har_json.get("log") or {}).get("entries") or []
    except AttributeError:
        return []
    if not isinstance(entries, list) or not entries:
        return []

    # Build a sample inputs dict for body_template inference — uses the
    # known input keys for the action, with placeholder values.
    known_input_keys = _KNOWN_INPUT_KEYS.get(action_name, [])
    inputs_sample: dict[str, Any] = {k: f"<sample_{k}>" for k in known_input_keys}

    # Filter + cluster.
    clusters: dict[tuple[str, str], list[dict]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        url = _request_url(entry)
        if not url:
            continue
        if not _is_business_request(url):
            continue
        method = _request_method(entry)
        pattern = _normalize_path(url)
        clusters.setdefault((method, pattern), []).append(entry)

    if not clusters:
        return []

    # Score each cluster.
    scored: list[tuple[float, tuple[str, str], list[dict]]] = []
    for key, members in clusters.items():
        method, _pattern = key
        if not members:
            continue
        # Use the first member for representative signals (status, mime, body).
        # In a real capture with N hits per pattern, the signal is consistent
        # across members; using [0] keeps this simple + deterministic.
        rep = members[0]
        score = _compute_business_score(
            method=method,
            response_mime=_response_mime(rep),
            response_status=_response_status(rep),
            response_text=_response_text(rep),
            path=urlparse(_request_url(rep)).path or "/",
            has_body=bool(_request_post_data(rep)),
            action_name=action_name,
        )
        scored.append((score, key, members))

    scored.sort(key=lambda t: t[0], reverse=True)

    # Build candidates for the top 3 clusters.
    candidates: list[DiscoveredEndpointCandidate] = []
    contract_outputs = _KNOWN_CONTRACT_OUTPUTS.get(action_name, [])
    for score, (method, pattern), members in scored[:3]:
        rep = members[0]
        url = _request_url(rep)
        post_data = _request_post_data(rep)
        response_json = _extract_response_json(rep)
        response_keys = list(response_json.keys()) if response_json else []
        field_mapping = _infer_field_mapping(response_keys, contract_outputs)
        body_template = _build_body_template(post_data, inputs_sample)
        response_shape: dict[str, str] = {}
        if response_json:
            for k, v in response_json.items():
                response_shape[k] = _json_type_name(v)
        cookie_env_var = _infer_cookie_env_var(url)
        # Default headers template: JSON content type + the cookie env var
        # reference. The adapter substitutes the actual cookie at runtime.
        headers_template: dict[str, Any] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if cookie_env_var:
            headers_template["Cookie"] = "{" + cookie_env_var + "}"
            headers_template["X-XSRF-TOKEN"] = "{" + cookie_env_var + "}"

        candidates.append(DiscoveredEndpointCandidate(
            action_name=action_name,
            method=method,
            url=url,
            url_pattern="*" + pattern,
            business_score=round(score, 3),
            cluster_size=len(members),
            body_template=body_template,
            headers_template=headers_template,
            cookie_env_var=cookie_env_var,
            field_mapping=field_mapping,
            response_shape=response_shape,
            connector_id=connector_id,
            discovered_from="har",
        ))

    return candidates
