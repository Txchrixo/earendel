"""Tests for ``app.core.validation.postconditions.validate_outputs``.

Covers:
  - valid outputs pass (all required fields present, correct types)
  - missing required field fails
  - wrong type fails (string where number expected)
  - enum constraint (value not in enum fails)
  - named postconditions: pdf downloaded, amount > 0, status present,
    report downloaded, rows > 0
  - empty string for required field fails
  - ``_humanReview`` outputs always pass
  - ``None`` for an optional field passes
"""
from __future__ import annotations

from datetime import datetime

from app.core.domain.entities import ActionContract, TypedAction
from app.core.domain.enums import (
    ActionStatus,
    AdapterType,
    PermissionScope,
    RiskLevel,
    WorkflowCategory,
)
from app.core.domain.value_objects import FieldSchema
from app.core.validation.postconditions import validate_outputs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_action(contract: ActionContract, name: str = "testAction") -> TypedAction:
    """Build a minimal TypedAction carrying the given contract."""
    return TypedAction(
        id=f"act_test_{name}",
        connectorId="conn_test",
        name=name,
        signature=f"{name}()",
        description="test action",
        category=WorkflowCategory.finance,
        contract=contract,
        permissions=PermissionScope.read_only,
        riskLevel=RiskLevel.low,
        executionMethods=[AdapterType.api],
        preferredAdapter=AdapterType.api,
        status=ActionStatus.published,
        version="1.0.0",
    )


def _invoice_action() -> TypedAction:
    """A downloadInvoice-shaped action with enum + named postconditions."""
    return _make_action(
        ActionContract(
            inputs=[FieldSchema("invoiceId", "string", True, "id")],
            outputs=[
                FieldSchema("invoiceNumber", "string", True, "number"),
                FieldSchema("pdfUrl", "url", True, "pdf"),
                FieldSchema("supplierName", "string", True, "supplier"),
                FieldSchema("amount", "number", True, "total"),
                FieldSchema(
                    "status", "string", True, "status",
                    enum=("paid", "pending", "overdue"),
                ),
            ],
            preconditions=["connector active"],
            postconditions=["pdf downloaded", "amount > 0", "status present"],
        ),
        name="downloadInvoice",
    )


# ---------------------------------------------------------------------------
# Valid outputs
# ---------------------------------------------------------------------------

def test_valid_outputs_pass():
    action = _invoice_action()
    outputs = {
        "invoiceNumber": "INV-1001",
        "pdfUrl": "https://files.acme.com/invoices/INV-1001.pdf",
        "supplierName": "Acme Supplies GmbH",
        "amount": 4280.50,
        "status": "paid",
    }
    ok, reasons = validate_outputs(action, outputs)
    assert ok is True
    assert reasons == []


def test_valid_outputs_with_optional_field_passes():
    """An optional field set to a valid value must not break validation."""
    action = _make_action(
        ActionContract(
            inputs=[],
            outputs=[
                FieldSchema("status", "string", True, "status"),
                FieldSchema("proofOfDeliveryUrl", "url", False, "pod"),
            ],
            postconditions=["status present"],
        ),
        name="trackShipment",
    )
    outputs = {
        "status": "in_transit",
        "proofOfDeliveryUrl": "https://files.maersk.com/pod/POD-1.pdf",
    }
    ok, reasons = validate_outputs(action, outputs)
    assert ok is True
    assert reasons == []


def test_none_for_optional_field_passes():
    """``None`` for an optional field must pass (field is simply absent)."""
    action = _make_action(
        ActionContract(
            inputs=[],
            outputs=[
                FieldSchema("status", "string", True, "status"),
                FieldSchema("proofOfDeliveryUrl", "url", False, "pod"),
            ],
            postconditions=["status present"],
        ),
        name="trackShipment",
    )
    outputs = {"status": "in_transit", "proofOfDeliveryUrl": None}
    ok, reasons = validate_outputs(action, outputs)
    assert ok is True
    assert reasons == []


# ---------------------------------------------------------------------------
# Missing / empty required fields
# ---------------------------------------------------------------------------

def test_missing_required_field_fails():
    action = _invoice_action()
    outputs = {
        "invoiceNumber": "INV-1001",
        "pdfUrl": "https://files.acme.com/invoices/INV-1001.pdf",
        "supplierName": "Acme Supplies GmbH",
        "amount": 4280.50,
        # "status" omitted entirely
    }
    ok, reasons = validate_outputs(action, outputs)
    assert ok is False
    assert any("missing required" in r and "status" in r for r in reasons)


def test_missing_all_required_fields_fails():
    action = _invoice_action()
    ok, reasons = validate_outputs(action, {})
    assert ok is False
    # Every required output must be reported missing (≥5 fields on the
    # invoice contract). Named-postcondition failures may add extra reasons.
    missing_reasons = [r for r in reasons if "missing required" in r]
    assert len(missing_reasons) >= 5


def test_empty_string_for_required_field_fails():
    action = _invoice_action()
    outputs = {
        "invoiceNumber": "",  # empty required string
        "pdfUrl": "https://files.acme.com/invoices/INV-1001.pdf",
        "supplierName": "Acme Supplies GmbH",
        "amount": 4280.50,
        "status": "paid",
    }
    ok, reasons = validate_outputs(action, outputs)
    assert ok is False
    assert any("empty required" in r and "invoiceNumber" in r for r in reasons)


# ---------------------------------------------------------------------------
# Wrong type
# ---------------------------------------------------------------------------

def test_wrong_type_string_where_number_expected_fails():
    action = _invoice_action()
    outputs = {
        "invoiceNumber": "INV-1001",
        "pdfUrl": "https://files.acme.com/invoices/INV-1001.pdf",
        "supplierName": "Acme Supplies GmbH",
        "amount": "not a number",  # string where number expected
        "status": "paid",
    }
    ok, reasons = validate_outputs(action, outputs)
    assert ok is False
    assert any("not of type number" in r and "amount" in r for r in reasons)


def test_wrong_type_number_where_string_expected_fails():
    action = _make_action(
        ActionContract(
            inputs=[],
            outputs=[FieldSchema("invoiceNumber", "string", True, "number")],
            postconditions=[],
        ),
    )
    ok, reasons = validate_outputs(action, {"invoiceNumber": 12345})
    assert ok is False
    assert any("not of type string" in r for r in reasons)


def test_wrong_type_url_not_starting_with_http_fails():
    action = _make_action(
        ActionContract(
            inputs=[],
            outputs=[FieldSchema("pdfUrl", "url", True, "pdf")],
            postconditions=[],
        ),
    )
    ok, reasons = validate_outputs(action, {"pdfUrl": "ftp://files/x.pdf"})
    assert ok is False
    assert any("not of type url" in r for r in reasons)


def test_boolean_rejected_for_number_field():
    """Booleans must not satisfy a 'number' check (Python bool is int subclass)."""
    action = _make_action(
        ActionContract(
            inputs=[],
            outputs=[FieldSchema("amount", "number", True, "total")],
            postconditions=[],
        ),
    )
    ok, reasons = validate_outputs(action, {"amount": True})
    assert ok is False
    assert any("not of type number" in r for r in reasons)


# ---------------------------------------------------------------------------
# Enum constraint
# ---------------------------------------------------------------------------

def test_enum_constraint_value_in_enum_passes():
    action = _invoice_action()
    outputs = {
        "invoiceNumber": "INV-1001",
        "pdfUrl": "https://files.acme.com/invoices/INV-1001.pdf",
        "supplierName": "Acme Supplies GmbH",
        "amount": 4280.50,
        "status": "pending",  # in enum
    }
    ok, reasons = validate_outputs(action, outputs)
    assert ok is True
    assert reasons == []


def test_enum_constraint_value_not_in_enum_fails():
    action = _invoice_action()
    outputs = {
        "invoiceNumber": "INV-1001",
        "pdfUrl": "https://files.acme.com/invoices/INV-1001.pdf",
        "supplierName": "Acme Supplies GmbH",
        "amount": 4280.50,
        "status": "totally_invalid",  # not in enum
    }
    ok, reasons = validate_outputs(action, outputs)
    assert ok is False
    assert any("enum" in r and "status" in r for r in reasons)


# ---------------------------------------------------------------------------
# Named postconditions
# ---------------------------------------------------------------------------

def test_postcondition_pdf_downloaded_pass_when_pdfurl_present():
    action = _invoice_action()
    outputs = {
        "invoiceNumber": "INV-1001",
        "pdfUrl": "https://files.acme.com/invoices/INV-1001.pdf",
        "supplierName": "Acme",
        "amount": 100,
        "status": "paid",
    }
    ok, _ = validate_outputs(action, outputs)
    assert ok is True


def test_postcondition_pdf_downloaded_fails_when_pdfurl_missing():
    """The 'pdf downloaded' postcondition must fail when pdfUrl is absent.

    We relax the contract to make pdfUrl optional so the field check passes,
    isolating the postcondition check.
    """
    action = _make_action(
        ActionContract(
            inputs=[],
            outputs=[
                FieldSchema("invoiceNumber", "string", True, "n"),
                FieldSchema("pdfUrl", "url", False, "pdf"),  # optional
                FieldSchema("amount", "number", True, "a"),
                FieldSchema("status", "string", True, "s"),
            ],
            postconditions=["pdf downloaded"],
        ),
    )
    outputs = {
        "invoiceNumber": "INV-1",
        "amount": 100,
        "status": "paid",
        # pdfUrl absent
    }
    ok, reasons = validate_outputs(action, outputs)
    assert ok is False
    assert any("pdf downloaded" in r for r in reasons)


def test_postcondition_amount_gt_zero_passes():
    action = _make_action(
        ActionContract(
            inputs=[],
            outputs=[FieldSchema("amount", "number", True, "total")],
            postconditions=["amount > 0"],
        ),
    )
    ok, _ = validate_outputs(action, {"amount": 4280.50})
    assert ok is True


def test_postcondition_amount_gt_zero_fails_when_zero():
    action = _make_action(
        ActionContract(
            inputs=[],
            outputs=[FieldSchema("amount", "number", True, "total")],
            postconditions=["amount > 0"],
        ),
    )
    ok, reasons = validate_outputs(action, {"amount": 0})
    assert ok is False
    assert any("amount > 0" in r for r in reasons)


def test_postcondition_amount_gt_zero_fails_when_negative():
    action = _make_action(
        ActionContract(
            inputs=[],
            outputs=[FieldSchema("amount", "number", True, "total")],
            postconditions=["amount > 0"],
        ),
    )
    ok, reasons = validate_outputs(action, {"amount": -5})
    assert ok is False
    assert any("amount > 0" in r for r in reasons)


def test_postcondition_status_present_passes():
    action = _make_action(
        ActionContract(
            inputs=[],
            outputs=[FieldSchema("status", "string", True, "status")],
            postconditions=["status present"],
        ),
    )
    ok, _ = validate_outputs(action, {"status": "shipped"})
    assert ok is True


def test_postcondition_status_present_fails_when_empty():
    """Empty status fails the field check AND the postcondition."""
    action = _make_action(
        ActionContract(
            inputs=[],
            outputs=[FieldSchema("status", "string", True, "status")],
            postconditions=["status present"],
        ),
    )
    ok, reasons = validate_outputs(action, {"status": ""})
    assert ok is False
    # Either the field check (empty required) or the postcondition fires.
    assert len(reasons) >= 1


def test_postcondition_report_downloaded_passes_when_reporturl_present():
    action = _make_action(
        ActionContract(
            inputs=[],
            outputs=[FieldSchema("reportUrl", "url", True, "report")],
            postconditions=["report downloaded"],
        ),
        name="downloadMarketplaceReport",
    )
    ok, _ = validate_outputs(action, {"reportUrl": "https://reports.x/r.csv"})
    assert ok is True


def test_postcondition_report_downloaded_fails_when_reporturl_missing():
    action = _make_action(
        ActionContract(
            inputs=[],
            outputs=[FieldSchema("reportUrl", "url", False, "report")],
            postconditions=["report downloaded"],
        ),
        name="downloadMarketplaceReport",
    )
    ok, reasons = validate_outputs(action, {})
    assert ok is False
    assert any("report downloaded" in r for r in reasons)


def test_postcondition_rows_gt_zero_passes():
    action = _make_action(
        ActionContract(
            inputs=[],
            outputs=[FieldSchema("rows", "number", True, "count")],
            postconditions=["rows > 0"],
        ),
        name="downloadMarketplaceReport",
    )
    ok, _ = validate_outputs(action, {"rows": 1284})
    assert ok is True


def test_postcondition_rows_gt_zero_fails_when_zero():
    action = _make_action(
        ActionContract(
            inputs=[],
            outputs=[FieldSchema("rows", "number", True, "count")],
            postconditions=["rows > 0"],
        ),
        name="downloadMarketplaceReport",
    )
    ok, reasons = validate_outputs(action, {"rows": 0})
    assert ok is False
    assert any("rows > 0" in r for r in reasons)


# ---------------------------------------------------------------------------
# _humanReview shortcut
# ---------------------------------------------------------------------------

def test_human_review_outputs_always_pass_even_with_empty_dict():
    action = _invoice_action()
    ok, reasons = validate_outputs(action, {"_humanReview": True})
    assert ok is True
    assert reasons == []


def test_human_review_outputs_pass_even_with_invalid_fields():
    """When _humanReview is True, no field/postcondition checks run."""
    action = _invoice_action()
    outputs = {"_humanReview": True, "amount": "not a number", "status": "invalid"}
    ok, reasons = validate_outputs(action, outputs)
    assert ok is True
    assert reasons == []


def test_human_review_truthy_value_passes():
    """A truthy _humanReview value (not just True) also short-circuits."""
    action = _invoice_action()
    ok, reasons = validate_outputs(action, {"_humanReview": "yes"})
    assert ok is True
    assert reasons == []
