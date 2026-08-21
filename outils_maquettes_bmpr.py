"""Génère le projet Balsamiq des maquettes SCRUM-9/10/11.

Format BMPR 2.0 : base SQLite, tables INFO / BRANCHES / RESOURCES /
THUMBNAILS / USERS / COMMENTS. La géométrie des contrôles est stockée en
CHAÎNES — Balsamiq ignore silencieusement un contrôle dont x/y/w/h sont
numériques. Les retours à la ligne d'une propriété `text` sont des \n bruts.
"""
import json, sqlite3, uuid
from pathlib import Path

SORTIE = Path("/Users/momoslim/Desktop/hmd_agro-main/maquettes_scrum_9_10_11.bmpr")
BRANCHE = "Master"

SCHEMAS = [
    "CREATE TABLE INFO (NAME VARCHAR(255) PRIMARY KEY, VALUE TEXT)",
    "CREATE TABLE BRANCHES (ID VARCHAR(255) PRIMARY KEY, ATTRIBUTES TEXT)",
    "CREATE TABLE RESOURCES (ID VARCHAR(255), BRANCHID VARCHAR(255), "
    "ATTRIBUTES TEXT, DATA LONGTEXT, PRIMARY KEY (ID, BRANCHID), "
    "FOREIGN KEY (BRANCHID) REFERENCES BRANCHES(ID))",
    "CREATE TABLE THUMBNAILS (ID VARCHAR(255) PRIMARY KEY, ATTRIBUTES MEDIUMTEXT)",
    "CREATE TABLE USERS (ID VARCHAR(255) PRIMARY KEY, ATTRIBUTES TEXT)",
    "CREATE TABLE COMMENTS (ID VARCHAR(255) PRIMARY KEY, BRANCHID VARCHAR(255), "
    "RESOURCEID VARCHAR(255), DATA LONGTEXT, USERID VARCHAR(255), ATTRIBUTES TEXT)",
]

# Dimensions par défaut, reprises des contrôles Balsamiq réels.
DEFAUTS = {
    "BrowserWindow": (450, 400), "Title": (200, 30), "SubTitle": (200, 24),
    "Label": (60, 21), "LineOfText": (200, 20), "BlockOfText": (275, 80),
    "TextInput": (100, 27), "ComboBox": (100, 27), "DateChooser": (100, 27),
    "Button": (65, 27), "DataGrid": (400, 200), "StickyNote": (109, 123),
    "Canvas": (100, 70), "HorizontalScrollBar": (100, 16),
}


class Ecran:
    def __init__(self, nom, ordre, largeur=1120, hauteur=780):
        self.nom, self.ordre = nom, ordre
        self.id = str(uuid.uuid4()).upper()
        self.largeur, self.hauteur = largeur, hauteur
        self.controles = []

    def ajoute(self, type_id, x, y, w=None, h=None, **props):
        mw, mh = DEFAUTS.get(type_id, (100, 24))
        c = {
            "ID": str(len(self.controles)),
            "typeID": type_id,
            "zOrder": str(len(self.controles)),
            "measuredW": str(w or mw),
            "measuredH": str(h or mh),
            "x": str(x), "y": str(y),
        }
        if w is not None:
            c["w"] = str(w)
        if h is not None:
            c["h"] = str(h)
        if props:
            c["properties"] = props
        self.controles.append(c)
        return c

    def data(self):
        return json.dumps({"mockup": {
            "controls": {"control": self.controles},
            "attributes": {"name": self.nom, "order": self.ordre,
                           "parentID": None, "notes": ""},
            "branchID": BRANCHE, "resourceID": self.id,
            "mockupW": str(self.largeur), "mockupH": str(self.hauteur),
            "measuredW": str(self.largeur), "measuredH": str(self.hauteur),
            "version": "1.0",
        }}, ensure_ascii=False)

    def attributs(self):
        return json.dumps({
            "mimeType": "text/vnd.balsamiq.bmml", "kind": "mockup",
            "creationDate": 0, "trashed": False, "name": self.nom,
            "importedFrom": "", "order": self.ordre,
        }, ensure_ascii=False)


def grille(lignes):
    """Texte d'un DataGrid : colonnes séparées par une virgule, lignes par \n.

    Les nombres sont écrits au point décimal : la virgule sépare les colonnes,
    un « 45 444,0 » couperait la ligne en deux cellules.
    """
    return "\n".join(",".join(str(c) for c in ligne) for ligne in lignes)


def cadre(e, titre, sous_titre, url, filtres):
    """En-tête commun : fenêtre, titre, sous-titre, barre de filtres."""
    e.ajoute("BrowserWindow", 0, 0, 1100, 760, text=url)
    e.ajoute("Title", 24, 66, 700, 34, text=titre)
    e.ajoute("SubTitle", 24, 104, 900, 22, text=sous_titre)
    x = 24
    for libelle, valeur, largeur in filtres:
        e.ajoute("Label", x, 148, None, None, text=libelle)
        e.ajoute("ComboBox", x, 168, largeur, 27, text=valeur)
        x += largeur + 16
    return 212


# ─────────────────────── SCRUM-9 ───────────────────────
e9 = Ecran("SCRUM-9 Production Lait", 1000000.0)
y = cadre(
    e9,
    "Rapport Périodique — Production",
    "Production laitière jour par jour, avec les deux dénominateurs : VL (vaches en lactation) et VP (vaches présentes).",
    "hmd.agro — Rapports > Rapport Périodique",
    [("Date", "30/06/2026", 130), ("Période", "Mois", 110),
     ("Section", "Production", 130), ("Granularité", "Quinzaine", 130),
     ("Effectif", "Jour", 100)],
)
e9.ajoute("DataGrid", 24, y, 1044, 330, text=grille([
    ["Jour / Période", "VL", "VP", "Production L", "Moy/VL", "Moy/VP", "TB", "TP",
     "Commercialisé L", "Auto-conso L", "Lait Veau L", "Écart L"],
    [1, 97, 119, 1643.0, 16.9, 13.8, "-", "-", 1571.0, 32.0, 35.0, 5.0],
    [2, 97, 119, 1626.0, 16.8, 13.7, "-", "-", 1554.0, 30.0, 35.0, 7.0],
    [3, 96, 118, 1587.0, 16.5, 13.5, "-", "-", 1518.0, 30.0, 35.0, 4.0],
    [4, 96, 118, 1569.0, 16.3, 13.3, "-", "-", 1502.0, 28.0, 35.0, 4.0],
    [5, 96, 118, 1511.0, 15.7, 12.8, 3.68, 3.15, 1394.0, 30.0, 35.0, 52.0],
    ["...", "", "", "", "", "", "", "", "", "", "", ""],
    ["Q1 (1 > 15)", "-", "-", 23197.0, "-", "-", "-", "-", 22164.0, 445.0, 525.0, 63.0],
    [16, 95, 117, 1502.0, 15.8, 12.8, "-", "-", 1436.0, 29.0, 35.0, 2.0],
    [17, 95, 117, 1483.0, 15.6, 12.7, "-", "-", "", "", "", ""],
    ["...", "", "", "", "", "", "", "", "", "", "", ""],
    ["Q2 (16 > 30)", "-", "-", 22247.0, "-", "-", "-", "-", 21264.0, 445.0, 525.0, 13.0],
    ["Total (VL/VP = moy.)", 96, 118, 45444.0, 15.8, 12.8, 3.68, 3.15, 43428.0, 890.0, 1050.0, 76.0],
]))
e9.ajoute("BlockOfText", 24, 560, 700, 130, text=(
    "1  VL et VP sont recalculés chaque jour depuis les vêlages, tarissements et sorties.\n"
    "2  Jour 5 : écart de 52 L affiché tel quel — l'anomalie se voit, elle n'est pas corrigée en silence.\n"
    "3  Jour 17 : bilan lait non saisi. Cellules VIDES, jamais des zéros.\n"
    "4  Ligne Total : moyennes pour VL/VP, sommes pour les litres, sur les seuls jours saisis."))
e9.ajoute("StickyNote", 760, 555, 308, 150, text=(
    "À trancher avec M. Samir\n\n"
    "- Dénominateur de référence : L/VL ou L/VP ?\n"
    "- TB/TP : jours de contrôle laitier seulement ?\n"
    "- Seuil d'alerte sur l'écart : 50 L/jour ?\n"
    "- BLOQUANT : sans événement de vêlage importé,\n"
    "  VL = 0 sur les données réelles."))

# ─────────────────────── SCRUM-10 ───────────────────────
e10 = Ecran("SCRUM-10 Charges par Atelier", 1000010.0)
y = cadre(
    e10,
    "Rapport de Performance — Charges & Coût du Lait",
    "Les charges ventilées par atelier, puis le coût du lait poste par poste pour rapprochement comptable.",
    "hmd.agro — Rapports > Rapport de Performance",
    [("Date", "30/06/2026", 130), ("Période", "Mois", 110),
     ("Périmètre coût/L", "LAIT_QUOTE_PART", 190)],
)
e10.ajoute("DataGrid", 24, y, 800, 420, text=grille([
    ["Indicateur", "Valeur", "Unité", "M-1", "Delta %"],
    ["— CHARGES PAR ATELIER —", "", "", "", ""],
    ["Lait — Troupeau Laitier", 62620.00, "DT", 60910.00, "+2.8"],
    ["Culture Fourragère & Traction", 21350.00, "DT", 20780.00, "+2.7"],
    ["Génisses & Élevage", 12780.00, "DT", 12410.00, "+3.0"],
    ["Frais Généraux", 9840.00, "DT", 9620.00, "+2.3"],
    ["Frigorifique", 4260.00, "DT", 3990.00, "+6.8"],
    ["Non imputé — écriture sans atelier", 1250.00, "DT", 720.00, "+73.6"],
    ["Total ventilé = Charges Totales", 112100.00, "DT", 108430.00, "+3.4"],
    ["— COÛT DU LAIT (DÉTAIL) —", "", "", "", ""],
    ["Ration & Aliments (601)", 41260.00, "DT", 39880.00, "+3.5"],
    ["Santé & Vétérinaire (602)", 3180.00, "DT", 2940.00, "+8.2"],
    ["Mécanique — Entretien (615)", 620.00, "DT", 480.00, "+29.2"],
    ["Personnel (64x)", 12900.00, "DT", 12900.00, "0.0"],
    ["Amortissements (68x)", 3860.00, "DT", 3860.00, "0.0"],
    ["Charges financières (66x)", 800.00, "DT", 850.00, "-5.9"],
    ["Autres charges d'exploitation", 0.00, "DT", 0.00, "-"],
    ["Sous-total — charges directes Lait", 62620.00, "DT", 60910.00, "+2.8"],
    ["Quote-part Frais Généraux — clé 61.98 %", 6099.23, "DT", 5962.40, "+2.3"],
    ["TOTAL retenu pour le coût du litre", 68719.23, "DT", 66872.40, "+2.8"],
    ["Rappel — non imputé exclu du coût/L", 1250.00, "DT", 720.00, "+73.6"],
    ["— COÛTS UNITAIRES —", "", "", "", ""],
    ["Coût Alimentaire / L", 0.908, "DT/L", 0.895, "+1.5"],
    ["Coût Mécanique / L (vue analytique)", 0.060, "DT/L", 0.044, "+36.4"],
    ["Coût Complet / L (Lait + quote-part)", 1.512, "DT/L", 1.501, "+0.7"],
    ["Coût du Litre hors Amortissement", 1.427, "DT/L", 1.414, "+0.9"],
    ["IOFC — CA Lait moins Coût Alimentaire", 8682.20, "DT", 8210.00, "+5.8"],
    ["IOFC / Vache Lactante / Jour", 3.01, "DT/VL/j", 2.87, "+4.9"],
]))
e10.ajoute("BlockOfText", 848, y, 220, 200, text=(
    "1  Les écritures sont enfin lues avec leur centre de coût.\n\n"
    "2  « Non imputé » s'affiche même à zéro : une ligne absente se lit "
    "« rien à signaler », une ligne à 0 se lit « vérifié ».\n\n"
    "3  Le total se recompte à l'écran et passe au rouge s'il diverge.\n\n"
    "4  La clé de quote-part est écrite en toutes lettres."))
e10.ajoute("StickyNote", 848, y + 220, 220, 200, text=(
    "À trancher avec M. Samir\n\n"
    "- Nom exact du centre « frigénerie »\n"
    "- Clé de quote-part : charges directes ou litres ?\n"
    "- Périmètre officiel du coût du litre\n"
    "- Saisie d'une charge répartie en % entre ateliers "
    "(Cost Center Allocation, non activé)"))

# ─────────────────────── SCRUM-11 ───────────────────────
e11 = Ecran("SCRUM-11 Interventions", 1000020.0)
y = cadre(
    e11,
    "Rapport des Interventions",
    "Ce qui a été fait sur le mois, ce qui arrive sous 30 jours, et le rapprochement avec le compte 615.",
    "hmd.agro — Rapports > Rapport des Interventions",
    [("Date", "30/06/2026", 130), ("Période", "Mois", 110),
     ("Équipement", "Tous", 130), ("Atelier", "Tous", 130)],
)
e11.ajoute("DataGrid", 24, y, 1044, 340, text=grille([
    ["Section", "Date", "Équipement", "Désignation", "Type", "Libellé",
     "Atelier", "Intervenant", "Coût", "Nb Interv.", "Nb Équip."],
    ["Réalisées", "06/06/2026", "ACC-ASS-2026-00003", "Tracteur Massey 385",
     "PRÉVENTIVE", "Vidange moteur + filtres", "Culture Fourragère", "Atelier Ben Salah", 340.00, "", ""],
    ["Réalisées", "11/06/2026", "ACC-ASS-2026-00007", "Tank à lait 3000 L",
     "CURATIVE", "Remplacement sonde de température", "Lait — Troupeau", "Frigotech", 620.00, "", ""],
    ["Réalisées", "18/06/2026", "ACC-ASS-2026-00012", "Groupe électrogène 60 kVA",
     "PRÉVENTIVE", "Contrôle 250 h + filtre à air", "Frais Généraux", "Interne", 180.00, "", ""],
    ["Réalisées", "23/06/2026", "ACC-ASS-2026-00003", "Tracteur Massey 385",
     "CURATIVE", "Réparation circuit hydraulique", "Culture Fourragère", "Atelier Ben Salah", 1480.00, "", ""],
    ["Réalisées", "27/06/2026", "ACC-ASS-2026-00019", "Remorque épandeuse",
     "PRÉVENTIVE", "Graissage + contrôle pneus", "Culture Fourragère", "Interne", 95.00, "", ""],
    ["Réalisées", "", "", "", "", "TOTAL — 5 intervention(s) / 4 équipement(s)", "", "", 2715.00, 5, 4],
    ["Préventif 30 j", "28/06/2026", "ACC-ASS-2026-00016", "Pompe à vide salle de traite",
     "EN RETARD", "Contrôle mensuel de dépression", "Lait — Troupeau", "", "", "", ""],
    ["Préventif 30 j", "05/07/2026", "ACC-ASS-2026-00003", "Tracteur Massey 385",
     "À VENIR", "Vidange 500 h", "Culture Fourragère", "", "", "", ""],
    ["Préventif 30 j", "14/07/2026", "ACC-ASS-2026-00007", "Tank à lait 3000 L",
     "À VENIR", "Nettoyage du condenseur", "Lait — Troupeau", "", "", "", ""],
    ["Rapprochement", "", "", "", "", "Entretien au Grand Livre (compte 615)", "", "", 2715.00, "", ""],
    ["Rapprochement", "", "", "", "", "Somme des interventions saisies", "", "", 2715.00, "", ""],
    ["Rapprochement", "", "", "", "", "Écart — aucun : chaque dinar est rattaché", "", "", 0.00, "", ""],
]))
e11.ajoute("BlockOfText", 24, 570, 700, 120, text=(
    "1  Nb Interventions et Nb Équipements sont des COLONNES, pas une phrase dans le libellé : ce qui s'exporte se compare.\n"
    "2  Une échéance dépassée s'affiche en rouge et reste dans la liste — c'est celle-là qu'il faut voir.\n"
    "3  Le rapprochement au compte 615 est fait par le rapport, pas découvert à la clôture."))
e11.ajoute("StickyNote", 760, 565, 308, 140, text=(
    "À trancher avec M. Samir\n\n"
    "- Fenêtre du préventif : 30 jours ?\n"
    "- Déclencheurs : jours / heures de marche / fréquence ?\n"
    "- Statuts : prêt à partir / à vérifier / en panne\n"
    "- Distinguer main-d'œuvre et pièces ?"))

# ─────────────────────── Écriture ───────────────────────
ecrans = [e9, e10, e11]
if SORTIE.exists():
    SORTIE.unlink()
conn = sqlite3.connect(SORTIE)
cur = conn.cursor()
for sql in SCHEMAS:
    cur.execute(sql)
cur.executemany("INSERT INTO INFO (NAME, VALUE) VALUES (?, ?)", [
    ("SchemaVersion", "2.0"),
    ("ArchiveFormat", "bmpr"),
    ("ArchiveRevisionUUID", ""),
    ("ArchiveAttributes", json.dumps({"name": "HMD AGRO — Maquettes SCRUM-9/10/11"},
                                     ensure_ascii=False)),
    ("ArchiveRevision", "1"),
])
cur.execute("INSERT INTO BRANCHES (ID, ATTRIBUTES) VALUES (?, ?)", (BRANCHE, json.dumps({
    "fontFace": "Balsamiq Sans", "fontSize": 13, "linkColor": 545684,
    "selectionColor": 9813234, "skinName": "sketch",
})))
for e in ecrans:
    cur.execute("INSERT INTO RESOURCES (ID, BRANCHID, ATTRIBUTES, DATA) VALUES (?,?,?,?)",
                (e.id, BRANCHE, e.attributs(), e.data()))
conn.commit()
conn.close()
print("écrit :", SORTIE, SORTIE.stat().st_size, "octets")
for e in ecrans:
    print(f"  {e.nom} — {len(e.controles)} contrôles")
