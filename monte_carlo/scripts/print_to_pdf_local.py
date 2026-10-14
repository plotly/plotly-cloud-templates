"""Local stand-in for Dash Enterprise's `print-to-pdf` executable.

Development only. On Dash Enterprise, Snapshot Engine calls DE's own
print-to-pdf service and this file is never used.

Snapshot Engine pipes a JSON request to the executable on stdin and reads the
PDF bytes from stdout. Point it here with:

    PRINT_TO_PDF_EXECUTABLE_PATH=".venv/bin/python scripts/print_to_pdf_local.py"

Requires `pip install playwright` (see requirements-dev.txt). It drives the
locally installed Google Chrome, so no browser download is needed.
"""

import json
import sys

from playwright.sync_api import sync_playwright

PAPER_SIZES = {"Letter", "A3", "A4", "A5", "Legal", "Tabloid"}


def main() -> None:
    request = json.loads(sys.stdin.buffer.read())
    options = request.get("pdf_options", {})
    wait_ms = int(float(request.get("wait_time") or 20) * 1000)

    pdf_kwargs = {
        "landscape": bool(options.get("landscape")),
        "print_background": True,
        "prefer_css_page_size": True,
    }
    page_size = options.get("pageSize") or "Letter"
    if page_size in PAPER_SIZES:
        pdf_kwargs["format"] = page_size
    if options.get("marginsType", 1) == 1:
        pdf_kwargs["margin"] = {"top": "0", "right": "0", "bottom": "0", "left": "0"}

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(
            extra_http_headers=request.get("http_headers") or {},
            viewport={"width": 1280, "height": 1000},
        )
        page.goto(request["url"], wait_until="networkidle", timeout=wait_ms)
        # The report is ready once Dash has rendered every Plotly graph in it.
        page.wait_for_function(
            """() => {
                const graphs = document.querySelectorAll('.pricing-report .dash-graph');
                return graphs.length > 0 && [...graphs].every(g => g.querySelector('.main-svg'));
            }""",
            timeout=wait_ms,
        )
        page.emulate_media(media="print")
        pdf = page.pdf(**pdf_kwargs)
        browser.close()

    sys.stdout.buffer.write(pdf)


if __name__ == "__main__":
    main()
