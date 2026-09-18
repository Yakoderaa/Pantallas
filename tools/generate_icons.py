from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "generated"
OUT.mkdir(parents=True, exist_ok=True)


def _app_icon(size: int = 1024, *, tray: bool = False) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    s = size

    if tray:
        pad = int(s * 0.12)
        width = max(3, int(s * 0.06))
        draw.rounded_rectangle(
            (pad, int(s * 0.18), s - pad, int(s * 0.70)),
            radius=int(s * 0.10),
            fill=(18, 24, 36, 255),
            outline=(96, 166, 255, 255),
            width=width,
        )
        cx = s // 2
        draw.line(
            (cx, int(s * 0.70), cx, int(s * 0.82)),
            fill=(96, 166, 255, 255),
            width=width,
        )
        draw.line(
            (int(s * 0.34), int(s * 0.84), int(s * 0.66), int(s * 0.84)),
            fill=(96, 166, 255, 255),
            width=width,
        )
        draw.line(
            (int(s * 0.22), int(s * 0.31), int(s * 0.22), int(s * 0.58)),
            fill=(86, 214, 255, 255),
            width=max(2, int(s * 0.035)),
        )
        draw.line(
            (int(s * 0.78), int(s * 0.31), int(s * 0.78), int(s * 0.58)),
            fill=(120, 113, 255, 255),
            width=max(2, int(s * 0.035)),
        )
        return image

    margin = int(s * 0.06)
    draw.rounded_rectangle(
        (margin, margin, s - margin, s - margin),
        radius=int(s * 0.22),
        fill=(13, 18, 30, 255),
    )
    draw.rounded_rectangle(
        (int(s * 0.10), int(s * 0.10), int(s * 0.90), int(s * 0.90)),
        radius=int(s * 0.18),
        outline=(45, 59, 84, 255),
        width=max(2, int(s * 0.012)),
    )

    def monitor(box, fill, outline, line_width=None):
        x1, y1, x2, y2 = box
        width = line_width or max(4, int(s * 0.018))
        radius = int(min(x2 - x1, y2 - y1) * 0.12)
        draw.rounded_rectangle(
            box,
            radius=radius,
            fill=fill,
            outline=outline,
            width=width,
        )
        cx = (x1 + x2) // 2
        stem = int((y2 - y1) * 0.12)
        draw.line((cx, y2, cx, y2 + stem), fill=outline, width=width)
        foot = int((x2 - x1) * 0.34)
        draw.line(
            (cx - foot // 2, y2 + stem, cx + foot // 2, y2 + stem),
            fill=outline,
            width=width,
        )

    monitor(
        (int(s * 0.15), int(s * 0.27), int(s * 0.36), int(s * 0.66)),
        (21, 31, 50, 255),
        (86, 214, 255, 255),
    )
    monitor(
        (int(s * 0.34), int(s * 0.20), int(s * 0.76), int(s * 0.68)),
        (20, 33, 57, 255),
        (92, 137, 255, 255),
        max(4, int(s * 0.022)),
    )
    monitor(
        (int(s * 0.70), int(s * 0.28), int(s * 0.86), int(s * 0.64)),
        (21, 31, 50, 255),
        (120, 113, 255, 255),
    )

    for x, color in (
        (0.33, (86, 214, 255, 255)),
        (0.67, (120, 113, 255, 255)),
    ):
        cx = int(s * x)
        cy = int(s * 0.79)
        radius = int(s * 0.018)
        draw.ellipse(
            (cx - radius, cy - radius, cx + radius, cy + radius),
            fill=color,
        )

    return image


def _save_ico(image: Image.Image, path: Path) -> None:
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    image.resize((256, 256), Image.Resampling.LANCZOS).save(
        path,
        format="ICO",
        sizes=[(size, size) for size in sizes],
    )


def main() -> None:
    app = _app_icon()
    tray = _app_icon(tray=True)

    app.resize((256, 256), Image.Resampling.LANCZOS).save(
        OUT / "pantallas-256.png"
    )
    tray.resize((256, 256), Image.Resampling.LANCZOS).save(
        OUT / "pantallas-tray-256.png"
    )
    _save_ico(app, OUT / "pantallas.ico")
    _save_ico(tray, OUT / "pantallas-tray.ico")
    print(f"Iconos generados en {OUT}")


if __name__ == "__main__":
    main()
