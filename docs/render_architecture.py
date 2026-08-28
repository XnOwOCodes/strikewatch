"""Render docs/architecture.png — StrikeWatch watch loop."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "architecture.png"
W, H = 1600, 900
BG = (14, 17, 22)
INK = (232, 237, 245)
MUTED = (139, 151, 168)
LINE = (42, 51, 64)
CARD = (23, 28, 36)
GREEN = (61, 214, 140)
GREEN_BG = (18, 53, 38)
AMBER = (255, 176, 32)
AMBER_BG = (58, 42, 12)
NAVY = (76, 125, 255)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)


def rounded(draw, box, fill, outline=LINE, radius=16, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def wrapped(draw, text, fnt, x, y, max_w, fill=MUTED, gap=4):
    words = text.split()
    line = ""
    cy = y
    for word in words:
        trial = (line + " " + word).strip()
        if draw.textbbox((0, 0), trial, font=fnt)[2] <= max_w:
            line = trial
        else:
            draw.text((x, cy), line, font=fnt, fill=fill)
            cy += fnt.size + gap
            line = word
    if line:
        draw.text((x, cy), line, font=fnt, fill=fill)
        cy += fnt.size + gap
    return cy


def arrow(draw, start, end, fill=NAVY):
    draw.line([start, end], fill=fill, width=4)
    x2, y2 = end
    x1, y1 = start
    ang = math.atan2(y2 - y1, x2 - x1)
    for delta in (2.6, -2.6):
        ax = x2 - 14 * math.cos(ang + delta)
        ay = y2 - 14 * math.sin(ang + delta)
        draw.line([(x2, y2), (ax, ay)], fill=fill, width=4)


def box(draw, xy, title, body, fill=CARD, title_fill=INK):
    rounded(draw, xy, fill=fill)
    x0, y0, x1, y1 = xy
    draw.text((x0 + 18, y0 + 14), title, font=font(18, True), fill=title_fill)
    wrapped(draw, body, font(14), x0 + 18, y0 + 44, x1 - x0 - 36, fill=MUTED)


def main() -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.text((48, 28), "StrikeWatch", font=font(36, True), fill=INK)
    draw.text(
        (48, 78),
        "Options-alpha pager  ·  defined-risk paper desk  ·  not a chatbot",
        font=font(16),
        fill=MUTED,
    )
    box(draw, (48, 140, 380, 320), "Universe", "SPY QQQ IWM AAPL. Fixtures locally. Alpaca option contracts when paper keys exist.")
    box(draw, (430, 140, 762, 320), "Policy", "IV rank + implied vs realized. Bull put credit, bear call credit, or cash-secured put. Deterministic. No LLM keys.")
    box(draw, (812, 140, 1552, 320), "Risk gates", "Paper only · kill switch · US regular hours · defined-risk · size / notional / daily loss / open names · duplicate signal.")
    arrow(draw, (380, 230), (430, 230))
    arrow(draw, (762, 230), (812, 230))
    box(draw, (48, 400, 762, 560), "QUIET", "Default. No signal, or any gate fires. Board still updates. Most cycles look like this.", fill=GREEN_BG, title_fill=GREEN)
    box(draw, (812, 400, 1552, 560), "ALERT", "One defined-risk mleg order. MockBroker fills now. AlpacaBroker posts to paper-api.alpaca.markets only.", fill=AMBER_BG, title_fill=AMBER)
    arrow(draw, (430, 320), (300, 400))
    arrow(draw, (1180, 320), (1180, 400))
    box(draw, (48, 620, 1552, 820), "Status board", "FastAPI last-decision board: why, which gates fired, paper/mock P&L, open legs. Kill with STRIKEWATCH_KILL=1. Official extras: uvx alpaca-mcp-server (ALPACA_PAPER_TRADE=true) and alpaca CLI.")
    arrow(draw, (300, 560), (300, 620))
    arrow(draw, (1180, 560), (1180, 620))
    img.save(OUT, "PNG")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
