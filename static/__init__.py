"""static: a static site generator on ultra.

  static build [SITE] [-o DIST] [--drafts]   markdown -> one ultra app + prerendered HTML
  static serve [SITE] [--port 8000]          build, serve DIST, rebuild on change
  static new DIR                             start a site from the example

A site is a folder with site.toml, content/**/*.md, and optionally static/
(copied as is) and islands/*.py (interactive ultra apps embedded in pages with
<ultra-island name="..."></ultra-island>).

All pages compile into a single LPython app (codegen.py), so after the first
load, moving between pages is an ultra update and a DOM patch. Every page is
also prerendered to plain HTML by running that same wasm in Node, so the site
reads fine without JavaScript and search engines see the content.
"""

import argparse
import html
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from email.utils import formatdate

from .codegen import POP, generate
from .content import load_site

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
EXAMPLE = os.path.join(os.path.dirname(HERE), "example")


def ultra_tool():
    """The ultra build tool: the `ultra` conda package's ultra_tool module, or a
    checkout of github.com/nandi-conda/ultra named by $ULTRA_HOME."""
    home = os.environ.get("ULTRA_HOME")
    if home:
        spec = importlib.util.spec_from_file_location("ultra_tool", os.path.join(home, "tools", "ultra.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    try:
        import ultra_tool
        return ultra_tool
    except ImportError:
        sys.exit("ultra not found: add the `ultra` package from https://prefix.dev/nandi-testing, "
                 "or set ULTRA_HOME to a checkout of github.com/nandi-conda/ultra")


PAGE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<link rel="preload" href="{base}app.wasm" as="fetch" type="application/wasm" crossorigin>
<link rel="icon" href="{base}favicon.svg">
<link rel="stylesheet" href="{base}ui.css">
<link rel="stylesheet" href="{base}style.css">
<link rel="alternate" type="application/rss+xml" title="{site}" href="{base}feed.xml">
</head>
<body>
<div id="app">{body}</div>
<script type="module" src="{base}site.js"></script>
</body>
</html>
"""


def page_title(site, p):
    return site.title if p.index == 0 else f"{p.title} · {site.title}"


def build(site_dir, dist, drafts=False, quiet=False):
    t0 = time.time()
    site = load_site(site_dir, drafts)
    tool = ultra_tool()
    islands_dir = os.path.join(site_dir, "islands")
    islands = sorted(f[:-3] for f in os.listdir(islands_dir) if f.endswith(".py")) \
        if os.path.isdir(islands_dir) else []
    src = generate(site, islands)

    if os.path.isdir(dist):
        shutil.rmtree(dist)
    os.makedirs(dist)
    gen_dir = os.path.join(site_dir, ".static")
    os.makedirs(gen_dir, exist_ok=True)
    app = os.path.join(gen_dir, "app.py")
    with open(app, "w", encoding="utf-8") as f:
        f.write(src)
    tool.build_app(app, os.path.join(dist, "app.wasm"))
    for name in islands:
        os.makedirs(os.path.join(dist, "islands"), exist_ok=True)
        tool.build_app(os.path.join(islands_dir, name + ".py"),
                       os.path.join(dist, "islands", name + ".wasm"))
    shutil.rmtree(os.path.join(dist, "islands", "__pycache__"), ignore_errors=True)
    for extra in ("ultra.js", "ui.css"):  # build_app drops these next to each wasm
        if islands:
            os.remove(os.path.join(dist, "islands", extra))

    r = subprocess.run(["node", os.path.join(ASSETS, "prerender.mjs"), os.path.join(dist, "app.wasm"),
                        str(len(site.pages)), str(POP)], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("prerender failed:\n" + r.stderr)
    bodies = json.loads(r.stdout)

    base = site.base
    routes = [{"url": base + p.url.lstrip("/"), "title": page_title(site, p)} for p in site.pages]
    with open(os.path.join(dist, "routes.js"), "w") as f:
        f.write(f"export const base = {json.dumps(base)};\nexport const POP = {POP};\n"
                f"export const pages = {json.dumps(routes, ensure_ascii=False, indent=1)};\n")
    shutil.copy(os.path.join(ASSETS, "site.js"), dist)
    for f in ("style.css", "favicon.svg"):
        shutil.copy(os.path.join(ASSETS, f), dist)

    lang = site.config.get("lang", "en")
    for p, body in zip(site.pages, bodies):
        desc = p.meta.get("description") or (p.text[:157] + "…" if len(p.text) > 160 else p.text)
        out = os.path.join(dist, p.url.strip("/"), "index.html")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(PAGE.format(lang=lang, title=html.escape(page_title(site, p)),
                                desc=html.escape(desc), base=base, site=html.escape(site.title),
                                body=body))
    write_404(site, dist)
    write_feeds(site, dist)

    static = os.path.join(site_dir, "static")
    if os.path.isdir(static):
        shutil.copytree(static, dist, dirs_exist_ok=True)
    if not quiet:
        size = os.path.getsize(os.path.join(dist, "app.wasm"))
        print(f"built {len(site.pages)} pages, {len(islands)} islands into {dist} "
              f"(app.wasm {size / 1024:.1f} KB) in {time.time() - t0:.1f}s")
    return site


def write_404(site, dist):
    home = open(os.path.join(dist, "index.html"), encoding="utf-8").read()
    # The home page's shell, but site.js picks the page from the URL; unknown URLs land home.
    with open(os.path.join(dist, "404.html"), "w", encoding="utf-8") as f:
        f.write(home)


def write_feeds(site, dist):
    url = site.config.get("url", "").rstrip("/")
    full = lambda p: url + site.base + p.url.lstrip("/")
    with open(os.path.join(dist, "sitemap.xml"), "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for p in site.pages:
            f.write(f"  <url><loc>{html.escape(full(p))}</loc></url>\n")
        f.write("</urlset>\n")
    posts = sorted((p for p in site.pages if p.date), key=lambda p: p.date, reverse=True)
    with open(os.path.join(dist, "feed.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>\n'
                f"<title>{html.escape(site.title)}</title><link>{html.escape(url + site.base)}</link>\n"
                f"<description>{html.escape(site.config.get('description', site.title))}</description>\n")
        for p in posts[:20]:
            try:
                when = formatdate(time.mktime(time.strptime(p.date[:10], "%Y-%m-%d")))
            except ValueError:
                when = ""
            f.write(f"<item><title>{html.escape(p.title)}</title><link>{html.escape(full(p))}</link>"
                    f"<guid>{html.escape(full(p))}</guid><pubDate>{when}</pubDate>"
                    f"<description>{html.escape(p.meta.get('description', p.text[:300]))}</description></item>\n")
        f.write("</channel></rss>\n")


def snapshot(site_dir):
    out = {}
    for d in ("content", "static", "islands"):
        for root, _, files in os.walk(os.path.join(site_dir, d)):
            for n in files:
                p = os.path.join(root, n)
                out[p] = os.path.getmtime(p)
    cfg = os.path.join(site_dir, "site.toml")
    if os.path.exists(cfg):
        out[cfg] = os.path.getmtime(cfg)
    return out


def serve(site_dir, dist, port, drafts):
    tool = ultra_tool()
    build(site_dir, dist, drafts)

    def watch():
        last = snapshot(site_dir)
        while True:
            time.sleep(0.5)
            now = snapshot(site_dir)
            if now != last:
                last = now
                try:
                    build(site_dir, dist, drafts)
                except SystemExit as e:
                    print(f"build failed: {e}", file=sys.stderr)

    threading.Thread(target=watch, daemon=True).start()
    srv = tool.make_server(dist, port)
    handler = srv.RequestHandlerClass

    class Handler(handler):  # serve 404.html for unknown paths, like a static host
        def send_error(self, code, message=None, explain=None):
            page = os.path.join(dist, "404.html")
            if code == 404 and os.path.exists(page):
                body = open(page, "rb").read()
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                super().send_error(code, message, explain)

    srv.RequestHandlerClass = Handler
    print(f"serving {dist} on http://localhost:{srv.server_address[1]} (rebuilds on change)")
    srv.serve_forever()


def new(target):
    if os.path.exists(target) and os.listdir(target):
        sys.exit(f"{target} exists and is not empty")
    shutil.copytree(EXAMPLE, target, ignore=shutil.ignore_patterns(".static", "dist"),
                    dirs_exist_ok=True)
    print(f"new site in {target}: run `static serve {target}`")


def main(argv=None):
    p = argparse.ArgumentParser(prog="static", description="static site generator on ultra")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("build", "serve"):
        s = sub.add_parser(name)
        s.add_argument("site", nargs="?", default=".")
        s.add_argument("-o", "--out", help="output folder (default SITE/dist)")
        s.add_argument("--drafts", action="store_true", help="include pages with draft: true")
        if name == "serve":
            s.add_argument("--port", type=int, default=8000)
    n = sub.add_parser("new")
    n.add_argument("dir")
    a = p.parse_args(argv)
    if a.cmd == "new":
        return new(a.dir)
    dist = os.path.abspath(a.out or os.path.join(a.site, "dist"))
    if a.cmd == "build":
        build(os.path.abspath(a.site), dist, a.drafts)
    else:
        serve(os.path.abspath(a.site), dist, a.port, a.drafts)
