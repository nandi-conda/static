# static

A static site generator on [ultra](https://github.com/nandi-conda/ultra), the Elm-style
frontend framework whose apps are LPython compiled to WebAssembly.

Markdown goes in. Out comes a site where **every page is prerendered HTML** (fast first paint,
works without JavaScript, crawlable) and **the whole site is also one ultra app** (`app.wasm`,
about 19 KB for the example), so once it loads, links between pages are ultra messages and DOM
patches instead of page loads. The header search runs in wasm too, and pages can embed
**islands**: small interactive ultra apps of their own.

Install the command from the [`nandi-testing`](https://prefix.dev/channels/nandi-testing) channel:

```sh
pixi global install --channel https://prefix.dev/nandi-testing --channel conda-forge static
static new mysite && static serve mysite
```

Or from a checkout:

```sh
pixi run serve            # example site on http://localhost:8000, rebuilds on change
pixi run build            # writes example/dist
pixi run new mysite       # start your own site from the example
pixi run python -m static serve mysite
```

`ultra` comes from the [`nandi-testing`](https://prefix.dev/channels/nandi-testing/packages/ultra)
channel on prefix.dev (it brings LPython 0.22 from conda-forge); see `pixi.toml`. To use a checkout
of ultra instead, set `ULTRA_HOME=/path/to/ultra`.

## A site

```text
mysite/
  site.toml          title, description, base, nav, footer, url, lang, search
  content/
    index.md         the home page, at /
    about.md         /about/
    posts/index.md   /posts/  (front matter `list: posts` appends a dated list)
    posts/hello.md   /posts/hello/
  static/            copied into dist as is (a style.css here replaces the theme)
  islands/
    counter.py       an ultra app, used in markdown as <ultra-island name="counter"></ultra-island>
```

Front matter is `key: value` lines between `---`: `title`, `date`, `description`, `tags`
(comma separated), `order` (default nav position), `draft: true`, `list: <folder>`, `nav_title`.
A leading `# heading` is the page's `<h1>` (and its title if the front matter has none).

`site.toml`:

```toml
title = "My site"
description = "Used in feed.xml"
url = "https://example.com"     # for sitemap.xml and feed.xml
base = "/"                      # "/repo/" when hosted under a subpath, like GitHub Pages
nav = ["/", "/posts/", "/about/"]   # default: home, then top-level pages by `order`
footer = "..."
search = "full"                 # or "titles": index only titles, descriptions and tags
```

Links to other pages, either as markdown files (`[x](posts/hello.md)`, relative to the current
file) or as URLs (`/posts/hello/`), become in-app links. Raw HTML in markdown is kept.

## Output

```text
dist/
  index.html, about/index.html, ...   prerendered pages
  app.wasm                            every page as one ultra app
  islands/*.wasm                      one per island
  ultra.js, ui.css                    ultra's runtime and shadcn-style theme (light + dark)
  site.js, routes.js, style.css       static's browser glue and theme
  404.html, sitemap.xml, feed.xml
```

Deploy `dist/` to any static host. The pages are real files, so no rewrite rules are needed.

## How it works

1. `content.py` renders markdown with markdown-it-py, parses the HTML into an element tree,
   resolves links and gives headings ids.
2. `codegen.py` writes one LPython module: a `page_N()` function of `el()`/`attr()`/`text()`/`end()`
   calls per page, `view()` with the layout (header, nav, search, footer), and
   `update()` for `GO` (navigate), `POP` (back/forward) and the search query.
3. `ultra_tool.build_app` compiles it to `app.wasm`, and each island to its own wasm.
4. `assets/prerender.mjs` runs `app.wasm` in Node with an HTML-string version of ultra's
   runtime, once per page, and the results become the `index.html` files.
5. In the browser, `site.js` mounts the app over the prerendered page, syncs the URL with
   `history.pushState`, and mounts islands as they appear.

LPython's wasm backend keeps string literals byte for byte (it doesn't process escapes), so
static never writes a backslash, newline or clashing quote into a literal: those characters
are emitted with a `ch(code)` import instead.

Islands use message numbers of their own; their events are stopped at the island's root so
they never reach the site app.

## Tests

```sh
pixi run test-unit             # literals, URLs, front matter, codegen
pixi run test                  # both; the first run fetches Playwright and Chromium
pixi run test-e2e              # builds the example, serves it, runs tests/e2e.cjs in Chromium
```

Set `CHROMIUM=/path/to/chrome` to use a browser you already have. The browser test checks the prerendered HTML with scripts blocked, hydration, the island,
in-app navigation without reloads, back/forward, search, and literal round-tripping.

## Releases

Every push to `main` builds the conda package from `recipe/` (version `0.1.<commit count>`) with the
shared [nandi-conda/ci](https://github.com/nandi-conda/ci) workflow and publishes it to
`prefix.dev/nandi-testing`.
