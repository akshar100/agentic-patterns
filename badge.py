#!/usr/bin/env python3
"""Render an agentic-pattern badge SVG from a scan-result JSON.

Design notes:
- Flat, 20px tall, shields.io-compatible visual language so it sits naturally
  in a README badge row.
- Signature element: a 2x2 four-quadrant glyph on the label side, one quadrant
  per taxonomy dimension (D1 control flow, D2 multiplicity, D3 memory,
  D4 human). A quadrant lights up when the scan found >=1 pattern in that
  dimension. The glyph IS the taxonomy, at 10px.
- Honesty encoding: message segment is green when all patterns are statically
  `detected`, amber when any are LLM-`inferred`, with a small dot marking
  inferred entries. Gray = no patterns found.

Usage:
  python badge.py scan.json out.svg [--style full|compact]
  Also writes out.endpoint.json (shields.io endpoint schema).
"""

import json
import sys

# ---- palette (deliberate, not shields defaults) ----------------------------
INK = "#1f2430"          # label side: deep slate, not shields' #555
DETECTED = "#1a7f5a"     # verifiable green
INFERRED = "#b45309"     # amber: honest "a model guessed this"
EMPTY = "#6b7280"        # gray
GLYPH_ON = "#e8b04c"     # lit quadrant: warm signal against the ink
GLYPH_OFF = "#4a5160"    # unlit quadrant
FONT = "Verdana,Geneva,DejaVu Sans,sans-serif"
FS = 11  # font size

# Approximate Verdana 11px advance widths (shields-style estimation).
_W = {"default": 6.3, "upper": 7.4, "narrow": 3.4, "wide": 9.5, "space": 3.9,
      "digit": 7.0, "sep": 4.0}
_NARROW = set("iljtfI.,'|:;!()[]")
_WIDE = set("mwMW@")


def text_width(s: str) -> float:
    w = 0.0
    for ch in s:
        if ch == " ":
            w += _W["space"]
        elif ch in _NARROW:
            w += _W["narrow"]
        elif ch in _WIDE:
            w += _W["wide"]
        elif ch.isdigit():
            w += _W["digit"]
        elif ch.isupper():
            w += _W["upper"]
        else:
            w += _W["default"]
    return w


def build_message(patterns, style="full", max_named=3):
    """Compose the right-segment text and per-token status flags."""
    if not patterns:
        return [("none found", "empty")]
    ordered = sorted(
        patterns,
        key=lambda p: ({"detected": 0, "inferred": 1}[p["status"]],
                       {"high": 0, "medium": 1, "low": 2}[p["confidence"]]),
    )
    if style == "compact":
        n_det = sum(1 for p in patterns if p["status"] == "detected")
        n_inf = len(patterns) - n_det
        txt = f"{len(patterns)} patterns"
        return [(txt, "inferred" if n_inf else "detected")]
    tokens = []
    for p in ordered[:max_named]:
        tokens.append((p.get("abbrev") or p["name"], p["status"]))
    rest = len(ordered) - max_named
    if rest > 0:
        hidden = ordered[max_named:]
        bucket_status = ("inferred" if any(p["status"] == "inferred" for p in hidden)
                         else "detected")
        tokens.append((f"+{rest}", bucket_status))
    return tokens


def render(scan, style="full"):
    patterns = scan.get("patterns", [])
    dims = scan.get("summary", {}).get("dimensions", {})
    tokens = build_message(patterns, style=style)
    any_inferred = any(p["status"] == "inferred" for p in patterns)
    seg_color = (EMPTY if not patterns
                 else (INFERRED if all(p["status"] == "inferred" for p in patterns)
                       else DETECTED))

    label = "agentic"
    glyph_w = 15            # 10px glyph + spacing
    pad = 6
    label_w = glyph_w + text_width(label) + 2 * pad

    # message segment: tokens separated by thin dividers; inferred tokens
    # get a small amber dot marker before them
    sep_w = 8
    tok_widths = []
    for txt, st in tokens:
        w = text_width(txt) + (7 if (st == "inferred" and any_inferred and len(tokens) > 1) else 0)
        tok_widths.append(w)
    msg_w = 2 * pad + sum(tok_widths) + sep_w * (len(tokens) - 1)
    total_w = round(label_w + msg_w)
    label_w = round(label_w)

    s = []
    s.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="20" '
             f'role="img" aria-label="agentic patterns: {", ".join(t for t, _ in tokens)}">')
    s.append(f'<title>agentic patterns: {", ".join(t for t, _ in tokens)}</title>')
    # flat segments, 3px radius via clip
    s.append(f'<clipPath id="r"><rect width="{total_w}" height="20" rx="3"/></clipPath>')
    s.append('<g clip-path="url(#r)">')
    s.append(f'<rect width="{label_w}" height="20" fill="{INK}"/>')
    s.append(f'<rect x="{label_w}" width="{total_w - label_w}" height="20" fill="{seg_color}"/>')
    s.append('</g>')

    # four-dimension glyph: 2x2, quadrant order D1 TL, D2 TR, D3 BL, D4 BR
    quads = [dims.get("control_flow"), dims.get("agent_multiplicity"),
             dims.get("memory_scope"), dims.get("human_involvement")]
    gx, gy, q, gap = pad, 5, 4.5, 1.2
    for i, on in enumerate(quads):
        x = gx + (i % 2) * (q + gap)
        y = gy + (i // 2) * (q + gap)
        s.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{q}" height="{q}" rx="1" '
                 f'fill="{GLYPH_ON if on else GLYPH_OFF}"/>')

    tx = pad + glyph_w
    s.append(f'<text x="{tx:.1f}" y="14.5" fill="#fff" font-family="{FONT}" '
             f'font-size="{FS}" textLength="{text_width(label):.0f}">{label}</text>')

    # message tokens
    x = label_w + pad
    for i, ((txt, st), tw) in enumerate(zip(tokens, tok_widths)):
        if i > 0:
            s.append(f'<rect x="{x + sep_w / 2 - 0.5:.1f}" y="5" width="1" height="10" '
                     f'fill="#ffffff" opacity="0.35"/>')
            x += sep_w
        dot = st == "inferred" and any_inferred and len(tokens) > 1
        if dot:
            s.append(f'<circle cx="{x + 2.5:.1f}" cy="10" r="2.2" fill="#ffd9a8"/>')
        ttx = x + (7 if dot else 0)
        s.append(f'<text x="{ttx:.1f}" y="14.5" fill="#fff" font-family="{FONT}" '
                 f'font-size="{FS}" textLength="{text_width(txt):.0f}">{txt}</text>')
        x += tw
    s.append('</svg>')
    return "".join(s)


def shields_endpoint(scan):
    patterns = scan.get("patterns", [])
    tokens = build_message(patterns)
    color = ("6b7280" if not patterns
             else ("b45309" if any(st == "inferred" for _, st in tokens) else "1a7f5a"))
    return {"schemaVersion": 1, "label": "agentic patterns",
            "message": " | ".join(t for t, _ in tokens), "color": color}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    scan_path, out_path = sys.argv[1], sys.argv[2]
    style = "compact" if "--style" in sys.argv and "compact" in sys.argv else "full"
    scan = json.load(open(scan_path))
    svg = render(scan, style=style)
    with open(out_path, "w") as f:
        f.write(svg)
    ep_path = out_path.rsplit(".", 1)[0] + ".endpoint.json"
    with open(ep_path, "w") as f:
        json.dump(shields_endpoint(scan), f, indent=2)
    print(f"wrote {out_path} and {ep_path}")


if __name__ == "__main__":
    main()
