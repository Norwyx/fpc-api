"""Inspección de páginas/tablas de Wikipedia durante desarrollo."""
import sys

from . import wiki
from .tables import all_tables, header_texts, rows, soup


def _main(argv):
    title = argv[1]
    what = argv[2] if len(argv) > 2 else "tables"
    got = wiki.page_html(title, max_age_days=30.0)
    if not got:
        print(f"NO EXISTE: {title}")
        return
    final, html = got
    print(f"PAGE: {final}")
    doc = soup(html)
    if what == "sections":
        for h in doc.find_all(["h2", "h3"]):
            print(" ", h.get_text(" ", strip=True))
    elif what == "tables":
        for i, t in enumerate(all_tables(doc)):
            heads = header_texts(t)
            n = len(t.find_all("tr"))
            print(f"[{i}] rows={n} headers={heads[:220]}")
    elif what == "rows":
        idx = int(argv[3])
        for r in rows(all_tables(doc)[idx])[:12]:
            print([c["t"] for c in r])
            print("   hrefs:", [c["href"] for c in r])


if __name__ == "__main__":
    _main(sys.argv)
