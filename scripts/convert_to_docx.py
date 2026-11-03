#!/usr/bin/env python3
# convert_to_docx.py - Markdown 초안을 DOCX 완성본으로 변환
# 실행: python3 convert_to_docx.py
# 필요 패키지: pip install python-docx markdown2 weasyprint pillow

import os
import subprocess
import sys
from pathlib import Path


def check_dependencies():
    """필요한 패키지 확인"""
    required = ["docx", "markdown2", "PIL"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"Missing packages: {missing}")
        print("Install with: pip install python-docx markdown2 pillow weasyprint")
        return False
    return True


def render_mermaid_to_png(mmd_file, output_dir):
    """Mermaid 다이어그램을 PNG로 렌더링 (mmdc 필요)"""
    try:
        # mmdc (Mermaid CLI) 확인
        result = subprocess.run(["which", "mmdc"], capture_output=True)
        if result.returncode != 0:
            print(f"Warning: mmdc not found. Install with: npm install -g @mermaid-js/mermaid-cli")
            return False

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        for mmd_file in Path(mmd_file).parent.glob("*.mmd"):
            png_file = output_dir / (mmd_file.stem + ".png")
            print(f"Rendering {mmd_file.name} -> {png_file.name}")
            subprocess.run(
                [
                    "mmdc",
                    "-i",
                    str(mmd_file),
                    "-o",
                    str(png_file),
                    "-b",
                    "white",
                    "-w",
                    "1920",
                ],
                check=True,
            )
        return True
    except Exception as e:
        print(f"Mermaid rendering failed: {e}")
        return False


def markdown_to_docx(md_file, docx_file, images_dir):
    """Markdown을 DOCX로 변환"""
    import re

    import markdown2
    from docx import Document
    from docx.enum.style import WD_STYLE_TYPE
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt, RGBColor

    # Markdown 읽기
    with open(md_file, "r", encoding="utf-8") as f:
        md_content = f.read()

    # Mermaid 블록을 이미지 참조로 치환
    def replace_mermaid(match):
        diagram_name = match.group(1).strip()
        img_path = images_dir / f"{diagram_name}.png"
        if img_path.exists():
            return f"[[IMAGE:{img_path}]]"
        return f"[Diagram: {diagram_name}.mmd - 렌더링 필요]"

    # ```mermaid 블록 처리
    md_content = re.sub(r"```mermaid\s*\n(.*?)\n```", replace_mermaid, md_content, flags=re.DOTALL)

    # HTML로 변환
    html = markdown2.markdown(
        md_content,
        extras=[
            "tables",
            "fenced-code-blocks",
            "header-ids",
            "toc",
            "break-on-newline",
            "cuddled-lists",
            "metadata",
        ],
    )

    # DOCX 문서 생성
    doc = Document()

    # 스타일 설정
    style = doc.styles["Normal"]
    font = style.font
    font.name = "NanumGothic"  # 또는 'Malgun Gothic'
    font.size = Pt(10)
    style.paragraph_format.space_after = Pt(6)
    style.paragraph_format.line_spacing = 1.15

    # 제목 스타일
    for level in range(1, 4):
        heading_style = doc.styles[f"Heading {level}"]
        heading_style.font.name = "NanumGothic"
        heading_style.font.color.rgb = RGBColor(0x1A, 0x23, 0x7E)
        if level == 1:
            heading_style.font.size = Pt(20)
        elif level == 2:
            heading_style.font.size = Pt(16)
        elif level == 3:
            heading_style.font.size = Pt(13)

    # 코드 블록 스타일
    code_style = doc.styles.add_style("CodeBlock", WD_STYLE_TYPE.PARAGRAPH)
    code_style.font.name = "Consolas"
    code_style.font.size = Pt(9)
    code_style.paragraph_format.space_before = Pt(6)
    code_style.paragraph_format.space_after = Pt(6)

    # 간단한 HTML 파싱하여 DOCX에 추가
    import html

    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    def add_html_to_doc(doc, html_content):
        """간단한 HTML을 DOCX 요소로 변환"""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, "html.parser")

        for elem in soup.children:
            if elem.name is None:
                # 텍스트 노드
                text = str(elem).strip()
                if text:
                    p = doc.add_paragraph(text)
            elif elem.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                level = int(elem.name[1])
                p = doc.add_heading(elem.get_text(), level=level)
            elif elem.name == "p":
                p = doc.add_paragraph(elem.get_text())
            elif elem.name == "ul":
                for li in elem.find_all("li", recursive=False):
                    p = doc.add_paragraph(li.get_text(), style="List Bullet")
            elif elem.name == "ol":
                for i, li in enumerate(elem.find_all("li", recursive=False), 1):
                    p = doc.add_paragraph(f"{i}. {li.get_text()}", style="List Number")
            elif elem.name == "pre":
                code_text = elem.get_text()
                p = doc.add_paragraph(code_text, style="CodeBlock")
            elif elem.name == "table":
                # 테이블 변환
                rows = elem.find_all("tr")
                if rows:
                    cols = max(len(row.find_all(["td", "th"])) for row in rows)
                    table = doc.add_table(rows=len(rows), cols=cols, style="Table Grid")
                    for r_idx, row in enumerate(rows):
                        cells = row.find_all(["td", "th"])
                        for c_idx, cell in enumerate(cells):
                            if c_idx < cols:
                                table.cell(r_idx, c_idx).text = cell.get_text().strip()
            elif elem.name == "img" or "[[IMAGE:" in str(elem):
                # 이미지 처리
                img_match = re.search(r"\[\[IMAGE:(.+?)\]\]", str(elem))
                if img_match:
                    img_path = img_match.group(1)
                    if os.path.exists(img_path):
                        doc.add_picture(img_path, width=Inches(6.5))
                    else:
                        doc.add_paragraph(f"[이미지 없음: {img_path}]")
            elif elem.name == "hr":
                doc.add_paragraph("_" * 50)
            elif elem.name == "blockquote":
                p = doc.add_paragraph(elem.get_text(), style="Quote")
            elif elem.name == "div" and "toc" in elem.get("class", []):
                # 목차 스킵
                pass
            else:
                # 기타 태그: 텍스트만 추출
                text = elem.get_text().strip()
                if text:
                    doc.add_paragraph(text)

    try:
        add_html_to_doc(doc, html)
    except Exception as e:
        print(f"HTML parsing error: {e}")
        # 폴백: 단순 텍스트 추가
        doc.add_paragraph(md_content[:1000] + "... (변환 오류로 원문 텍스트만 포함)")

    # 저장
    doc.save(docx_file)
    print(f"DOCX saved: {docx_file}")


def main():
    project_root = Path("/Users/amaster/projectm/Q250-V3-Opti")
    md_file = project_root / "docs" / "manual-draft.md"
    docx_file = project_root / "docs" / "manual-final.docx"
    images_dir = project_root / "docs" / "images"
    diagrams_dir = project_root / "docs" / "diagrams"

    print("==========================================")
    print("Q250-V3 Opti Manual: Markdown to DOCX")
    print("==========================================")

    # 1. 의존성 확인
    if not check_dependencies():
        sys.exit(1)

    # 2. Mermaid 다이어그램 렌더링
    print("\n[1/3] Rendering Mermaid diagrams...")
    render_mermaid_to_png(diagrams_dir, images_dir)

    # 3. Markdown to DOCX 변환
    print("\n[2/3] Converting Markdown to DOCX...")
    markdown_to_docx(md_file, docx_file, images_dir)

    # 4. 완료
    print("\n[3/3] Complete!")
    print(f"Output: {docx_file}")
    print(f"Size: {docx_file.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
