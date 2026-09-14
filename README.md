# AC Career Ramp

> **Folded into Verve (September 2026).** Everything this tool did is now built into
> [Verve](https://github.com/ververacing/verve): Verve reads the difficulty meter and each career event's own
> level at runtime and applies them to the AI itself -- nothing on disk is edited, the meter finally means
> something (AC ignores the per-event level on some installs), and the ramp across the career is an option
> in the Verve window. This repository is kept for reference and is archived.

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
app like [Verve](https://github.com/ververacing/verve), which adds mistakes and personality so
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
| `--offset`      | 0  | **the simple slider** — shift the WHOLE career up/down by this many AI levels |
| `--floor-start` | 83 | first module's floor AI level |
| `--floor-end`   | 91 | last module's floor AI level |
| `--module-ramp` | 7  | how much a module climbs from its first event to its last |
| `--ceiling`     | 97 | hard cap — no event's strongest opponent exceeds this |
| `--floor-min`   | 80 | never go below this |
| `--calib`       | 0.5| how much to lean on Kunos's own per-event tuning (0 = pure ramp, 1 = full) |

The default (no flags) is a curated curve that works well across the whole career — most people
never need to touch anything. If you *do* want to nudge it, `--offset` is the one-number dial:

```bash
python career_ramp.py apply --offset 3     # whole career 3 levels harder
python career_ramp.py apply --offset -4    # whole career 4 levels easier
```

`--calib` blends in Kunos's original per-event difficulty so events that were hand-made tougher
(a tricky car/track) stay proportionally tougher, without changing the overall progression. The
other flags reshape the curve itself if you want finer control:

```bash
# push the final seasons just past 100 (best with an AI-humaniser like Verve running)
python career_ramp.py apply --floor-end 96 --ceiling 102

# flat, consistently strong difficulty with no ramp
python career_ramp.py apply --floor-start 95 --floor-end 95 --module-ramp 0 --ceiling 95
```

## Works alongside Verve (or any CSP AI app)

This tool only sets the *number* each career race runs at — it doesn't change how the AI drives.
So an AI-behaviour app like [Verve](https://github.com/ververacing/verve) is fully active in
career races and stacks cleanly on top: the ramp sets the difficulty tier, Verve makes that field
feel human (variability, mistakes, cleaner racecraft, fewer silly retirements). They don't fight —
Verve only overrides a car's AI level when you assign it a driver profile, which career doesn't do
by default, so the ramped values stand. Because Verve humanises even a strong field, you can
comfortably run this a notch harder (`--offset 2..4`) than you would against bare AC AI.

## How it works / safety

- Only `AI_LEVEL` values inside `content/career/seriesN/eventM/event.ini` are edited. Nothing
  else in the game is touched.
- Files are edited byte-for-byte apart from the numbers, so formatting, comments and line
  endings are preserved.
- Backups live in `backups/` next to the script: `backups/original/` is the pristine copy
  (written once and never overwritten), plus a timestamped snapshot each time you apply.
- `restore` copies `backups/original/` back over the career.

Not affiliated with Kunos Simulazioni. Edits your own local game files only.
