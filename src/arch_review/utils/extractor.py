"""File extraction — extracts architecture text from PDF, images, Mermaid, and plain text."""

from __future__ import annotations

import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Check tesseract availability once at import time — no warnings if missing
_TESSERACT_AVAILABLE = False
try:
    import pytesseract
    pytesseract.get_tesseract_version()  # actually checks if binary exists
    _TESSERACT_AVAILABLE = True
except Exception:
    pass  # Tesseract not installed — OCR features silently disabled


def extract_from_bytes(file_bytes: bytes, filename: str) -> str:
    """
    Extract text from uploaded file bytes.
    Supports: .pdf, .png, .jpg, .jpeg, .mmd, .txt, .md
    Returns cleaned text ready for architecture review.
    """
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        return _extract_pdf(file_bytes)
    elif ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"):
        if not _TESSERACT_AVAILABLE:
            raise ValueError(
                "Image OCR requires Tesseract. Install it with:\n"
                "  macOS:  brew install tesseract\n"
                "  Ubuntu: apt-get install tesseract-ocr\n"
                "  Windows: https://github.com/UB-Mannheim/tesseract/wiki"
            )
        return _extract_image(file_bytes)
    elif ext in (".mmd", ".txt", ".md"):
        return file_bytes.decode("utf-8", errors="replace").strip()
    else:
        try:
            return file_bytes.decode("utf-8", errors="replace").strip()
        except Exception:
            raise ValueError(f"Unsupported file type: {ext}")


def get_supported_formats() -> list[str]:
    """Return list of supported file formats based on available libraries."""
    formats = ["pdf", "txt", "md", "mmd"]
    if _TESSERACT_AVAILABLE:
        formats += ["png", "jpg", "jpeg", "webp"]
    return formats


def _extract_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF using PyMuPDF. Falls back to OCR if text layer is empty."""
    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages_text = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()

            if text and len(text) > 50:
                pages_text.append(f"[Page {page_num + 1}]\n{text}")
            elif _TESSERACT_AVAILABLE:
                logger.info("Page %d has no text layer, attempting OCR", page_num + 1)
                ocr_text = _ocr_pdf_page(page)
                if ocr_text:
                    pages_text.append(f"[Page {page_num + 1} - OCR]\n{ocr_text}")
            else:
                logger.debug("Page %d has no text layer, skipping (Tesseract not available)", page_num + 1)

        doc.close()
        result = "\n\n".join(pages_text)
        if not result.strip():
            raise ValueError("No text could be extracted from this PDF. It may be a scanned document — install Tesseract for OCR support.")
        return _clean(result)

    except ImportError:
        raise ImportError("PyMuPDF not installed. Run: pip install pymupdf")


def _extract_image(file_bytes: bytes) -> str:
    """Extract text from image using pytesseract OCR."""
    import pytesseract
    from PIL import Image
    img = Image.open(io.BytesIO(file_bytes))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    text = pytesseract.image_to_string(img, config="--psm 6")
    return _clean(text)


def _ocr_pdf_page(page) -> str:
    """Render a PDF page to image and OCR it."""
    try:
        import fitz, pytesseract
        from PIL import Image
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img, config="--psm 6")
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return ""


def _clean(text: str) -> str:
    """Clean extracted text."""
    import re
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()

