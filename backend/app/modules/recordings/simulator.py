"""Recordings — deterministic simulator for capturing workflow steps.

Generates 6-10 realistic CapturedStep sequences per workflow type, so the
studio can demo compilation + execution without a live browser recording.
"""
from __future__ import annotations

from ...core.domain.entities import CapturedStep, Recording
from ...shared.ids import new_id

_WORKFLOWS: dict[str, list[CapturedStep]] = {
    "downloadInvoice": [
        CapturedStep(index=0, type="navigate", description="open supplier portal",
                     url="https://supplier-portal.acme.com", networkCalls=3, durationMs=520),
        CapturedStep(index=1, type="input", description="enter username",
                     selector='input[name="email"]', value="ap_user@acme.com",
                     networkCalls=0, durationMs=80),
        CapturedStep(index=2, type="input", description="enter password",
                     selector='input[name="password"]', value="••••••••",
                     networkCalls=0, durationMs=70),
        CapturedStep(index=3, type="click", description="submit login",
                     selector='button[type="submit"]', networkCalls=2, durationMs=410),
        CapturedStep(index=4, type="navigate", description="open invoices page",
                     url="https://supplier-portal.acme.com/invoices",
                     networkCalls=4, durationMs=340),
        CapturedStep(index=5, type="input", description="search invoice id",
                     selector='input[placeholder="Search invoices"]',
                     value="{{invoiceId}}", networkCalls=1, durationMs=120),
        CapturedStep(index=6, type="click", description="open invoice row",
                     selector='tr[data-invoice-id="{{invoiceId}}"]',
                     networkCalls=2, durationMs=180),
        CapturedStep(index=7, type="click", description="click download",
                     selector='button[data-testid="download-btn"]',
                     networkCalls=1, durationMs=90),
        CapturedStep(index=8, type="download", description="download PDF",
                     selector='a[href$=".pdf"]', networkCalls=2,
                     screenshot=True, durationMs=260),
        CapturedStep(index=9, type="assert", description="verify pdf in downloads",
                     selector='table.downloads tr:first-child', durationMs=40),
    ],
    "trackShipment": [
        CapturedStep(index=0, type="navigate", description="open Maersk portal",
                     url="https://my.maersk.com", networkCalls=4, durationMs=540),
        CapturedStep(index=1, type="click", description="go to tracking",
                     selector='a[href="/tracking"]', networkCalls=2, durationMs=180),
        CapturedStep(index=2, type="input", description="enter tracking number",
                     selector='input[name="trackingNumber"]',
                     value="{{trackingNumber}}", networkCalls=0, durationMs=90),
        CapturedStep(index=3, type="select", description="select carrier",
                     selector='select[name="carrier"]', value="maersk",
                     networkCalls=0, durationMs=60),
        CapturedStep(index=4, type="click", description="submit search",
                     selector='button[data-action="search"]', networkCalls=3,
                     durationMs=420),
        CapturedStep(index=5, type="wait", description="wait for map",
                     selector='div.tracking-map', networkCalls=2, durationMs=900),
        CapturedStep(index=6, type="click", description="open details",
                     selector='a[data-route="tracking-detail"]',
                     networkCalls=2, durationMs=200),
        CapturedStep(index=7, type="assert", description="verify ETA present",
                     selector='span.eta-value', durationMs=40),
    ],
    "checkClaimStatus": [
        CapturedStep(index=0, type="navigate", description="open payer portal",
                     url="https://provider.bluecross.com", networkCalls=4,
                     durationMs=600),
        CapturedStep(index=1, type="click", description="open claims tab",
                     selector='a[href="/claims"]', networkCalls=2, durationMs=180),
        CapturedStep(index=2, type="input", description="enter patient id",
                     selector='input[name="patientId"]',
                     value="{{patientId}}", networkCalls=0, durationMs=80),
        CapturedStep(index=3, type="input", description="enter claim id",
                     selector='input[name="claimId"]', value="{{claimId}}",
                     networkCalls=0, durationMs=80),
        CapturedStep(index=4, type="click", description="search claims",
                     selector='button[data-action="search-claims"]',
                     networkCalls=3, durationMs=460),
        CapturedStep(index=5, type="click", description="open claim detail",
                     selector='a[data-claim-id="{{claimId}}"]',
                     networkCalls=2, durationMs=220),
        CapturedStep(index=6, type="assert", description="verify status shown",
                     selector='div.claim-status', durationMs=40),
    ],
}


def simulate_recording(connector_id: str, workflow_name: str) -> Recording:
    """Generate a deterministic Recording for the given workflow name."""
    steps = list(_WORKFLOWS.get(workflow_name, _WORKFLOWS["downloadInvoice"]))
    return Recording(
        id=new_id("rec"), connectorId=connector_id, name=workflow_name,
        steps=steps, totalDurationMs=sum(s.durationMs for s in steps),
        networkRequests=sum(s.networkCalls for s in steps),
        domMutations=len(steps) * 3, screenshots=sum(1 for s in steps if s.screenshot),
    )
