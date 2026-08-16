import fitz  # PyMuPDF
import re
import base64
import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI
from api.core.config import config
from api.services.storage_service import StorageService

logger = logging.getLogger("pipelines.tasks.parsing")

def extract_displayed_page_number(page, height: float) -> Optional[str]:
    """
    Scans the bottom 10% of the page to locate a page number (digit or Roman numeral).
    """
    blocks = page.get_text("blocks")
    footer_text = ""
    for b in blocks:
        x0, y0, x1, y1, text, block_no, block_type = b
        if y0 > height * 0.90:
            footer_text += " " + text
    
    # Match standard page number patterns (e.g., "Page 12", "12", "ix", "IV")
    match = re.search(r'\b(?:page\s+)?([0-9a-f-ivxldcm]+)\b', footer_text.lower().strip())
    if match:
        val = match.group(1).upper()
        if re.match(r'^[0-9]+$', val) or re.match(r'^[IVXLCDM]+$', val):
            return val
    return None


def is_heading(text: str, font_size: float, avg_font_size: float, is_bold: bool) -> bool:
    """
    Heuristics to determine if a block of text represents a section heading.
    """
    text_clean = text.strip()
    if not text_clean or len(text_clean) > 100:
        return False
    
    # Match standard financial report section identifiers
    if re.match(r'^(?:item|part|note)\s+\d+[a-z]?\b', text_clean.lower()):
        return True
        
    # Bold and larger than average font size
    if is_bold and font_size > avg_font_size + 1.0:
        return True
        
    return False


def parse_pdf(document_id: int, company_id: int, s3_path: str) -> Dict[str, Any]:
    """
    Parses a PDF filing from MinIO.
    Renders pages to PNG, extracts text blocks, filters headers/footers,
    extracts heading paths, and uses OpenAI Vision OCR fallback when needed.
    """
    logger.info(f"Starting PDF parsing task for document_id {document_id}, s3_path {s3_path}")
    
    # 1. Download PDF bytes from MinIO
    try:
        pdf_bytes = StorageService.download_file(s3_path)
    except Exception as e:
        logger.error(f"Failed to download PDF from S3: {e}")
        raise e

    # 2. Open PDF with PyMuPDF
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
    
    parsed_pages = []
    current_section_path = []
    
    # Iterate through all pages
    for page_idx in range(len(doc)):
        page_num = page_idx + 1
        page = doc[page_idx]
        rect = page.rect
        width, height = rect.x1 - rect.x0, rect.y1 - rect.y0
        
        # A. Render and upload page image to MinIO
        pix = page.get_pixmap(dpi=150)
        png_bytes = pix.tobytes("png")
        page_s3_key = f"pages/{document_id}/page_{page_num}.png"
        try:
            StorageService.upload_file(png_bytes, page_s3_key, content_type="image/png")
        except Exception as e:
            logger.warning(f"Failed to upload rendered page image for page {page_num}: {e}")
            
        # B. Extract text blocks and determine if OCR fallback is needed
        # PyMuPDF 'blocks' format: (x0, y0, x1, y1, "text", block_no, block_type)
        raw_blocks = page.get_text("blocks")
        
        # Calculate selectable text length
        total_text = "".join([b[4] for b in raw_blocks if b[6] == 0])
        char_count = len(total_text.strip())
        
        blocks_data = []
        displayed_page_number = extract_displayed_page_number(page, height)
        
        # If selectable text is extremely short, perform OpenAI Vision API OCR fallback
        if char_count < 100:
            logger.info(f"Page {page_num} has only {char_count} chars. Triggering OpenAI Vision OCR fallback...")
            base64_image = base64.b64encode(png_bytes).decode("utf-8")
            try:
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text", 
                                    "text": (
                                        "Extract all text from this page image. Preserve reading order and layout. "
                                        "Do not output markdown, just output the plain text blocks separated by double newlines."
                                    )
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                                }
                            ]
                        }
                    ],
                    temperature=0.0
                )
                ocr_text = response.choices[0].message.content or ""
                # Split OCR text into paragraph blocks
                paragraphs = [p.strip() for p in ocr_text.split("\n\n") if p.strip()]
                for p_idx, p_text in enumerate(paragraphs):
                    blocks_data.append({
                        "id": f"p{page_num}_b{p_idx}",
                        "text": p_text,
                        "bbox": None
                    })
            except Exception as e:
                logger.error(f"OCR fallback failed on page {page_num}: {e}")
        else:
            # Normal PyMuPDF parsing
            # First, compute average font size for heading heuristics
            font_sizes = []
            # Extract detailed text spans to inspect fonts/sizes
            text_info = page.get_text("dict")
            for block in text_info.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        font_sizes.append(span.get("size", 10.0))
            avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 10.0
            
            block_idx = 0
            for b in raw_blocks:
                x0, y0, x1, y1, text, block_no, block_type = b
                if block_type != 0:  # Skip image blocks
                    continue
                
                # Header/Footer Removal: ignore elements in top 5% and bottom 5%
                if y0 < height * 0.05 or y1 > height * 0.95:
                    continue
                
                text_clean = text.strip()
                if not text_clean:
                    continue
                
                # Check if this block is a heading to update the section path
                # Inspect font properties of the first span in this block
                is_bold_block = False
                font_size_block = 10.0
                for block_dict in text_info.get("blocks", []):
                    # Match block coordinates roughly
                    bx0, by0, bx1, by1 = block_dict.get("bbox", (0,0,0,0))
                    if abs(bx0 - x0) < 5 and abs(by0 - y0) < 5:
                        for line in block_dict.get("lines", []):
                            for span in line.get("spans", []):
                                font_size_block = span.get("size", 10.0)
                                if "bold" in span.get("font", "").lower():
                                    is_bold_block = True
                                break
                            break
                        break
                
                if is_heading(text_clean, font_size_block, avg_font_size, is_bold_block):
                    # Update hierarchy
                    # If it's a top-level section (Item, Part), replace hierarchy
                    if re.match(r'^(?:item|part)\s+\d+[a-z]?\b', text_clean.lower()):
                        current_section_path = [text_clean]
                    else:
                        # Append to current hierarchy, keeping max 3 levels deep
                        if len(current_section_path) >= 3:
                            current_section_path = current_section_path[:2]
                        current_section_path.append(text_clean)
                
                blocks_data.append({
                    "id": f"p{page_num}_b{block_idx}",
                    "text": text_clean,
                    "bbox": [x0, y0, x1, y1]
                })
                block_idx += 1
                
        section_path_str = " > ".join(current_section_path) if current_section_path else ""
        
        parsed_pages.append({
            "page_number": page_num,
            "displayed_page_number": displayed_page_number,
            "section_path": section_path_str,
            "blocks": blocks_data
        })

    doc.close()
    logger.info(f"PDF parsing complete. Extracted {len(parsed_pages)} pages.")
    
    return {
        "document_id": document_id,
        "company_id": company_id,
        "pages": parsed_pages
    }
