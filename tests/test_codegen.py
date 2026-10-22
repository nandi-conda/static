import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from static.codegen import generate, lit_parts  # noqa: E402
from static.content import front_matter, load_site, url_for  # noqa: E402


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def decode(parts):
    """What the browser ends up with for lit_parts' output."""
    return "".join(v[1:-1] if k == "lit" else chr(v) for k, v in parts)


class Literals(unittest.TestCase):
    def test_round_trip(self):
        for s in ['plain', 'say "hi"', "it's", """both "x" and 'y'""", "C:\\Users\\v",
                  "a\nb", "\\", '"', "'\"'", "café ✓ 日本語", ""]:
            parts = lit_parts(s)
            self.assertEqual(decode(parts), s, s)
            for k, v in parts:
                if k == "lit":
                    self.assertNotIn("\\", v)
                    self.assertNotIn("\n", v)
                    self.assertNotIn(v[0], v[1:-1])


class Content(unittest.TestCase):
    def test_urls(self):
        self.assertEqual(url_for("index.md"), "/")
        self.assertEqual(url_for("about.md"), "/about/")
        self.assertEqual(url_for("posts/index.md"), "/posts/")
        self.assertEqual(url_for("posts/a-b.md"), "/posts/a-b/")

    def test_front_matter(self):
        meta, body = front_matter("---\ntitle: \"Hi: there\"\ntags: a, b\n---\nbody\n")
        self.assertEqual(meta, {"title": "Hi: there", "tags": "a, b"})
        self.assertEqual(body, "body\n")

    def test_site(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "content", "posts"))
            write(os.path.join(d, "site.toml"), 'title = "T"\nbase = "/sub"\n')
            write(os.path.join(d, "content", "index.md"),
                  "# Welcome\n\nSee [the post](posts/p.md) and [x](https://e.com).\n")
            write(os.path.join(d, "content", "posts", "p.md"),
                  "---\ndate: 2026-01-02\n---\n## Part one\n\n<b>raw</b> html\n")
            write(os.path.join(d, "content", "posts", "q.md"), "---\ndraft: true\n---\nx\n")
            site = load_site(d)
            self.assertEqual([p.src for p in site.pages], ["index.md", "posts/p.md"])
            self.assertEqual(site.pages[0].title, "Welcome")
            self.assertEqual(site.pages[1].title, "P")
            src = generate(site, [])
            self.assertIn('attr("href", "/sub/posts/p/")', src)
            self.assertIn("on_click(GO, 1)", src)
            self.assertIn('attr("href", "https://e.com")', src)
            self.assertIn('attr("id", "part-one")', src)
            self.assertIn('el("b")', src)
            self.assertEqual(len(load_site(d, drafts=True).pages), 3)


if __name__ == "__main__":
    unittest.main()
