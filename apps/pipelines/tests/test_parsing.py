"""
test_parsing.py — Integration tests for apps/pipelines/tasks/parsing.py

Tests cover:
  - extract_displayed_page_number: deterministic heuristic — no mocks needed.
  - is_heading: deterministic heuristic — no mocks needed.
  - parse_pdf: mocks MinIO download, fitz (PyMuPDF), and OpenAI Vision OCR.
"""
import sys
import re
from unittest.mock import MagicMock, patch, call
import pytest


# ---------------------------------------------------------------------------
# Unit tests for pure helper functions (no mocks required)
# ---------------------------------------------------------------------------

class TestExtractDisplayedPageNumber:
    """Tests for the footer page-number extraction heuristic."""

    def _make_page(self, blocks: list, height: float = 800.0):
        """Return a mock fitz.Page whose get_text('blocks') returns `blocks`."""
        page = MagicMock()
        page.get_text.return_value = blocks
        return page, height

    def _import_fn(self):
        from parsing import extract_displayed_page_number
        return extract_displayed_page_number

    def test_numeric_page_number_detected(self):
        fn = self._import_fn()
        # Block at y0=750 (above 90% of 800), text "42"
        page, h = self._make_page([(0, 750, 100, 770, "42", 0, 0)], height=800)
        assert fn(page, h) == "42"

    def test_roman_numeral_detected(self):
        fn = self._import_fn()
        page, h = self._make_page([(0, 750, 100, 770, " XIV ", 0, 0)], height=800)
        assert fn(page, h) == "XIV"

    def test_no_footer_block_returns_none(self):
        fn = self._import_fn()
        # Block is in the body (y0=400), not the footer zone
        page, h = self._make_page([(0, 400, 100, 420, "42", 0, 0)], height=800)
        assert fn(page, h) is None

    def test_empty_page_returns_none(self):
        fn = self._import_fn()
        page, h = self._make_page([], height=800)
        assert fn(page, h) is None

    def test_page_prefix_detected(self):
        fn = self._import_fn()
        page, h = self._make_page([(0, 730, 100, 750, "Page 7", 0, 0)], height=800)
        assert fn(page, h) == "7"


class TestIsHeading:
    """Tests for the heading-detection heuristic."""

    def _import_fn(self):
        from parsing import is_heading
        return is_heading

    def test_item_prefix_always_heading(self):
        fn = self._import_fn()
        assert fn("Item 1. Business", 10.0, 10.0, False) is True

    def test_part_prefix_always_heading(self):
        fn = self._import_fn()
        # Regex uses \d+ so Arabic numerals are matched; "Part 2" works, not "Part II"
        assert fn("Part 2", 10.0, 10.0, False) is True

    def test_bold_large_font_is_heading(self):
        fn = self._import_fn()
        # Font size > avg + 1.0 AND bold → heading
        assert fn("Revenue Summary", 14.0, 10.0, True) is True

    def test_bold_same_size_not_heading(self):
        fn = self._import_fn()
        # Bold but same font size → not a heading
        assert fn("Normal Bold Text", 10.0, 10.0, True) is False

    def test_long_text_never_heading(self):
        fn = self._import_fn()
        long = "x" * 101
        assert fn(long, 20.0, 10.0, True) is False

    def test_empty_text_never_heading(self):
        fn = self._import_fn()
        assert fn("", 20.0, 10.0, True) is False


# ---------------------------------------------------------------------------
# Integration test for parse_pdf (external dependencies fully mocked)
# ---------------------------------------------------------------------------

class TestParsePdf:
    """
    Tests parse_pdf() with MinIO and PyMuPDF fully mocked.
    Verifies:
      - StorageService.download_file is called with the correct s3_path.
      - Parsed output has the expected structure (pages, blocks, page numbers).
      - OCR fallback is triggered when a page has < 100 chars.
      - Header/footer blocks are stripped from the body (within top/bottom 5%).
    """

    def _build_fitz_page(
        self,
        *,
        text_blocks: list,
        char_count: int = 500,
        height: float = 800.0,
        width: float = 600.0,
        footer_blocks: list = None,
    ) -> MagicMock:
        """
        Return a mock fitz page whose get_text() calls return appropriate data.
        """
        page = MagicMock()
        page.rect = MagicMock(x0=0, y0=0, x1=width, y1=height)

        # Render to PNG
        pix = MagicMock()
        pix.tobytes.return_value = b"\x89PNG\r\n"  # minimal PNG bytes
        page.get_pixmap.return_value = pix

        # All text blocks (for char count + header/footer extraction)
        all_blocks = (footer_blocks or []) + text_blocks
        page.get_text.side_effect = lambda mode, **kw: (
            all_blocks if mode == "blocks" else {"blocks": []}
        )
        return page

    def test_parse_pdf_basic_structure(self):
        """parse_pdf returns correct document_id, company_id, and page list."""
        with (
            patch("parsing.StorageService") as mock_storage,
            patch("parsing.fitz") as mock_fitz,
            patch("parsing.OpenAI"),
        ):
            mock_storage.download_file.return_value = b"%PDF-1.4"
            mock_storage.upload_file.return_value = None

            # One page with adequate text
            page = self._build_fitz_page(
                text_blocks=[
                    (50, 100, 500, 120, "Revenue was $500M.", 0, 0),
                    (50, 130, 500, 150, "EBITDA was $120M.", 0, 0),
                ],
                char_count=400,
            )
            mock_doc = MagicMock()
            mock_doc.__len__.return_value = 1
            mock_doc.__iter__.return_value = iter([page])
            mock_doc.__getitem__.return_value = page
            mock_fitz.open.return_value = mock_doc

            from parsing import parse_pdf
            result = parse_pdf(document_id=1, company_id=10, s3_path="filings/doc.pdf")

        assert result["document_id"] == 1
        assert result["company_id"] == 10
        assert len(result["pages"]) == 1
        mock_storage.download_file.assert_called_once_with("filings/doc.pdf")

    def test_page_image_uploaded_to_minio(self):
        """Page PNG renders must be uploaded to MinIO with the correct key."""
        with (
            patch("parsing.StorageService") as mock_storage,
            patch("parsing.fitz") as mock_fitz,
            patch("parsing.OpenAI"),
        ):
            mock_storage.download_file.return_value = b"%PDF-1.4"
            mock_storage.upload_file.return_value = None

            page = self._build_fitz_page(
                text_blocks=[(50, 100, 500, 120, "Revenue was $500M." * 20, 0, 0)],
            )
            mock_doc = MagicMock()
            mock_doc.__len__.return_value = 1
            mock_doc.__getitem__.return_value = page
            mock_fitz.open.return_value = mock_doc

            from parsing import parse_pdf
            parse_pdf(document_id=42, company_id=5, s3_path="filings/test.pdf")

        upload_calls = mock_storage.upload_file.call_args_list
        assert len(upload_calls) == 1
        s3_key = upload_calls[0][0][1]  # second positional arg
        assert s3_key == "pages/42/page_1.png"
        assert upload_calls[0][1]["content_type"] == "image/png"

    def test_ocr_fallback_triggered_for_sparse_page(self):
        """When a page has < 100 chars, the OpenAI Vision API should be called."""
        ocr_response = MagicMock()
        ocr_response.choices[0].message.content = "Revenue: 500M\n\nEBITDA: 120M"

        with (
            patch("parsing.StorageService") as mock_storage,
            patch("parsing.fitz") as mock_fitz,
            patch("parsing.OpenAI") as mock_openai_cls,
        ):
            mock_storage.download_file.return_value = b"%PDF-1.4"
            mock_storage.upload_file.return_value = None

            # Sparse page — very few chars to trigger OCR
            page = self._build_fitz_page(
                text_blocks=[(50, 100, 200, 120, "x", 0, 0)],
                char_count=1,
            )
            mock_doc = MagicMock()
            mock_doc.__len__.return_value = 1
            mock_doc.__getitem__.return_value = page
            mock_fitz.open.return_value = mock_doc

            client_instance = MagicMock()
            client_instance.chat.completions.create.return_value = ocr_response
            mock_openai_cls.return_value = client_instance

            from parsing import parse_pdf
            result = parse_pdf(document_id=1, company_id=10, s3_path="filings/doc.pdf")

        assert client_instance.chat.completions.create.called
        # OCR output should have split on double newlines → 2 blocks
        page_blocks = result["pages"][0]["blocks"]
        assert len(page_blocks) == 2
        assert page_blocks[0]["text"] == "Revenue: 500M"

    def test_header_footer_blocks_excluded(self):
        """Blocks in the top 5% or bottom 5% of a page must be removed."""
        with (
            patch("parsing.StorageService") as mock_storage,
            patch("parsing.fitz") as mock_fitz,
            patch("parsing.OpenAI"),
        ):
            mock_storage.download_file.return_value = b"%PDF-1.4"
            mock_storage.upload_file.return_value = None

            height = 800.0
            # Header block: y0 = 10 (< 5% of 800 = 40)
            header = (0, 10, 600, 30, "COMPANY CONFIDENTIAL", 0, 0)
            # Body block: y0 = 100 — should survive
            body = (50, 100, 500, 120, "Revenue was $500M." * 20, 0, 0)
            # Footer block: y1 = 795 (> 95% of 800 = 760)
            footer = (0, 770, 600, 795, "Page 1 of 50", 0, 0)

            page = MagicMock()
            page.rect = MagicMock(x0=0, y0=0, x1=600, y1=height)
            pix = MagicMock()
            pix.tobytes.return_value = b"\x89PNG"
            page.get_pixmap.return_value = pix
            page.get_text.side_effect = lambda mode, **kw: (
                [header, body, footer] if mode == "blocks" else {"blocks": []}
            )

            mock_doc = MagicMock()
            mock_doc.__len__.return_value = 1
            mock_doc.__getitem__.return_value = page
            mock_fitz.open.return_value = mock_doc

            from parsing import parse_pdf
            result = parse_pdf(document_id=1, company_id=10, s3_path="filings/doc.pdf")

        page_result = result["pages"][0]
        texts = [b["text"] for b in page_result["blocks"]]
        assert not any("COMPANY CONFIDENTIAL" in t for t in texts), "Header leaked into blocks"
        assert not any("Page 1 of 50" in t for t in texts), "Footer leaked into blocks"
        assert any("Revenue" in t for t in texts), "Body block was wrongly removed"

    def test_both_page_numbers_carried_forward(self):
        """parse_pdf must populate both page_number (actual) and displayed_page_number."""
        with (
            patch("parsing.StorageService") as mock_storage,
            patch("parsing.fitz") as mock_fitz,
            patch("parsing.OpenAI"),
        ):
            mock_storage.download_file.return_value = b"%PDF-1.4"
            mock_storage.upload_file.return_value = None

            height = 800.0
            body = (50, 100, 500, 120, "Some content " * 20, 0, 0)
            # Footer contains a page number "5"
            footer_label = (0, 740, 100, 760, "5", 0, 0)

            page = MagicMock()
            page.rect = MagicMock(x0=0, y0=0, x1=600, y1=height)
            pix = MagicMock()
            pix.tobytes.return_value = b"\x89PNG"
            page.get_pixmap.return_value = pix
            page.get_text.side_effect = lambda mode, **kw: (
                [body, footer_label] if mode == "blocks" else {"blocks": []}
            )

            mock_doc = MagicMock()
            mock_doc.__len__.return_value = 1
            mock_doc.__getitem__.return_value = page
            mock_fitz.open.return_value = mock_doc

            from parsing import parse_pdf
            result = parse_pdf(document_id=1, company_id=10, s3_path="filings/doc.pdf")

        page_result = result["pages"][0]
        assert page_result["page_number"] == 1          # actual (counted) page
        assert page_result["displayed_page_number"] == "5"  # from footer
