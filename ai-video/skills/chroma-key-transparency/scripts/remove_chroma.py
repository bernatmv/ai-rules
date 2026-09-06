#!/usr/bin/env python3
"""Remove a flat key color and optionally write composited QA previews."""
import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageColor


def remove_key(image, key, inner=20, outer=150, hard=False, despill=False):
    if not 0 <= inner < outer <= math.sqrt(3 * 255**2):
        raise ValueError("Require 0 <= inner < outer <= 441.67")
    if despill and key not in ((0, 255, 0), (0, 0, 255)):
        raise ValueError("Despill supports pure green or blue keys only")
    spill_channel = 1 if key == (0, 255, 0) else 2
    result = image.convert("RGBA")
    pixels = []
    for r, g, b, old_alpha in result.getdata():
        rgb = (r, g, b)
        distance = math.sqrt(sum((c - k) ** 2 for c, k in zip(rgb, key)))
        coverage = float(distance > inner) if hard else min(1.0, max(0.0, (distance - inner) / (outer - inner)))
        alpha = round(old_alpha * coverage)
        if alpha == 0:
            pixels.append((0, 0, 0, 0))
        elif coverage < 1:
            # Undo the estimated backdrop contribution in straight RGB.
            clean = tuple(round(min(255, max(0, (c - (1 - coverage) * k) / coverage))) for c, k in zip(rgb, key))
            pixels.append((*clean, alpha))
        else:
            pixels.append((r, g, b, alpha))
    if despill:
        for index, pixel in enumerate(pixels):
            rgb = list(pixel[:3])
            rgb[spill_channel] = min(rgb[spill_channel], max(rgb[c] for c in range(3) if c != spill_channel))
            pixels[index] = (*rgb, pixel[3])
    result.putdata(pixels)
    return result


def previews(image):
    for label, color in (("light", "#f0f0f0"), ("dark", "#181820"), ("checker", "#dddddd")):
        background = Image.new("RGBA", image.size, color)
        if label == "checker":
            from PIL import ImageDraw
            draw = ImageDraw.Draw(background)
            for y in range(0, image.height, 16):
                for x in range(0, image.width, 16):
                    if (x // 16 + y // 16) % 2:
                        draw.rectangle((x, y, x + 15, y + 15), fill="#888888")
        yield label, Image.alpha_composite(background, image).convert("RGB")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--key", required=True, help="Key color, e.g. '#00FF00'")
    parser.add_argument("--inner", type=float, default=20)
    parser.add_argument("--outer", type=float, default=150)
    parser.add_argument("--hard", action="store_true")
    parser.add_argument("--despill", action="store_true", help="Suppress green/blue channel excess; only when that color is absent from the subject")
    parser.add_argument("--previews", action="store_true")
    args = parser.parse_args()
    try:
        key = ImageColor.getrgb(args.key)
        if len(key) != 3:
            raise ValueError("Key must be an RGB color without alpha")
        if args.output.suffix.lower() != ".png":
            raise ValueError("Output must use .png for lossless RGBA")
        targets = [args.output]
        if args.previews:
            targets += [args.output.with_name(f"{args.output.stem}.{label}.png") for label in ("light", "dark", "checker")]
        for target in targets:
            if target.exists() or target.is_symlink() or target.resolve() == args.source.resolve():
                raise ValueError(f"Refusing to overwrite {target}")
        with Image.open(args.source) as source:
            result = remove_key(source, key, args.inner, args.outer, args.hard, args.despill)
        histogram = result.getchannel("A").histogram()
        if histogram[0] == 0 or sum(histogram[1:]) == 0:
            raise ValueError("No transparent background or no visible foreground; inspect source and key settings")
        result.save(args.output)
        if args.previews:
            for target, (_, preview) in zip(targets[1:], previews(result)):
                preview.save(target)
        print(json.dumps({"output": str(args.output), "size": result.size, "key": key,
                          "inner": args.inner, "outer": args.outer, "hard": args.hard, "despill": args.despill,
                          "transparent": histogram[0], "partial": sum(histogram[1:255]),
                          "opaque": histogram[255]}))
    except (ValueError, OSError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
