# compose.py — three phone recordings side by side -> PNG frame sequence (+ ffmpeg GIF/MP4).
# usage: python compose.py <out_name> <panelA> <panelB> <panelC> [--fps 12] [--pw 300] [--labels "a|b|c"]
import json, sys, os, subprocess, argparse
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("panels", nargs="+")
ap.add_argument("--fps", type=int, default=12); ap.add_argument("--pw", type=int, default=300)
ap.add_argument("--labels", default="v0 · 지금 배포본(Song)|v1 · 우리 디자인 + 3D 타자|v2 · Song 틀 + 3D 타자")
ap.add_argument("--start", type=int, default=0); ap.add_argument("--end", type=int, default=None)
ap.add_argument("--gif-colors", type=int, default=160)
args = ap.parse_args()

# captions keyed by step time (ms); facts from data/849843.json (pitch idx 8..11)
STEP_AT = [600, 4600, 8600, 12600]
CAPTIONS = [
    "1회 초 Michael Busch 1구 · 볼 (안 치는 공)",
    "1회 초 Michael Busch 2구 · 헛스윙",
    "1회 초 Michael Busch 3구 · 타구 아웃",
    "1회 말 Fernando Tatis Jr. 1구 · 홈런",
]
PRE_CAPTION = "같은 경기(SD 대 CHC, 2026-09-30) 같은 네 공을 세 화면이 동시에 보여 줍니다"

def load(panel):
    d = json.load(open(os.path.join(HERE, "frames", panel, "index.json"), encoding="utf-8"))
    fr = d["frames"]
    return [(f["t"], os.path.join(HERE, "frames", panel, f["file"])) for f in fr], d

panels = [load(p) for p in args.panels]
labels = args.labels.split("|")
PW = args.pw; PH = round(PW * 812 / 375); GAP = 14; HEAD = 46; FOOT = 50; PAD = 14
W = PAD * 2 + PW * len(panels) + GAP * (len(panels) - 1); H = PAD + HEAD + PH + FOOT + PAD
font_path = "C:/Windows/Fonts/malgunbd.ttf"; font_path2 = "C:/Windows/Fonts/malgun.ttf"
f_head = ImageFont.truetype(font_path, 17); f_foot = ImageFont.truetype(font_path2, 16); f_small = ImageFont.truetype(font_path2, 12)
BG = (238, 243, 232); INK = (24, 36, 20); ACC = (47, 107, 18)

end = args.end if args.end is not None else max(p[0][-1][0] for p in panels)
times = list(range(args.start, end + 1, round(1000 / args.fps)))
out_dir = os.path.join(HERE, "out", args.out); os.makedirs(out_dir, exist_ok=True)
for f in os.listdir(out_dir): os.remove(os.path.join(out_dir, f))

cache = {}
def frame_at(frames, t):
    # latest frame with time <= t (fall back to first)
    lo, hi = 0, len(frames) - 1; best = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if frames[mid][0] <= t: best = mid; lo = mid + 1
        else: hi = mid - 1
    path = frames[best][1]
    if path not in cache:
        im = Image.open(path).convert("RGB")
        cache[path] = im.resize((PW, PH), Image.LANCZOS)
        if len(cache) > 400: cache.pop(next(iter(cache)))
    return cache[path]

def caption_for(t):
    cap = PRE_CAPTION
    for at, c in zip(STEP_AT, CAPTIONS):
        if t >= at: cap = c
    return cap

for n, t in enumerate(times):
    im = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(im)
    for k, (frames, meta) in enumerate(panels):
        x = PAD + k * (PW + GAP); y = PAD + HEAD
        dr.rounded_rectangle([x - 3, y - 3, x + PW + 3, y + PH + 3], radius=18, fill=(20, 24, 18))
        im.paste(frame_at(frames, t), (x, y))
        lab = labels[k] if k < len(labels) else ""
        dr.text((x + 2, PAD + 10), lab, font=f_head, fill=INK)
    cap = caption_for(t)
    tw = dr.textlength(cap, font=f_foot)
    dr.rounded_rectangle([W / 2 - tw / 2 - 14, H - PAD - FOOT + 8, W / 2 + tw / 2 + 14, H - PAD - 6], radius=12, fill=(9, 24, 17))
    dr.text((W / 2 - tw / 2, H - PAD - FOOT + 14), cap, font=f_foot, fill=(206, 255, 120))
    dr.text((W - PAD - 150, H - PAD - 16), f"{t/1000:5.1f} s · 로컬 데모 녹화", font=f_small, fill=(90, 100, 84))
    im.save(os.path.join(out_dir, f"c{n:04d}.png"), optimize=False)
print("frames", len(times), "size", W, "x", H, file=sys.stderr)

FF = r"C:\Users\zpfh1\ffmpeg-8.0-essentials_build\ffmpeg-8.0-essentials_build\bin\ffmpeg.exe"
seq = os.path.join(out_dir, "c%04d.png")
gif = os.path.join(HERE, "out", args.out + ".gif"); mp4 = os.path.join(HERE, "out", args.out + ".mp4")
subprocess.run([FF, "-y", "-loglevel", "error", "-framerate", str(args.fps), "-i", seq,
                "-vf", f"split[a][b];[a]palettegen=max_colors={args.gif_colors}:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle",
                "-loop", "0", gif], check=True)
subprocess.run([FF, "-y", "-loglevel", "error", "-framerate", str(args.fps), "-i", seq,
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p", "-c:v", "libx264", "-crf", "22", "-movflags", "+faststart", mp4], check=True)
for p in (gif, mp4): print(p, os.path.getsize(p), file=sys.stderr)
