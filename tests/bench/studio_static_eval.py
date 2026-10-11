#!/usr/bin/env python3
"""Static evaluation of the design studio sources (no LLM needed). Measures, from the vendored files:

1. ui-ux-pro-max palettes (colors.csv): violet share, stock Tailwind v3 hexes (needs the Tailwind colours file,
   optional), and WCAG contrast of each declared on-pair.
2. ui-ux-pro-max font pairings (typography.csv): share using a family our lint treats as a default.
3. Palettes it suggests for the three A/B specs (run sandboxed via `eos studio palette` logic), reviewed by our
   token contrast check and violet rule.
4. Rubric coverage proxy: for each of our 12 critique rows, how many paragraphs / rows in our refs vs the studio
   knowledge match a few keywords. A proxy for "does the source talk about this at all", not a quality score.

usage: python3 tests/bench/studio_static_eval.py <eos-home> [--tailwind /path/colors.js] [--json out.json]
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import tempfile
from pathlib import Path

HOME = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(HOME / "bin"))
import eos

UUPM = HOME / "packs/vendor/ui-ux-pro-max-knowledge/dot-claude/skills/ui-ux-pro-max/data"
PAIRS = [("On Primary", "Primary"), ("On Secondary", "Secondary"), ("On Accent", "Accent"),
         ("Foreground", "Background"), ("Card Foreground", "Card"), ("Muted Foreground", "Muted"),
         ("On Destructive", "Destructive")]  # fmt: skip
SPECS = {
    "01-sme-cash-dashboard": "fintech cash dashboard small business mobile money",
    "02-mobile-money-payment": "mobile money bill payment wallet",
    "03-landing-page": "savings group community finance app landing page",
}
ROWS = {
    1: r"direction|adjective|mood|personality|brand voice",
    2: r"generic|ai[- ]?(look|slop|default)|clich|overused",
    3: r"hierarch|primary action|squint|emphasis",
    4: r"typograph|type scale|font pair|line length|measure",
    5: r"contrast|palette|colou?r token|dark mode",
    6: r"spacing|grid|layout|breakpoint|responsive",
    7: r"empty state|loading|skeleton|error state|offline|success state",
    8: r"copy|microcopy|label text|error message|tone",
    9: r"touch target|focus|motion|animation|reduced.motion",
    10: r"accessib|aria|screen reader|keyboard|wcag",
    11: r"low[- ]end|slow network|data cost|literacy|offline",
    12: r"\bhig\b|material|safe area|back (button|gesture)|navigation pattern",
}


def arg(name: str) -> str | None:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None


def lin(hexs: str) -> list[float] | None:
    pc = eos.parse_css_color(hexs)
    return pc[0] if pc else None


def palettes(tw: set[str]) -> dict:
    rows = list(csv.DictReader(io.StringIO((UUPM / "colors.csv").read_text(encoding="utf-8"))))
    violet = stock = 0
    checked = passed = 0
    fails_by_pair: dict[str, int] = {}
    for r in rows:
        keys = [r.get(k, "") for k in ("Primary", "Secondary", "Accent")]
        if any(eos.is_violet(lin(h)) for h in keys if h):
            violet += 1
        if tw and any(h.lower() in tw for h in keys if h):
            stock += 1
        for fg, bg in PAIRS:
            a, b = lin(r.get(fg, "")), lin(r.get(bg, ""))
            if a and b:
                checked += 1
                if eos.contrast_ratio((a, 1.0), (b, 1.0)) >= 4.5:
                    passed += 1
                else:
                    fails_by_pair[f"{fg}/{bg}"] = fails_by_pair.get(f"{fg}/{bg}", 0) + 1
    return {"palettes": len(rows), "violet_key_colour": violet, "stock_tailwind_key_colour": stock if tw else None,
            "on_pairs_checked": checked, "on_pairs_pass_4_5": passed, "fails_by_pair": fails_by_pair}  # fmt: skip


def fonts() -> dict:
    rows = list(csv.DictReader(io.StringIO((UUPM / "typography.csv").read_text(encoding="utf-8"))))
    dflt = [r for r in rows if {r["Heading Font"].lower(), r["Body Font"].lower()} & eos.DEFAULT_FONTS]
    inter = [r for r in rows if "inter" in (r["Heading Font"].lower(), r["Body Font"].lower())]
    return {"pairings": len(rows), "with_default_family": len(dflt), "with_inter": len(inter)}


def spec_palettes() -> dict:
    out: dict = {}
    if eos.studio_backend() == "none":
        return {"skipped": "no sandbox (Docker/Podman/bubblewrap)"}
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rc, msgs = eos.studio_install(HOME, root, allow_pending=True)  # evaluation only, never a project install
        if rc:
            return {"skipped": "; ".join(msgs)}
        for spec, q in SPECS.items():
            rc, raw = eos.studio_run(root, "uupm", ["search", q, "--design-system", "--json", "-p", "Draft"])
            try:
                ds = json.loads(raw[raw.index("{") :])["design_system"]
            except (ValueError, KeyError):
                out[spec] = {"error": raw[-300:]}
                continue
            doc = eos.studio_palette_tokens(ds)
            errs, warns = eos.studio_palette_review(doc, ds)
            out[spec] = {"query": q, "style": (ds.get("style") or {}).get("name"),
                         "heading_font": (ds.get("typography") or {}).get("heading"),
                         "body_font": (ds.get("typography") or {}).get("body"),
                         "colours": len(doc["color"]) - 1, "contrast_errors": len(errs), "warnings": warns}  # fmt: skip
    return out


def units(paths: list[Path]) -> list[str]:
    us: list[str] = []
    for p in paths:
        t = p.read_text(encoding="utf-8", errors="replace")
        if p.suffix == ".csv":
            us += [" ".join(r) for r in list(csv.reader(io.StringIO(t)))[1:]]
        else:
            us += [u for u in re.split(r"\n\s*\n", t) if u.strip()]
    return us


def coverage() -> dict:
    ours = units(sorted((HOME / "packs/ref/design").glob("*.md")) + [HOME / "packs/phases/design-direction.md",
                 HOME / "packs/phases/ux-design.md"])  # fmt: skip
    vend = HOME / "packs/vendor"
    srcs = {sid: units(sorted(p for p in (vend / sid).rglob("*") if p.suffix in (".md", ".csv") and p.is_file()
                              and p.name not in ("ATTRIBUTION.md", "LICENSE", "NOTICE.md")))
            for sid in ("impeccable-knowledge", "ui-ux-pro-max-knowledge", "emil-review-animations")}  # fmt: skip
    res = {}
    for row, rx in ROWS.items():
        c = re.compile(rx, re.IGNORECASE)
        res[row] = {"ours": sum(1 for u in ours if c.search(u))} | {
            sid: sum(1 for u in us if c.search(u)) for sid, us in srcs.items()
        }
    return {"units": {"ours": len(ours)} | {k: len(v) for k, v in srcs.items()}, "rows": res}


def main() -> int:
    tw: set[str] = set()
    if arg("--tailwind"):
        tw = {h.lower() for h in re.findall(r"#[0-9a-fA-F]{6}\b", Path(arg("--tailwind")).read_text(encoding="utf-8"))}
    res = {"palettes": palettes(tw), "fonts": fonts(), "spec_palettes": spec_palettes(), "coverage": coverage(),
           "tailwind_hexes_loaded": len(tw)}  # fmt: skip
    print(json.dumps(res, indent=1))
    if arg("--json"):
        Path(arg("--json")).write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
