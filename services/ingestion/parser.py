"""Two-path PDF parsing: PyMuPDF for native PDFs, OCR for scanned ones.

Document type detection: if the PDF has a usable text layer we take the
PyMuPDF path (faster, more accurate). If a page has no extractable text it
is treated as scanned and routed through OCR. PaddleOCR is an optional
dependency; when it is not installed, scanned pages raise a clear error
instead of silently producing empty output.

Output is structured JSON: a list of text blocks with the section header
each block falls under, mirroring the layout-metadata JSON written to blob
storage in production.
"""

import re

import fitz  # PyMuPDF

try:
    from paddleocr import PaddleOCR

    _ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
except ImportError:
    _ocr = None


class ScannedPDFError(RuntimeError):
    pass


def detect_document_type(doc: fitz.Document) -> str:
    """A PDF is 'native' if any page has a real text layer."""
    for page in doc:
        if page.get_text().strip():
            return "native"
    return "scanned"


_HEADING_RE = re.compile(r"^(\d+[\.\)]\s+|[A-Z][A-Z\s\-&]{3,}$|ARTICLE\s+)", re.MULTILINE)


def _looks_like_heading(text: str, span_size: float, body_size: float) -> bool:
    text = text.strip()
    if not text or len(text) > 80:
        return False
    if span_size > body_size + 1.0:
        return True
    return bool(_HEADING_RE.match(text)) and not text.endswith(".")


def _parse_native(doc: fitz.Document) -> list[dict]:
    # First pass: find the dominant (body) font size.
    sizes: dict[float, int] = {}
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    n = len(span["text"].strip())
                    if n:
                        sizes[round(span["size"], 1)] = sizes.get(round(span["size"], 1), 0) + n
    body_size = max(sizes, key=sizes.get) if sizes else 11.0

    blocks = []
    section = "Preamble"
    for page_num, page in enumerate(doc, start=1):
        for block in page.get_text("dict")["blocks"]:
            lines = block.get("lines", [])
            if not lines:
                continue
            text = " ".join(
                span["text"] for line in lines for span in line["spans"]
            ).strip()
            if not text:
                continue
            max_size = max(span["size"] for line in lines for span in line["spans"])
            if _looks_like_heading(text, max_size, body_size):
                section = re.sub(r"^\d+[\.\)]\s+", "", text).strip()
                continue
            blocks.append({"page": page_num, "section_label": section, "text": text})
    return blocks


def _parse_scanned(doc: fitz.Document) -> list[dict]:
    if _ocr is None:
        raise ScannedPDFError(
            "This PDF has no text layer and requires OCR, but PaddleOCR is not "
            "installed. Install it with: pip install paddleocr paddlepaddle"
        )
    blocks = []
    for page_num, page in enumerate(doc, start=1):
        pix = page.get_pixmap(dpi=200)
        result = _ocr.ocr(pix.tobytes("png"), cls=True)
        text = " ".join(line[1][0] for line in (result[0] or []))
        if text.strip():
            blocks.append({"page": page_num, "section_label": "OCR", "text": text})
    return blocks


def parse_pdf(path: str) -> dict:
    """Parse a PDF into structured JSON (text blocks + layout metadata)."""
    doc = fitz.open(path)
    doc_type = detect_document_type(doc)
    blocks = _parse_native(doc) if doc_type == "native" else _parse_scanned(doc)
    return {"source_file": path.split("/")[-1], "document_type": doc_type, "blocks": blocks}
