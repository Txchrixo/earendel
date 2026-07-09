"""Demo HAR synthesizer — produces realistic HAR captures for the 6 seeded actions.

Real recordings capture XHR/fetch traffic via the browser extension. In the
demo / dev environment we don't have a recording extension, so this module
synthesizes a realistic HAR for each seeded action so the discovery
pipeline (``analyze_har`` + ``store_discovered_endpoints``) has something
to chew on at compile time.

Each synthesized HAR contains:
  - 1 business-relevant POST/GET to an internal-looking endpoint that
    returns JSON matching the action's contract output shape (snake_case
    keys, so the field-mapping inference gets exercised).
  - 2-3 noise entries: a static asset (``.js``), an analytics beacon
    (``google-analytics.com``), and an unrelated third-party call.

This is intentionally synthetic — it's only used when no real HAR is
available. Real captures will score higher on cluster_size + business_score
because they have more samples per cluster.
"""
from __future__ import annotations

import json
from typing import Any

# Per-action HAR templates. The business endpoint's response uses
# snake_case keys that DON'T exactly match the camelCase contract output
# fields — so the analyzer's snake_case<->camelCase + synonym inference
# gets exercised. The body values are chosen so that the body_template
# inference can substitute them with {inputKey} placeholders.
_DEMO_HARS: dict[str, dict[str, Any]] = {
    "downloadInvoice": {
        "log": {
            "version": "1.2",
            "creator": {"name": "earendel-demo", "version": "1.0"},
            "entries": [
                {
                    "request": {
                        "method": "POST",
                        "url": "https://supplier-portal.acme.com/internal/v2/invoices/INV-1001/download",
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"},
                            {"name": "Cookie", "value": "session=abc123"},
                        ],
                        "postData": {
                            "mimeType": "application/json",
                            "text": json.dumps({"invoiceId": "INV-1001"}),
                        },
                    },
                    "response": {
                        "status": 200,
                        "content": {
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "invoice_number": "INV-1001",
                                "download_url": "https://files.acme.com/invoices/INV-1001.pdf",
                                "supplier_name": "Acme Supplies GmbH",
                                "total": 4280.50,
                                "payment_status": "paid",
                            }),
                        },
                    },
                },
                {
                    "request": {
                        "method": "GET",
                        "url": "https://supplier-portal.acme.com/static/main.abc123.js",
                    },
                    "response": {
                        "status": 200,
                        "content": {"mimeType": "application/javascript", "text": ""},
                    },
                },
                {
                    "request": {
                        "method": "GET",
                        "url": "https://supplier-portal.acme.com/static/logo.svg",
                    },
                    "response": {
                        "status": 200,
                        "content": {"mimeType": "image/svg+xml", "text": ""},
                    },
                },
                {
                    "request": {
                        "method": "POST",
                        "url": "https://www.google-analytics.com/g/collect?v=2&tid=G-XXXX",
                    },
                    "response": {
                        "status": 204,
                        "content": {"mimeType": "text/plain", "text": ""},
                    },
                },
            ],
        }
    },
    "trackShipment": {
        "log": {
            "version": "1.2",
            "creator": {"name": "earendel-demo", "version": "1.0"},
            "entries": [
                {
                    "request": {
                        "method": "POST",
                        "url": "https://api.maersk.com/internal/v1/shipments/MAEU-8842/track",
                        "postData": {
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "carrier": "maersk",
                                "trackingNumber": "MAEU-8842",
                            }),
                        },
                    },
                    "response": {
                        "status": 200,
                        "content": {
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "shipment_status": "in_transit",
                                "eta": "2025-02-14",
                                "current_location": "Rotterdam, NL",
                                "pod_url": "https://files.maersk.com/pod/MAEU-8842.pdf",
                            }),
                        },
                    },
                },
                {
                    "request": {
                        "method": "GET",
                        "url": "https://api.maersk.com/static/tracking.css",
                    },
                    "response": {
                        "status": 200,
                        "content": {"mimeType": "text/css", "text": ""},
                    },
                },
                {
                    "request": {
                        "method": "GET",
                        "url": "https://segment.io/v1/track",
                    },
                    "response": {
                        "status": 200,
                        "content": {"mimeType": "application/json", "text": "{}"},
                    },
                },
            ],
        }
    },
    "checkClaimStatus": {
        "log": {
            "version": "1.2",
            "creator": {"name": "earendel-demo", "version": "1.0"},
            "entries": [
                {
                    "request": {
                        "method": "POST",
                        "url": "https://provider.bluecross.com/internal/v2/claims/CLM-7742/check",
                        "postData": {
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "patientId": "PAT-1",
                                "claimId": "CLM-7742",
                            }),
                        },
                    },
                    "response": {
                        "status": 200,
                        "content": {
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "claim_status": "approved",
                                "denial_reason": None,
                                "next_step": "no action needed",
                                "last_updated": "2025-01-22T14:30:00Z",
                            }),
                        },
                    },
                },
                {
                    "request": {
                        "method": "GET",
                        "url": "https://provider.bluecross.com/assets/fonts.woff2",
                    },
                    "response": {
                        "status": 200,
                        "content": {"mimeType": "font/woff2", "text": ""},
                    },
                },
                {
                    "request": {
                        "method": "GET",
                        "url": "https://www.google-analytics.com/collect",
                    },
                    "response": {
                        "status": 200,
                        "content": {"mimeType": "image/gif", "text": ""},
                    },
                },
            ],
        }
    },
    "downloadMarketplaceReport": {
        "log": {
            "version": "1.2",
            "creator": {"name": "earendel-demo", "version": "1.0"},
            "entries": [
                {
                    "request": {
                        "method": "GET",
                        "url": "https://sellercentral.amazon.com/internal/reports/settlement?marketplace=amazon&reportType=settlement&dateRange=2025-01-01..2025-01-31",
                        "postData": {
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "marketplace": "amazon",
                                "reportType": "settlement",
                                "dateRange": "2025-01-01..2025-01-31",
                            }),
                        },
                    },
                    "response": {
                        "status": 200,
                        "content": {
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "download_url": "https://reports.amazon.com/settlements/2025-01.zip",
                                "row_count": 1284,
                                "period_start": "2025-01-01",
                                "period_end": "2025-01-31",
                                "currency": "EUR",
                            }),
                        },
                    },
                },
                {
                    "request": {
                        "method": "GET",
                        "url": "https://sellercentral.amazon.com/static/app.js",
                    },
                    "response": {
                        "status": 200,
                        "content": {"mimeType": "application/javascript", "text": ""},
                    },
                },
                {
                    "request": {
                        "method": "POST",
                        "url": "https://stats.g.doubleclick.net/j/collect",
                    },
                    "response": {
                        "status": 200,
                        "content": {"mimeType": "image/gif", "text": ""},
                    },
                },
            ],
        }
    },
    "exportNewCandidates": {
        "log": {
            "version": "1.2",
            "creator": {"name": "earendel-demo", "version": "1.0"},
            "entries": [
                {
                    "request": {
                        "method": "POST",
                        "url": "https://ats.linkedin.com/internal/v2/jobs/JOB-204/candidates/export",
                        "postData": {
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "jobId": "JOB-204",
                                "source": "linkedin",
                            }),
                        },
                    },
                    "response": {
                        "status": 200,
                        "content": {
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "candidates": "https://exports.linkedin.com/JOB-204.csv",
                                "candidate_count": 38,
                                "duplicates_removed": 11,
                                "top_match_score": 0.92,
                            }),
                        },
                    },
                },
                {
                    "request": {
                        "method": "GET",
                        "url": "https://ats.linkedin.com/static/img/hero.png",
                    },
                    "response": {
                        "status": 200,
                        "content": {"mimeType": "image/png", "text": ""},
                    },
                },
                {
                    "request": {
                        "method": "GET",
                        "url": "https://bat.bing.com/action/0",
                    },
                    "response": {
                        "status": 200,
                        "content": {"mimeType": "image/gif", "text": ""},
                    },
                },
            ],
        }
    },
    "fillSecurityQuestionnaire": {
        "log": {
            "version": "1.2",
            "creator": {"name": "earendel-demo", "version": "1.0"},
            "entries": [
                {
                    "request": {
                        "method": "POST",
                        "url": "https://vendor.compliance.io/internal/v1/questionnaires/KB-001/draft",
                        "postData": {
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "portalUrl": "https://vendor.compliance.io/q/123",
                                "knowledgeBaseId": "KB-001",
                            }),
                        },
                    },
                    "response": {
                        "status": 200,
                        "content": {
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "filled_fields": 84,
                                "needs_review": 12,
                                "evidence_bundle": "https://evidence.earendel.io/KB-001.zip",
                                "draft_status": "draft",
                            }),
                        },
                    },
                },
                {
                    "request": {
                        "method": "GET",
                        "url": "https://vendor.compliance.io/static/styles.css",
                    },
                    "response": {
                        "status": 200,
                        "content": {"mimeType": "text/css", "text": ""},
                    },
                },
                {
                    "request": {
                        "method": "GET",
                        "url": "https://sentry.io/api/1/envelope/",
                    },
                    "response": {
                        "status": 200,
                        "content": {"mimeType": "application/json", "text": "{}"},
                    },
                },
            ],
        }
    },
}


def _synthesize_demo_har(action_name: str) -> dict[str, Any]:
    """Return a realistic synthesized HAR for one of the 6 seeded actions.

    For unknown actions, returns a minimal HAR with a single generic
    business endpoint so the analyzer has *something* to score.
    """
    if action_name in _DEMO_HARS:
        # Return a deep copy so callers can mutate freely.
        return json.loads(json.dumps(_DEMO_HARS[action_name]))
    # Generic fallback for unknown actions — single POST to a generic URL.
    return {
        "log": {
            "version": "1.2",
            "creator": {"name": "earendel-demo", "version": "1.0"},
            "entries": [
                {
                    "request": {
                        "method": "POST",
                        "url": f"https://example.com/internal/v1/{action_name}",
                        "postData": {
                            "mimeType": "application/json",
                            "text": "{}",
                        },
                    },
                    "response": {
                        "status": 200,
                        "content": {
                            "mimeType": "application/json",
                            "text": json.dumps({"status": "ok"}),
                        },
                    },
                },
            ],
        }
    }
