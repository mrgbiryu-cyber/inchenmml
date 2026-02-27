from __future__ import annotations


def render_pdf_from_html(html: str) -> bytes:
    """Render PDF bytes from HTML using WeasyPrint."""
    try:
        from weasyprint import HTML
    except Exception as e:
        raise RuntimeError("WeasyPrint is not installed or unavailable") from e

    return HTML(string=html).write_pdf()
