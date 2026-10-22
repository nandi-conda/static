"""Load a site: site.toml, content/**/*.md with front matter, into Page objects
whose body is an element tree (parsed from markdown-it's HTML output)."""

import datetime
import html
import os
import re
import sys
import tomllib
from dataclasses import dataclass, field
from html.parser import HTMLParser

from markdown_it import MarkdownIt

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "source", "track", "wbr"}
# Whitespace-only text directly inside these is layout noise, not content.
BLOCKY = {"#root", "ul", "ol", "li", "table", "thead", "tbody", "tfoot", "tr", "blockquote",
          "div", "section", "article", "aside", "header", "footer", "nav", "figure",
          "details", "dl", "select"}


@dataclass
class El:
    tag: str
    attrs: list = field(default_factory=list)  # [(name, value)]
    children: list = field(default_factory=list)  # El | str


@dataclass
class Page:
    index: int
    src: str  # path relative to content/
    url: str  # site-relative, "/" or "/about/"
    title: str
    meta: dict
    body: El
    text: str  # plain text, for the description fallback
    heading: str = ""  # the page's <h1>: its leading "# heading", else the title

    @property
    def date(self):
        return self.meta.get("date", "")

    @property
    def tags(self):
        return [t.strip() for t in self.meta.get("tags", "").split(",") if t.strip()]


@dataclass
class Site:
    root: str
    config: dict
    pages: list

    @property
    def title(self):
        return self.config.get("title", "Untitled site")

    @property
    def base(self):
        b = self.config.get("base", "/")
        return b if b.endswith("/") else b + "/"

    def page_for(self, url):
        for p in self.pages:
            if p.url == url:
                return p
        return None


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = El("#root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        e = El(tag, [(k, v if v is not None else "") for k, v in attrs])
        self.stack[-1].children.append(e)
        if tag not in VOID:
            self.stack.append(e)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(El(tag, [(k, v or "") for k, v in attrs]))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_html(src):
    tb = TreeBuilder()
    tb.feed(src)
    tb.close()
    tidy(tb.root, pre=False)
    return tb.root


def tidy(e, pre):
    """Collapse whitespace like a browser would, outside <pre>."""
    pre = pre or e.tag in ("pre", "textarea")
    out = []
    for c in e.children:
        if isinstance(c, El):
            tidy(c, pre)
            out.append(c)
        elif pre:
            out.append(c)
        else:
            s = re.sub(r"\s+", " ", c)
            if s == " " and e.tag in BLOCKY:
                continue
            out.append(s)
    # a <pre><code> block ends with a newline that browsers drop anyway
    if e.tag == "code" and pre and out and isinstance(out[-1], str):
        out[-1] = out[-1].rstrip("\n")
    e.children = [c for c in out if c != ""]


def plain_text(e):
    return "".join(plain_text(c) if isinstance(c, El) else c for c in e.children)


def slugify(s):
    s = re.sub(r"[^\w\s-]", "", s.lower()).strip()
    return re.sub(r"[\s_-]+", "-", s) or "section"


def add_heading_ids(root):
    seen = {}
    def walk(e):
        for c in e.children:
            if isinstance(c, El):
                if re.fullmatch(r"h[2-4]", c.tag) and not any(k == "id" for k, _ in c.attrs):
                    s = slugify(plain_text(c))
                    n = seen.get(s, 0)
                    seen[s] = n + 1
                    c.attrs.append(("id", s if n == 0 else f"{s}-{n}"))
                walk(c)
    walk(root)


def front_matter(src):
    """Minimal `key: value` front matter between --- lines."""
    meta = {}
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n", src, re.S)
    if not m:
        return meta, src
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        k, _, v = line.partition(":")
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        meta[k.strip()] = v
    return meta, src[m.end():]


def url_for(rel):
    stem = rel[:-3].replace(os.sep, "/")
    if stem == "index":
        return "/"
    if stem.endswith("/index"):
        stem = stem[: -len("/index")]
    return "/" + stem + "/"


def load_site(root, drafts=False):
    cfg_path = os.path.join(root, "site.toml")
    config = {}
    if os.path.exists(cfg_path):
        with open(cfg_path, "rb") as f:
            config = tomllib.load(f)
    content = os.path.join(root, "content")
    if not os.path.isdir(content):
        sys.exit(f"{root}: no content/ directory")
    md = MarkdownIt("commonmark", {"html": True, "typographer": True}).enable(
        ["table", "strikethrough", "replacements", "smartquotes"])
    files = []
    for d, _, names in os.walk(content):
        for n in names:
            if n.endswith(".md"):
                files.append(os.path.relpath(os.path.join(d, n), content))
    # index first (page 0 is the home page), then by path
    files.sort(key=lambda r: (r != "index.md", r))
    if not files or files[0] != "index.md":
        sys.exit(f"{content}: needs an index.md (the home page)")
    pages = []
    for rel in files:
        with open(os.path.join(content, rel), encoding="utf-8") as f:
            meta, body = front_matter(f.read())
        if meta.get("draft", "").lower() in ("true", "yes", "1") and not drafts:
            continue
        if isinstance(meta.get("date"), datetime.date):
            meta["date"] = meta["date"].isoformat()
        tree = parse_html(md.render(body))
        # A leading # heading is the page's <h1>, and its title unless the front matter has one.
        heading = None
        first = tree.children[0] if tree.children else None
        if isinstance(first, El) and first.tag == "h1":
            heading = plain_text(first)
            tree.children.pop(0)
        title = meta.get("title") or heading or \
            os.path.splitext(os.path.basename(rel))[0].replace("-", " ").title()
        add_heading_ids(tree)
        pages.append(Page(len(pages), rel, url_for(rel), title, meta, tree,
                          re.sub(r"\s+", " ", plain_text(tree)).strip(), heading or title))
    return Site(root, config, pages)


def escape(s, quote=False):
    return html.escape(s, quote=quote)
