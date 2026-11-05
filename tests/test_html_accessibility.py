"""Basic accessibility checks on app/static/index.html (stdlib only)."""
from html.parser import HTMLParser
from pathlib import Path

HTML = (Path(__file__).resolve().parent.parent / "app" / "static" / "index.html").read_text(encoding="utf-8")


class Scan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lang = None
        self.title = False
        self.h1 = 0
        self.label_for = set()
        self.fields = []
        self.live = False
        self.bad = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "title":
            self.title = True
        if tag == "h1":
            self.h1 += 1
        if tag == "label" and "for" in a:
            self.label_for.add(a["for"])
        if tag in ("input", "select", "textarea"):
            self.fields.append(a.get("id"))
        if a.get("role") == "status" and a.get("aria-live"):
            self.live = True
        for bad in ("autofocus", "autoplay"):
            if bad in a:
                self.bad.append(bad)


scan = Scan()
scan.feed(HTML)


def test_lang_and_title():
    assert scan.lang == "en"
    assert scan.title


def test_exactly_one_h1():
    assert scan.h1 == 1


def test_every_field_has_a_label():
    assert scan.fields
    for field_id in scan.fields:
        assert field_id in scan.label_for, f"field {field_id} has no label"


def test_status_region_is_live():
    assert scan.live


def test_no_autofocus_or_autoplay():
    assert scan.bad == []
