"""SmartPitch v3 발표용 PPTX 생성.

출력: outputs/presentations/smartpitch_v3.pptx
총 11장 (본발표 8 + 백업 3)
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt, Emu

REPO = Path(__file__).resolve().parent.parent
FIG_DIR = REPO / "outputs" / "figures"
OUT_DIR = REPO / "outputs" / "presentations"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / "smartpitch_v3.pptx"

# ── 색상 팔레트 ─────────────────────────────────────────────────────────────
C_ORANGE  = RGBColor(0xE6, 0x7E, 0x22)
C_GREEN   = RGBColor(0x27, 0xAE, 0x60)
C_BLUE    = RGBColor(0x29, 0x80, 0xB9)
C_DARK    = RGBColor(0x2C, 0x3E, 0x50)
C_WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
C_LGRAY   = RGBColor(0xF4, 0xF6, 0xF7)
C_LGGREEN = RGBColor(0xD5, 0xF5, 0xE3)
C_HEADER  = RGBColor(0xEB, 0xF5, 0xFB)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
MARGIN  = Inches(0.5)
FONT_KO = "맑은 고딕"
FONT_EN = "Calibri"


# ── 헬퍼 ────────────────────────────────────────────────────────────────────

def new_prs() -> Presentation:
    prs = Presentation()
    prs.slide_width  = SLIDE_W
    prs.slide_height = SLIDE_H
    return prs


def blank_slide(prs: Presentation):
    """Blank layout (index 6)."""
    return prs.slides.add_slide(prs.slide_layouts[6])


def add_rect_bg(slide, hex_color: RGBColor, left=0, top=0, width=None, height=None):
    """슬라이드 배경 직사각형 추가."""
    width  = width  or SLIDE_W
    height = height or SLIDE_H
    shape = slide.shapes.add_shape(1, left, top, width, height)  # MSO_SHAPE_TYPE.RECTANGLE
    shape.fill.solid()
    shape.fill.fore_color.rgb = hex_color
    shape.line.fill.background()
    return shape


def add_textbox(slide, text: str, left, top, width, height,
                font_size: int = 18, bold: bool = False, italic: bool = False,
                color: RGBColor = C_DARK, align=PP_ALIGN.LEFT,
                font_name: str = FONT_KO, line_spacing=None) -> None:
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    if line_spacing:
        from pptx.util import Pt as _Pt
        from pptx.oxml.ns import qn
        import lxml.etree as etree
    p = tf.paragraphs[0]
    p.alignment = align
    for i, line in enumerate(text.split("\n")):
        if i > 0:
            p = tf.add_paragraph()
            p.alignment = align
        run = p.add_run()
        run.text = line
        run.font.size = Pt(font_size)
        run.font.bold = bold
        run.font.italic = italic
        run.font.color.rgb = color
        run.font.name = font_name


def add_slide_title(slide, text: str, font_size: int = 28) -> None:
    """슬라이드 상단 제목 바."""
    # 짙은 헤더 바
    bar = add_rect_bg(slide, C_DARK, left=0, top=0,
                      width=SLIDE_W, height=Inches(1.0))
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


def add_image(slide, img_path: Path, left, top, width=None, height=None):
    if not img_path.exists():
        print(f"  [WARNING] 이미지 없음: {img_path}")
        return
    if width and height:
        slide.shapes.add_picture(str(img_path), left, top, width, height)
    elif width:
        slide.shapes.add_picture(str(img_path), left, top, width=width)
    elif height:
        slide.shapes.add_picture(str(img_path), left, top, height=height)
    else:
        slide.shapes.add_picture(str(img_path), left, top)


def caption(slide, text: str, y_offset=None, font_size: int = 14,
            color: RGBColor = C_DARK, italic: bool = True):
    y = y_offset or (SLIDE_H - Inches(0.5))
    add_textbox(slide, text, MARGIN, y, SLIDE_W - MARGIN * 2, Inches(0.5),
                font_size=font_size, italic=italic, color=color, align=PP_ALIGN.CENTER)


def cell_color(cell, rgb: RGBColor):
    from pptx.oxml.ns import qn
    from lxml import etree
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    solidFill = etree.SubElement(tcPr, qn("a:solidFill"))
    srgbClr  = etree.SubElement(solidFill, qn("a:srgbClr"))
    srgbClr.set("val", f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}")


def set_cell_text(cell, text: str, font_size: int = 18, bold: bool = False,
                  color: RGBColor = C_DARK, align=PP_ALIGN.CENTER,
                  font_name: str = FONT_KO):
    cell.text = ""
    p = cell.text_frame.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = font_name


# ── 슬라이드 생성 ───────────────────────────────────────────────────────────

def slide_01_cover(prs):
    """슬라이드 1: 표지."""
    slide = blank_slide(prs)
    add_rect_bg(slide, C_DARK)

    add_textbox(slide, "SmartPitch v3",
                left=MARGIN, top=Inches(1.2), width=SLIDE_W - MARGIN * 2, height=Inches(1.2),
                font_size=44, bold=True, color=C_WHITE, align=PP_ALIGN.CENTER)

    add_textbox(slide,
                "Pitcher 의사결정 시스템\n선행 연구 한계 극복 + MDP/RL 통합",
                left=MARGIN, top=Inches(2.4), width=SLIDE_W - MARGIN * 2, height=Inches(1.0),
                font_size=22, color=RGBColor(0xAB, 0xC4, 0xD4), align=PP_ALIGN.CENTER)

    add_textbox(slide, "발표자: 김현준\n충북대학교 소프트웨어공학과\n2026년 6월",
                left=MARGIN, top=Inches(4.5), width=SLIDE_W - MARGIN * 2, height=Inches(1.5),
                font_size=16, color=RGBColor(0x85, 0x9B, 0xAB), align=PP_ALIGN.CENTER)


def slide_02_problem(prs):
    """슬라이드 2: 문제 정의."""
    slide = blank_slide(prs)
    add_slide_title(slide, "투수의 의사결정은 단순 예측이 아닌 장기 전략")

    body = (
        "상황: count 2-1, 1루 주자\n"
        "           ↓\n"
        "가능한 pitch: 100+ (구종 × 존)\n"
        "           ↓\n"
        "핵심 질문: '어떤 pitch가 장기적으로 유리한가?'\n"
        "           ↓\n"
        "결과: at-bat 종료까지의 누적 reward"
    )
    add_textbox(slide, body,
                left=MARGIN, top=Inches(1.2), width=Inches(7.5), height=Inches(5.0),
                font_size=20, color=C_DARK, align=PP_ALIGN.LEFT)

    # 오른쪽 강조 박스
    box = slide.shapes.add_shape(1,
        SLIDE_W - Inches(5.0), Inches(1.4), Inches(4.5), Inches(3.8))
    box.fill.solid(); box.fill.fore_color.rgb = C_HEADER
    box.line.color.rgb = C_BLUE

    cap = (
        "1구만 보는 예측을 넘어,\n"
        "at-bat 전체의 reward를\n"
        "최적화하는 의사결정 시스템"
    )
    add_textbox(slide, cap,
                left=SLIDE_W - Inches(4.9), top=Inches(2.0), width=Inches(4.3), height=Inches(2.8),
                font_size=18, italic=True, color=C_BLUE, align=PP_ALIGN.CENTER)

    caption(slide, "참고: 단기 예측 정확도 vs. 장기 전략 보상 최적화", y_offset=Inches(6.9))


def slide_03_prior(prs):
    """슬라이드 3: 선행 연구 한계 — fig2."""
    slide = blank_slide(prs)
    add_slide_title(slide, "두 선행 연구는 각자 한계를 가짐")

    img_path = FIG_DIR / "fig2_paper_positioning.png"
    img_w = SLIDE_W * 0.88
    img_left = (SLIDE_W - img_w) / 2
    add_image(slide, img_path, left=img_left, top=Inches(1.05), width=img_w)


def slide_04_finding(prs):
    """슬라이드 4: 핵심 발견 — fig1."""
    slide = blank_slide(prs)
    add_slide_title(slide, "핵심 발견: Arsenal feature의 효과")

    img_path = FIG_DIR / "fig1_arsenal_vs_sequence.png"
    img_w = SLIDE_W * 0.90
    img_left = (SLIDE_W - img_w) / 2
    add_image(slide, img_path, left=img_left, top=Inches(1.05), width=img_w)

    caption(slide,
            "조건 통제 검증: Focal Loss γ=2.0 동일 적용 — context 58d 추가만으로 +26.5pp",
            y_offset=Inches(7.05))


def slide_05_top4(prs):
    """슬라이드 5: Top-4 평가 — fig4."""
    slide = blank_slide(prs)
    add_slide_title(slide, "MIT Sloan 2025와 같은 Top-4 평가 기준 적용")

    img_path = FIG_DIR / "fig4_top4_precision_heatmap.png"
    # fig4 pixel ratio = 4464:3026 = 1.4752
    # 가용 높이: 7.5 - 1.1(제목) - 0.12(gap) - 0.42(캡션) - 0.1(하단) = 5.76" → 5.5" 사용
    img_h = Inches(5.5)
    img_w = Inches(5.5 * 1.4752)   # ≈ 8.11"
    img_left = (SLIDE_W - img_w) / 2
    img_top  = Inches(1.1)
    add_image(slide, img_path, left=img_left, top=img_top, width=img_w, height=img_h)

    # 캡션을 이미지 바로 아래 별도 배치 (겹침 방지)
    cap_top = img_top + img_h + Inches(0.12)
    caption(slide,
            "MLP 135d (i.i.d., MDP 호환) — Walk 98%, Single 89% → Transformer와 동등",
            y_offset=cap_top, color=C_ORANGE, font_size=14)


def slide_06_rl(prs):
    """슬라이드 6: RL 비교 표."""
    slide = blank_slide(prs)
    add_slide_title(slide, "Transformer 환경에서 6개 RL 알고리즘 비교")

    rows_data = [
        ("알고리즘", "Mean Reward", "95% CI", "비고"),
        ("MDP-VI",  "+0.224", "[0.180, 0.267]", "모델 기반 RL ★"),
        ("Dyna-Q",  "+0.210", "[0.166, 0.254]", "모델 기반 RL"),
        ("DDQN",    "+0.133", "[0.080, 0.185]", "Model-free"),
        ("DQN",     "+0.015", "[-0.046, 0.076]", "Model-free"),
        ("PPO",     "-0.025", "[-0.088, 0.039]", "Policy gradient"),
        ("Random",  "-0.085", "[-0.156, -0.014]", "기준선"),
    ]

    n_rows = len(rows_data)
    n_cols = 4
    tbl_w = Inches(11.0)
    tbl_h = Inches(4.5)
    tbl_left  = (SLIDE_W - tbl_w) / 2
    tbl_top   = Inches(1.15)

    tbl = slide.shapes.add_table(n_rows, n_cols, tbl_left, tbl_top, tbl_w, tbl_h).table

    # 열 너비
    col_widths = [Inches(2.0), Inches(2.5), Inches(3.5), Inches(3.0)]
    for ci, w in enumerate(col_widths):
        tbl.columns[ci].width = w

    for ri, row_vals in enumerate(rows_data):
        for ci, val in enumerate(row_vals):
            cell = tbl.cell(ri, ci)
            is_header = (ri == 0)
            bold = is_header or (ri in (1, 2))

            if is_header:
                cell_color(cell, C_BLUE)
                txt_color = C_WHITE
            elif ri in (1, 2):
                cell_color(cell, C_LGGREEN)
                txt_color = C_DARK
            elif ri == n_rows - 1:
                cell_color(cell, C_LGRAY)
                txt_color = RGBColor(0x88, 0x88, 0x88)
            else:
                cell_color(cell, C_WHITE)
                txt_color = C_DARK

            set_cell_text(cell, val, font_size=18, bold=bold, color=txt_color)

    caption(slide,
            "본인 Transformer를 transition function으로 활용  →  모델 기반 RL (MDP-VI, Dyna-Q)이 압도적 우위",
            y_offset=Inches(5.85), font_size=16, italic=False)


def slide_07_contributions(prs):
    """슬라이드 7: 3가지 contribution."""
    slide = blank_slide(prs)
    add_slide_title(slide, "본인 SmartPitch의 3가지 Contribution")

    items = [
        ("① MDP/RL 통합 확장",
         "Otremba: Value Iteration 1개  →  본인: 6개 RL 알고리즘 비교 (MDP-VI / Dyna-Q / DDQN / DQN / PPO / Random)"),
        ("② i.i.d.로 Sequence 모델 수준 달성",
         "MIT Sloan: Transformer 필수 (MDP 비호환)  →  본인 MLP + context 58d: 동등 성능 + MDP 호환"),
        ("③ Pitcher 맥락 통합  (양측 선행연구 미수행)",
         "context 58d 추가  →  +26.5pp 정량 검증  (77d 41.1% → 135d 67.6%)"),
    ]

    BOX_COLORS  = [C_HEADER, RGBColor(0xFD, 0xF2, 0xE9), RGBColor(0xE9, 0xF7, 0xEF)]
    TITLE_COLORS = [C_BLUE, C_ORANGE, C_GREEN]

    for i, ((title, desc), bg, tc) in enumerate(zip(items, BOX_COLORS, TITLE_COLORS)):
        top = Inches(1.15) + Inches(i * 1.92)
        box = slide.shapes.add_shape(1, MARGIN, top, SLIDE_W - MARGIN * 2, Inches(1.7))
        box.fill.solid(); box.fill.fore_color.rgb = bg
        box.line.color.rgb = tc; box.line.width = Pt(1.5)

        add_textbox(slide, title,
                    left=MARGIN + Inches(0.15), top=top + Inches(0.1),
                    width=SLIDE_W - MARGIN * 2 - Inches(0.3), height=Inches(0.5),
                    font_size=20, bold=True, color=tc, align=PP_ALIGN.LEFT)
        add_textbox(slide, desc,
                    left=MARGIN + Inches(0.3), top=top + Inches(0.62),
                    width=SLIDE_W - MARGIN * 2 - Inches(0.5), height=Inches(0.9),
                    font_size=15, color=C_DARK, align=PP_ALIGN.LEFT)


def slide_08_closing(prs):
    """슬라이드 8: 향후 작업 + 감사."""
    slide = blank_slide(prs)
    add_slide_title(slide, "향후 작업")

    # 세 불릿을 하나의 텍스트박스로 통일 → 들여쓰기/폰트 완전 동일 보장
    future_text = (
        "• Phase 4.4: Model C 환경에서 RL 재실험 (Transformer 전이확률 활용)\n\n"
        "• Hit location 예측 추가 (MIT Sloan 참고 — 9-class hit location)\n\n"
        "• 한국 야구(KBO) 적용 검증"
    )
    add_textbox(slide, future_text,
                left=MARGIN, top=Inches(1.3), width=SLIDE_W - MARGIN * 2, height=Inches(2.8),
                font_size=20, color=C_DARK, align=PP_ALIGN.LEFT)

    # 감사 박스
    add_rect_bg(slide, C_DARK,
                left=Inches(2.0), top=Inches(4.5), width=Inches(9.3), height=Inches(2.3))
    add_textbox(slide, "감사합니다. 질문 주세요.",
                left=Inches(2.0), top=Inches(4.9), width=Inches(9.3), height=Inches(1.5),
                font_size=34, bold=True, color=C_WHITE, align=PP_ALIGN.CENTER)


def slide_09_backup_4cls(prs):
    """슬라이드 9 (백업): 4-class MDP 그룹."""
    slide = blank_slide(prs)
    add_slide_title(slide, "[백업] 4-class MDP 호환 모델 비교")

    img_path = FIG_DIR / "fig3_4class_mdp.png"
    img_w = SLIDE_W * 0.86
    img_left = (SLIDE_W - img_w) / 2
    add_image(slide, img_path, left=img_left, top=Inches(1.05), width=img_w)


def slide_10_backup_delta(prs):
    """슬라이드 10 (백업): 1차 발표 대비 개선."""
    slide = blank_slide(prs)
    add_slide_title(slide, "[백업] 1차 발표 대비 개선")

    rows_data = [
        ("항목",           "1차 발표",            "이번 발표"),
        ("데이터",          "2시즌",               "3시즌 (정합성 강화)"),
        ("LightGBM 4cls", "58.7%",               "60.8% (+2.1pp)"),
        ("신규 평가",       "—",                  "Macro-F1, Top-4 Precision"),
        ("새 모델",         "—",                  "MLP 135d, RNN, Transformer"),
        ("핵심 발견",       "—",                  "arsenal +26.5pp 정량 검증"),
    ]

    n_rows, n_cols = len(rows_data), 3
    tbl_w = Inches(11.0)
    tbl_h = Inches(4.5)
    tbl = slide.shapes.add_table(n_rows, n_cols,
                                 (SLIDE_W - tbl_w) / 2, Inches(1.2),
                                 tbl_w, tbl_h).table

    col_widths = [Inches(3.0), Inches(3.5), Inches(4.5)]
    for ci, w in enumerate(col_widths):
        tbl.columns[ci].width = w

    for ri, row_vals in enumerate(rows_data):
        for ci, val in enumerate(row_vals):
            cell = tbl.cell(ri, ci)
            is_hdr = (ri == 0)
            if is_hdr:
                cell_color(cell, C_BLUE)
                col = C_WHITE
            elif ci == 2:
                cell_color(cell, RGBColor(0xFD, 0xF2, 0xE9))
                col = C_DARK
            else:
                cell_color(cell, C_WHITE)
                col = C_DARK
            set_cell_text(cell, val, font_size=18, bold=is_hdr, color=col,
                          align=PP_ALIGN.CENTER if is_hdr or ci > 0 else PP_ALIGN.LEFT)


def slide_11_backup_setup(prs):
    """슬라이드 11 (백업): 실험 setup."""
    slide = blank_slide(prs)
    add_slide_title(slide, "[백업] 실험 Setup")

    items = [
        ("데이터",         "MLB Statcast 2022~2024 (3시즌, ~149만 투구)"),
        ("시즌별 규모",    "2022: 77.5만 / 2023: 77.4만 / 2024: 76.0만 행"),
        ("테스트셋",       "2024시즌 (날짜 기반 분리): 약 35만 샘플 (10-class)"),
        ("Focal Loss",    "γ=2.0 — i.i.d. 모델(77d/135d) 전용, sequence 모델 미적용"),
        ("Train/Val 분리","시즌 기반 (2022~2023 train, 2024 val/test) — 데이터 누수 없음"),
        ("모델 파라미터",  "LR ~308p / LGB ~50K leaves / MLP 27K / MLP135d 32K / RNN 590K / Transformer 9.7M"),
    ]

    for i, (label, desc) in enumerate(items):
        top = Inches(1.2 + i * 0.9)
        add_textbox(slide, label,
                    left=MARGIN, top=top, width=Inches(2.8), height=Inches(0.7),
                    font_size=17, bold=True, color=C_BLUE, align=PP_ALIGN.LEFT)
        add_textbox(slide, desc,
                    left=MARGIN + Inches(3.0), top=top, width=Inches(9.3), height=Inches(0.7),
                    font_size=17, color=C_DARK, align=PP_ALIGN.LEFT)
        # 구분선
        line_shape = slide.shapes.add_shape(1,
            MARGIN, top + Inches(0.76), SLIDE_W - MARGIN * 2, Emu(12000))
        line_shape.fill.solid(); line_shape.fill.fore_color.rgb = C_LGRAY
        line_shape.line.fill.background()


# ── 메인 ────────────────────────────────────────────────────────────────────

def main():
    prs = new_prs()

    print("슬라이드 생성 중...")
    slide_01_cover(prs);           print("  [1/11] 표지")
    slide_02_problem(prs);         print("  [2/11] 문제 정의")
    slide_03_prior(prs);           print("  [3/11] 선행 연구 한계")
    slide_04_finding(prs);         print("  [4/11] 핵심 발견")
    slide_05_top4(prs);            print("  [5/11] MIT Sloan 평가 기준")
    slide_06_rl(prs);              print("  [6/11] RL 비교 표")
    slide_07_contributions(prs);   print("  [7/11] Contribution")
    slide_08_closing(prs);         print("  [8/11] 향후 작업 + 감사")
    slide_09_backup_4cls(prs);     print("  [9/11] 백업: 4-class")
    slide_10_backup_delta(prs);    print(" [10/11] 백업: 1차 대비 개선")
    slide_11_backup_setup(prs);    print(" [11/11] 백업: 실험 Setup")

    prs.save(str(OUT_PATH))
    sz = OUT_PATH.stat().st_size
    print(f"\n[OK] 저장 완료: {OUT_PATH}")
    print(f"     슬라이드 수: {len(prs.slides)}장")
    print(f"     파일 크기:  {sz // 1024:,} KB")

    # 이미지 존재 여부 확인
    figs = ["fig1_arsenal_vs_sequence.png", "fig2_paper_positioning.png",
            "fig3_4class_mdp.png", "fig4_top4_precision_heatmap.png"]
    print("\n[이미지 삽입 확인]")
    for f in figs:
        p = FIG_DIR / f
        print(f"  {'OK' if p.exists() else 'MISSING':6s} {f}")

    print("\n[한글 폰트] '맑은 고딕' 사용 (Windows PowerPoint 호환)")


if __name__ == "__main__":
    main()
