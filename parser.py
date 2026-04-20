"""Parse AoE2 DE replay files using mgz fast parser."""

import json
import os
from datetime import datetime
from mgz.fast import header as fast_header
from mgz.fast import operation, meta, Operation, Action


# Load reference data for name lookups
_DATA_DIR = os.path.join(os.path.dirname(__file__), "venv", "Lib", "site-packages", "aocref", "data")
_DATASET_FILE = os.path.join(_DATA_DIR, "datasets", "100.json")
_CONSTANTS_FILE = os.path.join(_DATA_DIR, "constants.json")

def _load_ref_data():
    with open(_DATASET_FILE) as f:
        dataset = json.load(f)
    with open(_CONSTANTS_FILE) as f:
        constants = json.load(f)
    return dataset, constants

_dataset, _constants = _load_ref_data()

TECHNOLOGIES = _dataset["technologies"]
OBJECTS = _dataset["objects"]
CIVILIZATIONS = _dataset["civilizations"]
# Merge maps from multiple datasets for better coverage
MAPS = {}
for _ds_name in ["0", "100"]:
    _ds_path = os.path.join(_DATA_DIR, "datasets", f"{_ds_name}.json")
    if os.path.exists(_ds_path):
        with open(_ds_path) as _f:
            _ds = json.load(_f)
            MAPS.update(_ds.get("maps", {}))
# DE dataset takes priority (loaded second)

# Player type constants
PLAYER_TYPE_HUMAN = 2
PLAYER_TYPE_AI = 4

# Key technology IDs for age-ups
TECH_FEUDAL_AGE = 101
TECH_CASTLE_AGE = 102
TECH_IMPERIAL_AGE = 103

# Villager unit ID
UNIT_VILLAGER = 83

# Age research durations in milliseconds (at normal speed)
AGE_RESEARCH_DURATIONS = {
    TECH_FEUDAL_AGE: 130_000,
    TECH_CASTLE_AGE: 160_000,
    TECH_IMPERIAL_AGE: 190_000,
}

# Military unit IDs (non-exhaustive, covers common units)
MILITARY_UNIT_IDS = set()
_CIVILIAN_KEYWORDS = {"villager", "trade", "monk", "fishing", "transport", "farm", "lumber", "mining", "mill", "sheep", "turkey", "cow", "llama", "boar", "deer", "relic", "cart", "ship", "canoe", "galley", "missionary", "king", "hero"}
for _uid, _name in OBJECTS.items():
    if _name and not any(kw in _name.lower() for kw in _CIVILIAN_KEYWORDS):
        MILITARY_UNIT_IDS.add(int(_uid))
# Remove known non-military
MILITARY_UNIT_IDS.discard(UNIT_VILLAGER)


def get_tech_name(tech_id):
    return TECHNOLOGIES.get(str(tech_id), f"Unknown Tech {tech_id}")


def get_unit_name(unit_id):
    return OBJECTS.get(str(unit_id), f"Unknown Unit {unit_id}")


def get_civ_name(civ_id):
    civ = CIVILIZATIONS.get(str(civ_id))
    if civ:
        return civ["name"]
    return f"Unknown Civ {civ_id}"


def get_map_name(map_id):
    return MAPS.get(str(map_id), f"Custom Map ({map_id})")


def parse_replay(filepath):
    """Parse a single .aoe2record file and return structured data.

    Returns a dict with:
      - metadata: game info (map, duration, date, etc.)
      - players: list of player info dicts
      - actions: list of all parsed actions with timestamps
    """
    with open(filepath, "rb") as f:
        h = fast_header.parse(f)

        # Extract player info from both header sources
        players = []
        de_players = {dp["number"]: dp for dp in h["de"]["players"]}

        for p in h["players"]:
            number = p["number"]
            name = p["name"]
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace")

            # Skip Gaia (player 0)
            if number == 0:
                continue

            de_p = de_players.get(number, {})
            civ_id = de_p.get("civilization_id", p.get("civilization_id", 0))

            players.append({
                "number": number,
                "name": name,
                "civ_id": civ_id,
                "civ_name": get_civ_name(civ_id),
                "color_id": de_p.get("color_id", p.get("color_id", 0)),
                "team_id": de_p.get("team_id", -1),
                "type": de_p.get("type", p.get("type", 0)),
                "is_human": de_p.get("type", p.get("type", 0)) == PLAYER_TYPE_HUMAN,
                "profile_id": de_p.get("profile_id", -1),
                "position": p.get("position", {}),
            })

        # Parse the map ID — prefer DE rms_map_id over scenario map_id
        map_id = h.get("de", {}).get("rms_map_id") or h.get("scenario", {}).get("map_id", 0)

        # For custom maps, check scenario_name (USER:SCENARIOS), rms_filename, or scenario_filename
        custom_map_name = None
        # First priority: USER:SCENARIOS name (custom scenario with user-defined name)
        scenario_name = h.get("de", {}).get("scenario_name")
        if scenario_name:
            custom_map_name = scenario_name.replace(".aoe2scenario", "").strip()
        else:
            # Second priority: Workshop RMS filename
            rms_filename = h.get("de", {}).get("rms_filename")
            if rms_filename:
                # Strip .rms extension and clean up prefix (e.g., "ES_Paradise_Island.rms" -> "Paradise Island")
                name = rms_filename.replace(".rms", "").strip()
                # Remove common prefixes like "ES_", "ZR_", etc.
                if len(name) > 3 and name[2] == "_":
                    name = name[3:]
                custom_map_name = name.replace("_", " ")
            else:
                # Third priority: scenario_filename from scenario section
                scenario_filename = h.get("scenario", {}).get("scenario_filename", b"")
                if isinstance(scenario_filename, bytes):
                    scenario_filename = scenario_filename.decode("utf-8", errors="replace")
                if scenario_filename:
                    custom_map_name = scenario_filename.replace(".aoe2scenario", "").strip()

        # Parse body
        meta(f)
        time_ms = 0
        actions = []
        timeseries = {}  # player_number -> list of {time_ms, total_resources, total_objects}
        resigned_players = set()  # player numbers who resigned

        try:
            while True:
                op_type, payload = operation(f)

                if op_type == Operation.SYNC:
                    increment, checksum, sync_payload = payload
                    time_ms += increment

                    # Extract periodic resource/object snapshots
                    if sync_payload:
                        for key, stats in sync_payload.items():
                            if key == "current_time" or not isinstance(stats, dict):
                                continue
                            player_num = key
                            if player_num not in timeseries:
                                timeseries[player_num] = []
                            timeseries[player_num].append({
                                "time_ms": time_ms,
                                "total_resources": stats.get("total_res", 0),
                                "total_objects": stats.get("obj_count", 0),
                            })

                elif op_type == Operation.ACTION:
                    act_type, act_data = payload
                    act_data["time_ms"] = time_ms
                    act_data["action_type"] = act_type.name
                    act_data["action_type_id"] = act_type.value
                    actions.append(act_data)

                    # Track resignations for winner detection
                    if act_type == Action.RESIGN:
                        pid = act_data.get("player_id")
                        if pid is not None:
                            resigned_players.add(pid)

        except EOFError:
            pass
        except Exception:
            pass  # partial parse is okay

    # Determine winners based on resignations + team data
    # Build team mapping
    teams = {}  # team_id -> set of player numbers
    for p in players:
        tid = p.get("team_id", -1)
        if tid not in teams:
            teams[tid] = set()
        teams[tid].add(p["number"])

    # A player's team lost if anyone on it resigned
    losing_teams = set()
    for tid, members in teams.items():
        if members & resigned_players:
            losing_teams.add(tid)

    # Attach timeseries to each player first (needed for fallback detection)
    for p in players:
        p["timeseries"] = timeseries.get(p["number"], [])

    # Fallback: detect losers by checking if their objects were destroyed
    # A player likely lost if their final object count is very low or dropped significantly
    if not resigned_players:
        defeated_players = set()
        for p in players:
            ts = p.get("timeseries", [])
            if len(ts) >= 2:
                peak_objects = max(entry.get("total_objects", 0) for entry in ts)
                final_objects = ts[-1].get("total_objects", 0)
                # Player lost if: final objects < 50 AND dropped by more than 70% from peak
                if peak_objects > 100 and final_objects < 50 and final_objects < peak_objects * 0.3:
                    defeated_players.add(p["number"])

        # Mark teams with defeated players as losing
        for tid, members in teams.items():
            if members & defeated_players:
                losing_teams.add(tid)

        # Only set winners if we detected at least one loser
        if defeated_players:
            resigned_players = defeated_players  # Use for winner logic below

    for p in players:
        tid = p.get("team_id", -1)
        if resigned_players:
            # Someone resigned or was defeated, so we can determine outcome
            p["winner"] = tid not in losing_teams
        else:
            # No resignations or defeats detected
            p["winner"] = None

    # Extract date from filename if possible
    game_date, game_date_display = _extract_date_from_filename(filepath)

    # Use DE timestamp as fallback if filename date extraction fails
    de_timestamp = h.get("de", {}).get("timestamp")
    if not game_date and de_timestamp and isinstance(de_timestamp, int) and de_timestamp > 0:
        try:
            dt = datetime.fromtimestamp(de_timestamp)
            game_date = dt.strftime("%Y.%m.%d")
            hour = dt.hour % 12 or 12
            ampm = "AM" if dt.hour < 12 else "PM"
            game_date_display = f"{dt.month}/{dt.day} {hour}:{dt.minute:02d}{ampm}"
        except (OSError, ValueError):
            pass

    metadata = {
        "filename": os.path.basename(filepath),
        "game_date": game_date,
        "game_date_display": game_date_display,
        "de_timestamp": de_timestamp,
        "save_version": h.get("save_version"),
        "game_version": h.get("game_version"),
        "map_id": map_id,
        "map_name": custom_map_name or get_map_name(map_id),
        "duration_ms": time_ms,
        "duration_minutes": round(time_ms / 60_000, 1),
        "speed": h.get("metadata", {}).get("speed", 1.5),
        "population_limit": h.get("de", {}).get("population_limit", 200),
    }

    return {
        "metadata": metadata,
        "players": players,
        "actions": actions,
    }


def _extract_date_from_filename(filepath):
    """Try to extract date and time from MP Replay filename pattern.

    Returns (sort_date, display_date) where display_date is a short
    format like '4/3 11:19PM'.
    """
    basename = os.path.basename(filepath)
    # Pattern: MP Replay v101.103.39862.0 @2026.04.03 231951 (4).aoe2record
    if "@" in basename:
        try:
            after_at = basename.split("@")[1].strip()
            parts = after_at.split(" ")
            date_part = parts[0]  # "2026.04.03"
            year, month, day = date_part.split(".")
            time_part = parts[1] if len(parts) > 1 else None  # "231951"

            display = f"{int(month)}/{int(day)}"
            if time_part and len(time_part) >= 4:
                hour = int(time_part[:2])
                minute = int(time_part[2:4])
                ampm = "AM" if hour < 12 else "PM"
                display_hour = hour % 12 or 12
                display = f"{int(month)}/{int(day)} {display_hour}:{minute:02d}{ampm}"

            return date_part, display
        except (IndexError, ValueError):
            pass
    return None, None
