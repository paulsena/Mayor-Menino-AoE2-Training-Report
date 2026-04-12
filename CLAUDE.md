# AoE2 Replay Analyzer

## Project Overview

Python tool that parses AoE2 DE `.aoe2record` replay files and generates an HTML dashboard with performance stats, trends, and visualizations.

**Entry point:** `python analyze.py` (auto-detects savegame folder)

## Architecture

- `parser.py` - Parses replay files using `mgz.fast` module. Extracts players, actions, timeseries (resource/object snapshots), and winner/loser detection.
- `stats.py` - Computes per-player stats (age-ups, villagers, military, APM, build order, timeseries summaries) and cross-game trends.
- `dashboard.py` - Generates self-contained HTML dashboard from stats.
- `templates/dashboard.html` - HTML template with embedded Chart.js visualizations. Data injected as JSON.
- `analyze.py` - CLI entry point that orchestrates parsing, stats, and dashboard generation.

## mgz Library Patch (IMPORTANT)

The `mgz` library (PyPI version 1.8.51) does **not** support AoE2 DE save version 67.x+ out of the box. A patch is required for the fast header parser.

**Do NOT upgrade mgz from git** (`pip install git+https://github.com/happyleavesaoc/aoc-mgz.git`) - the git version breaks parsing for ALL current replays due to unrelated regressions.

### How to apply the patch

Edit `venv/Lib/site-packages/mgz/fast/header.py`, in the `parse_de` function's player loop (around line 469-471). Add a `de_string(data)` call for save version >= 67:

```python
        if save >= 64.3:
            data.read(4)
        if save >= 67:          # <-- ADD THIS
            de_string(data)     # <-- ADD THIS

        players.append(dict(
```

Save version 67.x adds one extra `de_string` field per player entry. Without this patch, all DE replays with save version >= 67 will fail with `AssertionError` in `de_string`.

### Known limitations

- 4 replays with save version 67.2 fail in `parse_scenario` (not `parse_de`). This is a separate issue where the scenario parser runs out of data. These are edge cases (~12% of replays) and don't have a fix yet.
- 2 replays with save version 67.0 (`v101.103.38580.0`) have corrupt/truncated headers and can't be parsed at all.

### After reinstalling mgz

If you run `pip install mgz` or recreate the venv, you must re-apply the patch above. The patch is to the installed library in site-packages, not to project source files.

## Game speed notes

Replay timestamps are in **real-time milliseconds**. To convert to in-game time: `game_seconds = real_ms / 1000 * speed`. Common speeds: 1.5 = Normal, 1.7 = Fast (most common for this user's replays), 2.0 = Very Fast.
