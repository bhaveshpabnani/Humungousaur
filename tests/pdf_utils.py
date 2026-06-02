from __future__ import annotations

import importlib.util
from pathlib import Path


def pdf_dependencies_available() -> bool:
    return bool(importlib.util.find_spec("pypdf") and importlib.util.find_spec("reportlab"))


def write_pdf(path: Path, text: str) -> None:
    from reportlab.pdfgen import canvas

    document = canvas.Canvas(str(path))
    y = 760
    for line in text.splitlines() or [text]:
        document.drawString(72, y, line)
        y -= 18
    document.save()
