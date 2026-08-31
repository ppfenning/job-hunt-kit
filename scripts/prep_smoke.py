#!/usr/bin/env python3
"""Prepare a built page for scripts/smoke_test.js.

The smoke test runs the page's JavaScript against a stubbed DOM under Node, to
catch the errors that only show up during a real render pass — an undefined
`.map`, a field that isn't there. Two things about the page make it
un-runnable as-is:

  * it is a `<script type="module">`, and
  * it opens with a top-level `await fetch("/api/seed")`, because the data
    lives in SQLite rather than in the file.

So the bootstrap is replaced with a literal assignment from a seed snapshot,
which also removes the only `await`. Everything after that line is unchanged,
which is the part the test is actually exercising.

    curl -s http://127.0.0.1:8899/api/seed > /tmp/seed.json
    python3 scripts/prep_smoke.py dist/index.html /tmp/seed.json /tmp/page.js
    node scripts/smoke_test.js /tmp/page.js
"""
from __future__ import annotations

import json
import re
import sys

BOOTSTRAP = re.compile(r"const SEED = await \(async \(\) => \{.*?\}\)\(\);", re.S)


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    html_path, seed_path, out_path = sys.argv[1:]

    html = open(html_path, encoding="utf-8").read()
    m = re.search(r'<script type="module">(.*?)</script>', html, re.S)
    if not m:
        sys.exit("error: no <script type=\"module\"> block found in " + html_path)
    body = m.group(1)

    seed = json.load(open(seed_path, encoding="utf-8"))
    literal = "const SEED = " + json.dumps(seed, ensure_ascii=False) + ";"
    body, n = BOOTSTRAP.subn(lambda _: literal, body, count=1)
    if not n:
        sys.exit("error: could not find the SEED bootstrap to replace — has the "
                 "template's opening changed?")

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(body)
    counts = {k: len(v) for k, v in seed.items() if isinstance(v, (list, dict))}
    print(f"wrote {out_path} ({len(body):,} chars)")
    print("  seed: " + ", ".join(f"{k}={v}" for k, v in counts.items() if v))


if __name__ == "__main__":
    main()
