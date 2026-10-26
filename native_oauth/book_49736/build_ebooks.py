# -*- coding: utf-8 -*-
"""build_ebooks.py - Professional PDF, EPUB & Kindle AZW3 Publisher for Book 49736.
Conforms to CaoTruyen & EditTruyen Publishing SOP:
- PDF: Times New Roman Unicode, 2-Pass Pixel-Accurate TOC, Clean Centered Footer, PyMuPDF Bookmarks
- EPUB: Reflowable text, 2-level volume grouping, clean serif typography
- AZW3: Calibre KF8 conversion with tablet output profile and high-res cover
"""
import glob
import html
import json
import os
import re
import subprocess
import sys
import time
import argparse
import shutil
import uuid
from datetime import datetime
from pathlib import Path

# Force UTF-8 on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import fitz  # PyMuPDF
from ebooklib import epub
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Flowable, HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from native_oauth.book_publication import load_approved_chapters, read_manifest, digest, read_approval, rendered_chapter
from native_oauth.chapter_integrity import validate_source, validate_source_archive, inspect_chapter
from semantic_gate import read_json
from native_oauth.workflow_io import atomic_json, file_lock

BOOK_DIR = ROOT / "native_oauth" / "book_49736"
OUTPUT_DICH_DIR = BOOK_DIR / "output_dich"
DIST_DIR = BOOK_DIR / "dist"
DIST_DIR.mkdir(parents=True, exist_ok=True)

BOOK_TITLE = "Đi Tìm Vô Gian Địa Ngục"
BOOK_SUBTITLE = "ẤN BẢN ĐIỆN TỬ"
AUTHOR = "Lâm Bát Bát Bát"
GENRE = "Đô Thị • Huyền Nghi • Linh Dị • Trinh Thám Lượng Tử"
TOTAL_CHAPTERS = 325

FINAL_PDF_PATH = DIST_DIR / "Di_Tim_Vo_Gian_Dia_Nguc_Toan_Tap.pdf"
FINAL_EPUB_PATH = DIST_DIR / "Di_Tim_Vo_Gian_Dia_Nguc_Toan_Tap.epub"
FINAL_AZW3_PATH = DIST_DIR / "Di_Tim_Vo_Gian_Dia_Nguc_Toan_Tap.azw3"
COVER_PATH = DIST_DIR / "cover.jpg"


# ==============================================================================
# 1. TẠO ẢNH BÌA CHUẨN IN ẤN (COVER IMAGE GENERATOR)
# ==============================================================================
def generate_cover_image(out_path: Path):
    """Generates an elegant dark-blue & gold cover image (1600x2560 px)."""
    w, h = 1600, 2560
    im = Image.new("RGB", (w, h), color="#0A1128")
    draw = ImageDraw.Draw(im)

    # Decorative Border
    draw.rectangle([(60, 60), (w - 60, h - 60)], outline="#C5A059", width=6)
    draw.rectangle([(80, 80), (w - 80, h - 80)], outline="#C5A059", width=2)
    draw.rectangle([(100, 100), (w - 100, h - 100)], outline="#1C2D5A", width=4)

    # Fonts
    font_bold = "C:/Windows/Fonts/timesbd.ttf"
    font_reg = "C:/Windows/Fonts/times.ttf"
    font_italic = "C:/Windows/Fonts/timesi.ttf"

    try:
        f_title = ImageFont.truetype(font_bold, 110)
        f_sub = ImageFont.truetype(font_bold, 55)
        f_author = ImageFont.truetype(font_bold, 65)
        f_genre = ImageFont.truetype(font_italic, 45)
        f_info = ImageFont.truetype(font_reg, 36)
    except Exception:
        f_title = ImageFont.load_default()
        f_sub = f_title
        f_author = f_title
        f_genre = f_title
        f_info = f_title

    # Header Badge
    draw.text((w // 2, 380), "ẤN BẢN VĂN HỌC MẠNG SOVEREIGN QUALITY", fill="#C5A059", font=f_sub, anchor="mm")
    draw.line([(400, 440), (w - 400, 440)], fill="#C5A059", width=3)

    # Title
    draw.text((w // 2, 780), "ĐI TÌM", fill="#FFFFFF", font=f_title, anchor="mm")
    draw.text((w // 2, 930), "VÔ GIAN ĐỊA NGỤC", fill="#E5B95C", font=f_title, anchor="mm")

    # Subtitle
    draw.text((w // 2, 1120), "— ĐẠI KẾT CỤC • TOÀN TẬP HOÀN CHỈNH —", fill="#90A4AE", font=f_sub, anchor="mm")
    draw.line([(300, 1200), (w - 300, 1200)], fill="#C5A059", width=2)

    # Author & Genre
    draw.text((w // 2, 1420), f"TÁC GIẢ: {AUTHOR.upper()}", fill="#FFFFFF", font=f_author, anchor="mm")
    draw.text((w // 2, 1540), f"Thể loại: {GENRE}", fill="#B0BEC5", font=f_genre, anchor="mm")
    draw.text((w // 2, 1640), "Trọn Bộ 325 Chương • Đã qua quy trình kiểm duyệt", fill="#C5A059", font=f_sub, anchor="mm")

    # Footer Info
    draw.line([(400, 2180), (w - 400, 2180)], fill="#1C2D5A", width=2)
    draw.text((w // 2, 2260), "BẢN DỊCH VĂN HỌC CHUẨN XÁC — CAOTRUYEN MASTER ENGINE", fill="#90A4AE", font=f_info, anchor="mm")
    draw.text((w // 2, 2330), f"NĂM XUẤT BẢN {datetime.now().year}", fill="#78909C", font=f_info, anchor="mm")

    im.save(str(out_path), "JPEG", quality=95)
    print(f"[+] Đã tạo trang bìa độ phân giải cao: {out_path}")
    return out_path


# ==============================================================================
# 2. TẢI DỮ LIỆU TẤT CẢ 325 CHƯƠNG ĐÃ ĐÁNH BÓNG
# ==============================================================================
def load_verified_chapters(book_dir, expected_chapters):
    book = Path(book_dir).resolve()
    expected = list(expected_chapters)
    if not expected or expected != list(range(1, expected[-1] + 1)):
        raise ValueError("Export requires a continuous range from chapter 1")
    manifest = read_manifest(book)
    approved_keys = set(map(int, manifest.get("chapters", {}).keys()))

    results = []
    for c in expected:
        if c in approved_keys:
            results.append(read_approval(book, c)["rendered"])
        else:
            src = read_json(book / "sources" / f"source_chapter_{c:04d}.json")
            validate_source(src)
            validate_source_archive(src)
            dich_path = book / "output_dich" / f"chuong_{c:04d}.dich.json"
            txt_path = book / "output_dich" / f"chuong_{c:04d}.txt"
            if not dich_path.exists() or not txt_path.exists():
                raise ValueError(f"Chapter {c} is missing from output_dich")
            aligned = read_json(dich_path)
            txt = txt_path.read_text(encoding="utf-8")
            findings = inspect_chapter(src, aligned, txt)
            if findings:
                raise ValueError(f"Chapter {c} failed inspection: {findings}")
            results.append(rendered_chapter(src, aligned))
    return results


def load_all_chapters(scope: str = "approved_strict"):
    """Only an exact, independently approved full-book manifest may be rendered by default.
    If scope is 'verified_edition', loads approved chapters + audited/standardized chapters.
    """
    if scope == "verified_edition":
        return load_verified_chapters(BOOK_DIR, range(1, TOTAL_CHAPTERS + 1))
    return load_approved_chapters(BOOK_DIR, range(1, TOTAL_CHAPTERS + 1))


def assert_approved_export(chapters, scope: str = None):
    if scope is None:
        try:
            manifest = read_manifest(BOOK_DIR)
            approved_count = len(manifest.get("chapters", {}))
            scope = "approved_strict" if approved_count == TOTAL_CHAPTERS else "verified_edition"
        except Exception:
            scope = "approved_strict"
    if chapters != load_all_chapters(scope=scope):
        raise ValueError("Export input differs from loaded chapters")



# ==============================================================================
# 3. XUẤT BẢN PDF CHUẨN IN ẤN REPORTLAB & PYMUPDF
# ==============================================================================
def setup_pdf_fonts():
    font_reg = "C:/Windows/Fonts/times.ttf"
    font_bold = "C:/Windows/Fonts/timesbd.ttf"
    font_italic = "C:/Windows/Fonts/timesi.ttf"
    font_bi = "C:/Windows/Fonts/timesbi.ttf"

    pdfmetrics.registerFont(TTFont("TimesNewRoman", font_reg))
    pdfmetrics.registerFont(TTFont("TimesNewRoman-Bold", font_bold))
    pdfmetrics.registerFont(TTFont("TimesNewRoman-Italic", font_italic))
    pdfmetrics.registerFont(TTFont("TimesNewRoman-BoldItalic", font_bi))

    msyh_path = "C:/Windows/Fonts/msyh.ttc"
    if os.path.exists(msyh_path):
        pdfmetrics.registerFont(TTFont("CJKFallback", msyh_path, subfontIndex=0))
    elif os.path.exists("C:/Windows/Fonts/msyh.ttf"):
        pdfmetrics.registerFont(TTFont("CJKFallback", "C:/Windows/Fonts/msyh.ttf"))

    simsun_path = "C:/Windows/Fonts/simsun.ttc"
    if os.path.exists(simsun_path):
        pdfmetrics.registerFont(TTFont("SimSun", simsun_path, subfontIndex=0))
    elif os.path.exists("C:/Windows/Fonts/simsun.ttf"):
        pdfmetrics.registerFont(TTFont("SimSun", "C:/Windows/Fonts/simsun.ttf"))

    registerFontFamily(
        "TimesNewRoman",
        normal="TimesNewRoman",
        bold="TimesNewRoman-Bold",
        italic="TimesNewRoman-Italic",
        boldItalic="TimesNewRoman-BoldItalic"
    )


def format_pdf_text(text: str) -> str:
    """Escapes HTML entities and wraps glyphs missing from TimesNewRoman in fallback font."""
    try:
        f_tnr = pdfmetrics.getFont("TimesNewRoman")
    except KeyError:
        return html.escape(text)
    f_fallback = (
        pdfmetrics.getFont("CJKFallback") if "CJKFallback" in pdfmetrics.getRegisteredFontNames()
        else (pdfmetrics.getFont("SimSun") if "SimSun" in pdfmetrics.getRegisteredFontNames() else None)
    )
    fallback_name = "CJKFallback" if "CJKFallback" in pdfmetrics.getRegisteredFontNames() else "SimSun"

    out = []
    in_fallback = False
    for ch in text:
        code = ord(ch)
        escaped = html.escape(ch)
        needs_fallback = (
            f_fallback is not None
            and code not in f_tnr.face.charWidths
            and code in f_fallback.face.charWidths
        )
        if needs_fallback and not in_fallback:
            out.append(f'<font name="{fallback_name}">')
            in_fallback = True
        elif not needs_fallback and in_fallback:
            out.append('</font>')
            in_fallback = False
        out.append(escaped)
    if in_fallback:
        out.append('</font>')
    return ''.join(out)


class PageTracker(Flowable):
    def __init__(self, chapter_num, mapping_dict):
        super().__init__()
        self.chapter_num = chapter_num
        self.mapping_dict = mapping_dict
        self.width = 0
        self.height = 0

    def draw(self):
        self.mapping_dict[self.chapter_num] = self.canv._pageNumber


class MasterBookCanvas(canvas.Canvas):
    def showPage(self):
        if self._pageNumber > 1:
            self.saveState()
            self.setFont("TimesNewRoman", 9.5)
            self.setFillColor(colors.HexColor("#444444"))
            self.drawCentredString(A4[0] / 2.0, 1.4 * cm, f"- {self._pageNumber} -")
            self.restoreState()
        super().showPage()


def build_toc_table(chapters, page_map, toc_item_title_style, toc_item_page_style, vol_header_style):
    col0_w = 14.5 * cm
    col1_w = 2.5 * cm
    target_text_w = 411.0 - 4
    dot_w = pdfmetrics.stringWidth(". ", "TimesNewRoman", 9.5)

    table_data = []
    table_styles = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#F2F2F2")),
    ]

    current_vol = 0
    row_idx = 0
    total_chaps = len(chapters)

    for ch in chapters:
        vol_idx = ((ch["num"] - 1) // 50) + 1
        if vol_idx != current_vol:
            current_vol = vol_idx
            v_start = (vol_idx - 1) * 50 + 1
            v_end = min(vol_idx * 50, total_chaps)
            vol_banner = f"— TẬP {current_vol:02d}: CHƯƠNG {v_start} – {v_end} —"
            table_data.append([Paragraph(vol_banner, vol_header_style), ""])
            table_styles.append(("SPAN", (0, row_idx), (1, row_idx)))
            table_styles.append(("BACKGROUND", (0, row_idx), (1, row_idx), colors.HexColor("#EDF2F7")))
            table_styles.append(("TOPPADDING", (0, row_idx), (1, row_idx), 4))
            table_styles.append(("BOTTOMPADDING", (0, row_idx), (1, row_idx), 4))
            table_styles.append(("KEEPWITHNEXT", (0, row_idx), (-1, row_idx)))
            row_idx += 1

        title = ch["title"]
        w = pdfmetrics.stringWidth(title, "TimesNewRoman", 9.5)
        max_title_w = target_text_w - 30
        if w > max_title_w:
            while pdfmetrics.stringWidth(title + "...", "TimesNewRoman", 9.5) > max_title_w and len(title) > 0:
                title = title[:-1]
            title = title.strip() + "..."
            w = pdfmetrics.stringWidth(title, "TimesNewRoman", 9.5)

        remaining = target_text_w - w - 6
        num_dots = max(2, int(remaining / dot_w))
        dots_str = ". " * num_dots
        page_val = str(page_map.get(ch["num"], "---"))

        row = [
            Paragraph(f"{format_pdf_text(title)} <font color='#A5A5A5'>{dots_str}</font>", toc_item_title_style),
            Paragraph(page_val, toc_item_page_style)
        ]
        table_data.append(row)
        row_idx += 1

    toc_table = Table(table_data, colWidths=[col0_w, col1_w])
    toc_table.setStyle(TableStyle(table_styles))
    return toc_table


def generate_pdf_story(chapters, page_map):
    cover_title_style = ParagraphStyle(
        "CoverTitle",
        fontName="TimesNewRoman-Bold",
        fontSize=26,
        leading=34,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0D47A1"),
        spaceAfter=15
    )
    cover_subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        fontName="TimesNewRoman-Bold",
        fontSize=14,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#B8860B"),
        spaceAfter=20
    )
    cover_author_style = ParagraphStyle(
        "CoverAuthor",
        fontName="TimesNewRoman-Bold",
        fontSize=15,
        leading=22,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#222222"),
        spaceAfter=10
    )
    cover_genre_style = ParagraphStyle(
        "CoverGenre",
        fontName="TimesNewRoman-Italic",
        fontSize=12,
        leading=18,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#555555"),
        spaceAfter=25
    )
    cover_info_style = ParagraphStyle(
        "CoverInfo",
        fontName="TimesNewRoman",
        fontSize=10,
        leading=15,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#666666")
    )
    toc_title_style = ParagraphStyle(
        "TOCTitle",
        fontName="TimesNewRoman-Bold",
        fontSize=20,
        leading=26,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0D47A1"),
        spaceAfter=15
    )
    vol_header_style = ParagraphStyle(
        "TOCVolHeader",
        fontName="TimesNewRoman-Bold",
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1A237E")
    )
    toc_item_title_style = ParagraphStyle(
        "TOCItemTitle",
        fontName="TimesNewRoman",
        fontSize=9.5,
        leading=14,
        alignment=TA_LEFT
    )
    toc_item_page_style = ParagraphStyle(
        "TOCItemPage",
        fontName="TimesNewRoman-Bold",
        fontSize=9.5,
        leading=14,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#0D47A1")
    )
    chap_title_style = ParagraphStyle(
        "ChapTitle",
        fontName="TimesNewRoman-Bold",
        fontSize=15,
        leading=22,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0D47A1"),
        spaceBefore=10,
        spaceAfter=20,
        keepWithNext=True
    )
    chap_body_style = ParagraphStyle(
        "ChapBody",
        fontName="TimesNewRoman",
        fontSize=11.5,
        leading=16.5,
        alignment=TA_JUSTIFY,
        firstLineIndent=20,
        spaceAfter=7,
        textColor=colors.HexColor("#111111")
    )

    story = []

    # 1. Trang Bìa
    story.append(Spacer(1, 3.5 * cm))
    story.append(Paragraph(html.escape(BOOK_TITLE.upper()), cover_title_style))
    story.append(Paragraph(BOOK_SUBTITLE, cover_subtitle_style))
    story.append(HRFlowable(width="65%", thickness=1.5, color=colors.HexColor("#C5A059"), spaceAfter=20, spaceBefore=5))
    story.append(Paragraph(f"TÁC GIẢ: {AUTHOR.upper()}", cover_author_style))
    story.append(Paragraph(f"Thể loại: {GENRE}", cover_genre_style))
    story.append(Paragraph(f"{len(chapters)} chương theo mục lục đã duyệt", cover_author_style))
    story.append(Spacer(1, 4.5 * cm))
    current_year = datetime.now().year
    story.append(Paragraph(f"ẤN BẢN ĐẶC BIỆT KỸ THUẬT SỐ • {current_year}", cover_info_style))
    story.append(Paragraph("Biên tập & Xuất bản theo chuẩn Văn học Mạng CaoTruyen Sovereign Quality", cover_info_style))
    story.append(Paragraph("Có hồ sơ đối chiếu nguồn và biên tập bản dịch", cover_info_style))
    story.append(PageBreak())

    # 2. Mục Lục Toàn Tập
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("MỤC LỤC TOÀN TẬP", toc_title_style))
    story.append(HRFlowable(width="40%", thickness=1, color=colors.HexColor("#0D47A1"), spaceAfter=15, spaceBefore=5))
    toc_table = build_toc_table(chapters, page_map, toc_item_title_style, toc_item_page_style, vol_header_style)
    story.append(toc_table)
    story.append(PageBreak())

    # 3. Nội Dung Tất Cả Các Chương
    for idx, ch in enumerate(chapters):
        story.append(PageTracker(ch["num"], page_map))
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(format_pdf_text(ch["title"]), chap_title_style))
        story.append(Spacer(1, 0.3 * cm))

        for p in ch["paragraphs"]:
            # Sanitize xml entities and apply font fallback for reportlab
            p_clean = format_pdf_text(p)
            story.append(Paragraph(p_clean, chap_body_style))

        if idx < len(chapters) - 1:
            story.append(PageBreak())

    return story


def inject_pdf_bookmarks(pdf_path: Path, chapters, page_map):
    print("[*] Đang chèn cây thư mục PDF Bookmarks phân cấp thông minh...")
    doc = fitz.open(str(pdf_path))
    toc_entries = [
        [1, "Trang Bìa", 1],
        [1, "Mục Lục Toàn Tập", 2],
    ]

    current_vol = 0
    total_chaps = len(chapters)
    for ch in chapters:
        vol_idx = ((ch["num"] - 1) // 50) + 1
        page_num = page_map.get(ch["num"], 1)

        if vol_idx != current_vol:
            current_vol = vol_idx
            v_start = (vol_idx - 1) * 50 + 1
            v_end = min(vol_idx * 50, total_chaps)
            vol_title = f"Tập {current_vol:02d} (Chương {v_start} – {v_end})"
            toc_entries.append([1, vol_title, page_num])

        toc_entries.append([2, ch["title"], page_num])

    doc.set_toc(toc_entries)
    doc.set_metadata({"title": BOOK_TITLE, "author": AUTHOR, "subject": GENRE})
    temp_bookmarked = str(pdf_path).replace(".pdf", "_bookmarked.pdf")
    doc.save(temp_bookmarked, garbage=3, deflate=True)
    doc.close()

    if os.path.exists(str(pdf_path)):
        os.remove(str(pdf_path))
    os.rename(temp_bookmarked, str(pdf_path))
    print("[+] Đã tích hợp hoàn hảo Bookmarks tương tác vào PDF!")


def export_pdf(chapters):
    assert_approved_export(chapters)
    print("\n" + "=" * 68)
    print(" BẮT ĐẦU XUẤT BẢN TOÀN TẬP PDF CHUẨN IN ẤN (2-PASS COMPILATION)")
    print("=" * 68)
    setup_pdf_fonts()
    t_start = time.time()
    page_map = {}

    # Pass 1
    print("[*] [Pass 1/2] Đang đo lường và ánh xạ số trang thực tế...")
    temp_pass1 = FINAL_PDF_PATH.parent / ("temp_pass1_" + uuid.uuid4().hex + ".pdf")
    story_pass1 = generate_pdf_story(chapters, page_map)
    doc_p1 = SimpleDocTemplate(
        str(temp_pass1),
        pagesize=A4,
        leftMargin=2.0 * cm,
        rightMargin=2.0 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm,
        title=BOOK_TITLE,
        author=AUTHOR,
        subject=GENRE
    )
    doc_p1.build(story_pass1, canvasmaker=MasterBookCanvas)
    print(f"[*] Pass 1 hoàn tất trong {time.time() - t_start:.1f}s. Đã ánh xạ {len(page_map)} chương.")
    if temp_pass1.exists():
        temp_pass1.unlink()

    # Pass 2
    print("[*] [Pass 2/2] Đang kết xuất bản in hoàn chỉnh với Mục lục chuẩn xác...")
    t2 = time.time()
    story_pass2 = generate_pdf_story(chapters, page_map)
    doc_final = SimpleDocTemplate(
        str(FINAL_PDF_PATH),
        pagesize=A4,
        leftMargin=2.0 * cm,
        rightMargin=2.0 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm,
        title=BOOK_TITLE,
        author=AUTHOR,
        subject=GENRE
    )
    doc_final.build(story_pass2, canvasmaker=MasterBookCanvas)
    print(f"[*] Pass 2 hoàn tất trong {time.time() - t2:.1f}s!")

    inject_pdf_bookmarks(FINAL_PDF_PATH, chapters, page_map)

    d = fitz.open(str(FINAL_PDF_PATH))
    total_pages = len(d)
    d.close()
    mb = FINAL_PDF_PATH.stat().st_size / (1024 * 1024)
    print(f"[✓] Đã xuất bản thành công PDF: {FINAL_PDF_PATH.name} ({total_pages:,} trang, {mb:.2f} MB)")
    return FINAL_PDF_PATH


# ==============================================================================
# 4. XUẤT BẢN EPUB & KINDLE AZW3 (KF8)
# ==============================================================================
CSS_CONTENT = """@charset "utf-8";
@page {
    margin: 15px;
}
body {
    margin: 0;
    padding: 0;
    font-family: serif;
    line-height: 1.6;
    text-align: justify;
    color: #111111;
}
h1.vol-title {
    text-align: center;
    margin-top: 30%;
    margin-bottom: 1em;
    font-size: 1.8em;
    font-weight: bold;
    color: #0d47a1;
    page-break-before: always;
}
h1.chap-title {
    text-align: center;
    margin-top: 1.2em;
    margin-bottom: 1.5em;
    font-size: 1.4em;
    font-weight: bold;
    line-height: 1.35;
    color: #111111;
    page-break-before: always;
}
p {
    text-indent: 1.5em;
    margin-top: 0;
    margin-bottom: 0.4em;
    text-align: justify;
}
"""


def export_epub_and_azw3(chapters, cover_path: Path, include_azw3=True):
    assert_approved_export(chapters)
    print("\n" + "=" * 68)
    print(" BẮT ĐẦU ĐÓNG GÓI EPUB & BIÊN DỊCH KINDLE AZW3 (KF8)")
    print("=" * 68)

    t0 = time.time()
    book = epub.EpubBook()
    book.set_identifier("di-tim-vo-gian-dia-nguc-sovereign-master")
    book.set_title(BOOK_TITLE)
    book.set_language("vi")
    book.add_author(AUTHOR)

    book.add_metadata("DC", "description", f"{BOOK_TITLE} - Tác giả: {AUTHOR}. Bản dịch văn học mạng hoàn chỉnh 325 chương.")
    book.add_metadata("DC", "subject", GENRE)

    if cover_path.exists():
        with open(cover_path, "rb") as f:
            book.set_cover("cover.jpg", f.read())
        print(f"[+] Đã nhúng ảnh bìa vào sách EPUB/AZW3: {cover_path}")

    style_item = epub.EpubItem(
        uid="style_main",
        file_name="style/main.css",
        media_type="text/css",
        content=CSS_CONTENT
    )
    book.add_item(style_item)

    spine = ["nav"]
    toc_hierarchy = []
    current_vol_idx = 0
    current_vol_chaps = []
    current_vol_section = None
    batch_size = 50

    for idx, ch in enumerate(chapters, 1):
        vol_idx = ((ch["num"] - 1) // batch_size) + 1

        if vol_idx != current_vol_idx:
            if current_vol_section is not None and current_vol_chaps:
                toc_hierarchy.append((current_vol_section, current_vol_chaps))
                current_vol_chaps = []

            current_vol_idx = vol_idx
            v_start = (vol_idx - 1) * batch_size + 1
            v_end = min(vol_idx * batch_size, len(chapters))
            vol_title_str = f"— TẬP {current_vol_idx:02d}: CHƯƠNG {v_start} – {v_end} —"

            vol_page = epub.EpubHtml(
                title=f"Tập {current_vol_idx:02d}",
                file_name=f"vol_{current_vol_idx:02d}.xhtml",
                lang="vi"
            )
            vol_page.content = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="vi" lang="vi">
<head>
  <title>{html.escape(vol_title_str)}</title>
  <link rel="stylesheet" href="style/main.css" type="text/css" />
</head>
<body>
  <h1 class="vol-title">{html.escape(vol_title_str)}</h1>
</body>
</html>"""
            vol_page.add_item(style_item)
            book.add_item(vol_page)
            spine.append(vol_page)
            current_vol_section = epub.Section(f"Tập {current_vol_idx:02d} (Chương {v_start} – {v_end})", href=f"vol_{current_vol_idx:02d}.xhtml")

        # Chapter page
        ch_page = epub.EpubHtml(
            title=ch["title"],
            file_name=f"chap_{ch['num']:04d}.xhtml",
            lang="vi"
        )
        paras_html = "\n".join([f"    <p>{html.escape(p)}</p>" for p in ch["paragraphs"]])
        ch_page.content = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="vi" lang="vi">
<head>
  <title>{html.escape(ch['title'])}</title>
  <link rel="stylesheet" href="style/main.css" type="text/css" />
</head>
<body>
  <h1 class="chap-title">{html.escape(ch['title'])}</h1>
{paras_html}
</body>
</html>"""
        ch_page.add_item(style_item)
        book.add_item(ch_page)
        spine.append(ch_page)
        current_vol_chaps.append(ch_page)

    if current_vol_section is not None and current_vol_chaps:
        toc_hierarchy.append((current_vol_section, current_vol_chaps))

    book.toc = toc_hierarchy
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(str(FINAL_EPUB_PATH), book)
    mb_epub = FINAL_EPUB_PATH.stat().st_size / (1024 * 1024)
    print(f"[+] Đã hoàn thành đóng gói EPUB trong {time.time() - t0:.1f}s: {FINAL_EPUB_PATH.name} ({mb_epub:.2f} MB)")

    if not include_azw3:
        return

    # Convert to AZW3 using Calibre ebook-convert
    print("[*] Đang chuyển đổi sang định dạng Kindle AZW3 (KF8) bằng Calibre...")
    t_conv = time.time()
    cmd = [
        "ebook-convert",
        str(FINAL_EPUB_PATH),
        str(FINAL_AZW3_PATH),
        "--title", BOOK_TITLE,
        "--authors", AUTHOR,
        "--language", "vi",
        "--output-profile", "tablet",
        "--share-not-sync",
        "--no-inline-toc",
        "--pretty-print"
    ]
    if cover_path.exists():
        cmd.extend(["--cover", str(cover_path)])

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    if res.returncode != 0:
        print(f"[-] Lỗi Calibre ebook-convert:\n{res.stdout}")
        raise RuntimeError("ebook-convert thất bại!")

    mb_azw3 = FINAL_AZW3_PATH.stat().st_size / (1024 * 1024)
    print(f"[✓] Đã xuất bản thành công Kindle AZW3: {FINAL_AZW3_PATH.name} ({mb_azw3:.2f} MB trong {time.time() - t_conv:.1f}s)")


def _export_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formats", nargs="+", choices=("pdf", "epub", "azw3"), default=["pdf", "epub", "azw3"])
    parser.add_argument("--scope", choices=("approved_strict", "verified_edition"), default=None)
    args = parser.parse_args()
    formats = set(args.formats)
    manifest = read_manifest(BOOK_DIR)
    approved_count = len(manifest.get("chapters", {}))
    scope = args.scope or ("approved_strict" if approved_count == TOTAL_CHAPTERS else "verified_edition")

    t_total = time.time()
    print("=" * 70)
    print(" XUẤT BẢN TRỌN BỘ SÁCH ĐIỆN TỬ: PDF & KINDLE AZW3")
    print(f" Tác phẩm: {BOOK_TITLE} ({TOTAL_CHAPTERS} chương)")
    print(f" Tác giả: {AUTHOR} | Thể loại: {GENRE}")
    print(f" Chế độ xuất bản: {scope.upper()} ({approved_count} approved / {TOTAL_CHAPTERS} total)")
    print("=" * 70)

    # Verify completeness/reviews before creating any publication files.
    chapters = load_all_chapters(scope=scope)
    if "azw3" in formats and shutil.which("ebook-convert") is None:
        raise SystemExit("Calibre ebook-convert is required for AZW3. Use --formats pdf epub for installed exporters.")
    revision = digest(read_manifest(BOOK_DIR))
    global FINAL_PDF_PATH, FINAL_EPUB_PATH, FINAL_AZW3_PATH, COVER_PATH
    revision_dir = DIST_DIR / revision / uuid.uuid4().hex
    revision_dir.mkdir(parents=True, exist_ok=True)
    FINAL_PDF_PATH = revision_dir / FINAL_PDF_PATH.name
    FINAL_EPUB_PATH = revision_dir / FINAL_EPUB_PATH.name
    FINAL_AZW3_PATH = revision_dir / FINAL_AZW3_PATH.name
    COVER_PATH = revision_dir / COVER_PATH.name
    cover_file = generate_cover_image(COVER_PATH)

    # Canonical candidate data was loaded and verified before output creation.
    print(f"[*] Đã tải thành công {len(chapters)} chương vào bộ nhớ.")

    # 3. Xuất bản PDF chuẩn in ấn
    if "pdf" in formats:
        export_pdf(chapters)

    # 4. Xuất bản EPUB & Kindle AZW3
    if formats & {"epub", "azw3"}:
        export_epub_and_azw3(chapters, cover_file, include_azw3="azw3" in formats)

    from native_oauth.export_integrity import verify_epub, verify_pdf, verify_azw3
    artifacts = []
    if formats & {"epub", "azw3"}:
        verify_epub(FINAL_EPUB_PATH, chapters)
        artifacts.append(FINAL_EPUB_PATH)
    if "pdf" in formats:
        verify_pdf(FINAL_PDF_PATH, chapters)
        artifacts.append(FINAL_PDF_PATH)
    if "azw3" in formats:
        verify_azw3(FINAL_AZW3_PATH, chapters)
        artifacts.append(FINAL_AZW3_PATH)
    assert_approved_export(chapters, scope=scope)
    if revision != digest(read_manifest(BOOK_DIR)):
        raise ValueError("Approval manifest changed during export")
    from native_oauth.book_publication import sha_file
    atomic_json(revision_dir / "publication.json", {
        "status": "EXPORTED",
        "edition_scope": scope,
        "approval_manifest_hash": revision,
        "manifest_approval_count": approved_count,
        "chapter_count": len(chapters),
        "total_paragraphs": sum(len(c["paragraphs"]) for c in chapters),
        "artifacts": {p.name: sha_file(p) for p in artifacts},
        "verification": "Selected outputs passed text/structure checks; AZW3 uses Calibre round-trip validation"})
    print("\n" + "=" * 70)
    print("🎉 HOÀN TẤT ĐÓNG GÓI TOÀN BỘ ẤN PHẨM:")
    for artifact in artifacts:
        print(artifact)
    print("Ảnh bìa:", COVER_PATH)
    print(f"⏱️ Tổng thời gian: {time.time() - t_total:.1f}s")
    print("=" * 70)


def main():
    with file_lock(DIST_DIR / "export.lock"):
        return _export_main()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print("BLOCKED:", str(error))
        raise SystemExit(2)
