"""
core/chart_renderer.py

Small, dependency-light chart primitives used to make the PDF report
readable at a glance instead of a wall of numbers: circular progress
rings (profile score, SEO score, response rate, ...) and a labeled map
pin. Like map_renderer.py, everything is drawn with Pillow and returned
as a base64 data URI -- no disk writes, so this works the same locally
and in a read-only serverless function.
"""

import base64
import io
import math

from PIL import Image, ImageDraw, ImageFont


def to_data_uri(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_ring(pct, color_hex: str, label: str = None, sublabel: str = None,
                 track_hex: str = "#EDE6D6", text_hex: str = "#1F3D2B",
                 size: int = 140, thickness: int = 16) -> str:
    """A circular progress ring with the percentage baked in as real
    pixels. xhtml2pdf doesn't support CSS position:absolute or
    background-image reliably enough to overlay live PDF text on top of
    an <img>, so the label is drawn straight into the PNG instead --
    the one approach that is guaranteed to line up.
    """
    pct_val = max(0.0, min(100.0, pct or 0.0))
    scale = 4
    s = size * scale
    t = thickness * scale
    pad = t // 2 + scale

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    bbox = [pad, pad, s - pad, s - pad]

    draw.arc(bbox, 0, 360, fill=track_hex, width=t)

    if pct_val > 0:
        end_angle = -90 + (pct_val / 100.0) * 360
        draw.arc(bbox, -90, end_angle, fill=color_hex, width=t)

        # Rounded end caps so the arc doesn't look cut off.
        r = t / 2
        for angle in (-90, end_angle):
            rad = math.radians(angle)
            cx = s / 2 + (s / 2 - pad) * math.cos(rad)
            cy = s / 2 + (s / 2 - pad) * math.sin(rad)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color_hex)

    if label is None:
        label = f"{round(pct_val)}%"

    main_font = ImageFont.load_default(size=int(s * 0.22))
    draw_center_text(draw, label, main_font, text_hex,
                      center=(s / 2, s / 2 - (s * 0.06 if sublabel else 0)))

    if sublabel:
        sub_font = ImageFont.load_default(size=int(s * 0.09))
        draw_center_text(draw, sublabel, sub_font, text_hex,
                          center=(s / 2, s / 2 + s * 0.16))

    img = img.resize((size, size), Image.LANCZOS)
    return to_data_uri(img)


def draw_center_text(draw: ImageDraw.ImageDraw, text: str, font, fill,
                      center):
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = center[0] - w / 2 - bbox[0]
    y = center[1] - h / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=fill)


def _hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _fit_text(draw, text, max_width, start_size, min_size, step=2):
    """Shrinks font size until `text` fits in `max_width`; if it still
    doesn't fit at the smallest size, truncates with an ellipsis -- the
    same behavior the reference report itself uses for long addresses."""
    size = start_size
    while size > min_size:
        font = ImageFont.load_default(size=size)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return font, text
        size -= step

    font = ImageFont.load_default(size=min_size)
    truncated = text
    while truncated and draw.textbbox((0, 0), truncated + "…", font=font)[2] > max_width:
        truncated = truncated[:-1]
    return font, (truncated + "…" if truncated != text else text)


def _star_points(cx, cy, outer_r, inner_r):
    points = []
    for i in range(10):
        angle = math.radians(-90 + i * 36)
        r = outer_r if i % 2 == 0 else inner_r
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return points


def render_header_banner(business_name: str, rating, review_count, address: str,
                          grad_start: str, grad_end: str,
                          width: int = 1060, height: int = 190) -> str:
    """The report's title band: a true left-to-right gradient with the
    business name, star rating, and address baked in as real pixels.
    xhtml2pdf supports neither CSS gradients nor a reliable way to
    overlay live PDF text on a background image, so -- as with the
    rings and the map -- this is drawn once with Pillow instead."""
    scale = 2
    w, h = width * scale, height * scale
    img = Image.new("RGB", (w, h), _hex_to_rgb(grad_end))
    draw = ImageDraw.Draw(img)

    start_rgb, end_rgb = _hex_to_rgb(grad_start), _hex_to_rgb(grad_end)
    steps = 160
    for i in range(steps):
        t = i / (steps - 1)
        color = tuple(round(start_rgb[c] + (end_rgb[c] - start_rgb[c]) * t) for c in range(3))
        x0, x1 = int(w * i / steps), int(w * (i + 1) / steps) + 1
        draw.rectangle([x0, 0, x1, h], fill=color)

    pad_x = 34 * scale
    max_text_w = w - 2 * pad_x

    wordmark_font = ImageFont.load_default(size=12 * scale)
    draw.text((pad_x, 18 * scale), "REPORTMYBIZZ", font=wordmark_font, fill=(224, 219, 250))

    name_font, name_text = _fit_text(draw, business_name, max_text_w,
                                      start_size=30 * scale, min_size=17 * scale)
    name_y = 46 * scale
    draw.text((pad_x, name_y), name_text, font=name_font, fill="white")
    name_bottom = draw.textbbox((pad_x, name_y), name_text, font=name_font)[3]

    meta_y = name_bottom + 14 * scale
    cursor_x = pad_x

    if rating:
        star_r_outer, star_r_inner = 7 * scale, 3 * scale
        star_gap = 18 * scale
        filled = round(rating)
        for i in range(5):
            sx = cursor_x + star_r_outer + i * star_gap
            sy = meta_y + star_r_outer
            color = (247, 197, 72) if i < filled else (255, 255, 255)
            draw.polygon(_star_points(sx, sy, star_r_outer, star_r_inner), fill=color)
        cursor_x += star_gap * 5 + 8 * scale

        meta_font = ImageFont.load_default(size=13 * scale)
        rating_text = f"{rating} ({review_count or 0} reviews)"
        draw.text((cursor_x, meta_y + star_r_outer - 7 * scale), rating_text,
                   font=meta_font, fill="white")
        bbox = draw.textbbox((cursor_x, meta_y), rating_text, font=meta_font)
        cursor_x = bbox[2] + 14 * scale

        sep_font = meta_font
        draw.text((cursor_x, meta_y + star_r_outer - 7 * scale), "·",
                   font=sep_font, fill=(224, 219, 250))
        cursor_x += 14 * scale

    addr_font, addr_text = _fit_text(draw, address or "Address not available",
                                      w - pad_x - cursor_x, start_size=13 * scale,
                                      min_size=13 * scale)
    draw.text((cursor_x, meta_y + 1 * scale), addr_text, font=addr_font, fill=(224, 219, 250))

    img = img.resize((width, height), Image.LANCZOS)
    return to_data_uri(img)
