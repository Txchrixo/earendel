"""Tests for Phase 2 — Real Repair Flywheel with Embeddings.

Tests that:
1. The TF-IDF embedding index can be built and queried
2. Semantic search finds similar failures that exact SQL matching misses
3. store_repair computes and persists embeddingText
4. query_kb uses semantic search first, falls back to SQL
5. The index is rebuilt after store_repair
6. Similarity threshold prevents false matches
"""
from __future__ import annotations

import pytest

from app.core.repair.embedding import (
    build_embedding_text,
    rebuild_index,
    search_semantic,
    get_index_size,
    get_index_version,
    MIN_SIMILARITY,
)
from app.core.repair.knowledge_base import (
    RepairFailure,
    query_kb,
    store_repair,
    compute_pattern_key,
)
from app.core.domain.entities import RepairProposal
from app.core.domain.enums import RepairStatus
from app.infrastructure.prisma_repositories import (
    repair_kb_put,
    repair_kb_list,
    repair_kb_set_status,
    repair_kb_get_by_pattern,
)


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #

@pytest.fixture
async def clean_kb(seeded_db):
    """Clean the repair KB before and after each test."""
    entries = await repair_kb_list()
    for e in entries:
        await repair_kb_set_status(e["id"], "deprecated")
    # Reset the TF-IDF index
    await rebuild_index([])
    yield
    entries = await repair_kb_list()
    for e in entries:
        await repair_kb_set_status(e["id"], "deprecated")
    await rebuild_index([])


def _make_kb_entry(
    pattern_key: str,
    target_domain: str,
    widget_type: str,
    intention: str,
    failed_selector: str,
    repaired_selector: str,
    confidence: float = 0.90,
    success_count: int = 3,
    embedding_text: str = "",
) -> dict:
    return {
        "id": f"rkb_test_{pattern_key[:12]}",
        "patternKey": pattern_key,
        "targetDomain": target_domain,
        "widgetType": widget_type,
        "intention": intention,
        "failedSelector": failed_selector,
        "repairedSelector": repaired_selector,
        "repairedLabel": repaired_selector,
        "confidence": confidence,
        "source": "llm",
        "successCount": success_count,
        "failureCount": 0,
        "autoAppliedCount": 0,
        "status": "active",
        "embeddingText": embedding_text or build_embedding_text(
            target_domain, widget_type, intention, failed_selector,
        ),
    }


async def _seed_kb_entry(entry: dict) -> None:
    await repair_kb_put(entry)


# --------------------------------------------------------------------------- #
# 1. TF-IDF embedding index                                                    #
# --------------------------------------------------------------------------- #

class TestTfidfEmbeddingIndex:
    """Tests for the TF-IDF embedding index."""

    @pytest.mark.asyncio
    async def test_build_embedding_text_includes_all_signals(self):
        """build_embedding_text should include domain, widget, intention, selector."""
        text = build_embedding_text(
            target_domain="acme.com",
            widget_type="button",
            intention="download",
            failed_selector="button[data-invoice-download]",
            error_message="selector not found",
            page_text="Download Invoice Page",
        )
        assert "acme.com" in text
        assert "button" in text
        assert "download" in text
        assert "button[data-invoice-download]" in text
        assert "selector not found" in text
        assert "Download Invoice Page" in text

    @pytest.mark.asyncio
    async def test_rebuild_index_with_empty_list(self):
        """rebuild_index with [] should result in an empty index."""
        count = await rebuild_index([])
        assert count == 0
        assert get_index_size() == 0

    @pytest.mark.asyncio
    async def test_rebuild_index_with_entries(self, seeded_db, clean_kb):
        """rebuild_index should return the count of active entries indexed."""
        await _seed_kb_entry(_make_kb_entry(
            "acme.com:button:download:btn1", "acme.com", "button", "download",
            "button[data-download]", "a[aria-label='Download']",
        ))
        await _seed_kb_entry(_make_kb_entry(
            "maersk.com:button:track:btn2", "maersk.com", "button", "track",
            "button[data-track]", "a[aria-label='Track']",
        ))
        entries = await repair_kb_list()
        count = await rebuild_index(entries)
        assert count == 2
        assert get_index_size() == 2

    @pytest.mark.asyncio
    async def test_rebuild_index_ignores_deprecated_entries(self, seeded_db, clean_kb):
        """Deprecated entries should not be included in the index."""
        entry = _make_kb_entry(
            "acme.com:button:download:btn1", "acme.com", "button", "download",
            "button[data-download]", "a[aria-label='Download']",
        )
        entry["status"] = "deprecated"
        await _seed_kb_entry(entry)
        entries = await repair_kb_list()
        count = await rebuild_index(entries)
        assert count == 0  # deprecated entry excluded


# --------------------------------------------------------------------------- #
# 2. Semantic search                                                           #
# --------------------------------------------------------------------------- #

class TestSemanticSearch:
    """Tests for the semantic search function."""

    @pytest.mark.asyncio
    async def test_semantic_search_finds_exact_match(self, seeded_db, clean_kb):
        """Semantic search should find an entry with identical embedding text."""
        await _seed_kb_entry(_make_kb_entry(
            "acme.com:button:download:btn1", "acme.com", "button", "download",
            "button[data-invoice-download]", "a[aria-label='Download PDF']",
        ))
        entries = await repair_kb_list()
        await rebuild_index(entries)

        query = build_embedding_text(
            "acme.com", "button", "download", "button[data-invoice-download]",
        )
        results = await search_semantic(query, top_k=5, min_similarity=0.1)
        assert len(results) > 0
        best, sim = results[0]
        assert best["patternKey"] == "acme.com:button:download:btn1"
        assert sim > 0.5  # exact match should have high similarity

    @pytest.mark.asyncio
    async def test_semantic_search_finds_similar_failure(self, seeded_db, clean_kb):
        """Semantic search should find a similar failure that exact SQL misses.

        This is the KEY test: a failure on 'button[data-invoice-download]' should
        match a KB entry stored from 'button[download-invoice]' because the
        embedding text is similar (same domain, same widget, same intention,
        similar selector keywords).
        """
        # KB entry from Client A: failure on button[data-invoice-download]
        await _seed_kb_entry(_make_kb_entry(
            "acme.com:button:download:btn-original", "acme.com", "button", "download",
            "button[data-invoice-download]", "a[aria-label='Download PDF']",
        ))
        entries = await repair_kb_list()
        await rebuild_index(entries)

        # Client B fails on a DIFFERENT selector but same domain + intention
        query = build_embedding_text(
            "acme.com", "button", "download", "button[download-invoice]",
        )
        results = await search_semantic(query, top_k=5, min_similarity=0.1)
        assert len(results) > 0
        best, sim = results[0]
        assert best["patternKey"] == "acme.com:button:download:btn-original"
        # Similarity should be decent (same domain + widget + intention + "download" + "invoice" keywords)
        assert sim > 0.2

    @pytest.mark.asyncio
    async def test_semantic_search_does_not_match_different_domain(self, seeded_db, clean_kb):
        """A failure on acme.com should not strongly match a KB entry from bluecross.com.

        TF-IDF will find SOME similarity (shared words like 'button', 'domain',
        'widget', 'intention'), but the similarity should be LOWER than a
        same-domain match. We verify the cross-domain similarity is below 0.8
        (a realistic threshold for 'not a real match').
        """
        await _seed_kb_entry(_make_kb_entry(
            "bluecross.com:button:check:btn1", "bluecross.com", "button", "check",
            "button[search-claims]", "button#claim-search",
        ))
        entries = await repair_kb_list()
        await rebuild_index(entries)

        query = build_embedding_text(
            "acme.com", "button", "download", "button[data-invoice-download]",
        )
        results = await search_semantic(query, top_k=5, min_similarity=0.0)
        # The cross-domain match should have low-ish similarity (< 0.8)
        # because the domain + intention keywords differ significantly.
        for entry, sim in results:
            if entry["targetDomain"] == "bluecross.com":
                assert sim < 0.8, f"cross-domain similarity {sim} too high"

    @pytest.mark.asyncio
    async def test_semantic_search_empty_index_returns_empty(self):
        """An empty index should return no results."""
        await rebuild_index([])
        results = await search_semantic("anything", top_k=5, min_similarity=0.0)
        assert results == []

    @pytest.mark.asyncio
    async def test_semantic_search_respects_min_similarity(self, seeded_db, clean_kb):
        """Results below min_similarity should be filtered out."""
        await _seed_kb_entry(_make_kb_entry(
            "acme.com:button:download:btn1", "acme.com", "button", "download",
            "button[data-invoice-download]", "a[aria-label='Download']",
        ))
        entries = await repair_kb_list()
        await rebuild_index(entries)

        query = build_embedding_text(
            "completely-different.com", "input", "fill", "input[name='unrelated']",
        )
        # With a high min_similarity, should get no results
        results = await search_semantic(query, top_k=5, min_similarity=0.99)
        assert len(results) == 0


# --------------------------------------------------------------------------- #
# 3. store_repair computes embeddingText                                       #
# --------------------------------------------------------------------------- #

class TestStoreRepairEmbedding:
    """Tests that store_repair computes and persists embeddingText."""

    @pytest.mark.asyncio
    async def test_store_repair_persists_embedding_text(self, seeded_db, clean_kb):
        """store_repair should compute and store embeddingText on the KB entry."""
        proposal = RepairProposal(
            id="rep_test_001",
            actionId="act_test",
            actionVersion="0.1.0",
            failedSelector="button[data-invoice-download]",
            candidateSelector="a[aria-label='Download PDF']",
            candidateLabel="Download PDF",
            confidence=0.88,
            reason="LLM proposed",
            status=RepairStatus.pending,
            source="llm",
        )

        pattern_key = await store_repair(
            proposal,
            target_domain="acme.com",
            widget_type="button",
            intention="download",
        )
        assert pattern_key is not None

        entry = await repair_kb_get_by_pattern(pattern_key)
        assert entry is not None
        assert entry["embeddingText"]  # should not be empty
        assert "acme.com" in entry["embeddingText"]
        assert "button[data-invoice-download]" in entry["embeddingText"]
        assert "download" in entry["embeddingText"]

    @pytest.mark.asyncio
    async def test_store_repair_rebuilds_index(self, seeded_db, clean_kb):
        """store_repair should rebuild the TF-IDF index so the new entry is searchable."""
        assert get_index_size() == 0  # index is empty before

        proposal = RepairProposal(
            id="rep_test_002",
            actionId="act_test",
            actionVersion="0.1.0",
            failedSelector="button[data-test]",
            candidateSelector="a[aria-label='Test']",
            candidateLabel="Test",
            confidence=0.85,
            reason="LLM proposed",
            status=RepairStatus.pending,
            source="llm",
        )

        await store_repair(
            proposal,
            target_domain="test.com",
            widget_type="button",
            intention="download",
        )

        # Index should now contain the new entry
        assert get_index_size() >= 1


# --------------------------------------------------------------------------- #
# 4. query_kb uses semantic search                                             #
# --------------------------------------------------------------------------- #

class TestQueryKbSemantic:
    """Tests that query_kb uses semantic search and falls back to SQL."""

    @pytest.mark.asyncio
    async def test_query_kb_returns_semantic_match(self, seeded_db, clean_kb):
        """query_kb should return a match from semantic search."""
        # Store a KB entry with high confidence + success
        await _seed_kb_entry(_make_kb_entry(
            "acme.com:button:download:btn1", "acme.com", "button", "download",
            "button[data-invoice-download]", "a[aria-label='Download PDF']",
            confidence=0.92, success_count=5,
        ))
        entries = await repair_kb_list()
        await rebuild_index(entries)

        # Query with a SIMILAR but not identical selector
        failure = RepairFailure(
            action_name="downloadInvoice",
            target_domain="acme.com",
            failed_selector="button[download-invoice]",  # different selector
            error_message="selector not found: button[download-invoice]",
            widget_type="button",
            intention="download",
        )

        proposal = await query_kb(failure)
        assert proposal is not None
        assert proposal.source == "knowledge_base"
        assert "semantic match" in proposal.reason
        assert proposal.candidateSelector == "a[aria-label='Download PDF']"

    @pytest.mark.asyncio
    async def test_query_kb_falls_back_to_sql_when_no_semantic_match(
        self, seeded_db, clean_kb
    ):
        """query_kb should fall back to SQL exact match when semantic search misses."""
        # Store with exact domain/widget/intention but NO embeddingText
        entry = _make_kb_entry(
            "acme.com:button:download:btn-exact", "acme.com", "button", "download",
            "button[data-exact]", "a[aria-label='Exact']",
            confidence=0.90, success_count=3,
        )
        entry["embeddingText"] = ""  # empty embedding text → won't match semantically
        await _seed_kb_entry(entry)
        # Don't rebuild the index — leave it empty
        await rebuild_index([])

        # Query with exact domain/widget/intention match
        failure = RepairFailure(
            action_name="downloadInvoice",
            target_domain="acme.com",
            failed_selector="button[data-exact]",
            error_message="selector not found: button[data-exact]",
            widget_type="button",
            intention="download",
        )

        proposal = await query_kb(failure)
        assert proposal is not None
        assert proposal.source == "knowledge_base"
        assert "exact match" in proposal.reason

    @pytest.mark.asyncio
    async def test_query_kb_returns_none_when_no_match(self, seeded_db, clean_kb):
        """query_kb should return None when no semantic or exact match exists."""
        await rebuild_index([])  # empty index

        failure = RepairFailure(
            action_name="unknownAction",
            target_domain="nonexistent.com",
            failed_selector="button[does-not-exist]",
            error_message="selector not found: button[does-not-exist]",
            widget_type="button",
            intention="generic",
        )

        proposal = await query_kb(failure)
        assert proposal is None

    @pytest.mark.asyncio
    async def test_query_kb_threshold_rejects_low_confidence(self, seeded_db, clean_kb):
        """query_kb should not return entries below the confidence threshold."""
        await _seed_kb_entry(_make_kb_entry(
            "acme.com:button:download:btn-low", "acme.com", "button", "download",
            "button[data-low]", "a[aria-label='Low']",
            confidence=0.50,  # below KB_MIN_CONFIDENCE (0.85)
            success_count=5,
        ))
        entries = await repair_kb_list()
        await rebuild_index(entries)

        failure = RepairFailure(
            action_name="downloadInvoice",
            target_domain="acme.com",
            failed_selector="button[data-low]",
            error_message="selector not found: button[data-low]",
            widget_type="button",
            intention="download",
        )

        proposal = await query_kb(failure)
        assert proposal is None  # confidence too low

    @pytest.mark.asyncio
    async def test_query_kb_threshold_rejects_low_success(self, seeded_db, clean_kb):
        """query_kb should not return entries below the success threshold."""
        await _seed_kb_entry(_make_kb_entry(
            "acme.com:button:download:btn-few", "acme.com", "button", "download",
            "button[data-few]", "a[aria-label='Few']",
            confidence=0.92,
            success_count=1,  # below KB_MIN_SUCCESS (2)
        ))
        entries = await repair_kb_list()
        await rebuild_index(entries)

        failure = RepairFailure(
            action_name="downloadInvoice",
            target_domain="acme.com",
            failed_selector="button[data-few]",
            error_message="selector not found: button[data-few]",
            widget_type="button",
            intention="download",
        )

        proposal = await query_kb(failure)
        assert proposal is None  # success count too low


# --------------------------------------------------------------------------- #
# 5. Cross-client flywheel                                                     #
# --------------------------------------------------------------------------- #

class TestCrossClientFlywheel:
    """Tests that the flywheel works across clients (the core moat)."""

    @pytest.mark.asyncio
    async def test_client_b_gets_client_a_repair_via_semantic_match(
        self, seeded_db, clean_kb
    ):
        """Client B's failure should retrieve Client A's repair via semantic similarity.

        This is the core flywheel test: Client A breaks on selector X, the repair
        is stored. Client B breaks on a different selector Y (but same portal +
        intention), and the semantic search finds Client A's repair.
        """
        # Client A: breaks on 'button[data-invoice-download]', repaired to 'a[aria-label="Download PDF"]'
        await _seed_kb_entry(_make_kb_entry(
            "acme.com:button:download:client-a-failure",
            "acme.com", "button", "download",
            "button[data-invoice-download]",
            "a[aria-label='Download PDF']",
            confidence=0.92, success_count=4,
        ))
        entries = await repair_kb_list()
        await rebuild_index(entries)

        # Client B: breaks on 'button#download-btn' (different selector, same portal)
        failure_b = RepairFailure(
            action_name="downloadInvoice",
            target_domain="acme.com",
            failed_selector="button#download-btn",
            error_message="selector not found: button#download-btn",
            widget_type="button",
            intention="download",
        )

        proposal = await query_kb(failure_b)
        # The flywheel should return Client A's repair
        assert proposal is not None
        assert proposal.source == "knowledge_base"
        assert proposal.candidateSelector == "a[aria-label='Download PDF']"
        assert "semantic" in proposal.reason
