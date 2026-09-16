# Vaccination tracking — approach & decisions

## What the task needs
Record vaccinations: **which animal**, **which vaccine product**, the **date given**, and the **next-due date**.

## Solution: a new `Vaccination` DocType
A new DocType is the right tool — it mirrors the existing per-animal event records
(`Insemination`, `Traitement`, `Pesee`, `Avortement`, etc.), each of which is a
standalone DocType that links to `Animal` plus a date. I copied that exact structure
so the new doctype is indistinguishable in style from the rest of the app.

### Files (drop into `hmd_agro/hmd_agro/doctype/vaccination/`)
| File | Purpose |
|------|---------|
| `vaccination.json` | DocType schema (the core deliverable) |
| `vaccination.py` | Controller — server-side validation |
| `vaccination.js` | Form script — link filters, lock animal when prefilled |
| `vaccination_list.js` | List view setting (hide name column, matching siblings) |
| `__init__.py` | Empty package marker (every doctype folder has one) |

### Field mapping (the 4 requested fields)
| Requested | Fieldname | Type |
|-----------|-----------|------|
| which animal | `animal` | Link → `Animal` (reqd) |
| which vaccine product | `vaccin` | Link → `Medicament` (reqd) |
| date given | `date_vaccination` | Date, default `Today` (reqd) |
| next-due date | `date_prochaine` | Date |

Plus `observations` (Small Text) — every event doctype in this app has one, so I
kept it for consistency.

## Key decisions
- **"Vaccine product" = `Medicament`, not a new master.** The app already has a
  `Medicament` doctype whose `type_medicament` Select includes `VACCIN`
  (see `medicament.json`). Vaccines are already modeled there, so `vaccin` links to
  `Medicament` and both the JS query filter and the Python `validate()` restrict it
  to `type_medicament == "VACCIN"`. This avoids a duplicate product master and reuses
  the existing stock/Item wiring on `Medicament`.
- **Naming series `VAC-{YYYY}-{#####}`** — matches `Traitement`'s
  `TRT-{YYYY}-{#####}` expression style. `title_field` is `animal` like the sibling
  event doctypes.
- **`date_vaccination` defaults to `Today`** — same as `Traitement.date_traitement`,
  since vaccinations are usually entered the day they happen.
- **`next-due` left optional and free-form.** The task says "record" the next-due
  date, so the user enters it. I did **not** auto-compute it, because there is no
  per-vaccine interval field in `Medicament` to derive it from, and inventing one
  would be gold-plating. The only rule enforced is that, when present, it must be
  **after** the date given (`validate_dates`).
- **Validation kept minimal and idiomatic** — `frappe.throw` with French messages,
  matching `insemination.py` / `traitement.py`. No over-engineering (no state
  machine, no stock decrement — vaccines-as-stock is out of scope here).
- **Permissions**: `System Manager` only, identical to the other event doctypes.

## Wiring / install notes (no bench run performed, per instructions)
- Dropping the folder under `hmd_agro/hmd_agro/doctype/vaccination/` and running
  `bench --site <site> migrate` (or restarting in developer mode) registers the
  doctype. The `module` is `HMD AGRO`, already in `modules.txt`.
- **Optional, not required:** to surface it like other animal activities, add an
  "Activité" button on the Animal form — see `animal_button_snippet.js`. This edits
  an existing app file, so it is provided as a snippet rather than applied (and the
  app must not be modified in this eval).

## How a user records a vaccination
New `Vaccination` → pick the **Animal**, pick the **Vaccin** (dropdown shows only
VACCIN médicaments), the **Date de Vaccination** defaults to today, optionally set
the **Prochaine échéance** (next-due), save.
