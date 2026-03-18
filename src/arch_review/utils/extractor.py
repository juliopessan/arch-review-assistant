"""File extraction — extracts architecture text from PDF, images, Mermaid, and plain text.

Tesseract OCR is REQUIRED for this project. Install it before running:
  macOS:  brew install tesseract
  Ubuntu: sudo apt-get install tesseract-ocr
  Windows: https://github.com/UB-Mannheim/tesseract/wiki
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Tesseract required check ───────────────────────────────────────────────────
def _check_tesseract() -> None:
    """Verify Tesseract is installed. Raise with clear install instructions if not."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
    except Exception:
        raise EnvironmentError(
            "\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "  Tesseract OCR is required for arch-review.\n"
            "  Install it with ONE of the following commands:\n\n"
            "  macOS:   brew install tesseract\n"
            "  Ubuntu:  sudo apt-get install tesseract-ocr\n"
            "  Windows: https://github.com/UB-Mannheim/tesseract/wiki\n\n"
            "  Then restart the app.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )

# Run check at module load — fail fast and clearly
_check_tesseract()


# ── Public API ─────────────────────────────────────────────────────────────────

SUPPORTED_FORMATS = ["pdf", "png", "jpg", "jpeg", "webp", "bmp", "tiff", "txt", "md", "mmd"]


def extract_from_bytes(file_bytes: bytes, filename: str) -> str:
    """
    Extract text from uploaded file bytes.
    Supports: .pdf (text + OCR), images (OCR), .txt, .md, .mmd
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
        try:
            return file_bytes.decode("utf-8", errors="replace").strip()
        except Exception:
            raise ValueError(f"Unsupported file type: {ext}. Supported: {', '.join(SUPPORTED_FORMATS)}")


def get_supported_formats() -> list[str]:
    return SUPPORTED_FORMATS


# ── Extractors ─────────────────────────────────────────────────────────────────

def _extract_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF. Uses text layer if available, OCR for scanned pages."""
    try:
        import fitz
    except ImportError:
        raise ImportError("PyMuPDF not installed. Run: pip install pymupdf")

    import pytesseract
    from PIL import Image

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages_text = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()

        if text and len(text) > 50:
            # Native text layer — fast and accurate
            pages_text.append(f"[Page {page_num + 1}]\n{text}")
        else:
            # Scanned page — render at 2x and OCR
            logger.info("Page %d: no text layer, using OCR", page_num + 1)
            try:
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr_text = pytesseract.image_to_string(img, config="--psm 6").strip()
                if ocr_text:
                    pages_text.append(f"[Page {page_num + 1} — OCR]\n{ocr_text}")
            except Exception as exc:
                logger.warning("OCR failed on page %d: %s", page_num + 1, exc)

    doc.close()

    result = "\n\n".join(pages_text)
    if not result.strip():
        raise ValueError(
            "No text extracted from PDF. "
            "The document may be corrupted or contain only non-text content."
        )
    return _clean(result)


def _extract_image(file_bytes: bytes) -> str:
    """Extract text from image via Tesseract OCR."""
    import pytesseract
    from PIL import Image

    img = Image.open(io.BytesIO(file_bytes))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    text = pytesseract.image_to_string(img, config="--psm 6")
    result = _clean(text)
    if not result:
        raise ValueError("No text found in image. Make sure the image contains readable architecture diagrams or text.")
    return result


def _clean(text: str) -> str:
    """Remove noise from extracted text."""
    import re
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


