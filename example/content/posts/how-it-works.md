---
title: How it works
date: 2026-10-22
description: Markdown to HTML to an element tree to LPython to wasm, and back to HTML.
tags: internals, wasm
---

## The pipeline

1. **markdown-it** renders each page to HTML.
2. The HTML is parsed into an element tree, links are resolved, headings get ids.
3. Each page becomes a function of ultra calls:

```python
def page_3() -> None:
    el("article")
    cls("page")
    el("h1")
    text("How it works")
    end()
    ...
```

4. `view()` wraps the current page in the layout, and `update(GO, i)` switches pages.
5. `ultra build` compiles it all to `app.wasm`.
6. Node runs that wasm once per page with a string-building copy of ultra's runtime,
   which writes the prerendered `index.html` files.

## Literals

LPython's wasm backend copies string literals byte for byte: `"\n"` stays a
backslash and an `n`. static never writes an escape; a newline, a backslash,
or a `"` next to a `'` is emitted as `ch(code)` instead.

## Navigation

Links between pages carry `data-go` and an `on_click(GO, i)`. A click becomes an
ultra message, `history.pushState` updates the URL, and ultra patches only the
nodes that differ between the two pages.
