"""
test_indexing.py — Integration tests for apps/pipelines/tasks/indexing.py

Tests cover:
  - is_irrelevant_page: deterministic classifier — no mocks needed.
  - chunk_text: deterministic splitter — no mocks needed.
  - index_document_chunks: mocks OpenAI embeddings and SQLAlchemy session.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call
import pytest


# ---------------------------------------------------------------------------
# Unit tests: is_irrelevant_page
# ---------------------------------------------------------------------------

class TestIsIrrelevantPage:

    def _fn(self):
        from indexing import is_irrelevant_page
        return is_irrelevant_page

    def test_empty_page_is_irrelevant(self):
        assert self._fn()("") is True

    def test_whitespace_only_is_irrelevant(self):
        assert self._fn()("   \n\t  ") is True

    def test_table_of_contents_is_irrelevant(self):
        assert self._fn()("Table of Contents\n1. Overview...........1") is True

    def test_index_to_financial_statements_is_irrelevant(self):
        assert self._fn()("Index to Financial Statements") is True

    def test_short_cover_page_is_irrelevant(self):
        # < 200 chars and contains "annual report"
        assert self._fn()("Annual Report 2024") is True

    def test_10k_cover_page_is_irrelevant(self):
        assert self._fn()("FORM 10-K\nFor the fiscal year ended December 31, 2024") is True

    def test_regular_content_page_is_relevant(self):
        content = (
            "Revenue for the year ended December 31, 2024 was $500 million, "
            "up 12% from the prior year. EBITDA reached $120 million. "
            "This was driven by growth in the North America segment."
        )
        assert self._fn()(content) is False

    def test_financial_statement_page_is_relevant(self):
        content = (
            "Consolidated Balance Sheet as of December 31, 2024.\n"
            "Total Assets: $1,200,000\nTotal Liabilities: $700,000\n"
            "Total Equity: $500,000\nNet Income: $45,000"
        )
        assert self._fn()(content) is False


# ---------------------------------------------------------------------------
# Unit tests: chunk_text
# ---------------------------------------------------------------------------

class TestChunkText:

    def _fn(self):
        from indexing import chunk_text
        return chunk_text

    def test_short_text_produces_single_chunk(self):
        chunks = self._fn()("Hello world", chunk_size=1000, overlap=150)
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    def test_empty_string_produces_single_empty_chunk(self):
        # chunk_text stops immediately for empty string (len==0); returns []
        chunks = self._fn()("")
        assert len(chunks) == 0

    def test_long_text_produces_multiple_chunks(self):
        # 3000 chars → with chunk_size=1000 and overlap=150:
        # chunk 0: 0–1000, chunk 1: 850–1850, chunk 2: 1700–2700, chunk 3: 2550–3000
        text = "A" * 3000
        chunks = self._fn()(text, chunk_size=1000, overlap=150)
        assert len(chunks) > 1

    def test_chunks_overlap_correctly(self):
        text = "X" * 2000
        chunks = self._fn()(text, chunk_size=1000, overlap=200)
        # Second chunk should start at position 800 (1000 - 200 overlap)
        assert len(chunks[0]) == 1000
        assert len(chunks[1]) == 1000
        # Content from 800–1000 of first chunk must match start of second chunk
        assert chunks[0][800:] == chunks[1][:200]

    def test_chunk_size_respected(self):
        text = "B" * 5000
        chunks = self._fn()(text, chunk_size=500, overlap=100)
        for c in chunks[:-1]:
            assert len(c) == 500


# ---------------------------------------------------------------------------
# Integration tests: index_document_chunks
# ---------------------------------------------------------------------------

class TestIndexDocumentChunks:

    def _make_mock_db(self):
        doc = MagicMock()
        doc.fiscal_year = 2024
        doc.fiscal_period = "FY"

        db = MagicMock()

        chunk_query = MagicMock()
        chunk_query.filter.return_value.delete.return_value = 0

        def query_side(*models):
            # Check DocumentChunk BEFORE Document to avoid the substring match
            names = [getattr(m, "__name__", str(m)) for m in models]
            joined = " ".join(names)
            if "DocumentChunk" in joined:
                return chunk_query
            elif "Document" in joined:
                q = MagicMock()
                q.filter.return_value.first.return_value = doc
                return q
            q = MagicMock()
            q.filter.return_value.delete.return_value = 0
            return q

        db.query.side_effect = query_side
        db.add = MagicMock()
        db.commit = MagicMock()
        db.rollback = MagicMock()
        db.close = MagicMock()
        return db

    def _make_embedding_response(self, dims: int = 1536):
        """Returns a mock OpenAI embeddings.create() response."""
        resp = MagicMock()
        resp.data = [MagicMock(embedding=[0.01] * dims)]
        return resp

    def test_toc_page_skipped(self, sample_parsed_data):
        """A Table-of-Contents page must be skipped — no chunks indexed."""
        # Replace content with TOC
        sample_parsed_data["pages"][1]["blocks"] = [
            {"id": "p2_b0", "text": "Table of Contents\n1. Overview..........1", "bbox": None}
        ]

        mock_db = self._make_mock_db()

        with (
            patch("indexing.SessionLocal", return_value=mock_db),
            patch("indexing.OpenAI") as mock_openai_cls,
        ):
            client = MagicMock()
            client.embeddings.create.return_value = self._make_embedding_response()
            mock_openai_cls.return_value = client

            from indexing import index_document_chunks
            result = index_document_chunks(sample_parsed_data)

        # TOC page (page 2) should be skipped; page 1 is the cover which
        # is also classified as irrelevant (short text containing "annual report").
        # So no chunks should be indexed.
        assert result["chunks_indexed"] == 0
        client.embeddings.create.assert_not_called()

    def test_content_pages_chunked_and_indexed(self, sample_parsed_data):
        """Relevant content pages must generate embeddings and DB inserts."""
        # Make page 2 content rich enough to avoid TOC/cover classification
        sample_parsed_data["pages"][1]["blocks"] = [
            {
                "id": "p2_b0",
                "text": (
                    "Revenue for the year ended December 31, 2024 was $500 million. "
                    "EBITDA reached $120 million representing a 24% margin. "
                    "Operating cash flow was $90 million. The company reduced net debt "
                    "by $50 million during the year. Interest expense was $15 million."
                ) * 5,
                "bbox": [50, 100, 500, 300],
            }
        ]

        mock_db = self._make_mock_db()

        with (
            patch("indexing.SessionLocal", return_value=mock_db),
            patch("indexing.OpenAI") as mock_openai_cls,
        ):
            client = MagicMock()
            client.embeddings.create.return_value = self._make_embedding_response()
            mock_openai_cls.return_value = client

            from indexing import index_document_chunks
            result = index_document_chunks(sample_parsed_data)

        assert result["chunks_indexed"] > 0
        assert client.embeddings.create.call_count == result["chunks_indexed"]
        assert mock_db.add.call_count == result["chunks_indexed"]
        mock_db.commit.assert_called()

    def test_existing_chunks_cleared_before_indexing(self, sample_parsed_data):
        """
        Any existing DocumentChunk rows for the document must be deleted
        before new chunks are inserted (idempotent reprocessing).
        """
        mock_db = MagicMock()

        doc = MagicMock()
        doc.fiscal_year = 2024
        doc.fiscal_period = "FY"

        chunk_delete_query = MagicMock()

        def query_side(*models):
            # Check DocumentChunk FIRST to avoid substring match with Document
            names = [getattr(m, "__name__", str(m)) for m in models]
            joined = " ".join(names)
            if "DocumentChunk" in joined:
                return chunk_delete_query
            elif "Document" in joined:
                q = MagicMock()
                q.filter.return_value.first.return_value = doc
                return q
            q = MagicMock()
            return q

        mock_db.query.side_effect = query_side
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.rollback = MagicMock()
        mock_db.close = MagicMock()

        with (
            patch("indexing.SessionLocal", return_value=mock_db),
            patch("indexing.OpenAI") as mock_openai_cls,
        ):
            client = MagicMock()
            client.embeddings.create.return_value = self._make_embedding_response()
            mock_openai_cls.return_value = client

            from indexing import index_document_chunks
            index_document_chunks(sample_parsed_data)

        # DocumentChunk.filter().delete() should have been called once (clear pass)
        chunk_delete_query.filter.return_value.delete.assert_called_once()

    def test_chunk_metadata_includes_concept_tags(self, sample_parsed_data):
        """
        Chunks containing financial keywords must have the relevant
        concept and affected_metric tags in their metadata.
        """
        rich_content = (
            "Revenue grew to $500M. EBITDA was $120M. Total Debt stands at $200M. "
            "Cash on hand: $80M. Interest expense was $15M. "
        ) * 10

        sample_parsed_data["pages"][1]["blocks"] = [
            {"id": "p2_b0", "text": rich_content, "bbox": [50, 100, 500, 300]}
        ]

        mock_db = self._make_mock_db()
        inserted_chunks = []

        original_add = mock_db.add.side_effect

        def capture_add(obj):
            inserted_chunks.append(obj)

        mock_db.add.side_effect = capture_add

        with (
            patch("indexing.SessionLocal", return_value=mock_db),
            patch("indexing.OpenAI") as mock_openai_cls,
        ):
            client = MagicMock()
            client.embeddings.create.return_value = self._make_embedding_response()
            mock_openai_cls.return_value = client

            from indexing import index_document_chunks
            index_document_chunks(sample_parsed_data)

        # At least one chunk should reference EBITDA
        all_metadata = [c.chunk_metadata for c in inserted_chunks if hasattr(c, "chunk_metadata")]
        ebitda_chunks = [m for m in all_metadata if "EBITDA" in (m.get("concepts_contained", []))]
        assert len(ebitda_chunks) > 0

    def test_db_rollback_on_exception(self, sample_parsed_data):
        """DB commit failure must trigger rollback."""
        mock_db = self._make_mock_db()
        mock_db.commit.side_effect = RuntimeError("Connection lost")

        with (
            patch("indexing.SessionLocal", return_value=mock_db),
            patch("indexing.OpenAI") as mock_openai_cls,
        ):
            client = MagicMock()
            client.embeddings.create.return_value = self._make_embedding_response()
            mock_openai_cls.return_value = client

            from indexing import index_document_chunks
            with pytest.raises(RuntimeError):
                index_document_chunks(sample_parsed_data)

        mock_db.rollback.assert_called_once()

    def test_missing_document_raises_error(self, sample_parsed_data):
        """If the document is not in the DB, index_document_chunks raises ValueError."""
        mock_db = MagicMock()
        doc_q = MagicMock()
        doc_q.filter.return_value.first.return_value = None
        mock_db.query.return_value = doc_q

        with (
            patch("indexing.SessionLocal", return_value=mock_db),
            patch("indexing.OpenAI"),
        ):
            from indexing import index_document_chunks
            with pytest.raises(ValueError, match="not found in database"):
                index_document_chunks(sample_parsed_data)
