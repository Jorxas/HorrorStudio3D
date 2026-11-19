"""Dossier de publication (PDF) d'une histoire : titres, descriptions, hashtags, tags (YouTube long, Shorts, TikTok) et la
fiche technique MESURÉE. Script AUTONOME (seulement reportlab + la bibliothèque standard) : le kit le lance avec le
Python qui a reportlab quand celui du studio ne l'a pas.

    python pdf_publication.py <donnees.json> <sortie.pdf>

Rien n'est publié : le PDF ne contient que des textes prêts à coller."""
import json
import os
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

INK, MUTED, RED, RULE, PANEL = colors.HexColor('#1b1b1f'), colors.HexColor('#5d5d66'), colors.HexColor('#9e1b1b'), colors.HexColor('#d9d6cf'), colors.HexColor('#f4f2ed')


def fonts():
    reg = r'C:\Windows\Fonts\segoeui.ttf'; bold = r'C:\Windows\Fonts\segoeuib.ttf'
    if os.path.exists(reg) and os.path.exists(bold):
        pdfmetrics.registerFont(TTFont('K', reg)); pdfmetrics.registerFont(TTFont('KB', bold)); return 'K', 'KB'
    for r, b in (('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),):
        if os.path.exists(r) and os.path.exists(b):
            pdfmetrics.registerFont(TTFont('K', r)); pdfmetrics.registerFont(TTFont('KB', b)); return 'K', 'KB'
    return 'Helvetica', 'Helvetica-Bold'


def esc(s): return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def main(data_path, out):
    D = json.load(open(data_path, encoding='utf-8'))
    R, B = fonts()
    ST = {'title': ParagraphStyle('t', fontName=B, fontSize=28, leading=32, textColor=INK),
          'sub': ParagraphStyle('s', fontName=R, fontSize=10.5, leading=14, textColor=MUTED),
          'h1': ParagraphStyle('h1', fontName=B, fontSize=15, leading=19, textColor=RED, spaceBefore=10, spaceAfter=4),
          'h2': ParagraphStyle('h2', fontName=B, fontSize=10.5, leading=14, textColor=INK, spaceBefore=7, spaceAfter=2),
          'p': ParagraphStyle('p', fontName=R, fontSize=9.6, leading=13.4, textColor=INK),
          'box': ParagraphStyle('m', fontName=R, fontSize=9.4, leading=13.2, textColor=INK, backColor=PANEL, borderPadding=(5, 6, 5, 6), spaceBefore=8, spaceAfter=9),
          'small': ParagraphStyle('sm', fontName=R, fontSize=8.2, leading=11, textColor=MUTED)}
    box = lambda t: Paragraph(esc(t).replace('\n', '<br/>'), ST['box'])
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"{D['titre']} — dossier de publication", author='Studio')
    s = [Paragraph(esc(D['titre']), ST['title']), Spacer(1, 3), Paragraph(esc(D['sous_titre']), ST['sub']), Spacer(1, 8)]
    imgs = [i for i in D.get('images', []) if i and os.path.exists(i['path'])]
    if imgs:
        cells, widths = [], []
        for i in imgs[:2]:
            h = 66 * mm; w = h * i['w'] / i['h']; cells.append(Image(i['path'], width=w, height=h)); widths.append(w + 4 * mm)
        s.append(Table([cells], colWidths=widths, style=[('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    s += [Spacer(1, 6), Paragraph("Rien n'est publié : les textes ci-dessous sont prêts à coller. Le titre est le même partout ; seule l'étiquette "
                                  "« PARTIE N » change sur les Shorts.", ST['p'])]
    rows = [['Fichier', 'Image', 'Durée', 'Taille', 'Son (intégré / crête)']]
    for f in D['fichiers']:
        rows.append([f['fichier'], f.get('image', ''), f"{int(f['duree'] // 60)} min {f['duree'] % 60:04.1f} s", f"{f['taille_mo']:.1f} Mo",
                     f"{f['LUFS']:.1f} LUFS / {f['crete_dBTP']:.1f} dBTP"])
    t = Table(rows, colWidths=[64 * mm, 22 * mm, 24 * mm, 18 * mm, 40 * mm])
    t.setStyle(TableStyle([('FONT', (0, 0), (-1, -1), R, 8.2), ('FONT', (0, 0), (-1, 0), B, 8.2), ('TEXTCOLOR', (0, 0), (-1, -1), INK),
                           ('LINEBELOW', (0, 0), (-1, 0), .6, INK), ('LINEBELOW', (0, 1), (-1, -1), .3, RULE), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                           ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
    s += [Paragraph('Fichiers livrés', ST['h1']), t, Spacer(1, 3),
          Paragraph("Son mesuré sur les fichiers finaux (ebur128 de ffmpeg) ; cible -14 LUFS intégrés, crête vraie au plus -1 dBTP. Les copies « _leger » "
                    "(720p, moins de 30 Mo) sont faites pour l'envoi dans le chat et les messageries ; publier les fichiers pleins.", ST['small'])]
    L = D.get('long')
    if L:
        s += [PageBreak(), Paragraph('YouTube · version longue (16:9)', ST['h1']), Paragraph('Titre', ST['h2']), box(L['titre']),
              Paragraph('Description', ST['h2']), box(L['description']), Paragraph('Hashtags', ST['h2']), box(L['hashtags']),
              Paragraph('Les trois premiers hashtags de la description s’affichent au-dessus du titre ; inutile d’en mettre plus.', ST['small']),
              Paragraph('Tags', ST['h2']), box(L['tags']), Paragraph(f"{len(L['tags'])} caractères sur 500 autorisés.", ST['small']),
              Paragraph('Réglages conseillés', ST['h2']),
              Paragraph('Catégorie : Films et animation. Public : « Non, cette vidéo n’est pas conçue pour les enfants ». Langue : français. '
                        'Sous-titres : ils sont incrustés dans l’image.' + (' Les chapitres de la description sont calés sur le film (premier à 00:00, tous de plus de 10 s).' if L.get('chapitres') else ''), ST['p'])]
    SH = D.get('shorts') or []
    if SH:
        s += [PageBreak(), Paragraph(f"Shorts · YouTube Shorts et TikTok (9:16{', ' + str(len(SH)) + ' parties' if len(SH) > 1 else ''})", ST['h1'])]
        if D.get('decoupe_texte'): s.append(Paragraph(esc(D['decoupe_texte']), ST['p']))
        for sh in SH:
            blk = [Paragraph(f"{esc(sh['nom'])} · {esc(sh['fichier'])}", ST['h2']), Paragraph('Titre YouTube Shorts', ST['small']), box(sh['titre']),
                   Paragraph('Description YouTube Shorts', ST['small']), box(sh['description']), Paragraph('Légende TikTok', ST['small']), box(sh['tiktok'])]
            s.append(KeepTogether(blk))
        if D.get('tags_shorts'):
            s += [Paragraph('Tags YouTube (Shorts)', ST['h2']), box(D['tags_shorts']), Paragraph(f"{len(D['tags_shorts'])} caractères.", ST['small'])]
        if len(SH) > 1:
            s += [Paragraph('Enchaîner les parties', ST['h2']), Paragraph(
                'YouTube : sur chaque partie, renseigner la suivante comme « vidéo associée » dès qu’elle est en ligne ; sur la dernière, la version longue. '
                'Épingler un commentaire « Partie suivante » sous chaque partie. TikTok : regrouper les parties dans une playlist au titre de l’histoire.', ST['p'])]
    doc.build(s)
    print(out)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
