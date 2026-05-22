# @cc_yaroh Visual Assets

## Versioning Convention

`avatar-v{N}.png` / `banner-v{N}.png` — increment N when regenerating. Keep old versions for A/B reference.

## Specs

| Asset | Size | Format | Notes |
|---|---|---|---|
| avatar-v1.png | 1024x1024 px | PNG | X crops to circle — keep subject centered |
| banner-v1.png | 1500x500 px | PNG | Safe zone: center 1500x400. Bottom-right 200x200 overlaps with avatar |

## Color Palette

| Role | Hex |
|---|---|
| Base | `#FAFAF9` (warm off-white) |
| Text | `#1C1917` (near-black) |
| Accent | `#CC785C` (Claude orange) |
| Sub | `#78716C` (warm gray) |
| Highlight | `#FAE3D1` (light orange) |

---

## Avatar v1 — Generation Record

**Generated**: 2026-05-19  
**Tool**: ChatGPT Image Generation (GPT-4o)  
**Style**: Soft 3D render, minimalist AI robot, Claude orange eyes + headset, warm off-white background

**Prompt (EN)**:

```
A minimalist Twitter/X profile avatar of a friendly AI robot character, bust-up portrait, centered composition, square 1:1 ratio.

Style: Soft 3D render, clean editorial illustration, minimalist tech aesthetic. Inspired by Anthropic's brand: warm, approachable, intelligent.

Robot design:
- Smooth white/off-white ceramic-like head with rounded edges (NOT chrome, NOT industrial)
- Two simple glowing rectangular eyes in warm orange (#CC785C / Claude orange)
- Subtle headset/headphones in matching orange
- A small, calm smile suggested by a single thin curve (optional)
- Slight 3/4 angle, looking slightly forward
- No human features, no skin texture

Background: solid warm off-white (#FAFAF9), with a very subtle radial gradient to slightly darker warm cream at edges. NO patterns, NO code overlay.

Lighting: soft, even studio light from upper-left, gentle shadow on lower-right side of head. Slight warm rim light on the right edge of the head.

Mood: friendly, intelligent, calm, "build in public" energy. NOT menacing, NOT cold, NOT cyberpunk.

The composition must work when cropped to a circle — keep the robot head centered with 15% padding on all sides.

Output: high-resolution 1024x1024 PNG, no text, no logos, no watermarks.
```

---

## Banner v1 — Generation Record

**Generated**: 2026-05-19  
**Tool**: ChatGPT Image Generation (GPT-4o)  
**Style**: Light-themed terminal/code editor window (left) + Japanese headline text (right), Claude orange accents

**Prompt (EN)**:

```
A minimalist Twitter/X header banner, 1500x500 pixel landscape format (3:1 aspect ratio).

Concept: A clean, light-themed code editor / terminal screen aesthetic. Editorial minimalism inspired by Anthropic's brand and modern dev tooling sites (Linear, Vercel, Stripe Press).

Layout (left-aligned, with generous whitespace):

LEFT 60% of the canvas — a stylized "terminal window" with:
- Warm off-white background (#FAFAF9)
- Subtle 1px border in light warm gray (#E7E5E4)
- Three small colored dots in the top-left (mac-style window controls), in muted tones — NOT bright traffic-light colors
- Inside the window, fixed-width text in dark warm gray (#1C1917):
    Line 1: `$ claude code --profile x-growth`
    Line 2: `> generating tweet...`
    Line 3: `> posted: build in public day 2`
- The `$` and `>` prompts are in Claude orange (#CC785C)
- A single blinking-cursor block in Claude orange at the end of the last line

RIGHT 40% of the canvas — a clean text block, right-aligned:
- Main headline (large, bold, near-black #1C1917):
    "Claude Code で副業を全自動化中"
- Sub-line in Claude orange (#CC785C), medium weight:
    "3ヶ月で1万フォロワー & 月50万円チャレンジ"
- Tiny tag below in warm gray (#78716C):
    "@cc_yaroh — build in public"

Typography: modern sans-serif for Japanese (similar to Inter / Noto Sans JP), monospace for terminal lines (similar to JetBrains Mono).

Color palette (strictly enforced):
- Background: #FAFAF9 (warm off-white)
- Primary text: #1C1917 (near-black)
- Accent: #CC785C (Claude orange)
- Sub-text: #78716C (warm gray)
- NO neon, NO bright cyan/purple, NO gradients beyond very subtle warm whites

Composition rules:
- The bottom-right 200x200 px area must be visually empty / safe (the profile avatar will overlap there) — do NOT place text or important visual elements in that zone
- Center-vertical middle 1500x400 strip must contain all key info (mobile crop-safe)
- Generous whitespace, editorial feel, NOT busy

Output: 1500x500 PNG, sharp, high resolution, no watermarks, no decorative icons, no emoji.
```

---

## Upload Instructions

1. Go to `https://x.com/settings/profile`
2. Profile image: click camera icon → select `avatar-v1.png` → confirm circle crop → Apply
3. Header image: click camera icon → select `banner-v1.png` → adjust position → Apply
4. Save
