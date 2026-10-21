from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image, ImageDraw, ImageFont

OUT = Path('deliverables')
QA = OUT / 'qa'
QA.mkdir(parents=True, exist_ok=True)
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)
sec.top_margin = sec.bottom_margin = Inches(.72)
sec.left_margin = sec.right_margin = Inches(.78)
for name in ['Normal', 'Title', 'Subtitle', 'Heading 1', 'Heading 2', 'Heading 3']:
    st = doc.styles[name]
    st.font.name = 'Calibri'
    st.font.color.rgb = RGBColor(0, 0, 0)
    st.paragraph_format.space_after = Pt(7)
doc.styles['Normal'].font.size = Pt(11)
doc.styles['Normal'].paragraph_format.line_spacing = 1.12
doc.styles['Title'].font.size = Pt(27)
doc.styles['Heading 1'].font.size = Pt(18)
doc.styles['Heading 2'].font.size = Pt(12)
doc.styles['Heading 2'].paragraph_format.space_before = Pt(10)
doc.core_properties.title = 'NovaCRM Customer Onboarding Automation Solution Approach'
doc.core_properties.subject = 'Project documentation for custom Python LangGraph orchestration and Rocketlane onboarding'
doc.core_properties.author = 'Harish'

footer = sec.footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
r = footer.add_run('NovaCRM onboarding automation   |   ')
r.font.size = Pt(9)
field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'), 'PAGE'); footer._p.append(field)

def p(text, style=None):
    return doc.add_paragraph(text, style)

def sub(title, text):
    doc.add_heading(title, 2)
    p(text)

def bullets(items):
    for text in items:
        p(text, 'List Bullet')

def table(headers, rows, widths, font=10):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for cell, width, text in zip(t.rows[0].cells, widths, headers):
        cell.width = Inches(width); cell.text = text
    for row in rows:
        cells = t.add_row().cells
        for cell, width, text in zip(cells, widths, row):
            cell.width = Inches(width); cell.text = str(text)
    for ri, row in enumerate(t.rows):
        pr = row._tr.get_or_add_trPr()
        avoid = OxmlElement('w:cantSplit'); pr.append(avoid)
        if ri == 0:
            repeat = OxmlElement('w:tblHeader'); pr.append(repeat)
        for ci, cell in enumerate(row.cells):
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            tcp = cell._tc.get_or_add_tcPr()
            sh = OxmlElement('w:shd'); sh.set(qn('w:fill'), '17365D' if ri == 0 else ('F1F5F9' if ri % 2 else 'FFFFFF')); tcp.append(sh)
            borders = OxmlElement('w:tcBorders')
            for edge in ['top','left','bottom','right']:
                e = OxmlElement('w:' + edge); e.set(qn('w:val'),'single'); e.set(qn('w:sz'),'4'); e.set(qn('w:color'),'D9D9D9'); borders.append(e)
            tcp.append(borders)
            margins = OxmlElement('w:tcMar')
            for edge in ['top','left','bottom','right']:
                e = OxmlElement('w:' + edge); e.set(qn('w:w'),'85'); e.set(qn('w:type'),'dxa'); margins.append(e)
            tcp.append(margins)
            for para in cell.paragraphs:
                para.paragraph_format.space_after = Pt(3)
                para.paragraph_format.line_spacing = 1.03
                if ci == 0 and len(headers) > 3:
                    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in para.runs:
                    run.font.size = Pt(font)
                    if ri == 0:
                        run.bold = True; run.font.color.rgb = RGBColor(255,255,255)
    p('').paragraph_format.space_after = Pt(0)
    return t

