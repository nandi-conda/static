"""Browser test for the example site: build it, serve it, drive it in Chromium.

    pixi run test-e2e   (installs Chromium on the first run)

SHOTS=DIR saves screenshots; CHROMIUM=PATH uses that browser binary.
"""
import os
import re
import sys
import threading

from playwright.sync_api import expect, sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from static import build, ultra_tool  # noqa: E402

SHOTS = os.environ.get("SHOTS")


def run(page, base):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))

    # 1. Prerendered HTML is there before any script runs.
    page.route("**/*.js", lambda r: r.abort())
    page.goto(base + "/posts/how-it-works/")
    assert page.text_content(".page h1") == "How it works"
    assert re.search(r"def page_3\(\) -> None:", page.text_content("pre code"))
    page.unroute("**/*.js")
    errors.clear()  # the aborted scripts

    # 2. With the wasm loaded, the home page hydrates and the island mounts.
    page.goto(base + "/")
    page.wait_for_selector(".island .counter-value")
    assert page.text_content(".page h1") == "Markdown in, WebAssembly out"
    assert page.title() == "static"
    plus = page.locator(".island").get_by_role("button", name="+", exact=True)
    plus.click()
    plus.click()
    expect(page.locator(".counter-value")).to_have_text("2")
    if SHOTS:
        page.screenshot(path=os.path.join(SHOTS, "home.png"), full_page=True)

    # 3. In-app navigation: no reload, URL and title follow.
    page.evaluate("window.__marker = 1")
    page.click("nav a:has-text('Posts')")
    page.wait_for_selector(".listing")
    assert page.url.endswith("/posts/"), page.url
    assert page.title() == "Posts · static"
    assert page.evaluate("window.__marker") == 1, "page reloaded"
    items = page.eval_on_selector_all(".listing a", "as => as.map(a => a.textContent)")
    assert items == ["How it works", "Hello, ultra"], items  # newest first
    assert page.get_attribute("nav a.active", "href") == "/posts/"

    page.click(".listing a:has-text('Hello, ultra')")
    page.wait_for_selector("h1:has-text('Hello, ultra')")
    # a relative .md link resolved to the other post
    page.click(".page a:has-text('how it works')")
    page.wait_for_selector("h1:has-text('How it works')")
    assert page.url.endswith("/posts/how-it-works/"), page.url

    # 4. Back button.
    page.go_back()
    page.wait_for_selector("h1:has-text('Hello, ultra')")
    assert page.evaluate("window.__marker") == 1, "page reloaded on back"

    # 5. Search runs in wasm.
    page.fill(".search input", "backslash")
    page.wait_for_selector(".results a")
    hits = page.eval_on_selector_all(".results a", "as => as.map(a => a.textContent)")
    assert "How it works" in hits, hits
    page.fill(".search input", "zzzz")
    page.wait_for_selector(".results .none:has-text('No matches')")
    page.fill(".search input", "docs")
    page.click(".results a:has-text('Docs')")
    page.wait_for_selector("h1:has-text('Docs')")
    assert page.query_selector(".results") is None

    # 6. Tricky literals made it through LPython intact.
    p = page.text_content(".page p:last-of-type")
    assert "C:\\Users\\v" in p and '"it\'s"' in p, p
    if SHOTS:
        page.screenshot(path=os.path.join(SHOTS, "docs.png"), full_page=True)

    # 7. Island survives a page round trip (re-mounted fresh).
    page.click("nav a:has-text('Home')")
    page.wait_for_selector(".island .counter-value")

    assert errors == [], errors


def main():
    site = os.path.join(ROOT, "example")
    dist = os.path.join(site, "dist")
    build(site, dist)
    srv = ultra_tool().make_server(dist, 0, quiet=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as pw:
            chromium = os.environ.get("CHROMIUM")
            browser = pw.chromium.launch(executable_path=chromium or None)
            run(browser.new_page(), f"http://localhost:{srv.server_address[1]}")
            browser.close()
    finally:
        srv.shutdown()
    print("e2e ok")


if __name__ == "__main__":
    main()
