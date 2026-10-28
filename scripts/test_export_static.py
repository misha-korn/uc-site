"""
Юнит-тесты переписывания ссылок для scripts/export_static.py (Django не нужен).

Запуск из корня проекта:
    python -m unittest scripts/test_export_static.py -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import export_static as ex  # noqa: E402

M = ex.Mapper("/static/", "/media/")


class PageFileTests(unittest.TestCase):
    def test_paths(self):
        self.assertEqual(M.page_file("/"), "index.html")
        self.assertEqual(M.page_file("/sveden/common/"), "sveden/common/index.html")
        self.assertEqual(M.page_file("/obuchenie/", "cat=ohrana-truda"), "obuchenie/cat-ohrana-truda/index.html")
        self.assertEqual(M.page_file("/obuchenie/", "page=2"), "obuchenie/index.html")
        self.assertEqual(M.page_file("/robots.txt"), "robots.txt")
        self.assertEqual(M.page_file("/kontakty"), "kontakty/index.html")


class RewriteUrlTests(unittest.TestCase):
    def test_from_root(self):
        self.assertEqual(ex.rewrite_url("/sveden/common/", "index.html", M), "sveden/common/index.html")
        self.assertEqual(ex.rewrite_url("/", "index.html", M), "index.html")

    def test_from_nested(self):
        cur = "sveden/struct/index.html"
        self.assertEqual(ex.rewrite_url("/sveden/common/", cur, M), "../common/index.html")
        self.assertEqual(ex.rewrite_url("/", cur, M), "../../index.html")
        self.assertEqual(ex.rewrite_url("/static/css/main.css", cur, M), "../../static/css/main.css")
        self.assertEqual(ex.rewrite_url("/media/docs/ustav.pdf", cur, M), "../../media/docs/ustav.pdf")

    def test_category_query(self):
        cur = "obuchenie/index.html"
        self.assertEqual(ex.rewrite_url("/obuchenie/?cat=pb", cur, M), "cat-pb/index.html")
        self.assertEqual(ex.rewrite_url("?cat=pb", cur, M, "/obuchenie/"), "cat-pb/index.html")
        self.assertEqual(ex.rewrite_url("/obuchenie/", "obuchenie/cat-pb/index.html", M), "../index.html")

    def test_fragment_and_query_kept(self):
        self.assertEqual(ex.rewrite_url("/kontakty/#map", "index.html", M), "kontakty/index.html#map")
        self.assertEqual(ex.rewrite_url("/static/a.css?v=2", "index.html", M), "static/a.css?v=2")

    def test_untouched(self):
        for u in ("#top", "https://example.com/x", "http://a.b", "mailto:a@b.ru", "tel:+78460000000",
                  "//cdn.example/x.js", "data:image/png;base64,AAA", "javascript:void(0)"):
            self.assertEqual(ex.rewrite_url(u, "sveden/index.html", M), u)


class RewriteHtmlTests(unittest.TestCase):
    def test_full_page(self):
        src = """<!doctype html><html><head>
<link rel="canonical" href="http://testserver/sveden/common/">
<meta property="og:url" content="http://testserver/sveden/common/">
<link rel="stylesheet" href="/static/css/main.css">
<style>.hero{background:url('/static/img/bg.jpg')}</style>
</head><body>
<a href="/" class="logo">Лого</a>
<a href="/sveden/struct/" itemprop="x">Структура</a>
<a href="/admin/" class="btn">Панель</a>
<a href="#main">к содержанию</a>
<a href="https://gosuslugi.ru/">ГУ</a>
<img src="/media/a b.png" srcset="/static/img/x1.png 1x, /static/img/x2.png 2x" alt="">
<div style="background-image: url(&quot;/static/img/p.svg&quot;)"></div>
<form method="post" action="/zayavka/" class="lead"><input type="hidden" name="csrfmiddlewaretoken" value="abc">
<input name="name"></form>
<form method="get"><input name="q"></form>
</body></html>"""
        out = ex.rewrite_html(src, "sveden/common/index.html", M, "https://uc-demo.ru")
        self.assertIn('href="https://uc-demo.ru/sveden/common/"', out)
        self.assertIn('content="https://uc-demo.ru/sveden/common/"', out)
        self.assertIn('href="../../static/css/main.css"', out)
        self.assertIn("url('../../static/img/bg.jpg')", out)
        self.assertIn('href="../../index.html" class="logo"', out)
        self.assertIn('href="../struct/index.html" itemprop="x"', out)
        self.assertNotIn("/admin/", out)
        self.assertIn('<span class="btn">Панель</span>', out)
        self.assertIn('href="#main"', out)
        self.assertIn('href="https://gosuslugi.ru/"', out)
        self.assertIn('src="../../media/a%20b.png"'.replace("%20", " "), out)
        self.assertIn('srcset="../../static/img/x1.png 1x, ../../static/img/x2.png 2x"', out)
        self.assertIn("../../static/img/p.svg", out)
        self.assertIn('action="#"', out)
        self.assertNotIn('action="/zayavka/"', out)
        self.assertNotIn("csrfmiddlewaretoken", out)
        self.assertEqual(out.count("data-demo"), 2)

    def test_css_file(self):
        css = "@import '/static/css/base.css';\n.a{background:url(/static/img/a.png)} .b{background:url(data:image/png;base64,AA)}"
        out = ex.rewrite_css(css, "static/css/main.css", M)
        self.assertIn("@import 'base.css'", out)
        self.assertIn("url(../img/a.png)", out)
        self.assertIn("url(data:image/png;base64,AA)", out)


class FontPreloadTests(unittest.TestCase):
    """preload шрифта на file:// даёт CORS-ошибку — в экспорте его быть не должно."""

    def test_font_preload_removed_other_links_kept(self):
        src = (
            '<head><link rel="preload" href="/static/fonts/a.woff2" as="font" type="font/woff2" crossorigin>\n'
            "<link as='font' crossorigin rel='preload' href='/static/fonts/b.woff2'>"
            '<link rel="preload" href="/static/css/main.css" as="style">'
            '<link rel="stylesheet" href="/static/css/main.css"></head>'
        )
        out = ex.rewrite_html(src, "index.html", M)
        self.assertNotIn("woff2", out)
        self.assertIn('as="style"', out)
        self.assertIn('rel="stylesheet" href="static/css/main.css"', out)

    def test_media_root_argument(self):
        from unittest import mock

        with mock.patch.object(ex, "export", return_value=0) as export, tempfile.TemporaryDirectory() as d:
            ex.main(["--out", str(Path(d) / "dist"), "--media-root", "/tmp/some-media"])
        self.assertEqual(export.call_args.args[3], "/tmp/some-media")


class CheckDistTests(unittest.TestCase):
    def test_broken_detected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a").mkdir()
            (root / "index.html").write_text('<a href="a/index.html">ok</a><a href="b/index.html">bad</a>'
                                             '<a href="/abs/">abs</a><a href="#x">x</a>', encoding="utf-8")
            (root / "a" / "index.html").write_text('<a href="../index.html">up</a><a href="../a/">dir</a>',
                                                   encoding="utf-8")
            broken = ex.check_dist(root)
            links = sorted(b[1] for b in broken)
            self.assertEqual(links, ["../a/", "/abs/", "b/index.html"])


if __name__ == "__main__":
    unittest.main()
