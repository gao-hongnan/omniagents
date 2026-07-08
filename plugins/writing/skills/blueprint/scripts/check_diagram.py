#!/usr/bin/env python3
"""
check_diagram.py — geometry linter for Blueprint HTML+SVG diagrams.

Re-derives the geometry of every node from its label's character count and the
monospace width formula, then fails on the format bugs Blueprint exists to
prevent:

  * a label wider than its box            (text overflow)
  * two node boxes overlapping            (collision)
  * a node box outside the viewBox        (clipping)
  * an arrow endpoint in empty space      (floating / disconnected arrow)

It relies on the conventions the skill mandates, so it needs no SVG rendering
engine and no third-party packages — just the standard library.

    python3 check_diagram.py diagram.html
    python3 check_diagram.py diagram.html --font-size 11 --advance 0.6

Exit code is 0 when every hard check passes, 1 otherwise. Warnings never fail
the build on their own; they flag things worth a human glance.

Conventions assumed (all produced by assets/template.html):
  node   <g class="node TYPE" transform="translate(cx,cy)"><rect x y width height/><text>…</text></g>
  band   <rect class="band" x y width height/>
  edge   <path class="edge"|"edge-dashed" d="M x,y L x,y …"/>
"""
from __future__ import annotations

import argparse
import html
import math
import re
import sys

RESET, RED, GREEN, YELLOW, DIM = "\033[0m", "\033[31m", "\033[32m", "\033[33m", "\033[2m"


def _attr(name: str, tag: str) -> str | None:
    m = re.search(rf'\b{name}\s*=\s*"([^"]*)"', tag)
    return m.group(1) if m else None


def _fnum(name: str, tag: str) -> float | None:
    v = _attr(name, tag)
    if v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _fnum_or(name: str, tag: str, default: float) -> float:
    v = _fnum(name, tag)
    return default if v is None else v


class Box:
    __slots__ = ("kind", "type", "label", "lines", "x0", "y0", "x1", "y1")

    def __init__(self, kind, type_, label, lines, x0, y0, x1, y1):
        self.kind, self.type, self.label, self.lines = kind, type_, label, lines
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1

    @property
    def w(self):
        return self.x1 - self.x0

    @property
    def h(self):
        return self.y1 - self.y0

    def __repr__(self):
        tag = f"{self.type} " if self.type else ""
        return f'{tag}"{self.label}" [{self.x0:.0f},{self.y0:.0f} {self.w:.0f}×{self.h:.0f}]'


def extract_svg(text: str) -> str:
    m = re.search(r"<svg\b.*?</svg>", text, re.DOTALL)
    if not m:
        sys.exit(f"{RED}No <svg> element found in the file.{RESET}")
    return m.group(0)


def parse_viewbox(svg: str):
    m = re.match(r"<svg\b[^>]*>", svg, re.DOTALL)
    open_tag = m.group(0) if m else "<svg>"
    vb = _attr("viewBox", open_tag)
    if vb:
        nums = [float(x) for x in re.split(r"[\s,]+", vb.strip()) if x]
        if len(nums) == 4:
            minx, miny, w, h = nums
            return minx, miny, minx + w, miny + h
    # fall back to width/height
    w = _fnum_or("width", open_tag, 0.0)
    h = _fnum_or("height", open_tag, 0.0)
    return 0.0, 0.0, w, h


def parse_nodes(svg: str):
    nodes = []
    for g in re.finditer(r"<g\b([^>]*)>(.*?)</g>", svg, re.DOTALL):
        attrs, body = g.group(1), g.group(2)
        cls = _attr("class", attrs) or ""
        if "node" not in cls.split():
            continue
        transform = _attr("transform", attrs) or ""
        tm = re.search(r"translate\(\s*(-?[\d.]+)[\s,]+(-?[\d.]+)\s*\)", transform)
        if not tm:
            continue
        cx, cy = float(tm.group(1)), float(tm.group(2))
        rect = re.search(r"<rect\b[^>]*>", body)
        if not rect:
            continue
        rt = rect.group(0)
        rx = _fnum_or("x", rt, 0.0)
        ry = _fnum_or("y", rt, 0.0)
        rw = _fnum("width", rt)
        rh = _fnum("height", rt)
        if rw is None or rh is None:
            continue
        text_m = re.search(r"<text\b[^>]*>(.*?)</text>", body, re.DOTALL)
        lines = []
        if text_m:
            inner = text_m.group(1)
            spans = re.findall(r"<tspan\b[^>]*>(.*?)</tspan>", inner, re.DOTALL)
            raw = spans if spans else [re.sub(r"<[^>]+>", "", inner)]
            lines = [html.unescape(s).strip() for s in raw]
        stype = next((c for c in cls.split() if c not in ("node",)), "")
        label = " / ".join(x for x in lines if x) or "(no label)"
        nodes.append(Box("node", stype, label, lines, cx + rx, cy + ry, cx + rx + rw, cy + ry + rh))
    return nodes


def parse_bands(svg: str):
    bands = []
    for rect in re.finditer(r"<rect\b[^>]*>", svg):
        rt = rect.group(0)
        cls = _attr("class", rt) or ""
        if "band" not in cls.split():
            continue
        x = _fnum_or("x", rt, 0.0)
        y = _fnum_or("y", rt, 0.0)
        w = _fnum("width", rt)
        h = _fnum("height", rt)
        if w is None or h is None:
            continue
        bands.append(Box("band", "band", "", [], x, y, x + w, y + h))
    return bands


def parse_edge_endpoints(svg: str):
    endpoints = []
    for path in re.finditer(r'<path\b[^>]*\bclass="[^"]*edge[^"]*"[^>]*>', svg):
        d = _attr("d", path.group(0)) or ""
        pairs = re.findall(r"(-?[\d.]+)\s*,\s*(-?[\d.]+)", d)
        if len(pairs) >= 2:
            (sx, sy), (ex, ey) = pairs[0], pairs[-1]
            endpoints.append(("start", float(sx), float(sy)))
            endpoints.append(("end", float(ex), float(ey)))
    return endpoints


def dist_to_box(px, py, box: Box):
    qx = min(max(px, box.x0), box.x1)
    qy = min(max(py, box.y0), box.y1)
    return math.hypot(px - qx, py - qy)


def overlap(a: Box, b: Box, slack=2.0):
    ox = min(a.x1, b.x1) - max(a.x0, b.x0)
    oy = min(a.y1, b.y1) - max(a.y0, b.y0)
    return ox > slack and oy > slack


def main():
    ap = argparse.ArgumentParser(description="Geometry linter for Blueprint diagrams.")
    ap.add_argument("file")
    ap.add_argument("--font-size", type=float, default=11.0, help="label font size in px (default 11)")
    ap.add_argument("--advance", type=float, default=0.6, help="monospace advance factor (default 0.6)")
    ap.add_argument("--pad-min", type=float, default=8.0, help="min px padding each side before a tight-fit warning")
    ap.add_argument("--tol", type=float, default=12.0, help="px tolerance for an arrow endpoint touching a surface")
    args = ap.parse_args()

    with open(args.file, encoding="utf-8") as fh:
        svg = extract_svg(fh.read())

    char_w = args.font_size * args.advance
    minx, miny, maxx, maxy = parse_viewbox(svg)
    nodes = parse_nodes(svg)
    bands = parse_bands(svg)
    endpoints = parse_edge_endpoints(svg)

    fails, warns = [], []

    # 1. text fits its box
    for n in nodes:
        chars = max((len(ln) for ln in n.lines), default=0)
        text_w = chars * char_w
        if text_w > n.w:
            fails.append(f"OVERFLOW  {n}: label needs {text_w:.0f}px but box is {n.w:.0f}px "
                         f"(widen to ≥ {text_w + 2 * 20:.0f})")
        elif (n.w - text_w) / 2 < args.pad_min:
            warns.append(f"tight     {n}: only {(n.w - text_w) / 2:.0f}px padding each side "
                         f"(aim for ≥ 16)")

    # 2. no node overlaps
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if overlap(nodes[i], nodes[j]):
                fails.append(f"OVERLAP   {nodes[i]}  ⟷  {nodes[j]}")

    # 3. every node inside the viewBox
    for n in nodes:
        if n.x0 < minx - 0.5 or n.y0 < miny - 0.5 or n.x1 > maxx + 0.5 or n.y1 > maxy + 0.5:
            fails.append(f"CLIPPED   {n}: outside viewBox [{minx:.0f},{miny:.0f} → {maxx:.0f},{maxy:.0f}]")

    # 4. arrow endpoints land on a real surface
    surfaces = nodes + bands
    for role, px, py in endpoints:
        if surfaces and min(dist_to_box(px, py, s) for s in surfaces) > args.tol:
            warns.append(f"floating  arrow {role} at ({px:.0f},{py:.0f}) is not on any box/band edge")

    # report
    print(f"{DIM}Blueprint geometry check — {args.file}{RESET}")
    print(f"{DIM}font-size {args.font_size:g}px · char width {char_w:g}px · "
          f"{len(nodes)} nodes · {len(bands)} bands · {len(endpoints) // 2} edges{RESET}\n")

    for f in fails:
        print(f"{RED}✗ {f}{RESET}")
    for w in warns:
        print(f"{YELLOW}! {w}{RESET}")

    if not fails and not warns:
        print(f"{GREEN}✓ all checks passed — {len(nodes)} nodes fit, no overlaps, "
              f"no clipping, arrows connected.{RESET}")
    elif not fails:
        print(f"\n{GREEN}✓ no hard failures{RESET} ({len(warns)} warning(s) to eyeball).")
    else:
        print(f"\n{RED}✗ {len(fails)} failure(s){RESET}, {len(warns)} warning(s). "
              f"Fix the failures and re-run.")

    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
