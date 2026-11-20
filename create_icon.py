"""
Generates the Lecture Desk — Engineering Study Suite application icon.

Design language: Warm Paper (#F7F6F2), Prussian Ink (#1E3A8A), Warm Ochre (#C27803),
and Graphite (#1A1917). Minimal Swiss-editorial open study ledger on a desk with a
bookmark ribbon and clean acoustic cadence mark — zero gradients, zero neon glows,
zero AI/circuit clichés.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter


def render_lecture_desk_icon(canvas_size: int = 2048) -> Image.Image:
    s = canvas_size
    pad = int(s * 0.04)
    radius = int(s * 0.22)

    # Palette (matches static/styles.css Warm Paper Light tokens)
    PAPER_BG = (247, 246, 242, 255)      # #F7F6F2
    PAPER_SHADOW = (232, 229, 220, 255)  # #E8E5DC
    BORDER_INK = (30, 58, 138, 255)      # #1E3A8A Prussian Ink
    COVER_DARK = (23, 44, 108, 255)      # #172C6C Deep Bookcloth
    COVER_MAIN = (30, 64, 175, 255)      # #1E40AF Prussian Blue
    PAGE_LEFT = (255, 255, 255, 255)     # #FFFFFF
    PAGE_RIGHT = (245, 243, 236, 255)    # #F5F3EC
    SPINE_INK = (26, 25, 23, 255)        # #1A1917
    LINE_MUTED = (145, 140, 130, 255)    # #918C82
    LINE_SOFT = (206, 201, 188, 255)     # #CEC9BC
    OCHRE = (194, 120, 3, 255)           # #C27803 Warm Ochre
    OCHRE_DARK = (154, 91, 19, 255)      # #9A5B13
    DESK_RULE = (196, 191, 179, 255)     # #C4BFB3

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # 1. Warm Paper Squircle Base (clipped cleanly to squircle mask)
    paper_canvas = Image.new("RGBA", (s, s), PAPER_BG)
    pdraw = ImageDraw.Draw(paper_canvas)

    # Quiet grounded desk surface band in lower quarter
    desk_band_y = int(s * 0.74)
    pdraw.rectangle((0, desk_band_y, s, s), fill=PAPER_SHADOW)

    # Crisp desk horizon rule
    rule_w = max(4, int(s * 0.007))
    pdraw.line([(0, desk_band_y), (s, desk_band_y)], fill=DESK_RULE, width=rule_w)

    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((pad, pad, s - pad, s - pad), radius=radius, fill=255)
    img.paste(paper_canvas, (0, 0), mask)

    # 2. Soft grounded shadow under the open book on the desk
    shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle(
        (int(s * 0.165), int(s * 0.695), int(s * 0.835), int(s * 0.768)),
        radius=int(s * 0.035),
        fill=(26, 25, 23, 52),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=int(s * 0.018)))
    img = Image.alpha_composite(img, shadow)

    # 3. Open Hardbound Study Ledger (Bookcloth Cover + Crisp Cream Pages)
    emblem = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(emblem)

    cx = s // 2
    book_left = int(s * 0.165)
    book_right = int(s * 0.835)
    book_top = int(s * 0.255)
    book_bottom = int(s * 0.735)
    cover_r = int(s * 0.036)

    # Outer Prussian Blue cloth hardcover
    draw.rounded_rectangle(
        (book_left, book_top, book_right, book_bottom),
        radius=cover_r,
        fill=COVER_MAIN,
        outline=COVER_DARK,
        width=int(s * 0.010),
    )

    # Bottom cloth spine notch
    spine_w = int(s * 0.064)
    draw.rounded_rectangle(
        (cx - spine_w // 2, book_bottom - int(s * 0.036), cx + spine_w // 2, book_bottom + int(s * 0.016)),
        radius=int(s * 0.018),
        fill=COVER_DARK,
    )

    # Left & Right crisp open pages inset inside hardcover
    inset_x = int(s * 0.038)
    inset_top = int(s * 0.034)
    inset_bot = int(s * 0.044)
    gutter = int(s * 0.008)
    page_r = int(s * 0.018)

    lp_x1 = book_left + inset_x
    lp_x2 = cx - gutter
    rp_x1 = cx + gutter
    rp_x2 = book_right - inset_x
    p_y1 = book_top + inset_top
    p_y2 = book_bottom - inset_bot

    # Stacked page edge underneath pages for physical depth
    draw.rounded_rectangle(
        (lp_x1 + int(s * 0.004), p_y1 + int(s * 0.014), rp_x2 - int(s * 0.004), p_y2 + int(s * 0.016)),
        radius=page_r,
        fill=LINE_SOFT,
    )

    # Left page (pure white paper)
    draw.rounded_rectangle((lp_x1, p_y1, lp_x2, p_y2), radius=page_r, fill=PAGE_LEFT)
    # Right page (subtle warm ivory paper)
    draw.rounded_rectangle((rp_x1, p_y1, rp_x2, p_y2), radius=page_r, fill=PAGE_RIGHT)

    # Crisp center spine crease
    draw.rectangle((cx - gutter, p_y1, cx + gutter, p_y2), fill=COVER_DARK)
    draw.line([(cx, p_y1), (cx, p_y2)], fill=(15, 30, 74, 255), width=max(4, int(s * 0.005)))

    # 4. Left Page Content: Editorial Study Notes + Warm Ochre Exam Highlight
    lx1 = lp_x1 + int(s * 0.044)
    lx2 = lp_x2 - int(s * 0.044)
    line_r = int(s * 0.010)

    # Chapter heading bar (Prussian Ink)
    y_head = p_y1 + int(s * 0.068)
    draw.rounded_rectangle(
        (lx1, y_head, lx1 + int((lx2 - lx1) * 0.72), y_head + int(s * 0.028)),
        radius=line_r,
        fill=BORDER_INK,
    )

    # Body text lines (Graphite)
    y_l1 = y_head + int(s * 0.068)
    draw.rounded_rectangle((lx1, y_l1, lx2, y_l1 + int(s * 0.020)), radius=line_r, fill=LINE_MUTED)

    y_l2 = y_l1 + int(s * 0.048)
    draw.rounded_rectangle((lx1, y_l2, lx1 + int((lx2 - lx1) * 0.86), y_l2 + int(s * 0.020)), radius=line_r, fill=LINE_MUTED)

    # Highlighted Exam Alert callout bar (Warm Ochre accent + cream tint)
    y_hl = y_l2 + int(s * 0.062)
    hl_h = int(s * 0.072)
    draw.rounded_rectangle(
        (lx1, y_hl, lx2, y_hl + hl_h),
        radius=int(s * 0.012),
        fill=(253, 248, 238, 255),
        outline=(233, 206, 153, 255),
        width=max(3, int(s * 0.004)),
    )
    draw.rounded_rectangle(
        (lx1, y_hl, lx1 + int(s * 0.018), y_hl + hl_h),
        radius=int(s * 0.006),
        fill=OCHRE,
    )
    draw.rounded_rectangle(
        (lx1 + int(s * 0.036), y_hl + int(hl_h * 0.36), lx2 - int(s * 0.030), y_hl + int(hl_h * 0.64)),
        radius=int(s * 0.008),
        fill=OCHRE_DARK,
    )

    # Bottom short note line
    y_l3 = y_hl + hl_h + int(s * 0.046)
    draw.rounded_rectangle((lx1, y_l3, lx1 + int((lx2 - lx1) * 0.65), y_l3 + int(s * 0.018)), radius=line_r, fill=LINE_SOFT)

    # 5. Right Page Content: Minimal Lecture Audio Cadence Bars + Summary Lines
    rx1 = rp_x1 + int(s * 0.044)
    rx2 = rp_x2 - int(s * 0.044)
    r_mid_x = (rx1 + rx2) // 2

    # Clean 5-bar symmetrical lecture audio cadence glyph (Prussian Ink)
    bar_heights = [0.052, 0.106, 0.156, 0.106, 0.052]
    bar_w = int(s * 0.023)
    bar_gap = int(s * 0.022)
    total_bars_w = len(bar_heights) * bar_w + (len(bar_heights) - 1) * bar_gap
    bar_start_x = r_mid_x - total_bars_w // 2
    wave_cy = p_y1 + int(s * 0.215)

    for idx, h_frac in enumerate(bar_heights):
        bh = int(s * h_frac)
        bx1 = bar_start_x + idx * (bar_w + bar_gap)
        bx2 = bx1 + bar_w
        by1 = wave_cy - bh // 2
        by2 = wave_cy + bh // 2
        bar_col = OCHRE if idx == 2 else BORDER_INK
        draw.rounded_rectangle((bx1, by1, bx2, by2), radius=bar_w // 2, fill=bar_col)

    # Clean caption lines underneath the audio cadence mark
    y_cap1 = wave_cy + int(s * 0.112)
    draw.rounded_rectangle((rx1 + int(s * 0.018), y_cap1, rx2 - int(s * 0.018), y_cap1 + int(s * 0.020)), radius=line_r, fill=LINE_MUTED)
    y_cap2 = y_cap1 + int(s * 0.042)
    draw.rounded_rectangle((rx1 + int(s * 0.048), y_cap2, rx2 - int(s * 0.048), y_cap2 + int(s * 0.018)), radius=line_r, fill=LINE_SOFT)

    # 6. Classic Warm Ochre Bookmark Ribbon at Top-Right of Ledger
    rib_w = int(s * 0.054)
    rib_x1 = rp_x2 - int(s * 0.088)
    rib_x2 = rib_x1 + rib_w
    rib_top = book_top - int(s * 0.026)
    rib_bot = p_y1 + int(s * 0.096)
    rib_notch = int(s * 0.022)

    ribbon_poly = [
        (rib_x1, rib_top),
        (rib_x2, rib_top),
        (rib_x2, rib_bot),
        ((rib_x1 + rib_x2) // 2, rib_bot - rib_notch),
        (rib_x1, rib_bot),
    ]
    draw.polygon(ribbon_poly, fill=OCHRE)
    draw.line([(rib_x1, rib_top), (rib_x2, rib_top)], fill=OCHRE_DARK, width=max(4, int(s * 0.006)))

    img = Image.alpha_composite(img, emblem)

    # 7. Outer Crisp Prussian Ink Frame around Squircle
    frame = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(frame)
    fdraw.rounded_rectangle(
        (pad, pad, s - pad, s - pad),
        radius=radius,
        outline=BORDER_INK,
        width=int(s * 0.016),
    )
    img = Image.alpha_composite(img, frame)

    return img


def build_clean_icon():
    base_dir = Path(__file__).parent.resolve()
    static_dir = base_dir / "static"
    static_dir.mkdir(exist_ok=True)

    png_out = static_dir / "app_icon.png"
    master_out = static_dir / "engineering_icon_master.png"
    ico_out_1 = base_dir / "biomedical_icon.ico"
    ico_out_2 = base_dir / "app_icon.ico"

    print("Rendering Lecture Desk editorial icon (2048x2048 -> 512x512)...")
    hi_res = render_lecture_desk_icon(2048)

    master_img = hi_res.resize((1024, 1024), Image.Resampling.LANCZOS)
    master_img.save(master_out, format="PNG")

    final_png = hi_res.resize((512, 512), Image.Resampling.LANCZOS)
    final_png.save(png_out, format="PNG")
    print(f"Saved PNG icon: {png_out}")

    icon_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    final_png.save(ico_out_1, format="ICO", sizes=icon_sizes)
    final_png.save(ico_out_2, format="ICO", sizes=icon_sizes)
    print(f"Saved ICO icons: {ico_out_1}, {ico_out_2}")


if __name__ == "__main__":
    build_clean_icon()
