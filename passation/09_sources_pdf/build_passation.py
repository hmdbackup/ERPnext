from pathlib import Path
import re, html, posixpath
from urllib.parse import quote
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

root=Path(__file__).resolve().parents[2]
source_path=root/'passation/01_dossier/passation_aziz_2026-09-16.md'
source=source_path.read_text()
for n,f in [('Body','Arial.ttf'),('Body-Bold','Arial Bold.ttf'),('Body-Italic','Arial Italic.ttf')]:
    pdfmetrics.registerFont(TTFont(n,'/System/Library/Fonts/Supplemental/'+f))
pdfmetrics.registerFontFamily('Body', normal='Body',bold='Body-Bold',italic='Body-Italic',boldItalic='Body-Bold')
ink=colors.HexColor('#1C302C'); green=colors.HexColor('#1C6251'); light=colors.HexColor('#EFF5F2')
styles={
 'body':ParagraphStyle('body',fontName='Body',fontSize=9.6,leading=13.2,textColor=ink,spaceAfter=7),
 'title':ParagraphStyle('title',fontName='Body-Bold',fontSize=22,leading=26,textColor=green,spaceAfter=14),
 'h2':ParagraphStyle('h2',fontName='Body-Bold',fontSize=14,leading=18,textColor=green,spaceBefore=13,spaceAfter=9,keepWithNext=True),
 'h3':ParagraphStyle('h3',fontName='Body-Bold',fontSize=11,leading=14,textColor=ink,spaceBefore=9,spaceAfter=6,keepWithNext=True),
 'cell':ParagraphStyle('cell',fontName='Body',fontSize=8.6,leading=11.4,textColor=ink,spaceAfter=0,splitLongWords=True),
 'th':ParagraphStyle('th',fontName='Body-Bold',fontSize=8.6,leading=11.4,textColor=colors.white),
 'quote':ParagraphStyle('quote',fontName='Body-Italic',fontSize=9.6,leading=13.5,textColor=green,leftIndent=12,borderPadding=9,backColor=light,spaceBefore=5,spaceAfter=12),
 'code':ParagraphStyle('code',fontName='Body',fontSize=8.6,leading=12,textColor=ink,backColor=light,borderPadding=8,spaceBefore=6,spaceAfter=12),
}
base='https://github.com/hmdbackup/ERPnext/blob/finance/socle-comptable/'
def inline(s):
    s=s.replace('—','-').replace('–','-').replace('\u2011','-')
    s=html.escape(s)
    def link(m):
        label,target=m.groups()
        return '<a color="#1C6251" href="'+base+quote(posixpath.normpath('passation/01_dossier/'+html.unescape(target)),safe='/')+'">'+label+'</a>'
    s=re.sub(r'\[([^]]+)\]\(([^)]+)\)',link,s)
    s=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'`([^`]+)`',r'<font color="#1C6251">\1</font>',s)
    return s
story=[]
def para(s,k='body'):
    p=Paragraph(inline(s),styles[k])
    if k=='body' and s.rstrip().endswith(':'):
        p.keepWithNext=True
    return p
lines=source.splitlines(); i=0
while i<len(lines):
    line=lines[i]
    if not line.strip(): i+=1; continue
    if line.startswith('# '): story.append(para(line[2:],'title')); i+=1; continue
    if line.startswith('## '):
        # Keep the inventory, action register and reception form on their own pages.
        if line.startswith(('## 3.','## 4.','## 5.','## 6.')): story.append(PageBreak())
        story.append(para(line[3:],'h2')); i+=1; continue
    if line.startswith('### '): story.append(para(line[4:],'h3')); i+=1; continue
    if line.startswith('|'):
        rows=[]
        while i<len(lines) and lines[i].startswith('|'):
            cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
            if not all(re.fullmatch('[-: ]+',x) for x in cells): rows.append(cells)
            i+=1
        count=len(rows[0]); widths=([101,406] if count==2 else [160,128,219])
        if rows[0][0]=='Durée': widths=[45,238,224]
        if rows[0][0]=='Support': widths=[197,114,196]
        tbl=Table([[para(c,'th' if r==0 else 'cell') for c in row] for r,row in enumerate(rows)],colWidths=widths,repeatRows=1,hAlign='LEFT')
        tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),green),('ROWBACKGROUNDS',(0,1),(-1,-1),[light,colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),0.6,green)]))
        story.extend([tbl,Spacer(1,9)]); continue
    if line.startswith('```'):
        i+=1; block=[]
        while i<len(lines) and not lines[i].startswith('```'): block.append(lines[i]); i+=1
        story.append(para(' '.join(block),'code')); i+=1; continue
    if line.startswith('>'):
        block=[]
        while i<len(lines) and lines[i].startswith('>'): block.append(lines[i].lstrip('> ').strip()); i+=1
        story.append(para(' '.join(block),'quote')); continue
    if line.startswith('- '):
        block=[line[2:]];i+=1
        while i<len(lines) and lines[i].startswith('  '):block.append(lines[i].strip());i+=1
        s=' '.join(block)
        s=s.replace('[ ]','□')
        if not s.startswith('□'):s='• '+s
        story.append(para(s));continue
    block=[line];i+=1
    while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','>','- ','```')):block.append(lines[i]);i+=1
    story.append(para(' '.join(block)))

out=root/'passation/01_dossier/passation_aziz_2026-09-16.pdf'
def footer(c,d):
    c.setStrokeColor(colors.HexColor('#CEDCD5')); c.line(44,39,551,39)
    c.setFont('Body',8);c.setFillColor(colors.HexColor('#62786F'))
    c.drawString(44,26,'HMD AGRO  /  Passation Mohamed Slim > Aziz  /  16 septembre 2026')
    c.drawRightString(551,26,str(d.page))
doc=SimpleDocTemplate(str(out),pagesize=A4,rightMargin=44,leftMargin=44,topMargin=38,bottomMargin=53,title='Passation avec Aziz - Finance HMD AGRO',author='Mohamed Slim')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(out)
