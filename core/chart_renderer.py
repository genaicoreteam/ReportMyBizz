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
