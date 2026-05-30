"""
scripts/41_build_pptx.py

python-pptx로 발표 슬라이드 10장 생성.

Usage:
    uv run pip install python-pptx   # 미설치 시
    uv run python scripts/41_build_pptx.py

출력: outputs/SmartPitch_TransitionModels_Presentation.pptx
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
PPTX_PATH = OUTPUT_DIR / "SmartPitch_TransitionModels_Presentation.pptx"

# ── 색상 팔레트 ────────────────────────────────────────────────────────────
C_BLUE   = RGBColor(0x29, 0x80, 0xB9)   # 메인 파란색
C_ORANGE = RGBColor(0xE6, 0x7E, 0x22)   # 핵심 기여 오렌지
C_GREEN  = RGBColor(0x27, 0xAE, 0x60)   # 긍정/성공 초록
C_RED    = RGBColor(0xE7, 0x4C, 0x3C)   # 경고/collapse 빨강
C_DARK   = RGBColor(0x2C, 0x3E, 0x50)   # 헤더 다크
C_LIGHT  = RGBColor(0xF8, 0xF9, 0xFA)   # 배경 연회색
C_WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
C_GRAY   = RGBColor(0x95, 0xA5, 0xA6)


def load_comp_data():
    with open(OUTPUT_DIR / "all_models_comparison_10cls.json", encoding="utf-8") as f:
        comp10 = json.load(f)
    with open(OUTPUT_DIR / "all_models_comparison_4cls.json", encoding="utf-8") as f:
        comp4 = json.load(f)
    return comp10, comp4


# ── 헬퍼: 슬라이드 배경색 설정 ────────────────────────────────────────────
def set_slide_bg(slide, color: RGBColor):
    from pptx.oxml.ns import qn
    from lxml import etree
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


# ── 헬퍼: 텍스트 박스 추가 ────────────────────────────────────────────────
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


# ── 헬퍼: 직사각형 도형 추가 ────────────────────────────────────────────────
def add_rect(slide, left, top, width, height, fill_color, line_color=None, line_width=Pt(0)):
    shape = slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        left, top, width, height,
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if line_color:
        shape.line.color.rgb = line_color
        shape.line.width = line_width
    else:
        shape.line.fill.background()
    return shape


# ── 헬퍼: 이미지 삽입 (존재 시) ──────────────────────────────────────────
def add_image_if_exists(slide, fname, left, top, width=None, height=None):
    p = FIG_DIR / fname
    if p.exists():
        if width and height:
            slide.shapes.add_picture(str(p), left, top, width, height)
        elif width:
            slide.shapes.add_picture(str(p), left, top, width=width)
        elif height:
            slide.shapes.add_picture(str(p), left, top, height=height)
        else:
            slide.shapes.add_picture(str(p), left, top)
        return True
    return False


# ── 슬라이드 레이아웃 상수 ────────────────────────────────────────────────
W = Inches(13.33)   # widescreen 16:9
H = Inches(7.5)
MARGIN = Cm(1.2)
HEADER_H = Cm(1.6)
BODY_TOP = HEADER_H + Cm(0.5)
BODY_H = H - BODY_TOP - MARGIN


def make_slide_header(slide, title: str, subtitle: str = ""):
    """공통 헤더: 다크 배경 + 흰 제목"""
    add_rect(slide, 0, 0, W, HEADER_H, C_DARK)
    add_textbox(slide, title, MARGIN, Cm(0.2), W - MARGIN * 2, HEADER_H - Cm(0.4),
                font_size=24, bold=True, color=C_WHITE, align=PP_ALIGN.LEFT)
    if subtitle:
        add_textbox(slide, subtitle, W - Cm(8), Cm(0.3), Cm(7.5), HEADER_H - Cm(0.6),
                    font_size=13, bold=False, color=C_GRAY, align=PP_ALIGN.RIGHT)


def make_pptx():
    prs = Presentation()
    prs.slide_width  = W
    prs.slide_height = H

    comp10, comp4 = load_comp_data()
    blank_layout = prs.slide_layouts[6]  # blank

    # =========================================================
    # Slide 1 — Cover
    # =========================================================
    sl = prs.slides.add_slide(blank_layout)
    set_slide_bg(sl, C_DARK)

    # 상단 오렌지 라인
    add_rect(sl, 0, 0, W, Cm(0.5), C_ORANGE)

    add_textbox(sl, "SmartPitch MDP", MARGIN, Cm(1.2), W - MARGIN*2, Cm(1.5),
                font_size=22, bold=False, color=C_ORANGE, align=PP_ALIGN.CENTER)
    add_textbox(sl, "전이확률 모델 비교 실험", MARGIN, Cm(2.5), W - MARGIN*2, Cm(1.8),
                font_size=36, bold=True, color=C_WHITE, align=PP_ALIGN.CENTER)
    add_textbox(sl, "Transition Probability Model Comparison", MARGIN, Cm(4.1), W - MARGIN*2, Cm(1.0),
                font_size=16, bold=False, color=C_GRAY, align=PP_ALIGN.CENTER)

    # 하단 정보 박스 3개
    for i, (label, val) in enumerate([
        ("데이터", "MLB Statcast 2022–2024\n2,983,621 투구"),
        ("재현 논문", "Otremba 2022\nMIT Sloan 2025"),
        ("주요 발견", "Arsenal Context 58d\nCollapse 해소 + MDP 호환"),
    ]):
        bx = Cm(1.2) + i * Cm(4.35)
        add_rect(sl, bx, Cm(5.5), Cm(4.0), Cm(1.8), RGBColor(0x1A, 0x2A, 0x3A))
        add_textbox(sl, label, bx + Cm(0.2), Cm(5.55), Cm(3.6), Cm(0.6),
                    font_size=10, bold=True, color=C_ORANGE)
        add_textbox(sl, val, bx + Cm(0.2), Cm(6.1), Cm(3.6), Cm(1.0),
                    font_size=11, color=C_WHITE)

    add_textbox(sl, "2026-05-06 ~ 2026-05-27 | Phase 1~10 완료",
                MARGIN, H - Cm(0.8), W - MARGIN*2, Cm(0.6),
                font_size=10, color=C_GRAY, align=PP_ALIGN.CENTER)

    # =========================================================
    # Slide 2 — 문제 정의
    # =========================================================
    sl = prs.slides.add_slide(blank_layout)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "문제 정의 & 연구 목표", "Slide 2 / 10")

    add_textbox(sl, "MDP 전이확률  P(outcome | pitch, context) 추정",
                MARGIN, BODY_TOP, W - MARGIN*2, Cm(1.0),
                font_size=18, bold=True, color=C_DARK)

    code_txt = (
        "state s  = 볼카운트 · 주자상황 · 이닝 ...\n"
        "action a = 투구 종류 · 위치\n"
        "outcome  = Ball / Strike / Foul / InPlay  (4-class)\n"
        "         = Ball / Strike / Single / Double / Triple\n"
        "           / HR / FieldOut / Strikeout / Walk / HBP  (10-class)"
    )
    add_rect(sl, MARGIN, BODY_TOP + Cm(1.1), W/2 - MARGIN - Cm(0.5), Cm(2.8),
             RGBColor(0xF0, 0xF4, 0xF8))
    add_textbox(sl, code_txt, MARGIN + Cm(0.3), BODY_TOP + Cm(1.2),
                W/2 - MARGIN - Cm(1.0), Cm(2.6),
                font_size=11, color=C_DARK)

    # 기존 논문 한계
    rows = [
        ("Otremba 2022 (SmartPitch)", "4-class만 예측, 투수 맥락 feature 없음", C_RED),
        ("MIT Sloan 2025 (Transformer)", "10-class 가능, MDP 비호환 (400-pitch history 필요)", C_ORANGE),
    ]
    y = BODY_TOP + Cm(1.1)
    for name, desc, c in rows:
        add_rect(sl, W/2 + Cm(0.3), y, W/2 - MARGIN - Cm(0.3), Cm(1.1), C_LIGHT,
                 line_color=c, line_width=Pt(2))
        add_textbox(sl, name, W/2 + Cm(0.6), y + Cm(0.05), W/2 - MARGIN - Cm(0.9), Cm(0.5),
                    font_size=12, bold=True, color=c)
        add_textbox(sl, desc, W/2 + Cm(0.6), y + Cm(0.55), W/2 - MARGIN - Cm(0.9), Cm(0.55),
                    font_size=10, color=C_DARK)
        y += Cm(1.3)

    goals = [
        ("① 비교 조건 분리", "같은 N·지표끼리만 직접 비교"),
        ("② MDP + 10-class", "MDP 호환 유지하면서 10-class 달성"),
        ("③ Collapse 규명", "원인 분석 및 해결"),
    ]
    y2 = BODY_TOP + Cm(3.9)
    add_textbox(sl, "연구 목표", MARGIN, y2, Cm(12), Cm(0.6),
                font_size=14, bold=True, color=C_BLUE)
    for i, (g, d) in enumerate(goals):
        gx = MARGIN + i * Cm(4.2)
        add_rect(sl, gx, y2 + Cm(0.7), Cm(3.9), Cm(0.9), RGBColor(0xEB, 0xF5, 0xFB),
                 line_color=C_BLUE, line_width=Pt(1.5))
        add_textbox(sl, g, gx + Cm(0.2), y2 + Cm(0.72), Cm(3.5), Cm(0.42),
                    font_size=12, bold=True, color=C_BLUE)
        add_textbox(sl, d, gx + Cm(0.2), y2 + Cm(1.15), Cm(3.5), Cm(0.45),
                    font_size=9.5, color=C_DARK)

    # =========================================================
    # Slide 3 — 논문 포지셔닝
    # =========================================================
    sl = prs.slides.add_slide(blank_layout)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "논문 포지셔닝: 3-way 비교", "Slide 3 / 10")

    img_ok = add_image_if_exists(sl, "fig2_paper_positioning.png",
                                  MARGIN, BODY_TOP, width=W - MARGIN*2)
    if not img_ok:
        add_textbox(sl, "그림: fig2_paper_positioning.png\n(scripts/40_build_presentation_figures.py 실행 필요)",
                    MARGIN, BODY_TOP + Cm(1), W - MARGIN*2, Cm(3),
                    font_size=14, color=C_GRAY, align=PP_ALIGN.CENTER)

    add_textbox(sl,
                "차별점: Otremba MDP/RL 통합  +  MIT Sloan-style 10-class 세분화  +  본인 Arsenal Context 58d",
                MARGIN, H - Cm(1.0), W - MARGIN*2, Cm(0.8),
                font_size=12, bold=True, color=C_ORANGE, align=PP_ALIGN.CENTER)

    # =========================================================
    # Slide 4 — 데이터 & 엔지니어링
    # =========================================================
    sl = prs.slides.add_slide(blank_layout)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "데이터 & 핵심 엔지니어링", "Slide 4 / 10")

    # 왼쪽: 데이터셋 정보
    data_rows = [
        ("시즌", "2022 · 2023 · 2024 (3시즌)"),
        ("총 투구 수", "2,983,621 rows"),
        ("Test set", "353,667–353,776 (2024 H2)"),
        ("Feature", "77d / 87d / 135d"),
    ]
    y = BODY_TOP + Cm(0.3)
    for k, v in data_rows:
        add_rect(sl, MARGIN, y, Cm(5.5), Cm(0.7), C_LIGHT)
        add_textbox(sl, k, MARGIN + Cm(0.2), y + Cm(0.1), Cm(2.0), Cm(0.55),
                    font_size=11, bold=True, color=C_BLUE)
        add_textbox(sl, v, MARGIN + Cm(2.3), y + Cm(0.1), Cm(3.0), Cm(0.55),
                    font_size=11, color=C_DARK)
        y += Cm(0.85)

    # 오른쪽: 엔지니어링 결정
    eng_items = [
        ("① Lazy Loading", "Eager: 72.6 GB → Lazy: 0.25 GB\n(290배 절감)", C_GREEN),
        ("② Stride=8 최적화", "38시간 → 5시간 (sequence_length=400 유지)", C_BLUE),
        ("③ Multi-platform", "CUDA → MPS → CPU 자동 감지 (get_device())", C_ORANGE),
    ]
    y2 = BODY_TOP + Cm(0.3)
    for title, desc, c in eng_items:
        add_rect(sl, W/2 + Cm(0.2), y2, W/2 - MARGIN - Cm(0.2), Cm(1.4),
                 C_LIGHT, line_color=c, line_width=Pt(2))
        add_textbox(sl, title, W/2 + Cm(0.5), y2 + Cm(0.1), W/2 - MARGIN - Cm(0.8), Cm(0.5),
                    font_size=13, bold=True, color=c)
        add_textbox(sl, desc, W/2 + Cm(0.5), y2 + Cm(0.6), W/2 - MARGIN - Cm(0.8), Cm(0.7),
                    font_size=10, color=C_DARK)
        y2 += Cm(1.6)

    # 135-dim 구성 설명
    dim_txt = (
        "135-dim = 77d (Model B) + 5d UMAP + 1d count_cluster + 32d arsenal_func + 20d arsenal_moment\n"
        "[0:77] 기존 feature   [77:83] 볼카운트 맥락   [83:135] Pitcher Arsenal 통계"
    )
    add_rect(sl, MARGIN, y + Cm(0.3), W - MARGIN*2, Cm(1.0),
             RGBColor(0xFF, 0xF3, 0xE0))
    add_textbox(sl, "135-dim Feature 구성", MARGIN + Cm(0.3), y + Cm(0.35),
                Cm(5), Cm(0.45), font_size=12, bold=True, color=C_ORANGE)
    add_textbox(sl, dim_txt, MARGIN + Cm(0.3), y + Cm(0.55),
                W - MARGIN*2 - Cm(0.6), Cm(0.7), font_size=10, color=C_DARK)

    # =========================================================
    # Slide 5 — 실험 설계 & 공정 비교
    # =========================================================
    sl = prs.slides.add_slide(blank_layout)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "실험 설계 & 공정 비교 환경", "Slide 5 / 10")

    # 아키텍처 표
    arch_header = ["모델", "Architecture", "Input", "Params", "MDP"]
    arch_data = [
        ("LR", "Linear", "77d / 135d", "~770 / ~1350", "✅"),
        ("LightGBM", "Tree (boosting)", "77d / 135d", "~50K leaves", "✅"),
        ("MLP ★", "FC [128,128]", "77d / 135d", "~27K / ~32K", "✅"),
        ("RNN (LSTM)", "2-layer LSTM", "400×87 seq", "~590K", "❌"),
        ("Transformer", "12-layer Enc.", "400×87 seq", "9.7M", "❌"),
    ]

    col_w = [(W - MARGIN*2) * r for r in [0.18, 0.20, 0.20, 0.20, 0.08]]
    col_x = [MARGIN]
    for w_val in col_w[:-1]:
        col_x.append(col_x[-1] + w_val)

    row_h = Cm(0.55)
    y = BODY_TOP + Cm(0.2)

    # 헤더 행
    for ci, (hdr, cx, cw) in enumerate(zip(arch_header, col_x, col_w)):
        add_rect(sl, cx, y, cw - Cm(0.05), row_h, C_DARK)
        add_textbox(sl, hdr, cx + Cm(0.1), y + Cm(0.05), cw - Cm(0.2), row_h - Cm(0.1),
                    font_size=11, bold=True, color=C_WHITE)
    y += row_h

    for ri, row in enumerate(arch_data):
        bg = RGBColor(0xEB, 0xF5, 0xFB) if ri == 2 else (C_LIGHT if ri % 2 == 0 else C_WHITE)
        for ci, (cell, cx, cw) in enumerate(zip(row, col_x, col_w)):
            add_rect(sl, cx, y, cw - Cm(0.05), row_h, bg)
            fc = C_BLUE if ri == 2 else (C_GREEN if cell == "✅" else (C_RED if cell == "❌" else C_DARK))
            fw = True if ri == 2 else False
            add_textbox(sl, cell, cx + Cm(0.1), y + Cm(0.05), cw - Cm(0.2), row_h - Cm(0.1),
                        font_size=10.5, bold=fw, color=fc)
        y += row_h

    # 공정 비교 원칙
    y2 = y + Cm(0.4)
    add_textbox(sl, "공정 비교 원칙", MARGIN, y2, W - MARGIN*2, Cm(0.5),
                font_size=14, bold=True, color=C_DARK)
    cmp_items = [
        ("G3 vs G4 (iid)", "같은 N (353K), 같은 architecture → context 효과만 비교 ✅", C_GREEN),
        ("G5 vs G6' (seq)", "같은 N=22,127, drop=False → hybrid 효과 비교 ✅", C_GREEN),
        ("G4 vs G5 (cross)", "N 다름 (iid: 전수, seq: last-pitch-of-AB) → 주의 ⚠️", C_ORANGE),
    ]
    y3 = y2 + Cm(0.6)
    for lbl, desc, c in cmp_items:
        add_rect(sl, MARGIN, y3, W - MARGIN*2, Cm(0.6), C_LIGHT, line_color=c, line_width=Pt(1.5))
        add_textbox(sl, lbl, MARGIN + Cm(0.2), y3 + Cm(0.08), Cm(3.5), Cm(0.5),
                    font_size=11, bold=True, color=c)
        add_textbox(sl, desc, MARGIN + Cm(3.8), y3 + Cm(0.08), W - MARGIN*2 - Cm(4.2), Cm(0.5),
                    font_size=10.5, color=C_DARK)
        y3 += Cm(0.7)

    # =========================================================
    # Slide 6 — 핵심 발견 1: Collapse
    # =========================================================
    sl = prs.slides.add_slide(blank_layout)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "핵심 발견 1: 10-class i.i.d. Collapse", "Slide 6 / 10")

    # collapse 표
    cl_header = ["모델 (77d)", "Top-1", "Macro-F1", "패턴"]
    cl_data = [
        ("LR", "41.1%", "5.9%", "Strike만 예측 (97.6%)"),
        ("LightGBM", "13.0%", "7.2%", "전 클래스 균등 예측 (역방향 collapse)"),
        ("MLP", "41.1%", "5.8%", "Strike만 예측 (Focal Loss γ=2 무효)"),
        ("RNN (seq)", "66.9%", "28.8%", "정상 ✅ — 400-pitch context 활용"),
        ("Transformer (seq)", "67.2%", "30.1%", "정상 ✅ — 400-pitch context 활용"),
    ]
    col_w2 = [(W - MARGIN*2) * r for r in [0.15, 0.12, 0.14, 0.55]]
    col_x2 = [MARGIN]
    for cw2 in col_w2[:-1]:
        col_x2.append(col_x2[-1] + cw2)

    y = BODY_TOP + Cm(0.2)
    for ci, (hdr, cx, cw2) in enumerate(zip(cl_header, col_x2, col_w2)):
        add_rect(sl, cx, y, cw2 - Cm(0.05), row_h, C_DARK)
        add_textbox(sl, hdr, cx + Cm(0.1), y + Cm(0.05), cw2 - Cm(0.2), row_h - Cm(0.1),
                    font_size=11, bold=True, color=C_WHITE)
    y += row_h

    for ri, row in enumerate(cl_data):
        bg = RGBColor(0xFD, 0xED, 0xEC) if ri < 3 else RGBColor(0xEB, 0xF5, 0xFB)
        for ci, (cell, cx, cw2) in enumerate(zip(row, col_x2, col_w2)):
            add_rect(sl, cx, y, cw2 - Cm(0.05), row_h + Cm(0.15), bg)
            fc = C_RED if (ri < 3 and ci > 0 and ci < 3) else (C_GREEN if "✅" in cell else C_DARK)
            fw = True if ci == 0 else False
            add_textbox(sl, cell, cx + Cm(0.1), y + Cm(0.05), cw2 - Cm(0.2), row_h,
                        font_size=10, bold=fw, color=fc)
        y += row_h + Cm(0.15)

    # Macro-F1 설명
    y2 = y + Cm(0.3)
    add_rect(sl, MARGIN, y2, W - MARGIN*2, Cm(1.2), RGBColor(0xFF, 0xF3, 0xE0))
    add_textbox(sl, "왜 Macro-F1이 핵심인가?",
                MARGIN + Cm(0.3), y2 + Cm(0.08), Cm(5), Cm(0.5),
                font_size=13, bold=True, color=C_ORANGE)
    add_textbox(sl,
                "Top-1 41.1%는 나름 성능 있어 보이지만 → Macro-F1 5.8% = random(10%) 이하\n"
                "= 'Strike 예측기' — class balancing · Focal Loss · sqrt-balanced 모두 무효 → 원인은 feature 부재",
                MARGIN + Cm(0.3), y2 + Cm(0.55), W - MARGIN*2 - Cm(0.6), Cm(0.65),
                font_size=10.5, color=C_DARK)

    # =========================================================
    # Slide 7 — 베이스라인 비교
    # =========================================================
    sl = prs.slides.add_slide(blank_layout)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "베이스라인 비교: 객관적 위치", "Slide 7 / 10")

    img_ok = add_image_if_exists(sl, "fig4_sota_comparison.png",
                                  MARGIN, BODY_TOP, width=W - MARGIN*2)
    if not img_ok:
        sota_rows = [
            ("외부 참고", "RF/XGBoost", "2~3-class", "72~91%", "직접 순위 비교 금지"),
            ("외부 참고", "LLM", "10-class next pitch", "64.0%", "label/state 정의 다름"),
            ("내부 baseline", "Transformer", "10-class seq", "67.2%", "400-pitch history"),
            ("내부 collapse", "MLP 77d", "10-class iid", "41.1%", "pitcher context 부재"),
            ("★ 본인 MLP10", "MLP 135d", "10-class MDP", "67.6%", "단일-step, RL 연동"),
        ]
        sota_hdr = ["비교군", "방법", "Task", "Top-1", "해석"]
        sota_col_w = [(W - MARGIN*2) * r for r in [0.25, 0.15, 0.15, 0.12, 0.28]]
        sota_col_x = [MARGIN]
        for sw in sota_col_w[:-1]:
            sota_col_x.append(sota_col_x[-1] + sw)

        y = BODY_TOP + Cm(0.5)
        for ci, (hdr, cx, sw) in enumerate(zip(sota_hdr, sota_col_x, sota_col_w)):
            add_rect(sl, cx, y, sw - Cm(0.05), row_h, C_DARK)
            add_textbox(sl, hdr, cx + Cm(0.1), y + Cm(0.05), sw - Cm(0.2), row_h - Cm(0.1),
                        font_size=11, bold=True, color=C_WHITE)
        y += row_h

        for ri, row in enumerate(sota_rows):
            bg = RGBColor(0xFF, 0xF3, 0xE0) if ri == 4 else (C_LIGHT if ri % 2 == 0 else C_WHITE)
            for ci, (cell, cx, sw) in enumerate(zip(row, sota_col_x, sota_col_w)):
                add_rect(sl, cx, y, sw - Cm(0.05), row_h, bg)
                fc = C_ORANGE if ri == 4 else (C_GRAY if ri < 2 else C_DARK)
                add_textbox(sl, cell, cx + Cm(0.1), y + Cm(0.05), sw - Cm(0.2), row_h - Cm(0.1),
                            font_size=10, color=fc, bold=(ri == 4))
            y += row_h

    add_textbox(sl,
                "직접 주장 가능한 비교: 내부 Transformer baseline 67.2% vs MLP10 67.6%; 외부 문헌은 참고용",
                MARGIN, H - Cm(1.0), W - MARGIN*2, Cm(0.8),
                font_size=12, bold=True, color=C_ORANGE, align=PP_ALIGN.CENTER)

    # =========================================================
    # Slide 8 — 핵심 발견 2: Context 해소
    # =========================================================
    sl = prs.slides.add_slide(blank_layout)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "핵심 발견 2: Arsenal Context가 Collapse 해소", "Slide 8 / 10")

    img_ok = add_image_if_exists(sl, "fig1_core_finding_context.png",
                                  MARGIN, BODY_TOP, width=W - MARGIN*2,
                                  height=Cm(3.8))
    y_below = BODY_TOP + Cm(4.0) if img_ok else BODY_TOP + Cm(0.5)

    # 표: iid 모델 context 효과
    tbl_data = [
        ("LR", "41.1% ❌", "62.4%", "+21.3pp"),
        ("LightGBM", "13.0% ❌", "67.3%", "+54.3pp"),
        ("MLP (focal) ★", "41.1% ❌", "67.6%", "+26.5pp"),
    ]
    tbl_hdr = ["모델", "77d (collapse)", "135d (+context)", "변화"]
    tbl_col_w = [(W - MARGIN*2) * r for r in [0.22, 0.22, 0.22, 0.18]]
    tbl_col_x = [MARGIN]
    for tw in tbl_col_w[:-1]:
        tbl_col_x.append(tbl_col_x[-1] + tw)

    y = y_below
    for ci, (hdr, cx, tw) in enumerate(zip(tbl_hdr, tbl_col_x, tbl_col_w)):
        add_rect(sl, cx, y, tw - Cm(0.05), row_h, C_DARK)
        add_textbox(sl, hdr, cx + Cm(0.1), y + Cm(0.05), tw - Cm(0.2), row_h - Cm(0.1),
                    font_size=11, bold=True, color=C_WHITE)
    y += row_h
    for ri, row in enumerate(tbl_data):
        bg = RGBColor(0xFF, 0xF3, 0xE0) if ri == 2 else C_LIGHT
        for ci, (cell, cx, tw) in enumerate(zip(row, tbl_col_x, tbl_col_w)):
            add_rect(sl, cx, y, tw - Cm(0.05), row_h, bg)
            fc = C_RED if "❌" in cell else (C_GREEN if "%" in cell and ci == 2 else
                                             (C_ORANGE if "pp" in cell else C_DARK))
            add_textbox(sl, cell, cx + Cm(0.1), y + Cm(0.05), tw - Cm(0.2), row_h - Cm(0.1),
                        font_size=10.5, color=fc, bold=(ri == 2))
        y += row_h

    # 결론 박스
    y2 = y + Cm(0.3)
    add_rect(sl, MARGIN, y2, W - MARGIN*2, Cm(0.9), RGBColor(0xEB, 0xF5, 0xFB))
    add_textbox(sl,
                "결론: Collapse 원인 = Architecture × Feature 수 아님 = 투수 맥락(pitcher context) 부재\n"
                "Top-1은 sequence baseline과 유사, MLP10은 MDP 호환성과 추론 효율이 강점",
                MARGIN + Cm(0.3), y2 + Cm(0.08), W - MARGIN*2 - Cm(0.6), Cm(0.8),
                font_size=11, bold=False, color=C_BLUE)

    # =========================================================
    # Slide 9 — Phase 10 최종 결과
    # =========================================================
    sl = prs.slides.add_slide(blank_layout)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "Phase 10 최종: 12-model 전체 비교", "Slide 9 / 10")

    img_ok = add_image_if_exists(sl, "fig3_phase10_12model.png",
                                  MARGIN, BODY_TOP, width=W - MARGIN*2,
                                  height=Cm(4.2))

    y_below2 = BODY_TOP + Cm(4.4) if img_ok else BODY_TOP + Cm(0.5)

    # 최종 권장 모델 박스
    add_rect(sl, MARGIN, y_below2, W - MARGIN*2, Cm(1.6),
             RGBColor(0xE8, 0xF8, 0xE8), line_color=C_GREEN, line_width=Pt(2.5))
    add_textbox(sl, "✅ 최종 모델: TransitionModelMLP10 / RL 권장 경로: MLP10H",
                MARGIN + Cm(0.3), y_below2 + Cm(0.08), Cm(8), Cm(0.55),
                font_size=14, bold=True, color=C_GREEN)
    add_textbox(sl,
                "MLP10: 135d 단일 pitch, Top-1 67.6%, Macro-F1 27.8%, CE 0.926, MDP 호환\n"
                "MLP10H: MLP10의 BIP 총량을 empirical BIP table로 재분배해 Single~HR 0% 문제 완화",
                MARGIN + Cm(0.3), y_below2 + Cm(0.65), W - MARGIN*2 - Cm(0.6), Cm(0.9),
                font_size=9.8, color=C_DARK)

    # =========================================================
    # Slide 10 — 결론 & 팀 통합
    # =========================================================
    sl = prs.slides.add_slide(blank_layout)
    set_slide_bg(sl, C_WHITE)
    make_slide_header(sl, "결론 & 팀 통합", "Slide 10 / 10")

    findings = [
        ("① Collapse 원인 규명",
         "77d i.i.d. 모델 collapse = 투수 맥락(pitcher context) 부재\nclass balancing · Focal Loss 모두 무효 — feature 구조 문제",
         C_RED),
        ("② Context = Architecture-Agnostic",
         "arsenal 58d 추가 → LR +21pp, LGB +54pp, MLP +27pp\nTop-1은 sequence baseline과 유사, MDP 호환성이 강점",
         C_ORANGE),
        ("③ Sequence는 Context를 내재 학습",
         "RNN/Transformer에 static context 추가 → 효과 없음\n400-pitch history가 arsenal context를 이미 포함",
         C_BLUE),
    ]
    y = BODY_TOP + Cm(0.2)
    for title, desc, c in findings:
        add_rect(sl, MARGIN, y, (W - MARGIN*2) * 0.6, Cm(1.25), C_LIGHT, line_color=c, line_width=Pt(2))
        add_textbox(sl, title, MARGIN + Cm(0.3), y + Cm(0.08), (W - MARGIN*2) * 0.57, Cm(0.5),
                    font_size=13, bold=True, color=c)
        add_textbox(sl, desc, MARGIN + Cm(0.3), y + Cm(0.58), (W - MARGIN*2) * 0.57, Cm(0.65),
                    font_size=10, color=C_DARK)
        y += Cm(1.4)

    # 팀 통합 박스 (오른쪽)
    add_rect(sl, (W - MARGIN*2) * 0.63, BODY_TOP + Cm(0.2),
             (W - MARGIN*2) * 0.37, Cm(4.0),
             RGBColor(0x1A, 0x2A, 0x3A))
    add_textbox(sl, "rl-agent 사용 방식",
                (W - MARGIN*2) * 0.63 + Cm(0.3), BODY_TOP + Cm(0.3),
                (W - MARGIN*2) * 0.34, Cm(0.55),
                font_size=13, bold=True, color=C_ORANGE)

    code = (
        "MDP-VI\n"
        "  P(s'|s,a) table 직접 precompute\n\n"
        "Dyna-Q\n"
        "  planning에서 transition cache 사용\n\n"
        "DQN / DDQN / PPO\n"
        "  전이표 직접 사용 X\n"
        "  PitchEnv.step()이 MLP10/MLP10H로\n"
        "  outcome을 샘플링"
    )
    add_textbox(sl, code,
                (W - MARGIN*2) * 0.63 + Cm(0.3), BODY_TOP + Cm(0.9),
                (W - MARGIN*2) * 0.34, Cm(3.0),
                font_size=8.8, color=C_WHITE)

    # Future Work 간략
    fw_items = ["MLP10H RL 비교 강화 → BIP 보상 안정화",
                "타자 arsenal feature → Single~HR 0% 해결",
                "Small Transformer (2-layer) MDP 호환 탐색",
                "UMAP 0-fill ablation"]
    y3 = y + Cm(0.3)
    add_textbox(sl, "Future Work", MARGIN, y3, W * 0.55, Cm(0.5),
                font_size=13, bold=True, color=C_DARK)
    for i, item in enumerate(fw_items):
        add_textbox(sl, f"• {item}", MARGIN + Cm(0.2), y3 + Cm(0.6) + i * Cm(0.5),
                    W * 0.55, Cm(0.5), font_size=10.5, color=C_DARK)

    # ── 저장 ─────────────────────────────────────────────────
    prs.save(str(PPTX_PATH))
    size_kb = PPTX_PATH.stat().st_size / 1024
    print(f"\n[OK] 저장 완료: {PPTX_PATH}")
    print(f"     크기: {size_kb:.0f} KB  |  슬라이드: 10장")


if __name__ == "__main__":
    print("=" * 60)
    print("SmartPitch MDP 발표 슬라이드 PPT 생성")
    print("=" * 60)
    make_pptx()
