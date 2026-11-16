# -*- coding: utf-8 -*-
"""Download a third-party bundle once, from pinned mirrors, and refuse it unless its SHA-256 matches.

Used by shot_server.py to vendor html2canvas into assets/. Nothing minified is shipped with
the skill, and nothing unverified is ever run.
"""
import os, sys, hashlib


def fetch(url):
    from urllib.request import urlopen, Request
    req = Request(url, headers={"User-Agent": "interactive-docs-skill/1.0"})
    with urlopen(req, timeout=60) as r:
        return r.read()


def fetch_pinned(dest, sha256, urls, label):
    """Download `dest` from the first mirror whose bytes match `sha256`. Returns dest or None."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    last = None
    for url in urls:
        try:
            print("fetching %s …" % url)
            blob = fetch(url)
            digest = hashlib.sha256(blob).hexdigest()
            if digest != sha256:
                raise ValueError("sha256 mismatch (got %s…) — refusing to use it" % digest[:16])
            with open(dest, "wb") as f:
                f.write(blob)
            print("vendored %s -> %s  %d KB  (sha256 verified)" % (label, dest, len(blob) // 1024))
            return dest
        except Exception as e:  # try the next mirror
            last = e
            print("  ! %s" % e)
    print("\nCould not vendor %s: %s" % (label, last), file=sys.stderr)
    return None
