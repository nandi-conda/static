---
title: Docs
order: 2
---

## Layout of a site

| Path | What it is |
| ---- | ---------- |
| `site.toml` | title, description, `base`, `nav`, `footer`, `url`, `lang` |
| `content/**/*.md` | pages; `content/index.md` is the home page |
| `static/` | copied into the output as is (put a `style.css` here to replace the theme) |
| `islands/*.py` | interactive ultra apps, embedded with `<ultra-island name="...">` |

`content/about.md` is served at `/about/`, and `content/posts/index.md` at `/posts/`.

## Front matter

```yaml
---
title: A page            # else the first "# heading", else the file name
date: 2026-10-22         # shown on the page, sorts listings, goes in feed.xml
description: One line.   # meta description, listings, search
tags: wasm, lpython
order: 2                 # position in the default nav
draft: true              # left out unless you pass --drafts
list: posts              # append a dated list of the pages in content/posts/
---
```

## Links

Link to other pages by their markdown file (`[x](posts/hello.md)`) or by
URL (`[x](/posts/hello/)`). Both become in-app links. Anything else is left alone.

## Islands

An island is a normal ultra app (`init`, `update`, `view`) in `islands/NAME.py`.
It's compiled to its own wasm and mounted where the page says
`<ultra-island name="NAME"></ultra-island>`, so it keeps its state while
you read the page.

## Commands

```sh
ultrasite new mysite        # copy this example
ultrasite serve mysite      # build, serve on :8000, rebuild on change
ultrasite build mysite      # write mysite/dist
```

## Output

```text
dist/
  index.html, about/index.html, …   prerendered pages
  app.wasm                           every page, as one ultra app
  islands/*.wasm                     one per island
  ultra.js, ui.css                   ultra's runtime and theme
  site.js, routes.js, style.css      ultrasite's glue and theme
  404.html, sitemap.xml, feed.xml
```

Strings with backslashes like `C:\Users\v` and both kinds of quotes, as in `"it's"`, survive the trip into LPython.
