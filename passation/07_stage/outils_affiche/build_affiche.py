"""Affiche de stage v2 : ajoute la clé de répartition des frais généraux
(livrée le 03/09) — textes, 3 captures recadrées, réorganisation des zones.
Part du pptx v1 sauvegardé, écrit le pptx dans ~/Downloads."""
import copy
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.util import Cm

HERE = Path(__file__).parent
CAP = HERE / "captures"
SRC = HERE / "affiche_v1_sauvegarde.pptx"
import os
STAGE = int(os.environ.get("STAGE", "9"))
OUT = Path(os.environ.get("OUT", str(Path.home() / "Downloads" / "Affiche_stage_Mohamed_Slim_HMD_AGRO.pptx")))

# ---------- captures recadrées ----------
def crop(name, box, out):
    im = Image.open(CAP / name).crop(box)
    im.save(CAP / out)
    return CAP / out, im.size

cle_png, cle_sz = crop("cle.jpg", (250, 140, 1385, 560), "cle_crop.png")
gl_png, gl_sz = crop("grand_livre.jpg", (17, 135, 1382, 565), "grand_livre_crop.png")

# rapport : en-tête de colonnes + lignes 39–48 et 51 (sans les 2 lignes de
# stock qui demandent une explication orale)
src = Image.open(CAP / "rapport_fg.jpg")
head = src.crop((17, 135, 1382, 178))
ROW0, RH = 218, 38.5
rows_keep = list(range(0, 10)) + [12]  # lignes 39..48 et 51
parts = [head] + [src.crop((17, int(ROW0 + i * RH), 1382, int(ROW0 + (i + 1) * RH))) for i in rows_keep]
W = 1365
H = sum(p.size[1] for p in parts)
rap = Image.new("RGB", (W, H), "white")
y = 0
for p in parts:
    rap.paste(p, (0, y))
    y += p.size[1]
rap_png = CAP / "rapport_fg_crop.png"
rap.save(rap_png)
rap_sz = rap.size

# ---------- pptx ----------
prs = Presentation(SRC)


# ---------- app.xml : nom du modèle (python-pptx ne l'expose pas) ----------
import re, shutil, zipfile
def fix_app_xml(path):
    tmp = path.with_suffix(".tmp.pptx")
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "docProps/app.xml":
                xml = data.decode("utf-8")
                xml = re.sub(r"<Template>.*?</Template>", "<Template>Affiche de stage HMD AGRO</Template>", xml)
                xml = re.sub(r"<TotalTime>.*?</TotalTime>", "<TotalTime>0</TotalTime>", xml)
                data = xml.encode("utf-8")
            zout.writestr(item, data)
    shutil.move(tmp, path)


# ---------- métadonnées : Mohamed Slim auteur et dernier modificateur ----------
import datetime
cp = prs.core_properties
cp.author = "Mohamed Slim"
cp.last_modified_by = "Mohamed Slim"
cp.title = "Affiche de stage — Mohamed Slim, HMD AGRO"
cp.subject = "Stage IFT-2580, Université Laval — HMD AGRO, Borj Essebai"
cp.comments = ""
cp.category = ""
cp.revision = 3
cp.modified = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
slide = prs.slides[0]
by_id = {sh.shape_id: sh for sh in slide.shapes}


def set_bullet(shape, idx, text):
    para = shape.text_frame.paragraphs[idx]
    runs = para.runs
    runs[0].text = text
    for r in runs[1:]:
        r._r.getparent().remove(r._r)


def insert_bullet_after(shape, idx, text):
    para = shape.text_frame.paragraphs[idx]
    new_p = copy.deepcopy(para._p)
    para._p.addnext(new_p)
    set_bullet(shape, idx + 1, text)


def remove_paragraph(shape, idx):
    p = shape.text_frame.paragraphs[idx]._p
    p.getparent().remove(p)


def remove_shape(shape):
    el = shape._element
    el.getparent().remove(el)


def add_caption(model, text, left, top, width):
    el = copy.deepcopy(model._element)
    cNvPr = el.find(".//{http://schemas.openxmlformats.org/presentationml/2006/main}cNvPr")
    new_id = max(sh.shape_id for sh in slide.shapes) + 1
    cNvPr.set("id", str(new_id))
    cNvPr.set("name", f"Legende {new_id}")
    slide.shapes._spTree.append(el)
    sh = slide.shapes[-1]
    sh.left, sh.top, sh.width, sh.height = Cm(left), Cm(top), Cm(width), Cm(1.1)
    p = sh.text_frame.paragraphs[0]
    p.runs[0].text = text
    for r in p.runs[1:]:
        r._r.getparent().remove(r._r)
    return sh


# 1 — Entreprise : les cinq ateliers (et comble le vide sous la section)
ent = by_id[3]
insert_bullet_after(
    ent, 3,
    "Cinq ateliers, cinq centres de coûts : Lait, Cultures - Fourrage, Génisses, Traction, Frais généraux",
)

# 3 — Travail réalisé
tr = by_id[107]
set_bullet(tr, 2, "Consommations valorisées automatiquement au coût moyen pondéré")
set_bullet(tr, 5, "Paie et charges patronales ventilées par atelier, primes du personnel")
set_bullet(tr, 4, "Cheptel et matériel à l'actif, amortissements, parc et interventions")
set_bullet(tr, 6, "Frais généraux ventilés au Grand Livre par une clé de répartition (Cost Center Allocation) fixée une fois")
insert_bullet_after(tr, 6, "Centre de coûts posé par l'app sur chaque mouvement de stock : rations, médicaments, paillettes")
# « Maquettes validées… Jira » est déjà porté par la section 4 → retiré
remove_paragraph(tr, 9)
set_bullet(tr, 9, "521 tests automatisés verts, migrations versionnées, Docker")

# 4 — Techniques : Git/Docker fusionné, le natif ERPNext ajouté
tech = by_id[19]
set_bullet(tech, 2, "Python, SQL et migrations MariaDB ; Git, Docker, bench et Jira au quotidien")
set_bullet(tech, 4, "S'appuyer sur le natif d'ERPNext (Cost Center Allocation) plutôt que sur du code sur mesure")
remove_paragraph(tech, 5)

# 4 — Communication : la revue du 03/09
com = by_id[28]
set_bullet(com, 2, "Maquettes validées ; revue du 03/09 : modèle repris et livré le jour même")

# 5 — Résultat
res = by_id[29]
set_bullet(res, 2, "Frais généraux répartis dans les écritures comptables ; contrôle écritures = clé, zéro écart")

# 5 — Points forts
pf = by_id[31]
set_bullet(pf, 3, "Savoir reprendre une conception après revue : la table par ligne remplacée par la clé native")

# 5 — Suggestions : la balance d'ouverture remplacée par une suggestion plus simple
sug = by_id[32]
set_bullet(sug, 1, "Consulter le tableau de bord économique chaque mois avec le gérant")

# 2 — logos ERPNext / Frappe recentrés dans le vide sous les objectifs
for sid in (17, 21):
    by_id[sid].top = by_id[sid].top + Cm(2.5)

# ---------- images ----------
if STAGE < 1:
    prs.save(OUT); fix_app_xml(OUT); raise SystemExit(0)
# Colonne gauche : « Seuils de pilotage » remplacé par le cheptel immobilisé
remove_shape(by_id[110])
remove_shape(by_id[111])
chep, chep_cap = by_id[121], by_id[122]
chep.left, chep.top, chep.width = Cm(3.7), Cm(101.4), Cm(27.7)
chep.height = Cm(27.7 * 771 / 1363)
chep_cap.left, chep_cap.top, chep_cap.width = Cm(3.7), Cm(101.4 + 27.7 * 771 / 1363 + 0.15), Cm(27.7)

if STAGE < 2:
    prs.save(OUT); fix_app_xml(OUT); raise SystemExit(0)
# Colonne droite, rangée 3 : la clé + le Grand Livre réparti
X0, GAP, TOTAL = 36.4, 0.5, 34.8
h3 = 5.9
w_cle = h3 * cle_sz[0] / cle_sz[1]
w_gl = TOTAL - GAP - w_cle
h_gl = w_gl * gl_sz[1] / gl_sz[0]
y3 = 40.6
slide.shapes.add_picture(str(cle_png), Cm(X0), Cm(y3), Cm(w_cle), Cm(h3))
slide.shapes.add_picture(str(gl_png), Cm(X0 + w_cle + GAP), Cm(y3), Cm(w_gl), Cm(h_gl))
cap_y = y3 + max(h3, h_gl) + 0.15
add_caption(chep_cap, "Clé de répartition : 60 / 25 / 15 %", X0, cap_y, w_cle)
add_caption(chep_cap, "Facture validée : Grand Livre réparti 900 / 375 / 225", X0 + w_cle + GAP, cap_y, w_gl)

# Rangée 4 : le rapport, section frais généraux
y4 = cap_y + 1.1 + 0.5
h_rap = TOTAL * rap_sz[1] / rap_sz[0]
slide.shapes.add_picture(str(rap_png), Cm(X0), Cm(y4), Cm(TOTAL), Cm(h_rap))
add_caption(chep_cap, "Rapport Performance : chaque charge, sa clé, et le contrôle écritures = clé (aucun écart)", X0, y4 + h_rap + 0.15, TOTAL)

print(f"rangée 3 : y={y3:.1f}→{cap_y + 1.1:.1f} ; rapport : y={y4:.1f}→{y4 + h_rap + 1.25:.1f} (section 4 à 64.2)")
print(f"cheptel : y=101.4→{101.4 + 27.7 * 771 / 1363 + 1.25:.1f} (cadre section 3 jusqu'à 118.5)")
prs.save(OUT); fix_app_xml(OUT)
print("écrit", OUT)
