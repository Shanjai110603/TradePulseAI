"""
Generate TradePulse Application Icon (.png and .ico)
Renders a modern dark neon trading pulse icon with candlestick bars and lightning badge.
"""
from pathlib import Path
from PIL import Image, ImageDraw

def create_icon():
    assets_dir = Path("assets")
    assets_dir.mkdir(parents=True, exist_ok=True)

    size = (256, 256)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Background rounded rectangle (Dark Navy with blue border)
    draw.rounded_rectangle([(8, 8), (248, 248)], radius=50, fill="#070a14", outline="#2979ff", width=4)

    # 2. Glowing inner background
    draw.rounded_rectangle([(16, 16), (240, 240)], radius=42, fill="#0d1424")

    # 3. Candlesticks
    # Red candle (left)
    draw.line([(68, 60), (68, 190)], fill="#ff1744", width=3)
    draw.rectangle([(54, 90), (82, 160)], fill="#ff1744")

    # Green candle (center)
    draw.line([(128, 40), (128, 210)], fill="#00e676", width=3)
    draw.rectangle([(114, 70), (142, 175)], fill="#00e676")

    # Green candle (right)
    draw.line([(188, 50), (188, 180)], fill="#00e676", width=3)
    draw.rectangle([(174, 65), (202, 130)], fill="#00e676")

    # 4. Neon Trend Line overlay
    points = [(40, 165), (70, 150), (110, 110), (128, 120), (160, 80), (216, 50)]
    draw.line(points, fill="#ffd600", width=5, joint="curve")

    # Save PNG
    png_path = assets_dir / "icon.png"
    img.save(png_path, format="PNG")
    print(f"Saved {png_path}")

    # Save multi-resolution ICO
    ico_path = assets_dir / "icon.ico"
    img.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Saved {ico_path}")

if __name__ == "__main__":
    create_icon()
