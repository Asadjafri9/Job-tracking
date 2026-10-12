"""Check the proposed DGN-002 semantic color pairs against WCAG contrast targets."""
from __future__ import annotations

import re
from pathlib import Path

TOKENS = Path(__file__).parents[1] / "tokens" / "tokens.css"
values = dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})\s*;", TOKENS.read_text()))


def luminance(color: str) -> float:
    rgb = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in rgb]
    return sum(channel * weight for channel, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))


def ratio(foreground: str, background: str) -> float:
    high, low = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)


pairs = [
    ("Primary text / canvas", "--color-text-primary", "--color-canvas", 4.5),
    ("Primary text / surface", "--color-text-primary", "--color-surface", 4.5),
    ("Secondary text / canvas", "--color-text-secondary", "--color-canvas", 4.5),
    ("Inverse text / brand", "--color-text-inverse", "--color-brand", 4.5),
    ("Inverse text / brand hover", "--color-text-inverse", "--color-brand-hover", 4.5),
    ("Brand text / subtle", "--color-brand", "--color-brand-subtle", 4.5),
    ("Success", "--color-success-text", "--color-success-surface", 4.5),
    ("Warning", "--color-warning-text", "--color-warning-surface", 4.5),
    ("Error", "--color-danger-text", "--color-danger-surface", 4.5),
    ("Information", "--color-info-text", "--color-info-surface", 4.5),
    ("Neutral", "--color-neutral-text", "--color-neutral-surface", 4.5),
    ("Control border / white", "--color-control-border", "--color-surface", 3.0),
    ("Control border / canvas", "--color-control-border", "--color-canvas", 3.0),
    ("Focus / white", "--color-focus", "--color-surface", 3.0),
    ("Focus / canvas", "--color-focus", "--color-canvas", 3.0),
    ("Focus on brand", "--color-focus-on-brand", "--color-brand", 3.0),
]
failed = False
for name, foreground, background, minimum in pairs:
    value = ratio(values[foreground], values[background])
    passed = value >= minimum
    failed |= not passed
    print(f"{'PASS' if passed else 'FAIL'} {name}: {value:.2f}:1 (minimum {minimum:.1f}:1)")
raise SystemExit(1 if failed else 0)
