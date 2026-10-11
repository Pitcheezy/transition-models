"""Draw a labelled pixel grid on a frame so a reader can give coordinates in source pixels.

    python -m intent.grid <in.jpg> <out.png>                    # whole frame, grid every 50 px
    python -m intent.grid <in.jpg> <out.png> x0 y0 x1 y1 zoom   # zoomed region, grid every 20 px

Yellow lines and labels every 100 source pixels, grey lines in between. The reading workflows
(``intent/workflows/*.js``) tell the readers to call this; the PNG stays in their scratch folder.
"""

from __future__ import annotations

import sys


def draw_grid(src, dst, region=None, zoom=1):
    from PIL import Image, ImageDraw

    im = Image.open(src).convert("RGB")
    x0, y0, x1, y1 = region or (0, 0, im.width, im.height)
    im = im.crop((x0, y0, x1, y1)).resize(
        ((x1 - x0) * zoom, (y1 - y0) * zoom), Image.Resampling.LANCZOS
    )
    d = ImageDraw.Draw(im)
    step = 20 if zoom >= 2 else 50
    for x in range((x0 // step) * step, x1 + 1, step):
        if x < x0:
            continue
        X = (x - x0) * zoom
        major = x % 100 == 0
        d.line((X, 0, X, im.height), fill=(255, 255, 0) if major else (90, 90, 90))
        if major:
            d.text((X + 2, 2), str(x), fill=(255, 255, 0))
            d.text((X + 2, im.height - 12), str(x), fill=(255, 255, 0))
    for y in range((y0 // step) * step, y1 + 1, step):
        if y < y0:
            continue
        Y = (y - y0) * zoom
        major = y % 100 == 0
        d.line((0, Y, im.width, Y), fill=(255, 255, 0) if major else (90, 90, 90))
        if major:
            d.text((2, Y + 2), str(y), fill=(255, 255, 0))
            d.text((im.width - 30, Y + 2), str(y), fill=(255, 255, 0))
    im.save(dst)
    return im.size


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (2, 7):
        raise SystemExit(__doc__)
    region, zoom = None, 1
    if len(argv) == 7:
        x0, y0, x1, y1, zoom = (int(v) for v in argv[2:7])
        region = (x0, y0, x1, y1)
    print(argv[1], draw_grid(argv[0], argv[1], region, zoom))


if __name__ == "__main__":
    main()
