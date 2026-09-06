#!/bin/bash
# Régénère les deux vidéos de démo à partir de presentation_finance.html.
#
#   demo_finance_hmd.mp4         narrée (une séquence par slide, durée = durée du texte lu)
#   demo_finance_hmd_muette.mp4  sans voix, 8 s par slide
#
# Source unique : le deck HTML + narration.json, tous deux produits par
# build_presentation.py. Modifier les notes là-bas, relancer ce script.
#
# Audio : la voix de chaque slide est rendue en WAV (PCM), les WAV sont
# concaténés en UNE piste continue, encodée en AAC une seule fois au mux final.
# NE PAS encoder l'AAC par slide puis concaténer en copy : l'amorçage de
# l'encodeur AAC laisse un clic/saut à chaque jointure (bug corrigé le 24/07).
set -euo pipefail

ICI="$(cd "$(dirname "$0")" && pwd)"
DECK="$(cd "$ICI/.." && pwd)/presentation_finance.html"
NARRATION="$ICI/narration.json"
SORTIE="${SORTIE:-$HOME/Downloads}"
TRAVAIL="${TMPDIR:-/tmp}/hmd_demo_video"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FFMPEG=/opt/homebrew/bin/ffmpeg
FFPROBE=/opt/homebrew/bin/ffprobe
# Voix neurale Microsoft via edge-tts (bien plus fluide que macOS `say`).
# Alternatives fr : fr-FR-DeniseNeural (femme), fr-FR-RemyMultilingualNeural,
# fr-CA-JeanNeural. `RATE`/`PITCH` ajustent le débit (ex. RATE=-8%).
VOIX="${VOIX:-fr-FR-HenriNeural}"
RATE="${RATE:-+0%}"
PITCH="${PITCH:-+0Hz}"
SILENCE_DEBUT=0.6      # s avant la phrase : le spectateur voit la slide arriver
SILENCE_FIN=1.0        # s après la phrase : on ne coupe pas sur le dernier mot
SEC_MUETTE=8

N=$(python3 -c "import json;print(len(json.load(open('$NARRATION'))))")
echo "→ $N slides · voix « $VOIX »"
rm -rf "$TRAVAIL"; mkdir -p "$TRAVAIL"

# ── 1. Une image par slide, en 1920x1080, sans le chrome de navigation
for i in $(seq 1 "$N"); do
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars \
    --force-device-scale-factor=1 --window-size=1920,1080 \
    --screenshot="$TRAVAIL/slide$(printf '%02d' "$i").png" \
    --virtual-time-budget=4000 \
    "file://$DECK?s=$i&clean=1" >/dev/null 2>&1
  printf '  image %2d/%d\n' "$i" "$N"
done

# ── 2. Une piste voix par slide (edge-tts = voix neurale, sortie mp3)
python3 - "$NARRATION" "$TRAVAIL" "$VOIX" "$RATE" "$PITCH" <<'PY'
import json, subprocess, sys, pathlib
notes, travail, voix, rate, pitch = (json.load(open(sys.argv[1])),
    pathlib.Path(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5])
for i, texte in enumerate(notes, 1):
    sortie = travail / f"voix{i:02d}.mp3"
    subprocess.run([sys.executable, "-m", "edge_tts", "--voice", voix,
                    "--rate", rate, "--pitch", pitch,
                    "--text", texte, "--write-media", str(sortie)], check=True)
    print(f"  voix  {i:2d}/{len(notes)}")
PY

# ── 3. Par slide : audio PCM (voix + respiration) et vidéo muette de même durée
: > "$TRAVAIL/liste_video.txt"
: > "$TRAVAIL/liste_audio.txt"
: > "$TRAVAIL/liste_muette.txt"
for i in $(seq 1 "$N"); do
  n=$(printf '%02d' "$i")
  # audio : voix, silence avant/après, format PCM uniforme (concat propre)
  "$FFMPEG" -y -loglevel error -i "$TRAVAIL/voix$n.mp3" \
    -af "adelay=$(python3 -c "print(int($SILENCE_DEBUT*1000))")|$(python3 -c "print(int($SILENCE_DEBUT*1000))"),apad=pad_dur=${SILENCE_FIN}" \
    -ar 44100 -ac 2 -sample_fmt s16 "$TRAVAIL/aud$n.wav"
  dur=$("$FFPROBE" -v error -show_entries format=duration -of default=nw=1:nk=1 "$TRAVAIL/aud$n.wav")
  # vidéo SANS son, calée exactement sur la durée de l'audio de la slide
  "$FFMPEG" -y -loglevel error -loop 1 -framerate 30 -t "$dur" -i "$TRAVAIL/slide$n.png" \
    -c:v libx264 -preset medium -tune stillimage -crf 20 -pix_fmt yuv420p \
    -an "$TRAVAIL/vid$n.mp4"
  # variante muette : durée fixe
  "$FFMPEG" -y -loglevel error -loop 1 -framerate 30 -t "$SEC_MUETTE" -i "$TRAVAIL/slide$n.png" \
    -c:v libx264 -preset medium -tune stillimage -crf 20 -pix_fmt yuv420p \
    "$TRAVAIL/mut$n.mp4"
  echo "file 'vid$n.mp4'" >> "$TRAVAIL/liste_video.txt"
  echo "file 'aud$n.wav'" >> "$TRAVAIL/liste_audio.txt"
  echo "file 'mut$n.mp4'" >> "$TRAVAIL/liste_muette.txt"
  printf '  séquence %2d/%d\n' "$i" "$N"
done

# ── 4. Assemblage
# La v1 est la vidéo d'origine : on ne l'écrase jamais lors d'une reprise.
for f in demo_finance_hmd.mp4 demo_finance_hmd_muette.mp4; do
  v1="$SORTIE/${f%.mp4}_v1.mp4"
  if [ -f "$SORTIE/$f" ] && [ ! -f "$v1" ]; then
    mv "$SORTIE/$f" "$v1" && echo "  sauvegarde → $(basename "$v1")"
  fi
done

# vidéo continue (copie, sans son) + piste audio continue (WAV concaténés)
"$FFMPEG" -y -loglevel error -f concat -safe 0 -i "$TRAVAIL/liste_video.txt" \
  -c copy -an "$TRAVAIL/video_muet.mp4"
"$FFMPEG" -y -loglevel error -f concat -safe 0 -i "$TRAVAIL/liste_audio.txt" \
  -c copy "$TRAVAIL/voix_totale.wav"
# mux unique : vidéo copiée, AAC encodé UNE seule fois sur toute la piste
"$FFMPEG" -y -loglevel error -i "$TRAVAIL/video_muet.mp4" -i "$TRAVAIL/voix_totale.wav" \
  -c:v copy -c:a aac -b:a 160k -ar 44100 -shortest \
  -movflags +faststart "$SORTIE/demo_finance_hmd.mp4"

# muette : concat simple (aucun son, aucune jointure audio à craindre)
"$FFMPEG" -y -loglevel error -f concat -safe 0 -i "$TRAVAIL/liste_muette.txt" \
  -c copy -movflags +faststart "$SORTIE/demo_finance_hmd_muette.mp4"

for f in demo_finance_hmd.mp4 demo_finance_hmd_muette.mp4; do
  d=$("$FFPROBE" -v error -show_entries format=duration -of default=nw=1:nk=1 "$SORTIE/$f")
  printf '✓ %-30s %s  (%s)\n' "$f" "$(du -h "$SORTIE/$f" | cut -f1)" \
    "$(python3 -c "d=float('$d');print(f'{int(d//60)} min {int(d%60):02d} s')")"
done
