#!/usr/bin/env python3
"""Collecte l'activité HMD AGRO d'une fenêtre de temps pour préparer le daily.

Sources :
  1. les transcripts des sessions Claude Code (~/.claude/projects/*hmd*agro*)
  2. le journal git du dépôt (commits + travail non commité)
  3. les dailies déjà postés (.claude/daily/*.md) pour ne pas se répéter

Sortie : un digest markdown compact, destiné à être lu par le modèle.

Usage :
  python3 collect_activity.py                 # depuis hier 00h00 jusqu'à maintenant
  python3 collect_activity.py --days 3        # les 3 derniers jours
  python3 collect_activity.py --since 2026-08-04 --until 2026-08-06
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

HOME = os.path.expanduser("~")
PROJECTS_DIR = os.path.join(HOME, ".claude", "projects")
TICKET_RE = re.compile(r"\b(?:SCRUM|FIN-S|FIN|HMD)-?\d+\b", re.I)
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
MAX_PROMPT = 260
MAX_PROMPTS_PER_SESSION = 14


def parse_day(s):
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=None)


def to_local(ts):
    """'2026-08-05T11:31:55.487Z' -> datetime naïf en heure locale."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().replace(tzinfo=None)


def project_dirs():
    """Répertoires de transcripts dont le nom évoque le projet hmd agro."""
    out = []
    for path in sorted(glob.glob(os.path.join(PROJECTS_DIR, "*"))):
        if not os.path.isdir(path):
            continue
        slug = os.path.basename(path).lower().replace("_", "-")
        if "hmd" in slug and "agro" in slug:
            out.append(path)
    return out


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [c.get("text", "") for c in content
                 if isinstance(c, dict) and c.get("type") == "text"]
        return "\n".join(p for p in parts if p)
    return ""


def clean_prompt(txt):
    """Retire les blocs injectés par le harness, garde ce que l'humain a écrit."""
    txt = re.sub(r"<(system-reminder|command-message|local-command-stdout)[\s\S]*?"
                 r"</\1>", " ", txt)
    txt = re.sub(r"<[^>]{1,40}>", " ", txt)
    return " ".join(txt.split())


def scan_session(path, since, until):
    """Extrait d'un .jsonl : titre, prompts humains, fichiers touchés, todos, tickets."""
    s = {
        "file": path,
        "title": None,
        "prompts": [],
        "files": [],
        "todos": [],
        "tickets": set(),
        "first": None,
        "last": None,
        "branches": set(),
    }
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return None
    with fh:
        for line in fh:
            try:
                d = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            typ = d.get("type")
            if typ == "ai-title":
                s["title"] = d.get("aiTitle")
                continue
            if typ not in ("user", "assistant"):
                continue
            if d.get("isSidechain"):
                continue
            when = to_local(d.get("timestamp", "")) if d.get("timestamp") else None
            if when is None or not (since <= when < until):
                continue
            s["first"] = when if s["first"] is None else min(s["first"], when)
            s["last"] = when if s["last"] is None else max(s["last"], when)
            if d.get("gitBranch"):
                s["branches"].add(d["gitBranch"])

            msg = d.get("message") or {}
            if typ == "user":
                if (d.get("origin") or {}).get("kind") != "human":
                    continue
                txt = clean_prompt(text_of(msg.get("content")))
                if not txt:
                    continue
                s["tickets"].update(t.upper() for t in TICKET_RE.findall(txt))
                s["prompts"].append((when, txt[:MAX_PROMPT]))
                continue

            for c in msg.get("content") or []:
                if not isinstance(c, dict) or c.get("type") != "tool_use":
                    continue
                name, inp = c.get("name"), c.get("input") or {}
                if name in EDIT_TOOLS and inp.get("file_path"):
                    s["files"].append(inp["file_path"])
                elif name == "TodoWrite":
                    s["todos"] = inp.get("todos") or s["todos"]
    if s["first"] is None:
        return None
    return s


def git(repo, *args):
    try:
        r = subprocess.run(("git", "-C", repo) + args, capture_output=True,
                           text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def git_section(repo, since, until):
    fmt = "%h %ad %an %s"
    log = git(repo, "log", "--all", "--date=format:%Y-%m-%d %H:%M",
              f"--since={since:%Y-%m-%d %H:%M}", f"--until={until:%Y-%m-%d %H:%M}",
              f"--pretty=format:{fmt}")
    out = ["## Git", f"branche courante : {git(repo, 'rev-parse', '--abbrev-ref', 'HEAD') or '?'}"]
    out.append("\n### Commits de la fenêtre")
    out.append(log if log else "(aucun commit dans la fenêtre)")
    status = git(repo, "status", "--porcelain")
    tracked = [l for l in status.splitlines() if not l.startswith("??")]
    untracked = [l for l in status.splitlines() if l.startswith("??")]
    out.append("\n### Travail non commité (fichiers suivis)")
    out.append("\n".join(tracked) if tracked else "(rien)")
    out.append(f"\n{len(untracked)} fichier(s) non suivi(s) — probablement des brouillons, "
               "ne pas les annoncer comme livrés.")
    unpushed = git(repo, "log", "--branches", "--not", "--remotes",
                   "--pretty=format:%h %s")
    out.append("\n### Commits locaux non poussés")
    out.append(unpushed if unpushed else "(rien — tout est poussé, ou pas de remote)")
    return "\n".join(out)


def previous_dailies(repo, limit=3):
    files = sorted(glob.glob(os.path.join(repo, ".claude", "daily", "*.md")))[-limit:]
    if not files:
        return "## Dailies déjà postés\n(aucun historique — c'est le premier)"
    chunks = ["## Dailies déjà postés (ne pas répéter, vérifier les promesses tenues)"]
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                chunks.append(f"### {os.path.basename(f)}\n{fh.read().strip()[:1200]}")
        except OSError:
            continue
    return "\n\n".join(chunks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="AAAA-MM-JJ (défaut : hier 00h00)")
    ap.add_argument("--until", help="AAAA-MM-JJ exclu (défaut : maintenant)")
    ap.add_argument("--days", type=int, help="raccourci : les N derniers jours")
    ap.add_argument("--repo", default=os.getcwd())
    args = ap.parse_args()

    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if args.since:
        since = parse_day(args.since)
    elif args.days:
        since = today - timedelta(days=args.days - 1)
    else:
        since = today - timedelta(days=1)
    until = parse_day(args.until) if args.until else now

    print(f"# Activité HMD AGRO — {since:%Y-%m-%d %H:%M} → {until:%Y-%m-%d %H:%M}")
    print(f"(généré le {now:%Y-%m-%d %H:%M}, heure locale)\n")

    sessions = []
    for pdir in project_dirs():
        for path in sorted(glob.glob(os.path.join(pdir, "*.jsonl"))):
            s = scan_session(path, since, until)
            if s:
                sessions.append(s)
    sessions.sort(key=lambda s: s["first"])

    print(f"## Sessions Claude ({len(sessions)} dans la fenêtre)\n")
    if not sessions:
        print("(aucune session — s'appuyer sur git et demander à l'utilisateur)\n")
    all_tickets = set()
    for s in sessions:
        all_tickets |= s["tickets"]
        title = s["title"] or "(sans titre)"
        print(f"### {s['first']:%d/%m %H:%M}–{s['last']:%H:%M} · {title}")
        print(f"session : {os.path.basename(s['file'])[:8]} · "
              f"branche(s) : {', '.join(sorted(s['branches'])) or '?'}")
        if s["tickets"]:
            print(f"tickets cités : {', '.join(sorted(s['tickets']))}")
        if s["prompts"]:
            print("\nDemandes de l'utilisateur :")
            kept = s["prompts"][:MAX_PROMPTS_PER_SESSION]
            for when, txt in kept:
                print(f"- [{when:%H:%M}] {txt}")
            if len(s["prompts"]) > len(kept):
                print(f"- … et {len(s['prompts']) - len(kept)} autre(s) demande(s)")
        files = list(dict.fromkeys(s["files"]))
        if files:
            print(f"\nFichiers écrits/modifiés ({len(files)}) :")
            for f in files[:25]:
                print(f"- {f}")
            if len(files) > 25:
                print(f"- … et {len(files) - 25} autre(s)")
        todos = [t for t in s["todos"] if isinstance(t, dict)]
        if todos:
            print("\nDernière liste de tâches de la session :")
            for t in todos[:20]:
                mark = {"completed": "x", "in_progress": "~"}.get(t.get("status"), " ")
                print(f"- [{mark}] {t.get('content', '')[:120]}")
        print()

    if all_tickets:
        print(f"## Tickets mentionnés sur la fenêtre\n{', '.join(sorted(all_tickets))}\n")

    print(git_section(args.repo, since, until))
    print()
    print(previous_dailies(args.repo))


if __name__ == "__main__":
    sys.exit(main())
