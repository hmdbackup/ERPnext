# Dossier de passation - Finance HMD AGRO

Commencer par le **[PDF de passation avec Aziz](01_dossier/passation_aziz_2026-09-16.pdf)**.
Il présente l'état du module, les procédures de reprise et les actions à attribuer.
Le code finance se trouve sur la branche `finance/socle-comptable`.

## Organisation

Ce dossier regroupe les **197 fichiers auparavant non suivis par Git** présents
au moment du classement du 16 septembre 2026. Les documents déjà versionnés
restent à leur emplacement habituel et sont référencés ci-dessous.

| Dossier | Contenu | Fichiers regroupés |
|---|---|---:|
| [01_dossier](01_dossier/) | PDF destiné à Aziz et source Markdown correspondante | 2 |
| [02_documentation](02_documentation/) | Guides Frappe/ERPNext, guide du code, spécifications et plans finance | 8 |
| [03_maquettes](03_maquettes/) | Maquettes HTML, PDF, Excalidraw et schémas | 8 |
| [04_demonstration](04_demonstration/) | Présentation finance, explication des user stories, conducteur et captures | 17 |
| [05_coordination](05_coordination/) | Points avec Aziz/Iheb, questions, supports de validation, messages et transcriptions | 20 |
| [06_outils](06_outils/) | Générateurs Python des maquettes et de la présentation des user stories | 6 |
| [07_stage](07_stage/) | Affiche de stage, photos, conducteurs et prompteur | 38 |
| [08_archives_techniques](08_archives_techniques/) | Essais de skills, packages et configuration de l'espace de travail | 92 |
| [09_sources_pdf](09_sources_pdf/) | Générateur du PDF de passation et aperçus de contrôle | 6 |

Les supports datés, les messages et les essais sont conservés comme archives.
Leurs compteurs de tests ou affirmations de déploiement peuvent décrire un état
ancien ; utiliser le dossier de passation pour les constats de reprise.
Les essais de `08_archives_techniques/` ne font pas partie du code de l'application.

## Documents utiles pour la reprise

- [Guide du code](02_documentation/hmd_agro_codebase_guide.html)
- [Spécification finance](02_documentation/spec_finance.html)
- [Guide de tests finance](02_documentation/guide_tests_finance.html)
- [Présentation finance](04_demonstration/presentation_finance.html)
- [Point assets avec Aziz](05_coordination/point_assets_aziz.pdf)
- [Questions au superviseur](05_coordination/questions_superviseur/README.md)
- [Passation technique du 06/09](../passation_2026-09-06.md)
- [Livraison finance](../livraison_finance.md)
- [Backlog et procédure Jira](../jira/README.md)
- [Installation et déploiement](../deploy/DEPLOY.md)
- [Runbook d'alignement des versions](../runbook_alignement_versions.md)
- [Scénario de vérification de la clé FG](../reunion_2026-09-03/scenario_verification_cle.md)

Les fichiers HTML se consultent après téléchargement ou clonage du dépôt.
Pour récupérer le dossier avec le code :

```bash
git clone --branch finance/socle-comptable https://github.com/hmdbackup/ERPnext hmd_agro
```

## Retrouver un ancien fichier

[INVENTAIRE.json](INVENTAIRE.json) associe chaque ancien chemin au nouveau,
avec l'empreinte SHA-256 d'origine et celle du fichier remis. Les éventuelles
différences correspondent aux adaptations de chemins, à la mise à jour du
dossier de passation et au nettoyage de quelques espaces en fin de ligne. Aucun des 197 fichiers inventoriés n'a été écarté.

Les fichiers ignorés par Git (secrets locaux et caches, notamment), les données
vivant dans le navigateur et les fichiers situés hors du dépôt ne font pas partie
de cet inventaire. Le journal de questions utilise le stockage du navigateur :
son transfert de données passe par l'export décrit dans son README.

## Régénérer les supports

Depuis la racine du dépôt :

```bash
python3 demo_finance/build_presentation.py
python3 passation/09_sources_pdf/build_passation.py
```

Le premier générateur utilise les captures de `04_demonstration/demo_finance/captures/`
et met à jour la présentation ainsi que `demo_finance/narration.json`.
Le générateur du PDF nécessite ReportLab et les polices Arial de macOS ; sa source
éditable est `01_dossier/passation_aziz_2026-09-16.md`.
Les outils de `06_outils/` retrouvent leurs entrées depuis leur emplacement,
sans dépendre du chemin du Mac d'origine.
