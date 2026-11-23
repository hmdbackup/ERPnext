# Serveur HMD — Stabilisation & extinction sur onduleur

Suite à l'incident du démarrage bloqué en `(initramfs)` (`UNEXPECTED INCONSISTENCY; RUN fsck MANUALLY`, inodes orphelins sur `/dev/mapper/ubuntu--vg-ubuntu--lv`).

**Cause probable** : une coupure secteur a éteint le serveur brutalement, et les inodes orphelins sont typiques de ce cas. La solution de fond est l'onduleur avec extinction automatique. Les journaux en RAM réduisent l'usure du disque mais ne protègent pas des coupures.

| Script | Rôle |
|---|---|
| `stabilite.sh` | fsck automatique au boot, logs en RAM (log2ram), Docker (rotation des logs, arrêt propre de MariaDB), service `hmd-erpnext`, SMART |
| `onduleur.sh`  | NUT : détection de l'onduleur USB, seuils, extinction propre, redémarrage automatique |
| `check.sh`     | Bilan de santé en lecture seule |
| `config.sh`    | **Tous les paramètres** (chemin `frappe_docker`, seuils onduleur, taille RAM des logs) |

Testé sur Ubuntu 24.04 (NUT 2.8.1). Compatible 22.04 (NUT 2.7, rôle `master` détecté automatiquement).

---

## 1. Déploiement

```bash
cd ~/hmd_agro/infra/hmd-server        # ou le clone du dépôt
nano config.sh                        # vérifier COMPOSE_DIR, UPS_*, ONBATT_MAX_SEC
sudo ./stabilite.sh
sudo ./onduleur.sh --dry-run          # mode test : rien ne s'éteint
sudo ./check.sh
```

Puis, en fenêtre de maintenance :

```bash
sudo reboot                           # active fsck.repair, log2ram, daemon.json
cd /home/hmd/hmd-deploy/frappe_docker
sudo docker compose --env-file .env up -d --force-recreate   # rotation des logs conteneurs
```

**BIOS/UEFI** : `Restore on AC Power Loss` (ou `AC Back`, `After Power Failure`) = **Power On**. Sans ce réglage, le serveur reste éteint au retour du courant.

## 2. Ce que fait `stabilite.sh`

| Mesure | Détail |
|---|---|
| `fsck.repair=yes` (GRUB) | L'initramfs lance `fsck -y` tout seul au lieu de s'arrêter sur BusyBox. Vérifié dans `initramfs-tools` 0.142 (`fsckfix`). |
| `tune2fs -c 30 -i 3m` | Vérification complète périodique de `/`, faite au boot. |
| log2ram + journald | `/var/log` en tmpfs (128 Mo), copié sur disque toutes les heures et à l'arrêt. journald reste `persistent`, plafonné à 40 Mo (`/etc/systemd/journald.conf.d/90-hmd.conf`). |
| `/etc/docker/daemon.json` | `log-driver: local` avec `10m × 3` (sans limite par défaut) et `shutdown-timeout: 60`. Le JSON existant est fusionné, pas écrasé. |
| `hmd-erpnext.service` | `docker compose up -d` au boot et `stop -t 60` **avant** l'arrêt de Docker, à chaque arrêt (onduleur, reboot, manuel). |
| smartd | Test court chaque jour à 02h, test long le samedi à 03h, alertes dans syslog. Les disques en veille ne sont pas réveillés (disque USB). |
| fstab | Affiche une alerte si un montage secondaire (disque USB `/dev/sdc`) n'a pas `nofail`. Sinon, un disque absent au boot bloque le démarrage. |

Chaque fichier système modifié est sauvegardé une fois en `*.orig-hmd`.

### Corrections apportées à la fiche initiale

- **`touch /forcefsck`** : ce fichier est ignoré depuis systemd. Pour forcer un fsck : `sudo tune2fs -C 999 /dev/mapper/ubuntu--vg-ubuntu--lv && sudo reboot` (le compteur de montages dépasse alors le maximum de 30). Autre méthode : ajouter `fsck.mode=force` à la ligne `linux` dans GRUB (touche `e`).
- **Méthode A (`Storage=volatile` + `rm -rf /var/log/journal/*`)** : avec elle, la trace de la prochaine coupure est perdue, c'est-à-dire précisément ce qu'il faut pour diagnostiquer. Elle reste disponible avec `LOG_MODE=volatile`, mais n'est pas recommandée.
- **Méthode B (tmpfs `/var/log` dans fstab)** : non retenue. Le tmpfs est vide au boot, donc les sous-dossiers (`/var/log/mysql`, `apt`, `samba`, `nginx`…) n'existent pas et les services qui en dépendent échouent. Elle est aussi incompatible avec log2ram, qui monte déjà `/var/log`.
- **ERPNext tourne sous Docker** : les logs des conteneurs vont dans `/var/lib/docker/containers`, pas dans `/var/log`. Leur rotation passe par `daemon.json`.
- **`smartctl` sur le disque USB** : si `-a` ne répond pas, utiliser `sudo smartctl -d sat -a /dev/sdc`.

## 3. Extinction sur coupure de courant

```
Secteur coupé ──► onduleur sur batterie (OB) ──► upssched lance un timer de ONBATT_MAX_SEC
     │                                                     │
     │  secteur revient avant la fin ──► timer annulé, rien ne se passe
     ▼
Premier critère atteint :
  • ONBATT_MAX_SEC écoulé (300 s)          → upsmon -c fsd
  • batterie < 50 % ou autonomie < 300 s   → le driver lève LB (ignorelb + override)
     ▼
upsmon : FSD → /etc/killpower → hmd-ups-shutdown → shutdown -h
     ▼
systemd : hmd-erpnext stop (MariaDB propre, 60 s) → Docker → démontage des FS
     ▼
nutshutdown : l'onduleur coupe sa sortie après ups.delay.shutdown
     ▼
Retour du secteur : l'onduleur rallume sa sortie → le BIOS démarre le serveur
     → fsck auto si besoin → hmd-erpnext up -d
```

**Retour du secteur pendant l'arrêt** : `POWEROFF_WAIT=180s` (dans `nut.conf`). Le serveur redémarre de lui-même au lieu de rester éteint.

**Budget d'autonomie** : il faut `battery.runtime` (affiché par `check.sh`) supérieur ou égal à `ONBATT_MAX_SEC` + environ 120 s d'arrêt + une marge. Si l'autonomie est trop faible, baisser `ONBATT_MAX_SEC`.

**Onduleur non reconnu** : `nut-scanner -U` indique le bon driver, que `onduleur.sh` adopte automatiquement. Les modèles génériques ou chinois utilisent souvent `nutdrv_qx`. Si l'onduleur ne remonte pas `battery.charge`, seul le timer protège le serveur (le script l'affiche).

### Tests

1. **Test à blanc** (pas d'extinction) :
   ```bash
   sudo ONBATT_MAX_SEC=30 ./onduleur.sh --dry-run
   # débrancher l'onduleur du secteur pendant 45 s, puis le rebrancher
   journalctl -t hmd-ups -f
   ```
   Messages attendus : `Secteur coupe`, puis `DRY-RUN : delai sur batterie depasse`, puis `Secteur retabli`.
2. **Retour au mode réel** : `sudo ./onduleur.sh --activer` (remet aussi `ONBATT_MAX_SEC` de `config.sh`).
3. **Test réel** (prévenir les utilisateurs d'ERPNext) : débrancher l'onduleur et attendre `ONBATT_MAX_SEC`. Le serveur s'éteint, l'onduleur coupe puis se rallume au rebranchement, et le serveur redémarre seul. Ensuite, contrôler avec `sudo ./check.sh` et `journalctl -b -1 -t hmd-ups`.

Ces trois chemins (timer, FSD via sudo, seuil LB) ont été validés avec le driver `dummy-ups`.

## 4. Maintenance

| Fréquence | Action | Commande |
|---|---|---|
| Hebdo | Bilan global | `sudo ./check.sh` |
| Hebdo | Erreurs disque/USB | `sudo dmesg -T \| grep -iE "error\|i/o\|ext4\|usb" \| tail -n 30` |
| Mensuel | SMART détaillé | `sudo smartctl -a /dev/sda` ; `sudo smartctl -d sat -a /dev/sdc` |
| Trimestriel | Test réel de l'onduleur | §3 test 3 |
| 3–5 ans | Batterie de l'onduleur | une alerte `REPLBATT` apparaît dans `journalctl -t hmd-ups` |

| Objectif | Commande |
|---|---|
| État onduleur | `upsc hmdups@localhost` |
| Événements onduleur | `journalctl -t hmd-ups` ; `journalctl -u nut-monitor` |
| Logs en RAM | `df -h /var/log` ; `journalctl --disk-usage` ; `systemctl status log2ram` |
| Forcer fsck au prochain boot | `sudo tune2fs -C 999 /dev/mapper/ubuntu--vg-ubuntu--lv` |
| État ext4 | `sudo tune2fs -l /dev/mapper/ubuntu--vg-ubuntu--lv \| grep -E "state\|error\|checked"` |
| Arrêt manuel propre | `sudo systemctl stop hmd-erpnext && sudo shutdown -h now` |

### Si le serveur retombe malgré tout en `(initramfs)`

```sh
fsck -y /dev/mapper/ubuntu--vg-ubuntu--lv    # jamais sur un FS monté
reboot -f
```

Après le redémarrage : `sudo ./check.sh` et `sudo smartctl -a` sur le disque système. Des erreurs répétées alors que l'onduleur est en place désignent le disque lui-même (secteurs réalloués ou en attente) : il faut le remplacer.

## 5. Désinstallation / retour arrière

```bash
for o in /etc/default/grub.orig-hmd /etc/log2ram.conf.orig-hmd /etc/docker/daemon.json.orig-hmd \
         /etc/smartd.conf.orig-hmd /etc/nut/*.orig-hmd; do
  [ -f "$o" ] && sudo cp -a "$o" "${o%.orig-hmd}"; done
sudo rm -f /etc/systemd/journald.conf.d/90-hmd.conf /etc/sudoers.d/hmd-nut
sudo systemctl disable hmd-erpnext            # sans --now : ERPNext reste en marche
sudo systemctl disable --now nut-monitor
sudo update-grub
```
