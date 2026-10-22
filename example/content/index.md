---
title: Home
description: Markdown in, WebAssembly out.
---

# Markdown in, WebAssembly out

**ultrasite** turns a folder of markdown into a site whose pages are an
[ultra](https://github.com/nandi-conda/ultra) app: every page becomes LPython
`view()` code, and the whole site compiles to a single small `app.wasm`.

- Each page is also **prerendered to HTML**, so it loads instantly and works without JavaScript.
- Once the wasm loads, links between pages are **ultra messages**, not reloads.
- The search box in the header runs in **wasm** too.
- Pages can embed **islands**: interactive ultra apps, like the counter below.

<ultra-island name="counter"></ultra-island>

Read [how it works](posts/how-it-works.md), or the [docs](docs.md).
