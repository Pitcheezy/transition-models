"""10-Class Model Comparison 발표용 PPTX 생성.

출력: outputs/presentations/10class_comparison.pptx
총 6장: 표지 / 6모델 비교표 / Collapse 분석 / Per-class Accuracy / Top-4 히트맵 / 핵심 발견
"""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

REPO = Path(__file__).resolve().parent.parent
FIG_DIR = REPO / "outputs" / "figures"
OUT_DIR = REPO / "outputs" / "presentations"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / "10class_comparison.pptx"

# ── 색상 팔레트 ─────────────────────────────────────────────────────────────
C_ORANGE = RGBColor(0xE6, 0x7E, 0x22)
C_GREEN = RGBColor(0x27, 0xAE, 0x60)
C_BLUE = RGBColor(0x29, 0x80, 0xB9)
C_RED = RGBColor(0xE7, 0x4C, 0x3C)
C_DARK = RGBColor(0x2C, 0x3E, 0x50)
C_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
C_LGRAY = RGBColor(0xF4, 0xF6, 0xF7)
C_LGGREEN = RGBColor(0xD5, 0xF5, 0xE3)
C_LGORANGE = RGBColor(0xFD, 0xF2, 0xE9)
C_HEADER = RGBColor(0xEB, 0xF5, 0xFB)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
MARGIN = Inches(0.5)
FONT_KO = "맑은 고딕"


# ── 헬퍼 ────────────────────────────────────────────────────────────────────


def new_prs() -> Presentation:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    return prs


def blank_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def add_rect_bg(slide, color, left=0, top=0, width=None, height=None):
    width = width or SLIDE_W
    height = height or SLIDE_H
    shape = slide.shapes.add_shape(1, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def add_textbox(
    slide, text, left, top, width, height, font_size=18, bold=False,
    italic=False, color=C_DARK, align=PP_ALIGN.LEFT, font_name=FONT_KO,
):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, line in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        run = p.add_run()
        run.text = line
        run.font.size = Pt(font_size)
        run.font.bold = bold
        run.font.italic = italic
        run.font.color.rgb = color
        run.font.name = font_name


def add_slide_title(slide, text, font_size=28):
    add_rect_bg(slide, C_DARK, left=0, top=0, width=SLIDE_W, height=Inches(1.0))
    txBox = slide.shapes.add_textbox(MARGIN, Inches(0.1), SLIDE_W - MARGIN * 2, Inches(0.8))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = True
    run.font.color.rgb = C_WHITE
    run.font.name = FONT_KO


def cell_color(cell, rgb):
    from lxml import etree
    from pptx.oxml.ns import qn

    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    solidFill = etree.SubElement(tcPr, qn("a:solidFill"))
    srgbClr = etree.SubElement(solidFill, qn("a:srgbClr"))
    srgbClr.set("val", f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}")


def set_cell_text(
    cell, text, font_size=16, bold=False, color=C_DARK, align=PP_ALIGN.CENTER,
):
    cell.text = ""
    p = cell.text_frame.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = FONT_KO


def add_image(slide, img_path, left, top, width=None, height=None):
    if not img_path.exists():
        print(f"  [WARNING] 이미지 없음: {img_path}")
        return
    kwargs = {}
    if width:
        kwargs["width"] = width
    if height:
        kwargs["height"] = height
    slide.shapes.add_picture(str(img_path), left, top, **kwargs)


def caption(slide, text, y_offset=None, font_size=14, color=C_DARK, italic=True):
    y = y_offset or (SLIDE_H - Inches(0.5))
    add_textbox(
        slide, text, MARGIN, y, SLIDE_W - MARGIN * 2, Inches(0.5),
        font_size=font_size, italic=italic, color=color, align=PP_ALIGN.CENTER,
    )


# ── 슬라이드 ───────────────────────────────────────────────────────────────


def slide_01_cover(prs):
    """표지."""
    slide = blank_slide(prs)
    add_rect_bg(slide, C_DARK)

    add_textbox(
        slide, "10-Class Pitch Outcome\nModel Comparison",
        left=MARGIN, top=Inches(1.5), width=SLIDE_W - MARGIN * 2, height=Inches(1.5),
        font_size=42, bold=True, color=C_WHITE, align=PP_ALIGN.CENTER,
    )
    add_textbox(
        slide, "6개 모델 아키텍처 × 10-class 분류 성능 비교\nMLB Statcast 2022-2024 (3시즌, ~149만 투구)",
        left=MARGIN, top=Inches(3.2), width=SLIDE_W - MARGIN * 2, height=Inches(1.0),
        font_size=20, color=RGBColor(0xAB, 0xC4, 0xD4), align=PP_ALIGN.CENTER,
    )
    add_textbox(
        slide, "SmartPitch MDP Transition Probability Models",
        left=MARGIN, top=Inches(5.5), width=SLIDE_W - MARGIN * 2, height=Inches(0.6),
        font_size=16, color=RGBColor(0x85, 0x9B, 0xAB), align=PP_ALIGN.CENTER,
    )


def slide_02_overview(prs):
    """6모델 비교 테이블."""
    slide = blank_slide(prs)
    add_slide_title(slide, "6개 모델 10-Class 성능 비교")

    rows = [
        ("모델", "Input", "Top-1", "Top-3", "CE", "MDP", "비고"),
        ("LR", "77d", "41.1%", "86.2%", "1.614", "✅", "collapse"),
        ("LightGBM", "77d", "13.0%", "48.1%", "2.087", "✅", "역collapse"),
        ("MLP (77d)", "77d", "41.1%", "86.2%", "1.470", "✅", "collapse"),
        ("MLP 135d", "135d", "67.6%", "—", "—", "✅", "MDP 최선"),
        ("RNN", "400×87", "66.9%", "94.8%", "0.873", "❌", "sequence"),
        ("Transformer", "400×87", "67.2%", "94.7%", "0.868", "❌", "sequence"),
    ]

    n_rows, n_cols = len(rows), 7
    tbl_w = Inches(12.0)
    tbl_h = Inches(5.0)
    tbl_left = (SLIDE_W - tbl_w) / 2
    tbl = slide.shapes.add_table(n_rows, n_cols, tbl_left, Inches(1.2), tbl_w, tbl_h).table

    col_widths = [Inches(2.0), Inches(1.5), Inches(1.3), Inches(1.3), Inches(1.3), Inches(1.0), Inches(3.6)]
    for ci, w in enumerate(col_widths):
        tbl.columns[ci].width = w

    for ri, row_vals in enumerate(rows):
        for ci, val in enumerate(row_vals):
            cell = tbl.cell(ri, ci)
            is_hdr = ri == 0
            is_best = ri == 4  # MLP 135d
            is_collapse = ri in (1, 2, 3)

            if is_hdr:
                cell_color(cell, C_BLUE)
                txt_color = C_WHITE
            elif is_best:
                cell_color(cell, C_LGGREEN)
                txt_color = C_DARK
            elif is_collapse:
                cell_color(cell, RGBColor(0xFD, 0xED, 0xED))
                txt_color = C_DARK
            elif ri >= 5:
                cell_color(cell, C_HEADER)
                txt_color = C_DARK
            else:
                cell_color(cell, C_WHITE)
                txt_color = C_DARK

            set_cell_text(cell, val, font_size=16, bold=is_hdr or is_best, color=txt_color)

    caption(slide, "빨강 배경 = collapse (다수 클래스만 예측)  |  초록 배경 = MDP 호환 최선 모델", font_size=14)


def slide_03_collapse(prs):
    """Collapse 현상 분석."""
    slide = blank_slide(prs)
    add_slide_title(slide, "77-dim i.i.d. 모델의 Collapse 현상")

    # 왼쪽: 설명
    add_textbox(
        slide,
        "10개 클래스 분포 (불균형):\n"
        "  Strike  41.1%  ← 다수 클래스\n"
        "  Ball    33.4%\n"
        "  FieldOut 11.9%\n"
        "  Strikeout 5.9%\n"
        "  Single   3.7%\n"
        "  Walk     2.2%\n"
        "  Double   1.1%\n"
        "  HomeRun  0.8%\n"
        "  HBP      0.3%\n"
        "  Triple   0.1%",
        left=MARGIN, top=Inches(1.2), width=Inches(5.0), height=Inches(5.5),
        font_size=17,
    )

    # 오른쪽: 핵심 포인트 박스 3개
    boxes = [
        ("Class balancing 미적용", "LR/MLP → Strike만 예측 (41.1%)\nMacro-F1 = 0.06", C_RED),
        ("Class balancing 과적용", "LightGBM → 전 클래스 균등 (13.0%)\ninverse-freq 과보정", C_ORANGE),
        ("해결: Context 추가", "Arsenal 52d → 41.1% → 67.6%\n+26.5pp 상승", C_GREEN),
    ]

    for i, (title, desc, color) in enumerate(boxes):
        top = Inches(1.3 + i * 1.85)
        box = slide.shapes.add_shape(
            1, Inches(6.0), top, Inches(6.8), Inches(1.6),
        )
        box.fill.solid()
        box.fill.fore_color.rgb = C_WHITE
        box.line.color.rgb = color
        box.line.width = Pt(2.5)

        add_textbox(
            slide, title,
            left=Inches(6.2), top=top + Inches(0.08), width=Inches(6.4), height=Inches(0.4),
            font_size=18, bold=True, color=color,
        )
        add_textbox(
            slide, desc,
            left=Inches(6.2), top=top + Inches(0.55), width=Inches(6.4), height=Inches(0.9),
            font_size=15, color=C_DARK,
        )

    caption(
        slide,
        "핵심: feature 부족이 원인 — class balancing, Focal Loss 등 기법으로는 해결 불가",
        font_size=14, color=C_RED, italic=False,
    )


def slide_04_perclass(prs):
    """Per-class Top-1 Accuracy 테이블."""
    slide = blank_slide(prs)
    add_slide_title(slide, "Per-class Top-1 Accuracy (%)")

    rows = [
        ("클래스", "비율", "LR", "LGB", "MLP 77d", "MLP 135d", "RNN", "Transformer"),
        ("Ball", "33.3%", "0.0", "13.3", "0.0", "88.4", "87.2", "87.6"),
        ("Strike", "41.1%", "99.8", "13.1", "100", "83.7", "82.8", "82.2"),
        ("Single", "3.6%", "0", "12.3", "0", "0", "0", "0"),
        ("Double", "1.1%", "0", "10.7", "0", "0", "0", "0"),
        ("Triple", "0.09%", "0", "0", "0", "0", "0", "0"),
        ("HomeRun", "0.8%", "0", "7.9", "0", "0", "0", "0"),
        ("FieldOut", "11.8%", "0", "13.3", "0", "7.3", "8.7", "10.7"),
        ("Strikeout", "5.9%", "0", "12.8", "0", "19.5", "16.6", "17.3"),
        ("Walk", "2.0%", "0", "12.1", "0", "85.9", "81.2", "85.6"),
        ("HBP", "0.3%", "0", "3.3", "0", "2.9", "10.9", "17.2"),
    ]

    n_rows, n_cols = len(rows), 8
    tbl_w = Inches(12.3)
    tbl_h = Inches(5.5)
    tbl_left = (SLIDE_W - tbl_w) / 2
    tbl = slide.shapes.add_table(n_rows, n_cols, tbl_left, Inches(1.1), tbl_w, tbl_h).table

    col_widths = [Inches(1.5), Inches(1.0), Inches(1.2), Inches(1.2), Inches(1.5), Inches(1.6), Inches(1.6), Inches(2.0)]
    for ci, w in enumerate(col_widths):
        tbl.columns[ci].width = w

    for ri, row_vals in enumerate(rows):
        for ci, val in enumerate(row_vals):
            cell = tbl.cell(ri, ci)
            is_hdr = ri == 0
            if is_hdr:
                cell_color(cell, C_BLUE)
                set_cell_text(cell, val, font_size=14, bold=True, color=C_WHITE)
            else:
                # 0 값은 빨간 배경
                is_zero = val == "0" or val == "0.0"
                if is_zero:
                    cell_color(cell, RGBColor(0xFD, 0xED, 0xED))
                elif ci >= 5 and val not in ("—", "0"):
                    cell_color(cell, C_LGGREEN)
                else:
                    cell_color(cell, C_WHITE)
                set_cell_text(cell, val, font_size=14, bold=False, color=C_DARK)

    caption(slide, "빨강 = 0% (해당 클래스 예측 불가)  |  초록 = 유의미한 예측 성능", font_size=13)


def slide_05_top4(prs):
    """Top-4 Precision 히트맵 (기존 figure 재사용)."""
    slide = blank_slide(prs)
    add_slide_title(slide, "Top-4 Precision: Per-class 분석")

    img_path = FIG_DIR / "fig4_top4_precision_heatmap.png"
    img_h = Inches(5.3)
    img_w = Inches(5.3 * 1.4752)
    img_left = (SLIDE_W - img_w) / 2
    add_image(slide, img_path, left=img_left, top=Inches(1.1), width=img_w, height=img_h)

    cap_top = Inches(1.1) + img_h + Inches(0.12)
    caption(
        slide,
        "MLP 135d (i.i.d., MDP 호환): Walk 98%, Single 89% → Transformer와 Top-4 동등 (98.0%)",
        y_offset=cap_top, color=C_ORANGE, font_size=14, italic=False,
    )


def slide_06_takeaway(prs):
    """핵심 발견 요약."""
    slide = blank_slide(prs)
    add_slide_title(slide, "핵심 발견: 10-Class 비교에서 배운 것")

    items = [
        (
            "① 77-dim collapse는 feature 부족이 원인",
            "어떤 class balancing 기법도 (Focal Loss, sqrt-weight, inverse-freq)\n"
            "feature가 부족하면 해결 불가 — 41.1%에서 정체",
            C_RED,
        ),
        (
            "② Arsenal 52d 추가로 +26.5pp 돌파",
            "투수 repertoire 통계를 정적 feature로 추가 →\n"
            "77d 41.1% → 135d 67.6% (Sequence 모델과 동등)",
            C_GREEN,
        ),
        (
            "③ MDP 호환성 유지하며 Transformer 수준 달성",
            "MLP 135d: i.i.d. 입력, MDP state로 사용 가능\n"
            "RNN/Transformer: sequence 의존 → MDP 비호환",
            C_BLUE,
        ),
    ]

    for i, (title, desc, color) in enumerate(items):
        top = Inches(1.2 + i * 1.95)
        box = slide.shapes.add_shape(
            1, MARGIN, top, SLIDE_W - MARGIN * 2, Inches(1.7),
        )
        box.fill.solid()
        box.fill.fore_color.rgb = C_WHITE
        box.line.color.rgb = color
        box.line.width = Pt(2.0)

        add_textbox(
            slide, title,
            left=MARGIN + Inches(0.2), top=top + Inches(0.1),
            width=SLIDE_W - MARGIN * 2 - Inches(0.4), height=Inches(0.5),
            font_size=20, bold=True, color=color,
        )
        add_textbox(
            slide, desc,
            left=MARGIN + Inches(0.3), top=top + Inches(0.65),
            width=SLIDE_W - MARGIN * 2 - Inches(0.6), height=Inches(0.9),
            font_size=16, color=C_DARK,
        )


# ── 메인 ────────────────────────────────────────────────────────────────────


def main():
    prs = new_prs()

    print("10-Class Comparison PPT 생성 중...")
    slide_01_cover(prs)
    print("  [1/6] 표지")
    slide_02_overview(prs)
    print("  [2/6] 6모델 비교표")
    slide_03_collapse(prs)
    print("  [3/6] Collapse 분석")
    slide_04_perclass(prs)
    print("  [4/6] Per-class Accuracy")
    slide_05_top4(prs)
    print("  [5/6] Top-4 히트맵")
    slide_06_takeaway(prs)
    print("  [6/6] 핵심 발견")

    prs.save(str(OUT_PATH))
    sz = OUT_PATH.stat().st_size
    print(f"\n[OK] 저장 완료: {OUT_PATH}")
    print(f"     슬라이드: {len(prs.slides)}장")
    print(f"     크기: {sz // 1024:,} KB")


if __name__ == "__main__":
    main()
