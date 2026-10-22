---
title: Hello, ultra
date: 2026-10-20
description: Why put a static site inside a WebAssembly app?
tags: intro
---

ultra apps are written in LPython and compiled to wasm. They have no runtime
strings, no lists and no dicts, which sounds like a poor fit for a content site.

But a static site doesn't *need* runtime strings: all of its text is known at
build time. So ultrasite writes every page as string literals in LPython, and the
compiler packs them into the wasm data section.

> The whole site is one `view()` function away.

Next: [how it works](how-it-works.md).
