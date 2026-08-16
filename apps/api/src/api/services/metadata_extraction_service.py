import re
import logging
import fitz  # PyMuPDF
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator
from openai import OpenAI
import instructor
from api.core.config import config

logger = logging.getLogger("api.services.metadata_extraction_service")

class ExtractedMetadata(BaseModel):
    company_name: str = Field(..., description="The full corporate name of the company, e.g. Acme Corp, Apple Inc.")
    fiscal_year: int = Field(..., description="The fiscal year in YYYY format, e.g. 2026")
    fiscal_period: str = Field(..., description="The fiscal period, must be Q1, Q2, Q3, Q4 or FY<YEAR_2_DIGITS> (e.g. FY26)")
    document_type: Literal["10-K", "10-Q", "Annual Report"] = Field(..., description="Must be '10-K', '10-Q', or 'Annual Report'")

    @field_validator("fiscal_year")
    @classmethod
    def validate_year(cls, v: int) -> int:
        if v < 1900 or v > 2100:
            raise ValueError("Fiscal year must be between 1900 and 2100")
        return v

    @field_validator("fiscal_period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        v = v.strip().upper()
        # Normalise FY2026 to FY26
        match = re.match(r"^FY(\d{4})$", v)
        if match:
            v = f"FY{match.group(1)[2:]}"
        # Normalise FY 26 to FY26
        v = v.replace(" ", "")

        if re.match(r"^Q[1-4]$", v) or re.match(r"^FY\d{2}$", v):
            return v
        raise ValueError("Fiscal period must be one of Q1, Q2, Q3, Q4 or FY<YY>")


class MetadataExtractionService:
    @classmethod
    def extract_text_from_first_pages(cls, file_bytes: bytes, max_pages: int = 3) -> str:
        """
        Extract text from the first N pages of the PDF.
        """
        text = ""
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for i in range(min(max_pages, len(doc))):
                text += f"\n--- Page {i + 1} ---\n"
                text += doc[i].get_text()
            doc.close()
        except Exception as e:
            logger.error(f"Error extracting text from PDF pages: {e}")
        return text

    @classmethod
    def extract_metadata(cls, file_bytes: bytes) -> ExtractedMetadata:
        """
        Runs GPT-4o-mini structured extraction on the first 3 pages of the PDF.
        """
        text = cls.extract_text_from_first_pages(file_bytes, max_pages=3)
        if not text.strip():
            logger.warning("No text could be extracted from PDF pages. Sending empty prompt to OpenAI.")

        # Initialize OpenAI client with instructor
        openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
        instructor_client = instructor.from_openai(openai_client)

        logger.info("Calling OpenAI gpt-4o-mini for structured metadata extraction...")
        
        # Call chat completion with response_model
        extracted: ExtractedMetadata = instructor_client.chat.completions.create(
            model="gpt-4o-mini",
            response_model=ExtractedMetadata,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert credit underwriting analyst. Your job is to extract corporate filing "
                        "metadata from the beginning of the filing document.\n"
                        "Locate the full corporate name of the company, the fiscal year, the fiscal period, "
                        "and the type of document (10-K, 10-Q, or Annual Report)."
                    )
                },
                {
                    "role": "user",
                    "content": f"Extract filing metadata from the following PDF text:\n\n{text}"
                }
            ],
            temperature=0.0,
            max_retries=3
        )
        logger.info(f"Extracted metadata: {extracted}")
        return extracted
