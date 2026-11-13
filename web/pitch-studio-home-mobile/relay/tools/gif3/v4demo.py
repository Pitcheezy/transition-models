# v4demo.py — V4 데모 녹화(frames/v4demo) → 자막 붙인 한 화면 GIF·MP4
import json, os, subprocess, sys, shutil
from PIL import Image, ImageDraw, ImageFont
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(HERE, "frames", "v4demo")
idx = json.load(open(os.path.join(src, "index.json"), encoding="utf-8"))
caps = json.load(open(os.path.join(HERE, "v4demo-captions.json"), encoding="utf-8"))
FPS, W = 12, 360
tmp = os.path.join(HERE, "out", "v4demo-frames"); shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 15); small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 11)
frames = idx["frames"]; span = frames[-1]["t"]; n = int(span / 1000 * FPS)
CAP_H = 34
for k in range(n + 1):
    t = k * 1000 / FPS
    f = min(frames, key=lambda x: abs(x["t"] - t))
    im = Image.open(os.path.join(src, f["file"])).convert("RGB")
    h = round(im.height * W / im.width); im = im.resize((W, h), Image.LANCZOS)
    cap = "V4 시작"
    for at, label in caps:
        if at <= t: cap = label
    out = Image.new("RGB", (W, h + CAP_H), "#091811"); out.paste(im, (0, CAP_H))
    d = ImageDraw.Draw(out); d.text((10, 8), cap, fill="#ceff78", font=font)
    d.text((W - 92, 11), "Pitcheezy V4 로컬", fill="#9fb3a3", font=small)
    out.save(os.path.join(tmp, f"f{k:05d}.png"))
gif = os.path.join(HERE, "out", "pitcheezy-v4-demo.gif"); mp4 = os.path.join(HERE, "out", "pitcheezy-v4-demo.mp4")
pal = os.path.join(tmp, "pal.png")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, "f%05d.png"), "-vf", "palettegen=max_colors=160:stats_mode=diff", pal], check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, "f%05d.png"), "-i", pal, "-lavfi", "paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle", gif], check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, "f%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", mp4], check=True)
print(gif, os.path.getsize(gif)); print(mp4, os.path.getsize(mp4)); print("frames", n + 1)
