#!/usr/bin/env python3
"""Build db.json from the CSV/markdown sources in tools/source/.

db.json is generated - do not hand-edit it. Edit the sources and re-run:

    python3 tools/build_db.py

Fails loudly on referential-integrity errors rather than writing a broken file.
"""
import csv
import json
import pathlib
import re
import sys
import unicodedata

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / "tools/source"
PUBLIC = REPO / "public"

# Absolute image URLs. Change this one constant when the images move to a
# real host; nothing else needs to know.
BASE_URL = "http://localhost:3001"


def norm(s):
    """Aggressive normalization for matching titles across sources."""
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s)


def read_csv(name):
    path = SRC / name
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def num(value, cast=float):
    value = (value or "").strip()
    return cast(value) if value else None


def text(value):
    return (value or "").strip() or None


def image_url(kind, slug):
    """Only claim an image URL when the file actually exists on disk."""
    for ext in ("jpg", "jpeg", "png", "webp"):
        if (PUBLIC / "images" / kind / f"{slug}.{ext}").exists():
            return f"{BASE_URL}/images/{kind}/{slug}.{ext}"
    return None


def read_articles():
    articles = []
    for path in sorted((SRC / "articles").glob("*.md")):
        raw = path.read_text()
        meta = {}
        body = raw
        if raw.startswith("---"):
            _, front, body = raw.split("---", 2)
            for line in front.strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
        articles.append({
            "id": path.stem,
            "title": meta.get("title", path.stem),
            "summary": meta.get("summary"),
            "body": body.strip(),
            "image_url": image_url("articles", path.stem),
            "updated": meta.get("updated"),
        })
    return articles


def main():
    types = [{
        "id": r["id"],
        "name": r["name"],
        "short_name": r["short_name"],
        "description": text(r["description"]),
        "legal_definition": text(r["legal_definition"]),
        "image_url": image_url("types", r["id"]),
    } for r in read_csv("types.csv")]

    distilleries = [{
        "id": r["id"],
        "name": r["name"],
        "county": text(r["county"]),
        "country": r["country"],
        "lat": num(r["lat"]),
        "lng": num(r["lng"]),
        "founded": num(r["founded"], int),
        "website": text(r["website"]),
        "visitor_centre": {"true": True, "false": False}.get(r["visitor_centre"]),
        "description": text(r["description"]),
        "image_url": image_url("distilleries", r["id"]),
    } for r in read_csv("distilleries.csv")]

    brands = [{
        "id": r["id"],
        "name": r["name"],
        "distillery_id": text(r["distillery_id"]),
        "description": text(r["description"]),
        "image_url": image_url("brands", r["id"]),
    } for r in read_csv("brands.csv")]

    raw_whiskeys = read_csv("whiskeys.csv")

    brand_name = {b["id"]: b["name"] for b in brands}
    distillery_name = {d["id"]: d["name"] for d in distilleries}
    # Related whiskeys are stored as source titles; resolve them to our slugs.
    by_title = {norm(r["name"]): r["id"] for r in raw_whiskeys}

    whiskeys = []
    unresolved = set()
    for r in raw_whiskeys:
        related = []
        for title in filter(None, (r["related_titles"] or "").split("|")):
            slug = by_title.get(norm(title))
            if slug and slug != r["id"]:
                related.append(slug)
            elif not slug:
                unresolved.add(title)

        dist_id = text(r["distillery_id"])
        whiskeys.append({
            "id": r["id"],
            "name": r["name"],
            "type_id": r["type_id"],
            "brand_id": r["brand_id"],
            "brand_name": brand_name.get(r["brand_id"]),
            "distillery_id": dist_id,
            "distillery_name": distillery_name.get(dist_id) if dist_id else None,
            "abv": num(r["abv"]),
            "age_years": num(r["age_years"], int),
            "price_usd": num(r["price_usd"]),
            "rating": num(r["rating"], int),
            "tasting_note": text(r["tasting_note"]),
            "excerpt": text(r["excerpt"]),
            "image_url": image_url("whiskeys", r["id"]),
            "related_whiskey_ids": sorted(set(related)),
            "source_url": text(r["source_url"]),
            "source_publisher": "VinePair" if text(r["source_url"]) else None,
            "source_author": text(r["source_author"]),
            "source_published": text(r["source_published"]),
        })

    news = [{
        "id": r["id"],
        "title": r["title"],
        "summary": text(r["summary"]),
        "url": r["url"],
        "source": r["source"],
        "published": r["published"],
        "image_url": text(r.get("image_url")),
    } for r in read_csv("news.csv")]

    # --- integrity checks: fail loudly rather than write a broken file -------
    type_ids = {t["id"] for t in types}
    brand_ids = {b["id"] for b in brands}
    distillery_ids = {d["id"] for d in distilleries}
    whiskey_ids = {w["id"] for w in whiskeys}

    assert len(whiskey_ids) == len(whiskeys), "duplicate whiskey slugs"
    assert len(brand_ids) == len(brands), "duplicate brand slugs"
    assert len(distillery_ids) == len(distilleries), "duplicate distillery slugs"

    for w in whiskeys:
        assert w["type_id"] in type_ids, f"{w['id']}: bad type {w['type_id']}"
        assert w["brand_id"] in brand_ids, f"{w['id']}: bad brand {w['brand_id']}"
        assert not w["distillery_id"] or w["distillery_id"] in distillery_ids, \
            f"{w['id']}: bad distillery {w['distillery_id']}"
        for rel in w["related_whiskey_ids"]:
            assert rel in whiskey_ids, f"{w['id']}: bad related {rel}"

    for b in brands:
        assert not b["distillery_id"] or b["distillery_id"] in distillery_ids, \
            f"brand {b['id']}: bad distillery {b['distillery_id']}"

    db = {
        "whiskeys": whiskeys,
        "brands": brands,
        "distilleries": distilleries,
        "types": types,
        "articles": read_articles(),
        "news": news,
    }
    (REPO / "db.json").write_text(
        json.dumps(db, indent=2, ensure_ascii=False) + "\n"
    )

    print(f"wrote db.json")
    for key, rows in db.items():
        with_img = sum(1 for r in rows if r.get("image_url"))
        print(f"  {key:14} {len(rows):>3} rows  ({with_img} with images)")

    linked = sum(len(w["related_whiskey_ids"]) for w in whiskeys)
    print(f"\n  {linked} related-whiskey links resolved")
    if unresolved:
        print(f"  {len(unresolved)} related titles not in our set (dropped):")
        for t in sorted(unresolved)[:5]:
            print(f"    - {t}")
        if len(unresolved) > 5:
            print(f"    ... and {len(unresolved) - 5} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
