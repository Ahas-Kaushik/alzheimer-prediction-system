from __future__ import annotations

from pathlib import Path
from typing import Optional

from backend.utils.logger import get_logger

logger = get_logger(__name__)

_ocr_instance = None


def _get_ocr():
    """Lazy-load PaddleOCR to avoid slow import on server startup."""
    global _ocr_instance
    if _ocr_instance is None:
        try:
            from paddleocr import PaddleOCR
            _ocr_instance = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            logger.info("PaddleOCR initialized")
        except ImportError:
            logger.warning("PaddleOCR not installed — OCR will return empty results")
            _ocr_instance = None
    return _ocr_instance


def extract_text(file_path: str | Path) -> str:
    """Run PaddleOCR on an image or PDF page and return all extracted text.

    Args:
        file_path: Path to an image (PNG/JPG/TIFF) or single-page PDF.

    Returns:
        Concatenated plain text extracted from the document.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Report file not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return _extract_from_pdf(file_path)

    ocr = _get_ocr()
    if ocr is None:
        return ""

    try:
        result = ocr.ocr(str(file_path), cls=True)
        lines: list[str] = []
        for page in result:
            if page is None:
                continue
            for item in page:
                if item and len(item) == 2:
                    text_confidence = item[1]
                    if text_confidence and len(text_confidence) == 2:
                        text = text_confidence[0]
                        if text:
                            lines.append(str(text))
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"OCR extraction failed for {file_path}: {e}")
        return ""


def _extract_from_pdf(pdf_path: Path) -> str:
    """Convert first page of PDF to image then OCR it."""
    try:
        from pdf2image import convert_from_path
        import tempfile

        images = convert_from_path(str(pdf_path), first_page=1, last_page=1)
        if not images:
            return ""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            images[0].save(tmp_path, "PNG")
        text = extract_text(tmp_path)
        tmp_path.unlink(missing_ok=True)
        return text
    except ImportError:
        logger.warning("pdf2image not installed — cannot extract PDF text")
        return ""
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return ""
