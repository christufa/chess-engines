"""Drive the playground in a real browser against a running image (real Stockfish):

    docker run -d --read-only --tmpfs /tmp -p 127.0.0.1:8000:8000 chess-engines:ci
    uv run --group browser python tests/browser_smoke.py http://127.0.0.1:8000

Not a pytest module (CI runs it in containers.yml). Fails on any page error or
Content-Security-Policy violation, so the production headers are checked too.
"""

import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge" if sys.platform == "win32" else None, headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(f"page error: {e}"))
    page.on("console", lambda m: m.type == "error" and errors.append(f"console: {m.text}"))
    page.add_init_script(
        "document.addEventListener('securitypolicyviolation',"
        " e => console.error('CSP violation: ' + e.violatedDirective + ' ' + e.blockedURI))"
    )

    # The start position is analysed on load: three ranked lines from Stockfish.
    page.goto(base)
    lines = page.get_by_label("Engine lines")
    expect(lines.locator("li")).to_have_count(3, timeout=30_000)
    expect(page.get_by_text("Stockfish 19").first).to_be_visible()

    # Play the engine's best move from its line; the move list and the analysis follow.
    best = lines.locator("li").first.get_by_role("button").first
    best_san = best.get_attribute("title").removeprefix("Play ")
    best.click()
    expect(page.get_by_label("Moves")).to_contain_text(f"1. {best_san}")
    expect(lines.locator("li")).to_have_count(3, timeout=30_000)
    assert "%20b%20" in page.url, "the URL carries the new position (Black to move)"

    # Maia as the analysis engine: lines show how likely a 1500 player is to play each move.
    page.goto(base)
    expect(lines.locator("li")).to_have_count(3, timeout=30_000)
    page.get_by_label("Engine", exact=True).select_option("maia-1500")
    expect(lines.locator("li").first).to_contain_text("%", timeout=30_000)
    expect(page.get_by_text("Maia 1500").first).to_be_visible()

    # Play against Maia while Stockfish analyses: White plays e4 and Maia answers as Black.
    page.get_by_label("Engine", exact=True).select_option("stockfish")
    page.get_by_label("Play against the engine").select_option("black")
    page.get_by_label("Opponent").select_option("maia-1500")
    page.locator('[data-square="e2"]').click()
    page.locator('[data-square="e4"]').click()
    expect(page.get_by_label("Moves")).to_contain_text("1. e4", timeout=15_000)
    expect(page.get_by_label("Moves").get_by_role("button")).to_have_count(2, timeout=30_000)
    assert "%20w%20" in page.url, "Maia replied, so it is White to move again"
    page.get_by_label("Play against the engine").select_option("off")

    # A shared link with a mated position: no engine call, just the outcome.
    page.goto(base + "/#fen=7k%2F6Q1%2F6K1%2F8%2F8%2F8%2F8%2F8%20b%20-%20-%200%201")
    page.reload()
    expect(page.get_by_text("Checkmate.")).to_be_visible(timeout=15_000)

    Path(".cache").mkdir(exist_ok=True)
    page.goto(base)
    expect(lines.locator("li")).to_have_count(3, timeout=30_000)
    page.screenshot(path=".cache/playground-desktop.png")
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(300)
    overflow = page.evaluate("document.documentElement.scrollWidth - innerWidth")
    assert overflow <= 0, f"horizontal overflow on mobile: {overflow}px"
    page.screenshot(path=".cache/playground-mobile.png", full_page=True)

    assert not errors, errors
    browser.close()
    print("Browser smoke passed: analysis on load, playing an engine move, Maia lines and play, a mated "
          "position, mobile width, no page errors or CSP violations")
