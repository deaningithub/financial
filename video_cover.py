from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


SOURCE_IMAGE_NAME = "vidoe_cover.png"
DEFAULT_OUTPUT_DIR = Path("outputs")
DEFAULT_FONT_SIZE = 72
MAX_LINE_WIDTH = 800
LINE_SPACING = 12
ALLOWED_TITLE_PUNCTUATION = {"!", "?", "！", "？"}


def load_font(size: int) -> ImageFont.ImageFont:
    """Load a font that supports Chinese characters when available."""
    font_paths = [
        "C:\\Windows\\Fonts\\msyh.ttc",
        "C:\\Windows\\Fonts\\msyhbd.ttc",
        "C:\\Windows\\Fonts\\simhei.ttf",
        "C:\\Windows\\Fonts\\mingliu.ttc",
        "C:\\Windows\\Fonts\\simsun.ttc",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    font_names = [
        "msyh.ttc",
        "msyhbd.ttc",
        "simhei.ttf",
        "mingliu.ttc",
        "simsun.ttc",
        "arial.ttf",
        "DejaVuSans-Bold.ttf",
        "NotoSansCJKtc-Regular.otf",
    ]

    for font_path in font_paths:
        path = Path(font_path)
        if not path.exists():
            continue
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            continue

    for font_name in font_names:
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue

    return ImageFont.load_default()


def clean_title_for_display(text: str) -> str:
    """Remove visible punctuation except exclamation and question marks."""
    cleaned: list[str] = []
    previous_space = False

    for char in text:
        if char in ALLOWED_TITLE_PUNCTUATION:
            cleaned.append("!" if char == "！" else "?" if char == "？" else char)
            previous_space = False
            continue

        if char.isalnum() or "\u4e00" <= char <= "\u9fff":
            cleaned.append(char)
            previous_space = False
            continue

        if char.isspace() and not previous_space:
            cleaned.append(" ")
            previous_space = True

    return "".join(cleaned).strip()


def tokenize_for_wrap(text: str) -> list[str]:
    """Tokenize mixed Chinese and English without using punctuation for line breaks."""
    tokens: list[str] = []
    current_ascii = ""

    for char in text:
        if char.isspace():
            if current_ascii:
                tokens.append(current_ascii)
                current_ascii = ""
            continue

        if char in {"!", "?"}:
            if current_ascii:
                tokens.append(current_ascii)
                current_ascii = ""
            tokens.append(char)
            continue

        if char.isascii() and char.isalnum():
            current_ascii += char
            continue

        if current_ascii:
            tokens.append(current_ascii)
            current_ascii = ""
        tokens.append(char)

    if current_ascii:
        tokens.append(current_ascii)

    return tokens


def _text_width(text: str, font: ImageFont.ImageFont, draw: ImageDraw.ImageDraw) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> str:
    """Wrap text by measured pixel width. Only ! and ? can remain as punctuation."""
    tokens = tokenize_for_wrap(text)
    lines: list[str] = []
    current_line = ""

    for token in tokens:
        if token in {"!", "?"} and current_line:
            current_line += token
            continue

        joiner = " " if current_line and token.isascii() and token.isalnum() else ""
        candidate = current_line + joiner + token

        if _text_width(candidate, font, draw) <= max_width:
            current_line = candidate
            continue

        if current_line:
            lines.append(current_line)
        current_line = token

    if current_line:
        lines.append(current_line)

    return "\n".join(lines)


def add_title_to_image(source_path: Path, title: str, output_path: Path) -> Path:
    if not source_path.exists():
        raise FileNotFoundError(f"Source image not found: {source_path}")

    image = Image.open(source_path).convert("RGBA")
    draw = ImageDraw.Draw(image)
    font = load_font(DEFAULT_FONT_SIZE)
    display_title = clean_title_for_display(title)
    wrapped_title = wrap_text(display_title, font, MAX_LINE_WIDTH, draw)

    text_bbox = draw.multiline_textbbox(
        (0, 0),
        wrapped_title,
        font=font,
        spacing=LINE_SPACING,
    )
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    x = (image.width - text_width) / 2
    y = (image.height - text_height) / 2

    for offset in [(-2, -2), (-2, 2), (2, -2), (2, 2)]:
        draw.multiline_text(
            (x + offset[0], y + offset[1]),
            wrapped_title,
            font=font,
            fill="black",
            spacing=LINE_SPACING,
            align="center",
        )

    draw.multiline_text(
        (x, y),
        wrapped_title,
        font=font,
        fill="white",
        spacing=LINE_SPACING,
        align="center",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add a video title onto a cover image and save the result."
    )
    parser.add_argument("title", help="Video title to write on the cover image.")
    parser.add_argument(
        "--source",
        default=SOURCE_IMAGE_NAME,
        help="Source image file name (default: vidoe_cover.png).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output image path (default: outputs/video_cover_{title}.png).",
    )
    return parser.parse_args()


def sanitize_filename(value: str) -> str:
    sanitized = re.sub(r"[^\w\s-]", "_", value, flags=re.UNICODE).strip()
    return "_".join(sanitized.split()) or "video_cover"


def main() -> None:
    args = parse_args()
    source_path = Path(args.source)
    safe_name = sanitize_filename(args.title)
    output_path = (
        Path(args.output).resolve()
        if args.output
        else DEFAULT_OUTPUT_DIR / f"video_cover_{safe_name}.png"
    )

    result_path = add_title_to_image(source_path, args.title, output_path)
    print(f"Saved cover image with title to: {result_path}")


if __name__ == "__main__":
    main()
