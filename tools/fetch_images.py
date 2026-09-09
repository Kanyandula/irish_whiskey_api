#!/usr/bin/env python3
"""Download and downsize source images into public/images/.

Re-runnable: files that already exist are skipped, so a partial run can be
resumed and a re-run costs nothing. Images are resized to 800px on the longest
side with `sips` (built into macOS).

    python3 tools/fetch_images.py

Then re-run tools/build_db.py - it only emits an image_url for files that
actually exist on disk.

Sources: whiskey bottle shots from the URLs captured in the original scrape
(whiskeys.csv:source_image_url); whiskey-type images from types_images below.
Distilleries and brands have no image source in the original data.
"""
import csv
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / "tools/source"
PUBLIC = REPO / "public/images"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
DELAY = 0.5      # be polite to the origin servers
MAX_PX = 800

# Captured from the original db.json whiskey_types[].image1
TYPE_IMAGES = {
    "single-malt":
        "https://www.masterofmalt.com/whiskies/p-2812/teeling/"
        "teeling-pineapple-rum-cask-whisky.jpg",
    "single-pot-still":
        "https://www.celticwhiskeyshop.com/image/cache/Al-2021/"
        "Dingle_Distillery_Award_'21_Pot_Still_4-776x1176-776x1176.jpg",
    "single-grain":
        "https://www.celticwhiskeyshop.com/image/cache/data/Whiskey/"
        "Teeling-Single-Grain-776x1176.jpg",
    "blended":
        "https://www.celticwhiskeyshop.com/image/cache/2020%20Uploads/"
        "Bushmills_Blackbush-776x1176.jpg",
}


# Two of the four type images are unreachable: masterofmalt.com bot-blocks
# with a persistent 429, and the celticwhiskeyshop pot-still image is a real
# 404. Fall back to a representative bottle we already downloaded - they are
# genuine examples of the category.
TYPE_IMAGE_FALLBACK = {
    "single-malt": "bushmills-single-malt-10-years",
    "single-pot-still": "redbreast-12-year-old-single-pot-still",
}


def fetch(url, dest):
    if dest.exists():
        return "skip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        return f"FAIL ({e})"
    if len(data) < 1000:
        return f"FAIL (only {len(data)} bytes)"
    dest.write_bytes(data)
    subprocess.run(["sips", "-Z", str(MAX_PX), str(dest)],
                   capture_output=True, check=False)
    time.sleep(DELAY)
    return f"ok ({dest.stat().st_size // 1024}KB)"


def main():
    jobs = []
    for r in csv.DictReader((SRC / "whiskeys.csv").open()):
        if r["source_image_url"]:
            jobs.append(("whiskeys", r["id"], r["source_image_url"]))
    for tid, url in TYPE_IMAGES.items():
        jobs.append(("types", tid, url))

    counts = {"ok": 0, "skip": 0, "fail": 0}
    for kind, slug, url in jobs:
        result = fetch(url, PUBLIC / kind / f"{slug}.jpg")
        key = "fail" if result.startswith("FAIL") else result.split()[0]
        counts[key] = counts.get(key, 0) + 1
        if result.startswith("FAIL"):
            print(f"  {result}  {kind}/{slug}")
            print(f"        {url}")

    for tid, whiskey_slug in TYPE_IMAGE_FALLBACK.items():
        dest = PUBLIC / "types" / f"{tid}.jpg"
        src = PUBLIC / "whiskeys" / f"{whiskey_slug}.jpg"
        if not dest.exists() and src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src.read_bytes())
            print(f"  fallback  types/{tid} <- whiskeys/{whiskey_slug}")

    print(f"\ndownloaded {counts['ok']}, skipped {counts['skip']}, "
          f"failed {counts['fail']} (of {len(jobs)})")
    total = sum(p.stat().st_size for p in PUBLIC.rglob("*.jpg"))
    print(f"public/images/ is now {total / 1024 / 1024:.1f}MB")
    return 1 if counts["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
