# v4sheet.py — V4 나가기 동작 녹화(frames/v4moves)에서 단계마다 시각별 존 부분을 잘라 한 장으로(확인용 접촉 시트)
import json, os, sys
from PIL import Image, ImageDraw, ImageFont
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
d = os.path.join(HERE, "frames", "v4moves")
idx = json.load(open(os.path.join(d, "index.json"), encoding="utf-8"))
steps = json.load(open(os.path.join(HERE, "v4moves-steps.json"), encoding="utf-8"))
frames = idx["frames"]
def frame_at(t):
    best = min(frames, key=lambda f: abs(f["t"] - t)); return os.path.join(d, best["file"])
OFFS = [float(x) for x in (sys.argv[1].split(",") if len(sys.argv) > 1 else "0.5,1.0,1.5,2.0,2.5,3.0,3.5,4.2".split(","))]
CROP = (0, 210, 750, 760)  # dpr 2: css y 105..380 (존 행 + 3D 타자)
SC = 0.36
cw, ch = int((CROP[2] - CROP[0]) * SC), int((CROP[3] - CROP[1]) * SC)
font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 15); small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 12)
LW = 0; TOP = 22; ROWH = ch + 22
W, H = len(OFFS) * cw, TOP + len(steps) * ROWH
sheet = Image.new("RGB", (W, H), "white"); dr = ImageDraw.Draw(sheet)
for j, o in enumerate(OFFS): dr.text((j * cw + 4, 3), f"+{o:.1f}s", fill="#333", font=small)
for k, (i, label) in enumerate(steps):
    t0 = 200 + 4500 * k
    y = TOP + k * ROWH
    dr.text((4, y + 2), f"{i}번 공 · {label}", fill="#0f2217", font=font)
    for j, o in enumerate(OFFS):
        im = Image.open(frame_at(t0 + o * 1000)).crop(CROP).resize((cw, ch))
        sheet.paste(im, (j * cw, y + 22))
out = os.path.join(HERE, "out", "v4moves-sheet.png"); os.makedirs(os.path.dirname(out), exist_ok=True)
sheet.save(out); print(out, sheet.size)
