from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from backend.utils.logger import get_logger

logger = get_logger(__name__)

_ocr_instance = None
_ocr_init_failed = False


def _get_ocr():
    """Lazy-load PaddleOCR to avoid slow import on server startup.

    Supports both PaddleOCR 2.x (use_angle_cls / show_log) and 3.x
    (use_textline_orientation, no show_log) by only passing constructor
    arguments the installed version actually accepts.
    """
    global _ocr_instance, _ocr_init_failed
    if _ocr_instance is not None or _ocr_init_failed:
        return _ocr_instance
    try:
        import inspect

        from paddleocr import PaddleOCR

        # Disable oneDNN/MKLDNN: some CPUs raise a NotImplementedError
        # (ConvertPirAttribute2RuntimeAttribute) inside Paddle's oneDNN kernels.
        os.environ.setdefault("FLAGS_use_mkldnn", "0")

        accepted = set(inspect.signature(PaddleOCR.__init__).parameters)
        kwargs: dict = {"lang": "en", "enable_mkldnn": False}

        # Speed: with oneDNN/MKLDNN disabled the default *server* models are very
        # slow on CPU (~70s/page). The lightweight *mobile* models are ~3x faster
        # (~25s) with negligible accuracy loss for printed lab reports, and we
        # skip the orientation / doc-unwarp passes (reports are upright).
        if "text_detection_model_name" in accepted:
            kwargs["text_detection_model_name"] = "PP-OCRv5_mobile_det"
            kwargs["text_recognition_model_name"] = "PP-OCRv5_mobile_rec"
        if "use_doc_orientation_classify" in accepted:
            kwargs["use_doc_orientation_classify"] = False
        if "use_doc_unwarping" in accepted:
            kwargs["use_doc_unwarping"] = False
        # Text-line orientation: renamed between 2.x and 3.x. Disable for speed.
        if "use_textline_orientation" in accepted:
            kwargs["use_textline_orientation"] = False
        elif "use_angle_cls" in accepted:
            kwargs["use_angle_cls"] = False
        # show_log only exists in 2.x.
        if "show_log" in accepted:
            kwargs["show_log"] = False

        try:
            _ocr_instance = PaddleOCR(**kwargs)
        except (ValueError, TypeError):
            # Older / different versions may reject some kwargs — retry minimally.
            for k in ("text_detection_model_name", "text_recognition_model_name",
                      "use_doc_orientation_classify", "use_doc_unwarping", "enable_mkldnn"):
                kwargs.pop(k, None)
            _ocr_instance = PaddleOCR(**kwargs)
        logger.info("PaddleOCR initialized (%s)", ", ".join(str(k) for k in kwargs))
    except ImportError:
        logger.warning("PaddleOCR not installed — OCR will return empty results")
        _ocr_init_failed = True
    except Exception as e:  # noqa: BLE001 — never let OCR init crash the request
        logger.error(f"PaddleOCR init failed: {e}")
        _ocr_init_failed = True
    return _ocr_instance


def warmup() -> None:
    """Eagerly initialise the OCR model (call at server startup in a thread)."""
    try:
        _get_ocr()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"OCR warmup skipped: {e}")


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
        # 3.x exposes .predict(); 2.x uses .ocr(). Prefer whichever exists.
        if hasattr(ocr, "predict"):
            try:
                result = ocr.predict(str(file_path))
            except Exception:
                result = ocr.ocr(str(file_path))
        else:
            result = ocr.ocr(str(file_path))
        return "\n".join(_result_to_lines(result))
    except Exception as e:
        logger.error(f"OCR extraction failed for {file_path}: {e}")
        return ""


def _result_to_lines(result) -> list[str]:
    """Flatten a PaddleOCR result into text lines across 2.x and 3.x formats."""
    lines: list[str] = []
    if not result:
        return lines
    for page in result:
        if page is None:
            continue
        # 3.x: each page is a dict-like OCRResult with a 'rec_texts' list.
        rec_texts = None
        if isinstance(page, dict):
            rec_texts = page.get("rec_texts")
        else:
            rec_texts = getattr(page, "get", lambda *_: None)("rec_texts") \
                if hasattr(page, "get") else None
        if rec_texts:
            lines.extend(str(t) for t in rec_texts if t)
            continue
        # 2.x: each page is a list of [box, (text, confidence)] items.
        try:
            for item in page:
                if item and len(item) == 2:
                    text_conf = item[1]
                    if text_conf and len(text_conf) == 2 and text_conf[0]:
                        lines.append(str(text_conf[0]))
        except TypeError:
            continue
    return lines


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
