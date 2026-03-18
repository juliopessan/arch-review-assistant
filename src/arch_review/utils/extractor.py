"""File extraction — extracts architecture text from PDF, images, Mermaid, and plain text."""

from __future__ import annotations

import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


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
        return _extract_image(file_bytes)
    elif ext in (".mmd", ".txt", ".md"):
        return file_bytes.decode("utf-8", errors="replace").strip()
    else:
        # Try plain text as fallback
        try:
            return file_bytes.decode("utf-8", errors="replace").strip()
        except Exception:
            raise ValueError(f"Unsupported file type: {ext}")


def _extract_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF using PyMuPDF. Falls back to OCR if text layer is empty."""
    try:
        import fitz  # pymupdf
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages_text = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()

            if text and len(text) > 50:
                # Good text layer — use directly
                pages_text.append(f"[Page {page_num + 1}]\n{text}")
            else:
                # Scanned page — render and OCR
                logger.info("Page %d has no text layer, attempting OCR", page_num + 1)
                ocr_text = _ocr_page(page)
                if ocr_text:
                    pages_text.append(f"[Page {page_num + 1} - OCR]\n{ocr_text}")

        doc.close()
        result = "\n\n".join(pages_text)
        return _clean_extracted_text(result)

    except ImportError:
        raise ImportError("PyMuPDF not installed. Run: pip install pymupdf")


def _extract_image(file_bytes: bytes) -> str:
    """Extract text from image using pytesseract OCR."""
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(file_bytes))
        # Convert to RGB if needed
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        text = pytesseract.image_to_string(img, config="--psm 6")
        return _clean_extracted_text(text)

    except ImportError:
        raise ImportError(
            "pytesseract not installed or Tesseract OCR not found. "
            "Install: pip install pytesseract && apt-get install tesseract-ocr"
        )


def _ocr_page(page) -> str:
    """Render a PDF page to image and OCR it."""
    try:
        import pytesseract
        from PIL import Image

        # Render at 2x scale for better OCR accuracy
        mat = page.get_pixmap(matrix=page.fitz.Matrix(2, 2))  # type: ignore
        img_bytes = mat.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        return pytesseract.image_to_string(img, config="--psm 6")
    except Exception as exc:
        logger.warning("OCR failed for page: %s", exc)
        return ""


def _clean_extracted_text(text: str) -> str:
    """Clean extracted text for architecture review."""
    import re

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove page headers/footers patterns (single line numbers)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    # Strip leading/trailing whitespace per line
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)
    return text.strip()


def get_supported_formats() -> list[str]:
    """Return list of supported file formats."""
    formats = ["pdf", "txt", "md", "mmd"]
    try:
        import pytesseract  # noqa: F401
        formats += ["png", "jpg", "jpeg", "webp"]
    except ImportError:
        pass
    return formats
