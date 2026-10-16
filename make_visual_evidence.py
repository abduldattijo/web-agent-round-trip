"""Make captioned article figures from saved browser screenshots; no browser/model calls."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "figures"
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
INK = "#17212b"
MUTED = "#526170"
BLUE = "#1774a5"
RED = "#bf3e3e"
GREEN = "#167a50"


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def label(draw, xy, title, subtitle, color=INK):
    x, y = xy
    draw.text((x, y), title, font=font(32, True), fill=color)
    draw.text((x, y + 46), subtitle, font=font(24), fill=MUTED)


def screenshot(path, box=None, scale=1):
    im = Image.open(ROOT / path).convert("RGB")
    if box:
        im = im.crop(box)
    if scale != 1:
        im = im.resize((im.width * scale, im.height * scale))
    return im


def frame(draw, box, color="#ccd5dd"):
    draw.rectangle(box, outline=color, width=2)


def search():
    base = Image.new("RGB", (1880, 570), "#f5f8fa")
    d = ImageDraw.Draw(base)
    d.text((40, 24), "A parser token changed the exact search", font=font(40, True), fill=INK)
    items = [
        ("results/phase_b_screenshots/search_token_10_clean.png", "Clean execution", "Field: Record-10", GREEN),
        ("results/phase_b_screenshots/search_token_10_defect.png", "Injected parser fault", "Field: Record-10[im_end]", RED),
    ]
    for i, (path, title, sub, color) in enumerate(items):
        x = 40 + i * 940
        label(d, (x, 94), title, sub, color)
        im = screenshot(path, (0, 0, 900, 230))
        base.paste(im, (x, 185))
        frame(d, (x, 185, x + 900, 415))
        d.rectangle((x + 17, 278, x + 179, 320), outline=color, width=4)
    d.text((40, 450), "Same recorded Haiku decision, seed 10; screenshots from clean and faulty Phase B replays.", font=font(23), fill=MUTED)
    d.text((40, 484), "The injected suffix is visible in the field; the Phase C trace reports 'No exact result'.", font=font(23), fill=MUTED)
    base.save(OUT / "search_token_evidence.png")


def iframe():
    base = Image.new("RGB", (1500, 710), "#f5f8fa")
    d = ImageDraw.Draw(base)
    d.text((40, 24), "The click succeeded; the tool said it did not", font=font(40, True), fill=INK)
    im = screenshot("results/phase_c_screenshots/frame_feedback_10_round_trip_run1_step1.png")
    base.paste(im, (40, 90))
    frame(d, (40, 90, 940, 690))
    d.rectangle((76, 429, 538, 468), outline=GREEN, width=4)
    label(d, (980, 118), "Page result", "Record 4 selected in the frame", GREEN)
    label(d, (980, 265), "Raw tool feedback", "No detectable change", RED)
    label(d, (980, 412), "Round-trip check", "Frame selected row-4", BLUE)
    d.text((980, 568), "Phase C, seed 10, run 1", font=font(23), fill=MUTED)
    d.text((980, 603), "Same-origin local fixture", font=font(23), fill=MUTED)
    base.save(OUT / "iframe_feedback_evidence.png")


def hover():
    base = Image.new("RGB", (1480, 640), "#f5f8fa")
    d = ImageDraw.Draw(base)
    d.text((40, 24), "The same layout under two feedback policies", font=font(40, True), fill=INK)
    items = [
        ("results/phase_c_screenshots/hover_value_21_unverified_run1_step1.png", "Unverified", "No value visible; agent stopped", RED),
        ("results/phase_c_screenshots/hover_value_21_generic_run1_step2.png", "Generic check", "After repeat hover: Value 89", GREEN),
    ]
    for i, (path, title, sub, color) in enumerate(items):
        x = 40 + i * 720
        label(d, (x, 105), title, sub, color)
        im = screenshot(path, (360, 260, 720, 460), scale=2)
        base.paste(im, (x, 205))
        frame(d, (x, 205, x + 720, 605))
    d.text((40, 615), "Separate episodes on the same page layout", font=font(18), fill=MUTED)
    base.save(OUT / "hover_timing_evidence.png")


def result_story():
    base = Image.new("RGB", (1800, 1220), "#f5f8fa")
    d = ImageDraw.Draw(base)
    d.text((50, 34), "The agent chose correctly. The browser clicked elsewhere.", font=font(43, True), fill=INK)
    d.text((50, 94), "Same recorded Haiku decision, replayed on the same local layout", font=font(26), fill=MUTED)
    panels = [
        ("figures/video_frame_clean.png", "Clean execution", "Item 15 selected", GREEN),
        ("figures/video_frame_faulty.png", "Faulty coordinate mapping", "Item 10 selected", RED),
    ]
    for i, (path, heading, outcome, color) in enumerate(panels):
        x = 50 + i * 870
        d.text((x, 155), heading, font=font(31, True), fill=color)
        im = screenshot(path).resize((800, 533))
        base.paste(im, (x, 215))
        frame(d, (x, 215, x + 800, 748))
        d.text((x, 770), outcome, font=font(29, True), fill=color)
    d.rounded_rectangle((50, 845, 1750, 1160), radius=18, fill="white", outline="#ccd5dd", width=2)
    d.text((86, 875), "What the full experiment found", font=font(36, True), fill=INK)
    lines = [
        ("Wrong click or corrupted search", "0/60 completed under every checking policy", RED),
        ("False iframe feedback", "60/60 completed under every policy", GREEN),
        ("Early tooltip screenshot", "56/60 unverified; 60/60 with either check", BLUE),
    ]
    for i, (name, outcome, color) in enumerate(lines):
        y = 940 + i * 65
        d.ellipse((87, y + 9, 111, y + 33), fill=color)
        d.text((135, y), name, font=font(26, True), fill=INK)
        d.text((750, y), outcome, font=font(26), fill=MUTED)
    d.text((50, 1180), "Deliberately injected faults; 20 layouts × 3 runs per policy. Checks diagnosed persistent faults but did not repair them.", font=font(20), fill=MUTED)
    base.save(OUT / "failure_and_result_story.png")


def click_pair():
    base = Image.new("RGB", (1880, 820), "#f5f8fa")
    d = ImageDraw.Draw(base)
    d.text((40, 22), "One decision, two browser outcomes", font=font(40, True), fill=INK)
    items = [
        ("figures/video_frame_clean.png", "Working coordinate conversion", "Item 15 selected", GREEN),
        ("figures/video_frame_faulty.png", "Injected coordinate error", "Item 10 selected", RED),
    ]
    for i, (path, heading, outcome, color) in enumerate(items):
        x = 40 + 940 * i
        d.text((x, 92), heading, font=font(31, True), fill=color)
        im = screenshot(path)
        base.paste(im, (x, 142))
        frame(d, (x, 142, x + 900, 742))
        d.text((x, 760), outcome, font=font(28, True), fill=color)
    base.save(OUT / "continuous_click_seed12_comparison.png")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    search()
    iframe()
    hover()
    result_story()
    click_pair()
