# AC Career Ramp

Makes the **Assetto Corsa single-player career** actually engaging and *progressively* harder.

Vanilla AC hard-codes each career event's AI difficulty (`AI_LEVEL` in every `event.ini`) and
ships almost the whole career at **~78–89** — so it never gets genuinely challenging, and the
final seasons feel no harder than the first. This tool rewrites `AI_LEVEL` across all **176
events** on a two-level ramp:

- **Within each series (a "module"/season):** gentle on event 1, hard on the last event.
- **Across the career:** each module's floor creeps up, so later seasons are tougher overall.

The default ceiling is **97, deliberately below 100**. Vanilla AC AI near 100 isn't "alien"
because it's fast — it's alien because it's flawless and metronomic. Topping out around 97 keeps
it hard without tipping into robot territory. (It pairs especially well with an AI-humanising
app like [Verve](https://github.com/tyleebs-hub/verve), which adds mistakes and personality so
even the top of the ramp feels like a real human field.)

It also **preserves AC's opponent stagger.** Many events give each opponent its own `AI_LEVEL`
(e.g. 87, 86, 86, 85 … down to 81) so the field isn't identical. The tool shifts that whole set
up together, so the strongest opponent lands on the ramp target while the varied spread is kept.

Everything is **reversible** — the first run saves a pristine copy of every original file.

## Requirements

- Python 3.8+
- Assetto Corsa installed

## Usage

```bash
# see exactly what it would change, without touching anything
python career_ramp.py plan

# back up the originals, then apply the ramp
python career_ramp.py apply

# undo — put every original event.ini back
python career_ramp.py restore
```

If your AC isn't found automatically, point at it:

```bash
python career_ramp.py apply --ac "D:\SteamLibrary\steamapps\common\assettocorsa"
```

## Tuning the curve

All values are flags (defaults shown). Re-run `apply` any time — it always shifts from the
pristine originals, so you can retune freely without stacking changes.

| Flag | Default | Meaning |
|------|---------|---------|
| `--floor-start` | 83 | first module's floor AI level |
| `--floor-end`   | 91 | last module's floor AI level |
| `--module-ramp` | 7  | how much a module climbs from its first event to its last |
| `--ceiling`     | 97 | hard cap — no event's strongest opponent exceeds this |
| `--floor-min`   | 80 | never go below this |

Examples:

```bash
# harder overall, pushing just past 100 for the final seasons (best with Verve running)
python career_ramp.py apply --floor-start 88 --floor-end 96 --ceiling 102

# flat, consistently strong difficulty with no ramp
python career_ramp.py apply --floor-start 95 --floor-end 95 --module-ramp 0 --ceiling 95
```

## How it works / safety

- Only `AI_LEVEL` values inside `content/career/seriesN/eventM/event.ini` are edited. Nothing
  else in the game is touched.
- Files are edited byte-for-byte apart from the numbers, so formatting, comments and line
  endings are preserved.
- Backups live in `backups/` next to the script: `backups/original/` is the pristine copy
  (written once and never overwritten), plus a timestamped snapshot each time you apply.
- `restore` copies `backups/original/` back over the career.

Not affiliated with Kunos Simulazioni. Edits your own local game files only.
