#!/usr/bin/env python3
"""
AC Career Ramp -- makes the Assetto Corsa single-player career progressively harder.

Vanilla AC hard-codes every career event's AI difficulty (AI_LEVEL in each event.ini),
and ships almost the entire career at ~78-89 -- so it never gets genuinely challenging and
the later seasons feel no harder than the first. This tool rewrites AI_LEVEL across every
career event on a two-level ramp:

  * within each series (a "module"/season): gentle on the first event, hard on the last
  * across the career: each module's floor creeps up, so later seasons are tougher overall

The ceiling is deliberately kept below 100. Vanilla AC AI at ~100 isn't "alien" because it's
fast -- it's alien because it's flawless and metronomic. Topping out around 97 stays hard
without tipping into robot territory (and it pairs well with an AI-humanising app like Verve).

Everything is reversible: the first run saves a pristine copy of every original event.ini,
and `restore` puts them all back. Nothing else in the game is touched.

Usage:
  python career_ramp.py plan                 # dry run: print what each event would become
  python career_ramp.py apply                # back up originals, then rewrite AI_LEVEL
  python career_ramp.py restore              # put the original files back (undo)

Options (all have sensible defaults):
  --ac PATH            Assetto Corsa root folder (auto-detected if omitted)
  --floor-start N      first module's floor AI level         (default 83)
  --floor-end N        last module's floor AI level          (default 91)
  --module-ramp N      how much a module climbs start->end   (default 7)
  --ceiling N          hard cap -- never exceed this         (default 97)
  --floor-min N        never go below this                   (default 80)
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime

# ------------------------------------------------------------------ config

DEFAULTS = dict(floor_start=83, floor_end=91, module_ramp=7, ceiling=97, floor_min=80)

# Common install locations, tried in order when --ac isn't given.
GUESS_AC_PATHS = [
    r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa",
    r"C:\Program Files\Steam\steamapps\common\assettocorsa",
    r"D:\Steam\steamapps\common\assettocorsa",
    r"D:\SteamLibrary\steamapps\common\assettocorsa",
    r"E:\SteamLibrary\steamapps\common\assettocorsa",
]

AI_LINE_RE = re.compile(rb"(?i)^([ \t]*AI_LEVEL[ \t]*=[ \t]*)(\d+)(.*)$")   # one line
SECTION_RE = re.compile(rb"^\s*\[([^\]]+)\]")
SERIES_RE = re.compile(r"^series(\d+)$", re.IGNORECASE)
EVENT_RE = re.compile(r"^event(\d+)$", re.IGNORECASE)

HERE = os.path.dirname(os.path.abspath(__file__))
BACKUP_ROOT = os.path.join(HERE, "backups")
ORIGINAL_DIR = os.path.join(BACKUP_ROOT, "original")  # pristine, written once, never overwritten


# ------------------------------------------------------------------ helpers

def find_ac(explicit):
    if explicit:
        if os.path.isdir(os.path.join(explicit, "content", "career")):
            return explicit
        sys.exit(f"error: no content\\career under --ac path: {explicit}")
    for p in GUESS_AC_PATHS:
        if os.path.isdir(os.path.join(p, "content", "career")):
            return p
    sys.exit("error: couldn't auto-detect Assetto Corsa. Pass --ac \"<path to assettocorsa>\".")


def collect_events(career_dir):
    """Return an ordered list of modules: [{'series': name, 'events': [event.ini paths in order]}]."""
    series = []
    for name in os.listdir(career_dir):
        m = SERIES_RE.match(name)
        sdir = os.path.join(career_dir, name)
        if not m or not os.path.isdir(sdir):
            continue
        events = []
        for ename in os.listdir(sdir):
            em = EVENT_RE.match(ename)
            ini = os.path.join(sdir, ename, "event.ini")
            if em and os.path.isfile(ini):
                events.append((int(em.group(1)), ini))
        if events:
            events.sort(key=lambda t: t[0])
            series.append((int(m.group(1)), name, [ini for _, ini in events]))
    series.sort(key=lambda t: t[0])  # numeric career order (series0, series1, ... series10, ...)
    return [{"series": name, "events": evs} for _, name, evs in series]


def lerp(a, b, t):
    return a + (b - a) * t


def clampi(x, lo, hi):
    return max(lo, min(hi, x))


def plan_levels(modules, cfg):
    """Compute the target AI_LEVEL for every event. Returns list of dicts per event."""
    out = []
    S = len(modules)
    for si, mod in enumerate(modules):
        s_t = si / (S - 1) if S > 1 else 0.0
        floor = lerp(cfg["floor_start"], cfg["floor_end"], s_t)
        N = len(mod["events"])
        for ei, ini in enumerate(mod["events"]):
            e_t = (ei / (N - 1)) if N > 1 else 0.0     # single-event module sits at its floor
            raw = floor + cfg["module_ramp"] * e_t
            lvl = clampi(int(round(raw)), cfg["floor_min"], cfg["ceiling"])
            out.append({"series": mod["series"], "event_idx": ei, "n_events": N, "ini": ini, "level": lvl})
    return out


# AC events can carry MANY AI_LEVEL lines: a default in [RACE], plus a per-opponent one in each
# [CAR_1], [CAR_2]... block. Vanilla staggers those (e.g. 87, 86, 86, 85, ... down to 81) so the
# field isn't identical -- a nice detail we PRESERVE. We shift the whole set by one delta so the
# STRONGEST opponent lands on the ramp target, keeping the vanilla spread but raising the level.

def parse_entries(data):
    """Return (lines, entries) where entries = [(line_idx, value, SECTION_upper_bytes), ...]."""
    lines = data.split(b"\n")
    section = b""
    entries = []
    for idx, line in enumerate(lines):
        h = SECTION_RE.match(line)
        if h:
            section = h.group(1).upper()
            continue
        m = AI_LINE_RE.match(line)
        if m:
            entries.append((idx, int(m.group(2)), section))
    return lines, entries


def anchor_of(entries):
    """The strongest opponent: max of the [CAR_*] values, else the max of whatever's present."""
    if not entries:
        return None
    car = [v for (_, v, s) in entries if s.startswith(b"CAR_")]
    return max(car) if car else max(v for (_, v, _) in entries)


def read_anchor(ini):
    with open(ini, "rb") as f:
        _lines, entries = parse_entries(f.read())
    return anchor_of(entries), len(entries)


def apply_event(ini, target, cfg):
    """Shift every AI_LEVEL so the strongest opponent = target (preserving spread). Returns
    (old_anchor, new_anchor, n_lines_changed) or (None, None, 0) if the file has no AI_LEVEL."""
    with open(ini, "rb") as f:
        data = f.read()
    lines, entries = parse_entries(data)
    if not entries:
        return None, None, 0
    anchor = anchor_of(entries)
    delta = target - anchor
    for (idx, val, _sec) in entries:
        newv = clampi(val + delta, cfg["floor_min"], cfg["ceiling"])
        m = AI_LINE_RE.match(lines[idx])
        lines[idx] = m.group(1) + str(newv).encode() + m.group(3)
    new = b"\n".join(lines)
    if new != data:
        with open(ini, "wb") as f:
            f.write(new)
    return anchor, clampi(anchor + delta, cfg["floor_min"], cfg["ceiling"]), len(entries)


def rel_to_career(career_dir, ini):
    return os.path.relpath(ini, career_dir)


# ------------------------------------------------------------------ commands

def cmd_plan(args, cfg, ac, career_dir):
    modules = collect_events(career_dir)
    rows = plan_levels(modules, cfg)
    print(f"Assetto Corsa: {ac}")
    print(f"Modules (series): {len(modules)}   Events: {len(rows)}")
    print(f"Curve: floor {cfg['floor_start']}->{cfg['floor_end']}, module ramp +{cfg['module_ramp']}, "
          f"cap {cfg['ceiling']}, min {cfg['floor_min']}\n")
    cur = None
    for r in rows:
        if r["series"] != cur:
            cur = r["series"]
            print(f"  {cur}:")
        old, nlines = read_anchor(r["ini"])
        old_s = str(old) if old is not None else "--"
        opp = f"{r['n_events']}ev, {nlines}x" if nlines > 1 else f"{r['n_events']}ev"
        name = rel_to_career(career_dir, r["ini"])
        print(f"    event {r['event_idx']+1:<2} top opp {old_s:>3} -> {r['level']:<3}  ({opp})  {name}")
    lvls = [r["level"] for r in rows]
    print(f"\nStrongest-opponent range: {min(lvls)}..{max(lvls)}   (nothing exceeds the {cfg['ceiling']} cap)")
    print("Each event's full field is shifted by one step, so the vanilla stagger (varied opponents) is kept.")


def save_originals(career_dir, rows):
    """Write a pristine backup of every event.ini once. Also a timestamped snapshot each apply."""
    first_time = not os.path.isdir(ORIGINAL_DIR)
    stamp_dir = os.path.join(BACKUP_ROOT, datetime.now().strftime("%Y%m%d-%H%M%S"))
    for r in rows:
        rel = rel_to_career(career_dir, r["ini"])
        if first_time:
            dst = os.path.join(ORIGINAL_DIR, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(r["ini"], dst)
        snap = os.path.join(stamp_dir, rel)
        os.makedirs(os.path.dirname(snap), exist_ok=True)
        shutil.copy2(r["ini"], snap)
    manifest = dict(ac=career_dir_to_ac(career_dir), career_dir=career_dir,
                    when=datetime.now().isoformat(timespec="seconds"),
                    files=[rel_to_career(career_dir, r["ini"]) for r in rows])
    with open(os.path.join(stamp_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return first_time, stamp_dir


def career_dir_to_ac(career_dir):
    return os.path.dirname(os.path.dirname(career_dir))


def cmd_apply(args, cfg, ac, career_dir):
    modules = collect_events(career_dir)
    rows = plan_levels(modules, cfg)
    if not rows:
        sys.exit("error: no career events found.")
    first_time, stamp_dir = save_originals(career_dir, rows)
    changed = 0
    for r in rows:
        _old, _new, n = apply_event(r["ini"], r["level"], cfg)
        if n > 0:
            changed += 1
    lvls = [r["level"] for r in rows]
    print(f"Applied to {changed}/{len(rows)} events across {len(modules)} modules.")
    print(f"Strongest opponent now ramps {min(lvls)}..{max(lvls)} across the career (was ~78-89 vanilla),")
    print("with each event's staggered field shifted up together so opponents stay varied.")
    if first_time:
        print(f"Pristine originals saved to: {os.path.relpath(ORIGINAL_DIR, HERE)}")
    print(f"Snapshot: {os.path.relpath(stamp_dir, HERE)}")
    print("Undo any time with:  python career_ramp.py restore")


def cmd_restore(args, cfg, ac, career_dir):
    if not os.path.isdir(ORIGINAL_DIR):
        sys.exit("error: no original backup found -- nothing to restore (have you run apply?).")
    restored = 0
    for root, _dirs, files in os.walk(ORIGINAL_DIR):
        for fn in files:
            src = os.path.join(root, fn)
            rel = os.path.relpath(src, ORIGINAL_DIR)
            dst = os.path.join(career_dir, rel)
            if os.path.isfile(dst):
                shutil.copy2(src, dst)
                restored += 1
    print(f"Restored {restored} original event.ini files. Career is back to vanilla.")


# ------------------------------------------------------------------ main

def build_parser():
    p = argparse.ArgumentParser(description="Make the AC career progressively harder (edits AI_LEVEL).")
    p.add_argument("command", choices=["plan", "apply", "restore"],
                   help="plan = dry run; apply = back up + rewrite; restore = undo")
    p.add_argument("--ac", default=None, help="Assetto Corsa root folder (auto-detected if omitted)")
    p.add_argument("--floor-start", type=int, default=DEFAULTS["floor_start"])
    p.add_argument("--floor-end", type=int, default=DEFAULTS["floor_end"])
    p.add_argument("--module-ramp", type=int, default=DEFAULTS["module_ramp"])
    p.add_argument("--ceiling", type=int, default=DEFAULTS["ceiling"])
    p.add_argument("--floor-min", type=int, default=DEFAULTS["floor_min"])
    return p


def main():
    args = build_parser().parse_args()
    cfg = dict(floor_start=args.floor_start, floor_end=args.floor_end,
               module_ramp=args.module_ramp, ceiling=args.ceiling, floor_min=args.floor_min)
    ac = find_ac(args.ac)
    career_dir = os.path.join(ac, "content", "career")
    {"plan": cmd_plan, "apply": cmd_apply, "restore": cmd_restore}[args.command](args, cfg, ac, career_dir)


if __name__ == "__main__":
    main()
