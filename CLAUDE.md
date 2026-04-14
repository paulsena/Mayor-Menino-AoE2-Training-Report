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

## mgz Library Patches (IMPORTANT)

The `mgz` library (PyPI version 1.8.51) does **not** support AoE2 DE save version 67.x+ out of the box. Multiple patches are required.

**Do NOT upgrade mgz from git** (`pip install git+https://github.com/happyleavesaoc/aoc-mgz.git`) - the git version breaks parsing for ALL current replays due to unrelated regressions.

**After reinstalling mgz** (`pip install mgz`), you must re-apply ALL patches below.

### Patch 1: mgz/util.py - Buffer size validation

Add size validation to prevent memory allocation errors on corrupted files.

```python
# Around line 319, REPLACE the unpack function:

MAX_UNPACK_SIZE = 65536  # 64KB max for any single unpack operation

def unpack(fmt, data, shorten=True):
    """Unpack bytes according to format string."""
    size = struct.calcsize(fmt)
    if size > MAX_UNPACK_SIZE:
        raise ValueError(f"unpack size too large: {size} bytes (max {MAX_UNPACK_SIZE})")
    output = struct.unpack(fmt, data.read(size))
    if len(output) == 1 and shorten:
        return output[0]
    return output
```

### Patch 2: mgz/fast/header.py - String length validation

Add constant after SKIP_OBJECTS (around line 20):

```python
# Maximum sane string length to prevent buffer allocation errors on corrupt files
MAX_STRING_LENGTH = 65536
```

Modify string functions to validate lengths:

```python
def aoc_string(data):
    """Read AOC string."""
    length = unpack('<h', data)
    if length < 0 or length > MAX_STRING_LENGTH:
        raise ValueError(f"invalid string length: {length}")
    return data.read(length)

def int_prefixed_string(data):
    """Read length prefixed (4 byte) string."""
    length = unpack('<I', data)
    if length > MAX_STRING_LENGTH:
        raise ValueError(f"invalid string length: {length}")
    return data.read(length)

def de_string(data):
    """Read DE string."""
    assert data.read(2) == b'\x60\x0a'
    length = unpack('<h', data)
    if length < 0 or length > MAX_STRING_LENGTH:
        raise ValueError(f"invalid string length: {length}")
    return unpack(f'<{length}s', data)

def hd_string(data):
    """Read HD string."""
    length = unpack('<h', data)
    if length < 0 or length > MAX_STRING_LENGTH:
        raise ValueError(f"invalid string length: {length}")
    assert data.read(2) == b'\x60\x0a'
    return unpack(f'<{length}s', data)
```

### Patch 3: mgz/fast/header.py - Skip parse_mod for DE

Add early return at start of `parse_mod` function:

```python
def parse_mod(header, num_players, version):
    """Parse Userpatch mod version."""
    # Only needed for USERPATCH15; skip for other versions to avoid parse errors
    if version is not Version.USERPATCH15:
        return None
    # ... rest of function unchanged
```

### Patch 4: mgz/fast/header.py - parse_de player loop

In the player loop (around line 469-471), add de_string for save >= 67:

```python
        if save >= 64.3:
            data.read(4)
        if save >= 67:          # <-- ADD THIS
            de_string(data)     # <-- ADD THIS

        players.append(dict(
```

### Patch 5: mgz/fast/header.py - parse_de scenario_name extraction

In `parse_de`, modify the strings loop (around line 580) to extract scenario names:

```python
    rms_mod_id = None
    rms_filename = None
    scenario_name = None  # <-- ADD THIS
    for s in strings:
        if s[0] == 'SUBSCRIBEDMODS' and s[1] == 'RANDOM_MAPS':
            rms_mod_id = s[3].split('_')[0]
            rms_filename = s[2]
        elif s[0] == 'USER' and s[1] == 'SCENARIOS':  # <-- ADD THIS BLOCK
            scenario_name = s[2]
```

Add `scenario_name=scenario_name,` to the return dict (after rms_filename).

### Patch 6: mgz/fast/header.py - parse_scenario fixes for save 67+

In `parse_scenario`, add settings_version 4.7 (around line 329):

```python
    if version is Version.DE:
        if save >= 67:              # <-- ADD THIS
            settings_version = 4.7  # <-- ADD THIS
        elif save >= 66.3:
            settings_version = 4.5
```

Add extra byte read before instructions (around line 302):

```python
    data.read(20)
    if save >= 67:
        data.read(30)  # extra bytes added in save 67: 6 + (6 x 4)
    instructions = aoc_string(data)
```

Wrap trigger parsing in try/except (around line 358):

```python
    if version is Version.DE:
        try:
            data.read(1)
            n_triggers = unpack("<I", data)
            # ... existing trigger parsing code ...
            data.read(1032)  # default!
        except (ValueError, struct.error):
            pass  # Skip trigger parsing if format is incompatible (e.g., save >= 67.2)
```

### Patch 7: mgz/fast/header.py - parse() fallback for scenario/lobby

In the main `parse` function, wrap scenario/lobby parsing with fallback:

```python
        players, mod, device = parse_players(header, num_players, version, save)
        # Scenario and lobby parsing can fail on newer save versions (67.2+)
        # due to changed trigger/effect structures. These sections are optional.
        try:
            scenario = parse_scenario(header, num_players, version, save)
            lobby = parse_lobby(header, version, save)
        except (struct.error, ValueError, AssertionError):
            # Use fallback values from DE header if available
            scenario = dict(
                map_id=de.get('rms_map_id', 0) if de else 0,
                difficulty_id=de.get('difficulty_id', -1) if de else -1,
                instructions=b'',
                scenario_filename=b'',
            )
            lobby = dict(
                reveal_map_id=0,
                map_size=0,
                population=de.get('population_limit', 200) if de else 200,
                game_type_id=0,
                lock_teams=de.get('lock_teams', False) if de else False,
                chat=[],
                seed=None,
            )
```

## Game speed notes

Replay timestamps are in **real-time milliseconds**. To convert to in-game time: `game_seconds = real_ms / 1000 * speed`. Common speeds: 1.5 = Normal, 1.7 = Fast (most common for this user's replays), 2.0 = Very Fast.
