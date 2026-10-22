#!/usr/bin/env python3
"""Generate an animated, Kali-terminal-styled Neofetch profile card as a single SVG."""
import glob
import math
import os
from xml.sax.saxutils import escape

try:
    import requests
except ImportError:  # stats fall back to N/A
    requests = None
from PIL import Image, ImageOps

# ───────────────────────── CONFIG (edit me) ─────────────────────────
LOGIN = os.environ.get("GITHUB_LOGIN", "eujz")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT_PATH = os.environ.get("OUT_PATH", "assets/profile.svg")
AVATAR_PATH = os.environ.get("AVATAR_PATH", "")

PROFILE_FIELDS = [
    ("Role", "developer"),
    ("Focus", "software, tooling & experiments"),
    ("Stack.Langs", "c, c++, rust, lua, python, js, ts"),
    ("Stack.Web", "react, html, css"),
    ("Stack.DB", "mysql, mongodb"),
    ("Tools", "git"),
    ("Contact.GitHub", f"github.com/{LOGIN}"),
]

PROMPT_COMMANDS = [
    "developer",
    "building things, one commit at a time",
    "learning by building and iterating",
]

BG_COLOR = "#0b1120"
TITLEBAR_COLOR = "#141c30"
ACCENT = "#5dc9f2"
HEADER_COLOR = "#e8384f"
LABEL_COLOR = "#ffffff"
VALUE_COLOR = "#5dc9f2"
PALETTE = ["#0b1120", "#e8384f", "#3ddc84", "#ffd166",
           "#4d8cff", "#b16cff", "#39e0d0", "#e8e8e8"]

ART_COLS = 34
PROMPT_TYPE_SPEED = 0.08
PROMPT_DELETE_SPEED = 0.045
PROMPT_HOLD_TIME = 1.1
PROMPT_GAP_TIME = 0.4
# ────────────────────────────────────────────────────────────────────

FONT = "'DejaVu Sans Mono','Fira Code',Consolas,Menlo,monospace"
FS = 13            # font size
CW = FS * 0.602    # char width (monospace)
LH = 16            # line height
RAMP = " .:-=+*#%@"


def avatar_file():
    if AVATAR_PATH and os.path.exists(AVATAR_PATH):
        return AVATAR_PATH
    for ext in ("jpg", "jpeg", "png", "webp"):
        hits = glob.glob(f"assets/avatar.{ext}")
        if hits:
            return hits[0]
    return None


def ascii_from_image(path, cols):
    img = Image.open(path).convert("L")
    img = ImageOps.fit(img, (cols * 4, cols * 4))          # square crop
    img = ImageOps.autocontrast(img, cutoff=2)
    rows = cols // 2                                        # chars are ~2x taller
    img = img.resize((cols, rows), Image.LANCZOS)
    px = img.load()
    out = []
    for y in range(rows):
        line = "".join(RAMP[int(px[x, y] / 256 * len(RAMP))] for x in range(cols))
        out.append(line.rstrip())
    return out


def ascii_fallback(cols):
    """Procedural motif used when no avatar is provided."""
    rows = cols // 2
    out = []
    for y in range(rows):
        line = ""
        for x in range(cols):
            nx, ny = (x - cols / 2) / (cols / 2), (y - rows / 2) / (rows / 2)
            d = math.hypot(nx, ny)
            v = 0.5 + 0.5 * math.sin(d * 9 - 1.2) * (1 - d)
            line += RAMP[min(len(RAMP) - 1, int(max(0, v) * len(RAMP)))] if d < 1 else " "
        out.append(line.rstrip())
    return out


def fetch_stats():
    na = {"Repos": "N/A", "Stars": "N/A", "Followers": "N/A", "Top.Langs": "N/A"}
    if requests is None or not TOKEN:
        return na
    h = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}
    try:
        u = requests.get(f"https://api.github.com/users/{LOGIN}", headers=h, timeout=20).json()
        repos, page = [], 1
        while page <= 5:
            r = requests.get(f"https://api.github.com/users/{LOGIN}/repos",
                             params={"per_page": 100, "page": page, "type": "owner"},
                             headers=h, timeout=20).json()
            if not isinstance(r, list) or not r:
                break
            repos += r
            page += 1
        langs = {}
        for r in repos:
            if r.get("language") and not r.get("fork"):
                langs[r["language"]] = langs.get(r["language"], 0) + 1
        top = ", ".join(k for k, _ in sorted(langs.items(), key=lambda kv: -kv[1])[:3]).lower()
        return {
            "Repos": str(u.get("public_repos", len(repos))),
            "Stars": str(sum(r.get("stargazers_count", 0) for r in repos)),
            "Followers": str(u.get("followers", 0)),
            "Top.Langs": top or "N/A",
        }
    except Exception:
        return na


def prompt_css(cmds):
    """Per-command CSS keyframes: clip width grows (typing) then shrinks (deleting)."""
    segs = []
    for c in cmds:
        n = len(c)
        segs.append((n, n * PROMPT_TYPE_SPEED, PROMPT_HOLD_TIME,
                     n * PROMPT_DELETE_SPEED, PROMPT_GAP_TIME))
    total = sum(t + h + d + g for _, t, h, d, g in segs)
    css, t0 = [], 0.0
    for i, (n, t, h, d, g) in enumerate(segs):
        w = n * CW
        pts = [(t0, 0), (t0 + t, w), (t0 + t + h, w), (t0 + t + h + d, 0), (total, 0)]
        if t0 == 0:
            pts = pts[:]  # starts at 0%
        kf_w, kf_c = [], []
        for (ta, wa) in pts:
            pct = round(ta / total * 100, 3)
            kf_w.append(f"{pct}%{{width:{wa:.1f}px}}")
            kf_c.append(f"{pct}%{{transform:translateX({wa:.1f}px)}}")
        css.append(f"@keyframes w{i}{{{''.join(kf_w)}}}@keyframes c{i}{{{''.join(kf_c)}}}")
        css.append(f".w{i}{{animation:w{i} {total:.2f}s steps({n},end) infinite}}"
                   f".c{i}{{animation:c{i} {total:.2f}s linear infinite}}")
        t0 += t + h + d + g
    return "".join(css), total


def build_svg():
    path = avatar_file()
    art = ascii_from_image(path, ART_COLS) if path else ascii_fallback(ART_COLS)
    stats = fetch_stats()

    fields = [(k, v) for k, v in PROFILE_FIELDS] + list(stats.items())
    pad = 24
    top = 36
    art_x = pad
    art_w = ART_COLS * CW
    info_x = art_x + art_w + 36
    info_w = 46 * CW
    width = int(info_x + info_w + pad)

    body_y = top + 30
    header = f"{LOGIN}@github"
    info_lines = 3 + len(fields) + 3
    body_h = max(len(art), info_lines) * LH
    prompt_y = body_y + body_h + 34
    height = int(prompt_y + 30)

    css_prompt, _ = prompt_css(PROMPT_COMMANDS)
    p = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(LOGIN)} terminal profile card">')
    p.append(f"<style>text{{font-family:{FONT};font-size:{FS}px;white-space:pre}}"
             f".art{{fill:{ACCENT}}}.hd{{fill:{HEADER_COLOR};font-weight:700}}"
             f".lb{{fill:{LABEL_COLOR};font-weight:700}}.vl{{fill:{VALUE_COLOR}}}"
             f".dim{{fill:#6b7a99}}.cur{{animation:blink 1s steps(1) infinite}}"
             f"@keyframes blink{{50%{{opacity:0}}}}{css_prompt}</style>")
    p.append(f'<rect width="{width}" height="{height}" rx="10" fill="{BG_COLOR}"/>')
    p.append(f'<path d="M0 10a10 10 0 0 1 10-10h{width-20}a10 10 0 0 1 10 10V{top}H0z" fill="{TITLEBAR_COLOR}"/>')
    for i, c in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        p.append(f'<circle cx="{20+i*20}" cy="{top/2}" r="6" fill="{c}"/>')
    p.append(f'<text x="{width/2}" y="{top/2+4}" text-anchor="middle" class="dim">{escape(LOGIN)}@github: ~</text>')

    for i, line in enumerate(art):
        p.append(f'<text class="art" x="{art_x}" y="{body_y + i*LH}" xml:space="preserve">{escape(line)}</text>')

    y = body_y
    p.append(f'<text class="hd" x="{info_x}" y="{y}">{escape(header)}</text>')
    y += LH
    p.append(f'<text class="dim" x="{info_x}" y="{y}">{"─" * len(header)}</text>')
    y += LH * 2
    lw = max(len(k) for k, _ in fields) + 2
    for k, v in fields:
        p.append(f'<text x="{info_x}" y="{y}" xml:space="preserve"><tspan class="lb">{escape((k + ":").ljust(lw))}</tspan>'
                 f'<tspan class="vl">{escape(v)}</tspan></text>')
        y += LH
    y += LH
    for i, c in enumerate(PALETTE):
        p.append(f'<rect x="{info_x + i*26}" y="{y-12}" width="24" height="14" fill="{c}" stroke="#2a3552"/>')

    px = pad + len(f"{LOGIN}@github:~$ ") * CW
    p.append(f'<text x="{pad}" y="{prompt_y}" xml:space="preserve"><tspan class="hd">{escape(LOGIN)}@github</tspan>'
             f'<tspan class="lb">:</tspan><tspan style="fill:{ACCENT}">~</tspan>'
             f'<tspan class="lb">$ </tspan></text>')
    for i, c in enumerate(PROMPT_COMMANDS):
        p.append(f'<clipPath id="cp{i}"><rect class="w{i}" x="{px:.1f}" y="{prompt_y-FS}" width="0" height="{FS+6}"/></clipPath>')
        p.append(f'<text x="{px:.1f}" y="{prompt_y}" clip-path="url(#cp{i})" style="fill:{HEADER_COLOR}">{escape(c)}</text>')
        p.append(f'<g class="c{i}"><rect class="cur" x="{px:.1f}" y="{prompt_y-FS+1}" width="{CW:.1f}" height="{FS+2}" fill="{ACCENT}"/></g>')
    p.append("</svg>")
    return "\n".join(p)


if __name__ == "__main__":
    svg = build_svg()
    os.makedirs(os.path.dirname(OUT_PATH) or ".", exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {OUT_PATH} ({len(svg)} bytes)")
