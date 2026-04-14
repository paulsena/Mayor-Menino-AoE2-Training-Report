# AoE2 Replay Analyzer

A Python tool that parses Age of Empires 2: Definitive Edition replay files (`.aoe2record`) and generates an interactive HTML dashboard with performance stats, trends, and visualizations.

## Features

- **Automatic savegame detection** - finds your AoE2 DE replay folder automatically
- **Per-game analysis**:
  - Age-up times (Feudal, Castle, Imperial) with skill benchmarks
  - Villager counts at key intervals and age-ups
  - Idle TC estimation
  - APM tracking over time
  - Military production breakdown
  - Build order timeline
- **Cross-game trends** with Chart.js visualizations:
  - Age-up time progression
  - Villager economy trends
  - APM improvements
  - Win/loss tracking
  - Civilization usage pie chart
- **Self-contained HTML output** - shareable single-file dashboard

## Installation

```bash
# Clone the repository
git clone https://github.com/PaulSena/Mayor-Menino-AoE2-Training-Report.git
cd aoe2-replay-analyzer

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Required Patches for mgz Library

The `mgz` library (PyPI version 1.8.51) does not support AoE2 DE save version 67.x+ out of the box. **Multiple patches are required** after installing.

**Do NOT install mgz from git** (`pip install git+https://github.com/happyleavesaoc/aoc-mgz.git`) - the git version breaks parsing for all current replays due to unrelated regressions.

**Files to patch:**
- `site-packages/mgz/util.py` - Add buffer size validation to `unpack()` function
- `site-packages/mgz/fast/header.py` - Multiple changes for save version 67.x support

**Quick summary of patches:**
1. Add `MAX_UNPACK_SIZE` validation in `util.py` to prevent memory errors
2. Add `MAX_STRING_LENGTH` validation in string functions
3. Skip `parse_mod` for non-USERPATCH15 versions
4. Add `de_string(data)` in player loop for save >= 67
5. Add `scenario_name` extraction from USER:SCENARIOS strings
6. Add `settings_version = 4.7` for save >= 67
7. Add `data.read(30)` before instructions for save >= 67
8. Wrap trigger parsing in try/except
9. Add scenario/lobby fallback in main `parse()` function

**See [CLAUDE.md](CLAUDE.md) for complete patch details with code snippets.**

These patches fix:
- Buffer allocation errors on corrupted files
- Parse failures on save version 67.x replays
- Custom scenario map name extraction

## Usage

```bash
# Auto-detect AoE2 savegame folder and analyze all multiplayer replays
python analyze.py

# Analyze replays in a specific directory
python analyze.py --dir "C:\path\to\replays"

# Analyze a single replay file
python analyze.py game.aoe2record

# Include single-player replays (skipped by default)
python analyze.py --include-sp

# Specify output file (default: docs/dashboard.html)
python analyze.py --output my_dashboard.html
```

### Options

| Option | Description |
|--------|-------------|
| `--dir <path>` | Directory containing `.aoe2record` files |
| `--output <path>` | Output HTML file (default: `docs/dashboard.html`) |
| `--include-sp` | Include single-player replays (skipped by default) |
| `--help` | Show help message |

## Output

The tool generates an interactive HTML dashboard with:

- **Overview tab**: Summary stats for each game
- **Game details**: Expandable cards with age-up times, villager counts, military production
- **Trends tab**: Charts showing improvement over time
- **Benchmarks**: Color-coded skill ratings for age-up times
  - Excellent (green): Feudal < 8:00, Castle < 16:00
  - Great (lime): Feudal < 9:00, Castle < 18:00
  - Good (yellow): Feudal < 10:00, Castle < 21:00
  - Average (orange): Feudal < 12:00, Castle < 25:00

## Project Structure

```
aoe2/
├── analyze.py      # CLI entry point
├── parser.py       # Replay file parser (uses mgz.fast)
├── stats.py        # Stats computation and benchmarks
├── dashboard.py    # HTML dashboard generator
├── templates/
│   └── dashboard.html  # HTML template with Chart.js
├── docs/
│   └── dashboard.html  # Generated output
└── requirements.txt
```

## Known Limitations

- Replay timestamps are in real-time; the tool converts to game time using the speed multiplier
- Some severely corrupted replay files may still fail to parse (rare)

## Dependencies

- Python 3.8+
- [mgz](https://pypi.org/project/mgz/) >= 1.8.51 (with patch applied)
- [aocref](https://pypi.org/project/aocref/) (installed as mgz dependency)

## License

GPL-3.0 - See [LICENSE](LICENSE) for details.
