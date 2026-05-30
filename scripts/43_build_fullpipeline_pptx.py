"""
scripts/43_build_fullpipeline_pptx.py

SmartPitch 전체 4-repo 파이프라인 발표 슬라이드 10장 생성.
(data / clustering / transition-models / rl-agent 통합)

Usage:
    uv run python scripts/43_build_fullpipeline_pptx.py

출력: outputs/SmartPitch_FullPipeline_Presentation.pptx
"""

from pathlib import Path

try:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Cm, Inches, Pt
except ImportError:
    print("python-pptx가 없습니다. 설치 후 재실행:")
    print("  uv run pip install python-pptx")
    raise

import json
import os

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "outputs"
FIG_DIR = OUTPUT_DIR / "figures"
PPTX_PATH = OUTPUT_DIR / "SmartPitch_FullPipeline_Presentation.pptx"
RL_RESULTS_DIR = ROOT.parent / "rl-agent" / "outputs" / "results"

# ── 색상 팔레트 ────────────────────────────────────────────────────────────
C_BLUE   = RGBColor(0x29, 0x80, 0xB9)
C_ORANGE = RGBColor(0xE6, 0x7E, 0x22)
C_GREEN  = RGBColor(0x27, 0xAE, 0x60)
C_RED    = RGBColor(0xE7, 0x4C, 0x3C)
C_PURPLE = RGBColor(0x8E, 0x44, 0xAD)
C_DARK   = RGBColor(0x2C, 0x3E, 0x50)
C_LIGHT  = RGBColor(0xF8, 0xF9, 0xFA)
C_WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
C_GRAY   = RGBColor(0x95, 0xA5, 0xA6)

# 폴더 태그 색상
TAG_COLORS = {
    "data":               RGBColor(0x29, 0x80, 0xB9),
    "clustering":         RGBColor(0x8E, 0x44, 0xAD),
    "transition-models":  RGBColor(0xE6, 0x7E, 0x22),
    "rl-agent":           RGBColor(0x27, 0xAE, 0x60),
    "전체":               RGBColor(0x7F, 0x8C, 0x8D),
}

# ── 레이아웃 상수 ─────────────────────────────────────────────────────────
W = Inches(13.33)
H = Inches(7.5)
MARGIN = Cm(1.2)
HEADER_H = Cm(1.6)
BODY_TOP = HEADER_H + Cm(0.5)
BODY_H = H - BODY_TOP - MARGIN
ROW_H = Cm(0.55)


# ═════════════════════════════════════════════════════════════════════════════
# 헬퍼 함수들
# ═════════════════════════════════════════════════════════════════════════════

def set_slide_bg(slide, color: RGBColor):
    from pptx.oxml.ns import qn
    from lxml import etree
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_textbox(slide, text, left, top, width, height,
                font_size=18, bold=False, color=C_DARK,
                align=PP_ALIGN.LEFT, wrap=True):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = color
    return txBox


def add_rect(slide, left, top, width, height, fill_color, line_color=None, line_width=Pt(0)):
    shape = slide.shapes.add_shape(1, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if line_color:
        shape.line.color.rgb = line_color
        shape.line.width = line_width
    else:
        shape.line.fill.background()
    return shape


def add_image_fit(slide, fname, left, top, box_w, box_h):
    """비율 보존 이미지 삽입 — PIL로 원본 비율 읽어 letterbox fit."""
    p = FIG_DIR / fname
    if not p.exists():
        return False
    try:
        from PIL import Image
        iw, ih = Image.open(p).size
        ar = iw / ih
    except Exception:
        slide.shapes.add_picture(str(p), left, top, width=box_w)
        return True
    w = int(box_w)
    h = int(round(w / ar))
    if h > int(box_h):
        h = int(box_h)
        w = int(round(h * ar))
    lx = int(left) + (int(box_w) - w) // 2
    ty = int(top) + (int(box_h) - h) // 2
    slide.shapes.add_picture(str(p), lx, ty, w, h)
    return True


def make_slide_header(slide, title: str, slide_num: str = ""):
    add_rect(slide, 0, 0, W, HEADER_H, C_DARK)
    add_textbox(slide, title, MARGIN, Cm(0.2), W - MARGIN * 2 - Cm(4), HEADER_H - Cm(0.4),
                font_size=22, bold=True, color=C_WHITE, align=PP_ALIGN.LEFT)
    if slide_num:
        add_textbox(slide, slide_num, W - Cm(5), Cm(0.3), Cm(4.5), HEADER_H - Cm(0.6),
                    font_size=12, bold=False, color=C_GRAY, align=PP_ALIGN.RIGHT)


def add_folder_tags(slide, tags: list):
    """슬라이드 우상단에 폴더 태그 칩들을 그린다."""
    chip_w = Cm(3.4)
    chip_h = Cm(0.62)
    gap = Cm(0.15)
    x_start = W - MARGIN - chip_w * len(tags) - gap * (len(tags) - 1)
    y_top = Cm(0.5)
    for i, tag in enumerate(tags):
        x = x_start + i * (chip_w + gap)
        color = TAG_COLORS.get(tag, C_GRAY)
        add_rect(slide, x, y_top, chip_w, chip_h, color)
        add_textbox(slide, f"[{tag}]", x, y_top + Cm(0.05), chip_w, chip_h - Cm(0.1),
                    font_size=9.5, bold=True, color=C_WHITE, align=PP_ALIGN.CENTER)


def load_rl_result(fname):
    p = RL_RESULTS_DIR / fname
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_comp_data():
    with open(OUTPUT_DIR / "all_models_comparison_10cls.json", encoding="utf-8") as f:
        comp10 = json.load(f)
    with open(OUTPUT_DIR / "all_models_comparison_4cls.json", encoding="utf-8") as f:
        comp4 = json.load(f)
    return comp10, comp4


# ═════════════════════════════════════════════════════════════════════════════
# 슬라이드 빌더
# ═════════════════════════════════════════════════════════════════════════════

def make_pptx():
    prs = Presentation()
    prs.slide_width  = W
    prs.slide_height = H
    blank = prs.slide_layouts[6]

    comp10, comp4 = load_comp_data()

    # RL 수치 로드
    d_mlp10_mdp   = load_rl_result("mdp_modelMLP10_b0_p0.json")
    d_mlp10_dynaq = load_rl_result("dynaq_modelMLP10_b0_p0_b_vs_mlp10_v1.json")
    mdp_vi_mlp10  = d_mlp10_mdp["results"]["MDP-VI"]["mean_reward"]  if d_mlp10_mdp  else 0.121
    random_mlp10  = d_mlp10_mdp["results"]["Random"]["mean_reward"]  if d_mlp10_mdp  else -0.290
    dynaq_mlp10   = d_mlp10_dynaq["results"]["Dyna-Q"]["mean_reward"] if d_mlp10_dynaq else 0.098

    our_top1 = comp10.get("MLP 135d (focal)", {}).get("top1", 0.676)
    delta_re24 = mdp_vi_mlp10 - random_mlp10

    # ─────────────────────────────────────────────────────────────
    # Slide 1 — Cover
    # ─────────────────────────────────────────────────────────────
    sl = prs.slides.add_slide(blank)
    set_slide_bg(sl, C_DARK)
    add_rect(sl, 0, 0, W, Cm(0.5), C_ORANGE)

    add_textbox(sl, "SmartPitch", MARGIN, Cm(0.8), W - MARGIN*2, Cm(1.0),
                font_size=20, bold=False, color=C_ORANGE, align=PP_ALIGN.CENTER)
    add_textbox(sl, "투구 결과 예측 → 장기 보상 최대화 추천", MARGIN, Cm(1.7), W - MARGIN*2, Cm(1.4),
                font_size=30, bold=True, color=C_WHITE, align=PP_ALIGN.CENTER)
    add_textbox(sl, "MLB Statcast 기반 4-stage 파이프라인 | 2계층 베이스라인 비교",
                MARGIN, Cm(3.0), W - MARGIN*2, Cm(0.8),
                font_size=15, bold=False, color=C_GRAY, align=PP_ALIGN.CENTER)

    # 헤드라인 수치 박스 3개
    metrics = [
        ("예측 정확도", f"{our_top1*100:.1f}%", "Top-1 (10-class, MLP10 135d)", C_ORANGE),
        ("정책 가치 Δ", f"{delta_re24:+.2f}", "RE24/inning vs Random (MDP-VI)", C_GREEN),
        ("MDP 호환", "✅ MLP10", "단일 pitch, 135-dim 입력", C_BLUE),
    ]
    for i, (lbl, val, sub, c) in enumerate(metrics):
        bx = MARGIN + i * Cm(4.0)
        add_rect(sl, bx, Cm(4.0), Cm(3.7), Cm(2.1), RGBColor(0x1A, 0x2A, 0x3A))
        add_textbox(sl, lbl, bx + Cm(0.2), Cm(4.1), Cm(3.3), Cm(0.5),
                    font_size=11, bold=True, color=c)
        add_textbox(sl, val, bx + Cm(0.2), Cm(4.55), Cm(3.3), Cm(0.8),
                    font_size=24, bold=True, color=C_WHITE, align=PP_ALIGN.CENTER)
        add_textbox(sl, sub, bx + Cm(0.2), Cm(5.35), Cm(3.3), Cm(0.6),
                    font_size=8.5, color=C_GRAY, align=PP_ALIGN.CENTER)

    add_textbox(sl, "data  →  clustering  →  transition-models  →  rl-agent",
                MARGIN, Cm(6.3), W - MARGIN*2, Cm(0.6),
                font_size=12, bold=False, color=C_GRAY, align=PP_ALIGN.CENTER)
    add_textbox(sl, "2026-05 | 전 코드 transition-models repo 내 관리",
                MARGIN, H - Cm(0.75), W - MARGIN*2, Cm(0.6),
                font_size=10, color=C_GRAY, align=PP_ALIGN.CENTER)
    add_folder_tags(sl, ["전체"])

    # ─────────────────────────────────────────────────────────────
    # Slide 2 — 문제 정의 + 기존 접근의 한계
    # ─────────────────────────────────────────────────────────────
    sl = prs.slides.add_slide(blank)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "문제 정의 & 기존 접근의 한계", "Slide 2 / 10")
    add_folder_tags(sl, ["전체"])

    # 핵심 질문
    add_rect(sl, MARGIN, BODY_TOP, W - MARGIN*2, Cm(0.9), RGBColor(0xEB, 0xF5, 0xFB))
    add_textbox(sl, "핵심 질문: 어떤 구종 · 위치를 어떤 상황에 던질 때 투수에게 장기적으로 가장 유리한가?",
                MARGIN + Cm(0.3), BODY_TOP + Cm(0.1), W - MARGIN*2 - Cm(0.6), Cm(0.7),
                font_size=13, bold=True, color=C_BLUE)

    # 기존 연구 한계 표
    prior_works = [
        ("Otremba 2022", "4-class (Ball/Strike/Foul/InPlay) MLP", "MDP 호환 ✅",
         "10-class 세분화 없음, 투수 맥락 feature 없음 → collapse", C_BLUE),
        ("MIT Sloan 2025", "12-layer Transformer, 87d × 400 seq", "10-class 예측 ✅",
         "MDP 비호환 — 400-pitch history 필요, 단일 step 불가", C_PURPLE),
        ("MONEYBaRL 2019", "선수 데이터 기반 RL 투구 추천", "RL 시도 ✅",
         "transition probability 명시적 추정 없음, 환경 모델 미공개", C_GRAY),
    ]
    y = BODY_TOP + Cm(1.1)
    hdrs = ["논문 / 방법", "핵심 접근", "강점", "한계", ""]
    col_ws = [(W - MARGIN*2) * r for r in [0.20, 0.24, 0.16, 0.38, 0.0]]
    col_xs = [MARGIN]
    for cw in col_ws[:-2]:
        col_xs.append(col_xs[-1] + cw)

    for ci, (hdr, cx, cw) in enumerate(zip(hdrs[:4], col_xs, col_ws[:4])):
        add_rect(sl, cx, y, cw - Cm(0.05), ROW_H, C_DARK)
        add_textbox(sl, hdr, cx + Cm(0.1), y + Cm(0.05), cw - Cm(0.2), ROW_H - Cm(0.1),
                    font_size=11, bold=True, color=C_WHITE)
    y += ROW_H

    for name, approach, strength, limitation, c in prior_works:
        for ci, (cell, cx, cw) in enumerate(zip(
            [name, approach, strength, limitation],
            col_xs, col_ws[:4]
        )):
            bg = C_LIGHT if ci % 2 == 0 else C_WHITE
            add_rect(sl, cx, y, cw - Cm(0.05), ROW_H + Cm(0.1), bg)
            fc = c if ci == 0 else (C_GREEN if "✅" in cell else C_DARK)
            add_textbox(sl, cell, cx + Cm(0.1), y + Cm(0.05), cw - Cm(0.2), ROW_H,
                        font_size=9.5, color=fc, bold=(ci == 0))
        y += ROW_H + Cm(0.1)

    # 우리 접근법
    y2 = y + Cm(0.35)
    add_rect(sl, MARGIN, y2, W - MARGIN*2, Cm(1.1), RGBColor(0xFF, 0xF3, 0xE0))
    add_textbox(sl, "★ 본 프로젝트", MARGIN + Cm(0.3), y2 + Cm(0.08), Cm(3), Cm(0.5),
                font_size=12, bold=True, color=C_ORANGE)
    add_textbox(sl,
                "4-repo 파이프라인: 데이터 수집 → 상태 추상화 → 전이확률 추정(10-class, MDP 호환) → RL 정책 학습\n"
                "2계층 베이스라인: ① 예측 정확도 (같은 test set) ② 정책 가치 (같은 MDP, RE24 보상)",
                MARGIN + Cm(3.3), y2 + Cm(0.08), W - MARGIN*2 - Cm(3.6), Cm(1.0),
                font_size=10.5, color=C_DARK)

    # ─────────────────────────────────────────────────────────────
    # Slide 3 — 4-Stage Pipeline 다이어그램
    # ─────────────────────────────────────────────────────────────
    sl = prs.slides.add_slide(blank)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "SmartPitch 4-Stage 파이프라인", "Slide 3 / 10")
    add_folder_tags(sl, ["전체"])

    img_ok = add_image_fit(sl, "fig_pipeline_4stage.png",
                           MARGIN, BODY_TOP, W - MARGIN*2, H - BODY_TOP - Cm(1.1))
    if not img_ok:
        add_textbox(sl,
                    "그림 미생성: uv run python scripts/42_build_fullpipeline_figures.py 실행 필요",
                    MARGIN, BODY_TOP + Cm(1), W - MARGIN*2, Cm(3),
                    font_size=14, color=C_GRAY, align=PP_ALIGN.CENTER)

    add_textbox(sl,
                "CONTRACT_v1.md (byte-equal 계약)로 4개 repo 간 artifact 인터페이스 고정 — 팀 동시 개발 가능",
                MARGIN, H - Cm(1.0), W - MARGIN*2, Cm(0.7),
                font_size=11, bold=True, color=C_BLUE, align=PP_ALIGN.CENTER)

    # ─────────────────────────────────────────────────────────────
    # Slide 4 — Stage 1: Data
    # ─────────────────────────────────────────────────────────────
    sl = prs.slides.add_slide(blank)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "Stage 1 — Data: 수집 · 정제 · Feature Engineering", "Slide 4 / 10")
    add_folder_tags(sl, ["data"])

    # 데이터 흐름 요약
    flow_items = [
        ("pybaseball\nStatcast 다운로드", "2022–2025\n4시즌", C_BLUE),
        ("정제 (clean)", "3.08M → 2.98M\n(8 deprecated cols,\ntruncated_pa 제거)", C_ORANGE),
        ("Feature Engineering", "15-D z-scored\n17 pitch vocab\nlefty 미러링", C_PURPLE),
        ("Split & 산출", "train=2023\nval=2024H1\ntest=2024H2", C_GREEN),
    ]
    box_w = (W - MARGIN*2 - Cm(0.5)*3) / 4
    bx = MARGIN
    for i, (title, body, c) in enumerate(flow_items):
        add_rect(sl, bx, BODY_TOP, box_w, Cm(2.2), RGBColor(0xF8, 0xF9, 0xFA),
                 line_color=c, line_width=Pt(2))
        add_rect(sl, bx, BODY_TOP, box_w, Cm(0.65), c)
        add_textbox(sl, title, bx + Cm(0.15), BODY_TOP + Cm(0.05), box_w - Cm(0.3), Cm(0.58),
                    font_size=10, bold=True, color=C_WHITE)
        add_textbox(sl, body, bx + Cm(0.15), BODY_TOP + Cm(0.7), box_w - Cm(0.3), Cm(1.4),
                    font_size=9.5, color=C_DARK)
        if i < 3:
            add_textbox(sl, "→", bx + box_w + Cm(0.05), BODY_TOP + Cm(0.8), Cm(0.4), Cm(0.6),
                        font_size=18, bold=True, color=C_GRAY, align=PP_ALIGN.CENTER)
        bx += box_w + Cm(0.5)

    # 핵심 산출물 표
    y = BODY_TOP + Cm(2.5)
    add_textbox(sl, "핵심 산출물 (downstream 소비 관계)", MARGIN, y, W - MARGIN*2, Cm(0.55),
                font_size=13, bold=True, color=C_DARK)
    y += Cm(0.6)

    artifact_rows = [
        ("normalized_{train,val,test}.parquet", "15 z-scored cols + raw",
         "transition-models (학습·평가)", C_ORANGE),
        ("scaler.pkl", "StandardScaler (fit on 2023, n=749,880)",
         "transition-models (byte-equal 정규화)", C_ORANGE),
        ("cluster_input.parquet", "15-D Otremba features + 미러링",
         "clustering (UMAP 입력)", C_PURPLE),
        ("batter_features.parquet", "vs L/R 29개 통계 × 546 qualified batters",
         "rl-agent (PitchEnv 상태)", C_GREEN),
        ("pitcher_pool.parquet", "624 qualified pitchers",
         "rl-agent, clustering", C_GREEN),
    ]
    ahdr = ["산출물", "내용", "소비처"]
    acol_ws = [(W - MARGIN*2) * r for r in [0.30, 0.33, 0.35]]
    acol_xs = [MARGIN]
    for aw in acol_ws[:-1]:
        acol_xs.append(acol_xs[-1] + aw)

    for ci, (hdr, cx, cw) in enumerate(zip(ahdr, acol_xs, acol_ws)):
        add_rect(sl, cx, y, cw - Cm(0.05), ROW_H, C_DARK)
        add_textbox(sl, hdr, cx + Cm(0.1), y + Cm(0.05), cw - Cm(0.2), ROW_H - Cm(0.1),
                    font_size=10.5, bold=True, color=C_WHITE)
    y += ROW_H

    for ri, (fname, content, consumer, c) in enumerate(artifact_rows):
        bg = C_LIGHT if ri % 2 == 0 else C_WHITE
        for ci, (cell, cx, cw) in enumerate(zip([fname, content, consumer], acol_xs, acol_ws)):
            add_rect(sl, cx, y, cw - Cm(0.05), ROW_H, bg)
            fc = c if ci == 2 else (C_BLUE if ci == 0 else C_DARK)
            add_textbox(sl, cell, cx + Cm(0.1), y + Cm(0.05), cw - Cm(0.2), ROW_H - Cm(0.1),
                        font_size=9, bold=(ci == 0), color=fc)
        y += ROW_H

    # ─────────────────────────────────────────────────────────────
    # Slide 5 — Stage 2: Clustering
    # ─────────────────────────────────────────────────────────────
    sl = prs.slides.add_slide(blank)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "Stage 2 — Clustering: MDP 상태 추상화", "Slide 5 / 10")
    add_folder_tags(sl, ["clustering"])

    # 4-track 박스 (Pitch / Batter / Arsenal / Count)
    tracks = [
        {
            "name": "① Pitch\nUMAP 5D",
            "color": C_BLUE,
            "light": RGBColor(0xD6, 0xEA, 0xF8),
            "lines": [
                "input: 15-D Otremba features",
                "UMAP (nn=30, min_dist=0.0)",
                "→ 5D 연속 임베딩 (no cluster)",
                "HDBSCAN 거부 (2개 or 99개)",
                "L/R Pearson r = 0.9795",
            ],
            "out": "pitch_embeddings.parquet\numap_5d_reducer.pkl",
        },
        {
            "name": "② Batter\nk=3 (L/R)",
            "color": C_PURPLE,
            "light": RGBColor(0xE8, 0xDA, 0xEF),
            "lines": [
                "input: UMAP 5D (anchor K=32)",
                "NMF(10) → KMeans",
                "k=3 (L: Sil=0.256, R: 0.290)",
                "608 LHB / 778 RHB",
                "batter_cluster_id → MDP state",
            ],
            "out": "batter_clusters_vs_{L,R}.parquet",
        },
        {
            "name": "③ Arsenal\nk=3 (투수)",
            "color": C_ORANGE,
            "light": RGBColor(0xFD, 0xEB, 0xD0),
            "lines": [
                "moment 20D + function 32D",
                "per-pitcher 연속 벡터",
                "k=3 (Sil func=0.376)",
                "1,116 pitchers (250+ pitches)",
                "→ transition-models 58D input",
            ],
            "out": "arsenal_features_v1.parquet\narsenal_groups_v1.parquet",
        },
        {
            "name": "④ Count\nk=4 (Ward)",
            "color": C_GREEN,
            "light": RGBColor(0xD5, 0xF5, 0xE3),
            "lines": [
                "12 ball-strike counts → 4 groups",
                "Ward hierarchical clustering",
                "G0 투수유리 / G1 초구·균형",
                "G2 풀카운트 / G3 3-0 (singleton)",
                "count_cluster_id → MDP state",
            ],
            "out": "count_clusters_v1.parquet",
        },
    ]

    box_w2 = (W - MARGIN*2 - Cm(0.3)*3) / 4
    bx2 = MARGIN
    box_h2 = Cm(4.0)
    hdr_h2 = Cm(0.75)

    for t in tracks:
        add_rect(sl, bx2, BODY_TOP, box_w2, box_h2,
                 t["light"], line_color=t["color"], line_width=Pt(1.5))
        add_rect(sl, bx2, BODY_TOP, box_w2, hdr_h2, t["color"])
        add_textbox(sl, t["name"], bx2 + Cm(0.1), BODY_TOP + Cm(0.05),
                    box_w2 - Cm(0.2), hdr_h2 - Cm(0.1),
                    font_size=11, bold=True, color=C_WHITE, align=PP_ALIGN.CENTER)
        for li, line in enumerate(t["lines"]):
            add_textbox(sl, line, bx2 + Cm(0.1), BODY_TOP + hdr_h2 + Cm(0.1) + li * Cm(0.52),
                        box_w2 - Cm(0.2), Cm(0.5),
                        font_size=8.5, color=C_DARK)
        # 산출물
        out_y = BODY_TOP + box_h2 - Cm(0.65)
        add_rect(sl, bx2 + Cm(0.05), out_y, box_w2 - Cm(0.1), Cm(0.58),
                 C_WHITE, line_color=t["color"], line_width=Pt(1), )
        add_textbox(sl, t["out"], bx2 + Cm(0.1), out_y + Cm(0.05),
                    box_w2 - Cm(0.2), Cm(0.5),
                    font_size=7, color=t["color"],
                    align=PP_ALIGN.CENTER)
        bx2 += box_w2 + Cm(0.3)

    # 공유 코드북 설명
    y3 = BODY_TOP + box_h2 + Cm(0.25)
    add_rect(sl, MARGIN, y3, W - MARGIN*2, Cm(0.8), RGBColor(0xFD, 0xF2, 0xE4))
    add_textbox(sl,
                "핵심 설계: batter_anchors_v1.pkl (K=32 codebook) — Batter/Arsenal/Count 세 track이 동일 기하학 공간 공유 → 정합성 보장",
                MARGIN + Cm(0.3), y3 + Cm(0.1), W - MARGIN*2 - Cm(0.6), Cm(0.65),
                font_size=11, bold=False, color=C_ORANGE)

    add_textbox(sl,
                "MDP 상태 소비: batter_cluster_id + count_cluster_id (이산) · pitcher arsenal_features_v1 (연속 → 58D context)",
                MARGIN, y3 + Cm(0.9), W - MARGIN*2, Cm(0.5),
                font_size=10.5, color=C_DARK)

    # ─────────────────────────────────────────────────────────────
    # Slide 6 — Stage 3: Transition Model + 핵심 발견
    # ─────────────────────────────────────────────────────────────
    sl = prs.slides.add_slide(blank)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "Stage 3 — Transition Model: P(outcome | state, action, context)", "Slide 6 / 10")
    add_folder_tags(sl, ["transition-models"])

    # 왼쪽: 핵심 발견 그래프 (fig1)
    img_ok = add_image_fit(sl, "fig1_core_finding_context.png",
                           MARGIN, BODY_TOP, W * 0.56, H - BODY_TOP - Cm(1.0))

    # 오른쪽: 설명
    rx = W * 0.58
    rw = W - rx - MARGIN

    add_textbox(sl, "10-class 분류 목표", rx, BODY_TOP, rw, Cm(0.55),
                font_size=13, bold=True, color=C_DARK)
    add_textbox(sl,
                "Ball / Strike / Single / Double\nTriple / HR / FieldOut\nStrikeout / Walk / HBP",
                rx, BODY_TOP + Cm(0.6), rw, Cm(1.1),
                font_size=10, color=C_DARK)

    # 3단계 입력 진화
    evol_items = [
        ("77d (Otremba)", "단일 pitch\n물리 feature", C_BLUE, "collapse\n41.1%"),
        ("87d × 400 seq", "MIT-Sloan\nTransformer", C_PURPLE, "MDP 불가\n67.2%"),
        ("135d (ours) ★", "77d + arsenal\n58d context", C_ORANGE, "MDP 호환\n67.6%"),
    ]
    y4 = BODY_TOP + Cm(1.9)
    add_textbox(sl, "입력 feature 진화", rx, y4, rw, Cm(0.5),
                font_size=12, bold=True, color=C_DARK)
    y4 += Cm(0.55)
    for ename, einfo, ec, eresult in evol_items:
        add_rect(sl, rx, y4, rw * 0.55, Cm(0.85), RGBColor(0xF8, 0xF9, 0xFA),
                 line_color=ec, line_width=Pt(1.5))
        add_textbox(sl, ename, rx + Cm(0.15), y4 + Cm(0.05), rw * 0.5, Cm(0.42),
                    font_size=10, bold=True, color=ec)
        add_textbox(sl, einfo, rx + Cm(0.15), y4 + Cm(0.45), rw * 0.5, Cm(0.35),
                    font_size=8.5, color=C_DARK)
        add_rect(sl, rx + rw * 0.58, y4, rw * 0.42, Cm(0.85),
                 ec if "★" in ename else RGBColor(0xF8, 0xF9, 0xFA),
                 line_color=ec, line_width=Pt(1))
        add_textbox(sl, eresult,
                    rx + rw * 0.58 + Cm(0.1), y4 + Cm(0.1), rw * 0.38, Cm(0.75),
                    font_size=10, bold=True,
                    color=C_WHITE if "★" in ename else (C_RED if "collapse" in eresult else C_DARK),
                    align=PP_ALIGN.CENTER)
        y4 += Cm(1.0)

    # 핵심 발견 callout
    y5 = y4 + Cm(0.2)
    add_rect(sl, rx, y5, rw, Cm(1.1), RGBColor(0xFF, 0xF3, 0xE0))
    add_textbox(sl, "핵심 발견", rx + Cm(0.2), y5 + Cm(0.05), rw - Cm(0.4), Cm(0.45),
                font_size=11, bold=True, color=C_ORANGE)
    add_textbox(sl,
                "Collapse ≠ feature 수 부족\n= pitcher context (arsenal 58D) 부재",
                rx + Cm(0.2), y5 + Cm(0.48), rw - Cm(0.4), Cm(0.6),
                font_size=10, color=C_DARK)

    # ─────────────────────────────────────────────────────────────
    # Slide 7 — 베이스라인 비교 ① 예측 정확도
    # ─────────────────────────────────────────────────────────────
    sl = prs.slides.add_slide(blank)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "베이스라인 비교 ① — 예측 정확도 (동일 10-class · 동일 test set)", "Slide 7 / 10")
    add_folder_tags(sl, ["transition-models"])

    img_ok = add_image_fit(sl, "fig4_sota_comparison.png",
                           MARGIN, BODY_TOP, W - MARGIN*2, H - BODY_TOP - Cm(1.2))
    if not img_ok:
        add_textbox(sl, "그림 미생성: uv run python scripts/40_build_presentation_figures.py 실행 필요",
                    MARGIN, BODY_TOP + Cm(1), W - MARGIN*2, Cm(2),
                    font_size=14, color=C_GRAY, align=PP_ALIGN.CENTER)

    add_textbox(sl,
                "직접 비교: MLP 77d(collapse) 41.1% → Transformer 67.2% → MLP10 135d(ours) 67.6% — 동급, MDP 호환 유지\n"
                "외부 RF/XGB/LLM은 다른 task·다른 class 정의 → 회색 참고용 (직접 우열 비교 금지)",
                MARGIN, H - Cm(1.1), W - MARGIN*2, Cm(0.9),
                font_size=11, bold=False, color=C_DARK, align=PP_ALIGN.CENTER)

    # ─────────────────────────────────────────────────────────────
    # Slide 8 — Stage 4: MDP + RL
    # ─────────────────────────────────────────────────────────────
    sl = prs.slides.add_slide(blank)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "Stage 4 — MDP + RL Agent: 장기 보상 최적 정책 학습", "Slide 8 / 10")
    add_folder_tags(sl, ["rl-agent"])

    # MDP 정의 박스 (왼쪽)
    add_rect(sl, MARGIN, BODY_TOP, W * 0.44, Cm(3.2), RGBColor(0x1A, 0x2A, 0x3A))
    add_textbox(sl, "MDP 정의", MARGIN + Cm(0.3), BODY_TOP + Cm(0.1), W * 0.41, Cm(0.55),
                font_size=13, bold=True, color=C_GREEN)
    mdp_lines = [
        ("State s", "(balls, strikes, outs, runners,\nbatter_cluster, pitcher_cluster)\n|S| = 4×3×3×8×3×4 = 9,216"),
        ("Action a", "(pitch_type × zone)\n9 types × 13 zones = 117 actions"),
        ("Reward r", "RE24(prev) - RE24(next) - runs\n+ count-shaping (Ng et al. 1999)"),
        ("Discount γ", "0.99 | 3 outs → episode 종료"),
    ]
    y6 = BODY_TOP + Cm(0.7)
    for k, v in mdp_lines:
        add_textbox(sl, k, MARGIN + Cm(0.3), y6, Cm(2.0), Cm(0.9),
                    font_size=10, bold=True, color=C_ORANGE)
        add_textbox(sl, v, MARGIN + Cm(2.3), y6, W * 0.39, Cm(0.9),
                    font_size=9, color=C_WHITE)
        y6 += Cm(0.75)

    # 알고리즘 표 (오른쪽)
    algo_rows = [
        ("MDP-VI",    "tabular Value Iteration",   "P(s'|s,a) table 전체 precompute",  "✅ model-based", C_GREEN),
        ("Dyna-Q",    "Q-learning + planning sweep", "TM 기반 Bellman 업데이트",        "✅ model-based", C_GREEN),
        ("DQN/DDQN",  "Stable-Baselines3 DQN",     "env.step()으로 TM 샘플링",         "△ model-free",  C_GRAY),
        ("PPO",       "Stable-Baselines3 PPO",      "env.step()으로 TM 샘플링",         "△ model-free",  C_GRAY),
        ("Random",    "uniform random action",      "—",                               "baseline",      C_GRAY),
    ]
    ax = W * 0.46
    aw = W - ax - MARGIN
    ahdr2 = ["알고리즘", "TM 소비 방식", "결과"]
    acol_ws2 = [aw * r for r in [0.22, 0.48, 0.28]]
    acol_xs2 = [ax]
    for aw2 in acol_ws2[:-1]:
        acol_xs2.append(acol_xs2[-1] + aw2)

    y7 = BODY_TOP
    for ci, (hdr, cx, cw) in enumerate(zip(ahdr2, acol_xs2, acol_ws2)):
        add_rect(sl, cx, y7, cw - Cm(0.05), ROW_H, C_DARK)
        add_textbox(sl, hdr, cx + Cm(0.1), y7 + Cm(0.05), cw - Cm(0.2), ROW_H - Cm(0.1),
                    font_size=10.5, bold=True, color=C_WHITE)
    y7 += ROW_H

    for name, desc, tm_usage, result_lbl, c in algo_rows:
        bg = RGBColor(0xD5, 0xF5, 0xE3) if "model-based" in result_lbl else (
             RGBColor(0xF8, 0xF9, 0xFA) if "model-free" in result_lbl else C_WHITE)
        cells = [name, tm_usage, result_lbl]
        for ci, (cell, cx, cw) in enumerate(zip(cells, acol_xs2, acol_ws2)):
            add_rect(sl, cx, y7, cw - Cm(0.05), ROW_H + Cm(0.1), bg)
            fc = c if ci in (0, 2) else C_DARK
            add_textbox(sl, cell, cx + Cm(0.1), y7 + Cm(0.05), cw - Cm(0.2), ROW_H,
                        font_size=9, color=fc, bold=(ci == 2 and "model-based" in result_lbl))
        y7 += ROW_H + Cm(0.1)

    # 추론 설명
    y8 = max(y7, BODY_TOP + Cm(3.3))
    add_textbox(sl,
                "출력 형식: pitch_type + zone → 예) 'FF-Z5' (4-seam fastball, zone 5)\n"
                "MDP-VI 정책: policy[state_idx] = argmax_a Q[s,a] | 추론 레이턴시 < 1ms",
                ax, y8, aw, Cm(0.9),
                font_size=9.5, color=C_DARK)

    # 장기 MDP 장점 박스
    y9 = y8 + Cm(1.1)
    add_rect(sl, MARGIN, y9, W - MARGIN*2, Cm(0.85), RGBColor(0xEB, 0xF5, 0xFB))
    add_textbox(sl,
                "MDP 장점: 단순 확률 예측 모델과 달리 장기적 기대 보상(Expected RE24/inning)을 명시적으로 최적화",
                MARGIN + Cm(0.3), y9 + Cm(0.1), W - MARGIN*2 - Cm(0.6), Cm(0.7),
                font_size=11, bold=True, color=C_BLUE)

    # ─────────────────────────────────────────────────────────────
    # Slide 9 — 베이스라인 비교 ② 정책 가치
    # ─────────────────────────────────────────────────────────────
    sl = prs.slides.add_slide(blank)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "베이스라인 비교 ② — 정책 가치 RE24/inning (동일 MDP, n=1,000 ep)", "Slide 9 / 10")
    add_folder_tags(sl, ["rl-agent", "transition-models"])

    img_ok = add_image_fit(sl, "fig_rl_reward_comparison.png",
                           MARGIN, BODY_TOP, W - MARGIN*2, H - BODY_TOP - Cm(1.4))
    if not img_ok:
        add_textbox(sl, "그림 미생성: uv run python scripts/42_build_fullpipeline_figures.py 실행 필요",
                    MARGIN, BODY_TOP + Cm(1), W - MARGIN*2, Cm(2),
                    font_size=14, color=C_GRAY, align=PP_ALIGN.CENTER)

    add_textbox(sl,
                f"핵심: MDP-VI (MLP10) {mdp_vi_mlp10:+.3f} vs Random {random_mlp10:+.3f} → Δ = {delta_re24:+.2f} RE24/inning | "
                "DQN·DDQN·PPO는 Random과 통계적 무차이 (reward SNR ≈ 0.02, model-free 붕괴) → model-based RL 필수",
                MARGIN, H - Cm(1.1), W - MARGIN*2, Cm(0.9),
                font_size=10.5, bold=False, color=C_DARK, align=PP_ALIGN.CENTER)

    # ─────────────────────────────────────────────────────────────
    # Slide 10 — 결론 · 기여 · 한계
    # ─────────────────────────────────────────────────────────────
    sl = prs.slides.add_slide(blank)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "결론 · 기여 · 한계 & Future Work", "Slide 10 / 10")
    add_folder_tags(sl, ["전체"])

    # 3대 기여 (상단)
    contributions = [
        ("① 4-repo 통합 파이프라인",
         "byte-equal CONTRACT_v1 계약\n팀 동시 개발 + 재현성 보장",
         C_BLUE),
        ("② 10-class Collapse → 135d 돌파",
         f"77d 41.1% → 135d {our_top1*100:.1f}% (+{(our_top1-0.411)*100:.1f}pp)\n"
         "MDP 호환 유지 — arsenal 58D 해결",
         C_ORANGE),
        ("③ Model-based RL 우월성 입증",
         f"MDP-VI Δ = {delta_re24:+.2f} RE24/inning vs Random\n"
         "DQN·PPO·Random ≈ 무차이 (SNR 부족)",
         C_GREEN),
    ]
    box_w3 = (W - MARGIN*2 - Cm(0.4)*2) / 3
    bx3 = MARGIN
    y_c = BODY_TOP
    for title, desc, c in contributions:
        add_rect(sl, bx3, y_c, box_w3, Cm(1.8),
                 RGBColor(0xF8, 0xF9, 0xFA), line_color=c, line_width=Pt(2.5))
        add_rect(sl, bx3, y_c, box_w3, Cm(0.6), c)
        add_textbox(sl, title, bx3 + Cm(0.15), y_c + Cm(0.06),
                    box_w3 - Cm(0.3), Cm(0.52),
                    font_size=11, bold=True, color=C_WHITE)
        add_textbox(sl, desc, bx3 + Cm(0.15), y_c + Cm(0.65),
                    box_w3 - Cm(0.3), Cm(1.1),
                    font_size=9.5, color=C_DARK)
        bx3 += box_w3 + Cm(0.4)

    # 한계 (중단)
    y_lim = y_c + Cm(2.05)
    add_textbox(sl, "한계 (정직한 평가)", MARGIN, y_lim, W - MARGIN*2, Cm(0.5),
                font_size=13, bold=True, color=C_RED)
    y_lim += Cm(0.55)
    limitations = [
        "실제 MLB 투수 imitation 베이스라인 미구현 — 'RL 정책 vs 실제 투수 선택' 직접 비교 없음",
        "Single~HR per-class 0% — batter context feature(batter_func/moment) 없음, 구조적 한계",
        "Arsenal feature가 4시즌 전체(2022–2025) 집계 — train-only 분리 검증 필요 (잠재적 leakage 가능)",
    ]
    for lim in limitations:
        add_rect(sl, MARGIN, y_lim, W - MARGIN*2, Cm(0.6),
                 RGBColor(0xFF, 0xEB, 0xEB), line_color=C_RED, line_width=Pt(1))
        add_textbox(sl, f"▸ {lim}", MARGIN + Cm(0.2), y_lim + Cm(0.08),
                    W - MARGIN*2 - Cm(0.4), Cm(0.5),
                    font_size=10, color=C_DARK)
        y_lim += Cm(0.68)

    # Future Work (하단)
    y_fw = y_lim + Cm(0.2)
    add_textbox(sl, "Future Work", MARGIN, y_fw, W - MARGIN*2, Cm(0.5),
                font_size=12, bold=True, color=C_DARK)
    y_fw += Cm(0.55)
    fw_items = [
        "batter_func/moment 추가 → Single~HR > 5% 목표",
        "실제 MLB 투수 선택 vs RL 정책 RE24 비교 (imitation baseline)",
        "train-only arsenal aggregation 재검증 (leakage 제거)",
    ]
    fw_bx = MARGIN
    fw_w = (W - MARGIN*2 - Cm(0.3)*2) / 3
    for fw in fw_items:
        add_rect(sl, fw_bx, y_fw, fw_w, Cm(0.65),
                 RGBColor(0xEB, 0xF5, 0xFB), line_color=C_BLUE, line_width=Pt(1))
        add_textbox(sl, fw, fw_bx + Cm(0.15), y_fw + Cm(0.08),
                    fw_w - Cm(0.3), Cm(0.55),
                    font_size=9, color=C_DARK)
        fw_bx += fw_w + Cm(0.3)

    # ── 저장 ─────────────────────────────────────────────────────────────
    prs.save(str(PPTX_PATH))
    size_kb = PPTX_PATH.stat().st_size / 1024
    print(f"\n[OK] 저장 완료: {PPTX_PATH}")
    print(f"     크기: {size_kb:.0f} KB  |  슬라이드: 10장")


if __name__ == "__main__":
    print("=" * 60)
    print("SmartPitch Full-Pipeline 발표 슬라이드 생성")
    print("=" * 60)
    make_pptx()
