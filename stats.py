"""Compute stats from parsed replay data."""

from parser import (
    TECH_FEUDAL_AGE, TECH_CASTLE_AGE, TECH_IMPERIAL_AGE,
    AGE_RESEARCH_DURATIONS, UNIT_VILLAGER,
    get_tech_name, get_unit_name,
)

# Key tech IDs to track
AGE_TECH_IDS = {TECH_FEUDAL_AGE, TECH_CASTLE_AGE, TECH_IMPERIAL_AGE}

KEY_TECH_IDS = {
    22: "Loom",
    101: "Feudal Age",
    102: "Castle Age",
    103: "Imperial Age",
    213: "Wheelbarrow",
    249: "Hand Cart",
    202: "Double-Bit Axe",
    203: "Bow Saw",
    221: "Two-Man Saw",
    14: "Horse Collar",
    13: "Heavy Plow",
    12: "Crop Rotation",
    55: "Gold Mining",
    182: "Gold Shaft Mining",
    278: "Stone Mining",
    279: "Stone Shaft Mining",
    67: "Forging",
    68: "Iron Casting",
    75: "Blast Furnace",
    199: "Fletching",
    200: "Bodkin Arrow",
    201: "Bracer",
    140: "Guard Tower",
    63: "Ballistics",
    875: "Gambesons",
}

# Benchmarks for skill assessment (times in seconds, normal speed)
BENCHMARKS = {
    "feudal_age": [
        (480, "Excellent", "#22c55e"),   # < 8:00
        (540, "Great", "#84cc16"),       # < 9:00
        (600, "Good", "#eab308"),        # < 10:00
        (720, "Average", "#f97316"),     # < 12:00
        (9999, "Needs Work", "#ef4444"),
    ],
    "castle_age": [
        (960, "Excellent", "#22c55e"),   # < 16:00
        (1080, "Great", "#84cc16"),      # < 18:00
        (1260, "Good", "#eab308"),       # < 21:00
        (1500, "Average", "#f97316"),    # < 25:00
        (9999, "Needs Work", "#ef4444"),
    ],
    "imperial_age": [
        (1800, "Excellent", "#22c55e"),  # < 30:00
        (2100, "Great", "#84cc16"),      # < 35:00
        (2400, "Good", "#eab308"),       # < 40:00
        (3000, "Average", "#f97316"),    # < 50:00
        (9999, "Needs Work", "#ef4444"),
    ],
}


def format_time(seconds):
    """Format seconds as MM:SS."""
    if seconds is None:
        return "N/A"
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


def get_benchmark(category, seconds):
    """Return (label, color) for a benchmark category and time."""
    if seconds is None:
        return ("N/A", "#6b7280")
    for threshold, label, color in BENCHMARKS.get(category, []):
        if seconds < threshold:
            return (label, color)
    return ("N/A", "#6b7280")


def compute_player_stats(actions, player_number, game_duration_ms, game_speed):
    """Compute all stats for a single player from action list.

    game_speed: the speed multiplier (1.0=slow, 1.5=normal, 1.7=fast, 2.0=very fast).
    Times in the replay are in real-time ms. To convert to in-game time, multiply by speed.
    """
    player_actions = [a for a in actions if a.get("player_id") == player_number]
    all_player_actions = player_actions  # includes all action types

    # --- Age-up times ---
    age_ups = {}
    for a in actions:
        if a.get("action_type") == "RESEARCH" and a.get("player_id") == player_number:
            tech_id = a.get("technology_id")
            if tech_id in AGE_TECH_IDS:
                # Time the research was STARTED (clicked)
                click_time_ms = a["time_ms"]
                # Research completion = click + research duration / speed
                duration_ms = AGE_RESEARCH_DURATIONS.get(tech_id, 0)
                completion_ms = click_time_ms + duration_ms / game_speed
                age_ups[tech_id] = {
                    "click_time_s": round(click_time_ms / 1000 * game_speed, 1),
                    "completion_time_s": round(completion_ms / 1000 * game_speed, 1),
                }

    # --- Research timings ---
    researches = []
    for a in actions:
        if a.get("action_type") == "RESEARCH" and a.get("player_id") == player_number:
            tech_id = a.get("technology_id")
            game_time_s = round(a["time_ms"] / 1000 * game_speed, 1)
            tech_name = KEY_TECH_IDS.get(tech_id, get_tech_name(tech_id))
            researches.append({
                "tech_id": tech_id,
                "tech_name": tech_name,
                "time_s": game_time_s,
                "time_str": format_time(game_time_s),
                "is_key": tech_id in KEY_TECH_IDS,
            })

    # --- Villager production ---
    villager_queues = []
    for a in actions:
        if a.get("player_id") != player_number:
            continue
        if a.get("action_type") in ("QUEUE", "MULTIQUEUE", "DE_QUEUE"):
            unit_id = a.get("unit_id")
            if unit_id == UNIT_VILLAGER:
                amount = a.get("amount", 1)
                game_time_s = round(a["time_ms"] / 1000 * game_speed, 1)
                villager_queues.append({
                    "time_s": game_time_s,
                    "amount": amount,
                })

    # Count villagers at key timestamps
    total_vils = 0
    vil_counts_at = {}
    checkpoints = [300, 600, 900, 1200, 1500, 1800]  # 5, 10, 15, 20, 25, 30 min
    queue_idx = 0
    # Villager production time ~25s at normal speed
    vil_train_time = 25
    for cp in checkpoints:
        count = 0
        for vq in villager_queues:
            # Villager finished = queue time + train time
            finish_time = vq["time_s"] + vil_train_time
            if finish_time <= cp:
                count += vq["amount"]
        # Add starting villagers (3 in standard game)
        vil_counts_at[cp] = count + 3

    total_vils = sum(vq["amount"] for vq in villager_queues) + 3

    # --- Idle TC estimation ---
    # Look for gaps between villager/research queues at TC
    tc_events = []
    for a in actions:
        if a.get("player_id") != player_number:
            continue
        if a.get("action_type") in ("QUEUE", "MULTIQUEUE", "DE_QUEUE"):
            if a.get("unit_id") == UNIT_VILLAGER:
                tc_events.append(round(a["time_ms"] / 1000 * game_speed, 1))
        elif a.get("action_type") == "RESEARCH":
            tc_events.append(round(a["time_ms"] / 1000 * game_speed, 1))

    tc_events.sort()
    idle_tc_s = 0
    # Estimate: if gap between TC events > 30s, it's likely idle time
    # (villager trains in ~25s, so gaps > 30s suggest idle TC)
    for i in range(1, len(tc_events)):
        gap = tc_events[i] - tc_events[i - 1]
        if gap > 30:
            idle_tc_s += gap - 25  # subtract expected training time

    # Cap idle TC at first 20 minutes for relevance
    early_tc_events = [t for t in tc_events if t <= 1200]
    early_idle_tc_s = 0
    for i in range(1, len(early_tc_events)):
        gap = early_tc_events[i] - early_tc_events[i - 1]
        if gap > 30:
            early_idle_tc_s += gap - 25

    # --- Military production ---
    military_units = {}
    first_military_time = None
    for a in actions:
        if a.get("player_id") != player_number:
            continue
        if a.get("action_type") in ("QUEUE", "MULTIQUEUE", "DE_QUEUE"):
            unit_id = a.get("unit_id")
            if unit_id and unit_id != UNIT_VILLAGER:
                unit_name = get_unit_name(unit_id)
                amount = a.get("amount", 1)
                game_time_s = round(a["time_ms"] / 1000 * game_speed, 1)
                if unit_name not in military_units:
                    military_units[unit_name] = {"count": 0, "first_time_s": game_time_s}
                military_units[unit_name]["count"] += amount
                if first_military_time is None:
                    first_military_time = game_time_s

    # --- APM ---
    game_duration_s = game_duration_ms / 1000
    total_player_actions = len(player_actions)
    apm = round(total_player_actions / (game_duration_s / 60), 1) if game_duration_s > 0 else 0

    # APM over time (2-minute windows)
    apm_over_time = []
    window_s = 120
    max_time = game_duration_s * game_speed
    t = 0
    while t < max_time:
        window_start = t / game_speed
        window_end = (t + window_s) / game_speed
        count = sum(1 for a in player_actions if window_start <= a["time_ms"] / 1000 < window_end)
        apm_val = round(count / (window_s / 60), 1)
        apm_over_time.append({"time_s": t, "apm": apm_val})
        t += window_s

    # --- Build order (first 40 build/research/wall actions) ---
    build_order = []
    for a in actions:
        if a.get("player_id") != player_number:
            continue
        game_time_s = round(a["time_ms"] / 1000 * game_speed, 1)
        atype = a.get("action_type")
        if atype in ("BUILD", "WALL"):
            build_id = a.get("building_id")
            build_order.append({
                "time_s": game_time_s,
                "time_str": format_time(game_time_s),
                "type": "build",
                "name": get_unit_name(build_id) if build_id else "Unknown",
            })
        elif atype == "RESEARCH":
            tech_id = a.get("technology_id")
            build_order.append({
                "time_s": game_time_s,
                "time_str": format_time(game_time_s),
                "type": "research",
                "name": KEY_TECH_IDS.get(tech_id, get_tech_name(tech_id)),
            })
        if len(build_order) >= 40:
            break

    # --- Villager counts at age-up times ---
    def _vils_at_time(target_s):
        if target_s is None:
            return None
        count = 0
        for vq in villager_queues:
            finish_time = vq["time_s"] + vil_train_time
            if finish_time <= target_s:
                count += vq["amount"]
        return count + 3  # +3 starting villagers

    # --- Compile results ---
    feudal_time = age_ups.get(TECH_FEUDAL_AGE, {}).get("click_time_s")
    castle_time = age_ups.get(TECH_CASTLE_AGE, {}).get("click_time_s")
    imperial_time = age_ups.get(TECH_IMPERIAL_AGE, {}).get("click_time_s")

    vils_at_feudal = _vils_at_time(feudal_time)
    vils_at_castle = _vils_at_time(castle_time)
    vils_at_imperial = _vils_at_time(imperial_time)

    return {
        "age_ups": {
            "feudal": {
                "time_s": feudal_time,
                "time_str": format_time(feudal_time),
                "benchmark": get_benchmark("feudal_age", feudal_time),
                "villagers": vils_at_feudal,
            },
            "castle": {
                "time_s": castle_time,
                "time_str": format_time(castle_time),
                "benchmark": get_benchmark("castle_age", castle_time),
                "villagers": vils_at_castle,
            },
            "imperial": {
                "time_s": imperial_time,
                "time_str": format_time(imperial_time),
                "benchmark": get_benchmark("imperial_age", imperial_time),
                "villagers": vils_at_imperial,
            },
        },
        "researches": researches,
        "villagers": {
            "total_produced": total_vils,
            "queues": villager_queues,
            "counts_at": {f"{k // 60}min": v for k, v in vil_counts_at.items()},
        },
        "idle_tc": {
            "total_s": round(idle_tc_s, 1),
            "early_game_s": round(early_idle_tc_s, 1),
            "early_game_str": format_time(early_idle_tc_s),
        },
        "military": {
            "units": military_units,
            "total_produced": sum(u["count"] for u in military_units.values()),
            "first_military_time_s": first_military_time,
            "first_military_time_str": format_time(first_military_time),
        },
        "apm": {
            "overall": apm,
            "over_time": apm_over_time,
        },
        "build_order": build_order,
    }


def compute_timeseries_stats(timeseries, game_speed, villager_queues=None):
    """Compute summary stats from player timeseries data.

    Returns a dict with the timeseries points (converted to game time)
    and final snapshot values. Also computes villager count over time
    based on villager queue actions.
    """
    if not timeseries:
        return {
            "points": [],
            "final_resources": None,
            "final_objects": None,
            "peak_resources": None,
            "peak_objects": None,
        }

    # Pre-compute villager finish times for efficient lookup
    # Each villager takes ~25s to train
    vil_train_time = 25
    vil_finish_times = []
    if villager_queues:
        for vq in villager_queues:
            finish_time = vq["time_s"] + vil_train_time
            for _ in range(vq["amount"]):
                vil_finish_times.append(finish_time)
        vil_finish_times.sort()

    def count_vils_at(target_s):
        """Count villagers finished by target_s (includes 3 starting vils)."""
        count = 3  # Starting villagers
        for ft in vil_finish_times:
            if ft <= target_s:
                count += 1
            else:
                break
        return count

    points = []
    peak_resources = 0
    peak_objects = 0
    for entry in timeseries:
        game_time_s = round(entry["time_ms"] / 1000 * game_speed, 1)
        res = entry["total_resources"]
        obj = entry["total_objects"]
        vils = count_vils_at(game_time_s) if villager_queues else None
        points.append({
            "time_s": game_time_s,
            "resources": res,
            "objects": obj,
            "villagers": vils,
        })
        if res > peak_resources:
            peak_resources = res
        if obj > peak_objects:
            peak_objects = obj

    last = timeseries[-1]
    return {
        "points": points,
        "final_resources": last["total_resources"],
        "final_objects": last["total_objects"],
        "peak_resources": peak_resources,
        "peak_objects": peak_objects,
    }


def compute_game_stats(parsed_replay):
    """Compute stats for all players in a game."""
    metadata = parsed_replay["metadata"]
    players = parsed_replay["players"]
    actions = parsed_replay["actions"]
    game_speed = metadata.get("speed", 1.5)

    game_stats = {
        "metadata": metadata,
        "players": [],
    }

    for player in players:
        player_stats = compute_player_stats(
            actions, player["number"],
            metadata["duration_ms"], game_speed,
        )

        # Compute timeseries stats from raw timeseries data
        # Pass villager queues to compute villager count over time
        vil_queues = player_stats.get("villagers", {}).get("queues", [])
        ts_stats = compute_timeseries_stats(
            player.get("timeseries", []), game_speed, vil_queues
        )

        # Build player entry (exclude raw timeseries to keep output lean)
        player_entry = {k: v for k, v in player.items() if k != "timeseries"}
        player_entry["stats"] = player_stats
        player_entry["timeseries"] = ts_stats
        player_entry["winner"] = player.get("winner")

        game_stats["players"].append(player_entry)

    return game_stats


def compute_trend_stats(all_game_stats):
    """Compute trend data across multiple games.

    Returns per-player trends for key metrics.
    """
    # Collect all human players across games
    player_names = set()
    for gs in all_game_stats:
        for p in gs["players"]:
            if p["is_human"]:
                player_names.add(p["name"])

    trends = {}
    for name in sorted(player_names):
        player_trend = {
            "games": [],
            "feudal_times": [],
            "castle_times": [],
            "imperial_times": [],
            "villagers_at_15min": [],
            "villagers_at_30min": [],
            "villagers_at_castle": [],
            "total_villagers": [],
            "apm": [],
            "idle_tc_early": [],
            "first_military": [],
            "total_military": [],
            "game_durations": [],
            "wins": [],
            "final_resources": [],
            "final_objects": [],
            "peak_resources": [],
            "peak_objects": [],
            "civs": [],  # Track civ usage for pie chart
            "ai_difficulty": [],  # Track AI difficulty level
        }

        for gs in all_game_stats:
            for p in gs["players"]:
                if p["name"] != name:
                    continue
                stats = p["stats"]
                game_date = gs["metadata"].get("game_date", "unknown")
                player_trend["games"].append(game_date)
                player_trend["game_durations"].append(gs["metadata"]["duration_minutes"])

                ft = stats["age_ups"]["feudal"]["time_s"]
                ct = stats["age_ups"]["castle"]["time_s"]
                it = stats["age_ups"]["imperial"]["time_s"]
                player_trend["feudal_times"].append(ft)
                player_trend["castle_times"].append(ct)
                player_trend["imperial_times"].append(it)

                vil_15 = stats["villagers"]["counts_at"].get("15min")
                vil_30 = stats["villagers"]["counts_at"].get("30min")
                player_trend["villagers_at_15min"].append(vil_15)
                player_trend["villagers_at_30min"].append(vil_30)
                player_trend["villagers_at_castle"].append(stats["age_ups"]["castle"].get("villagers"))
                player_trend["total_villagers"].append(stats["villagers"]["total_produced"])
                player_trend["apm"].append(stats["apm"]["overall"])
                player_trend["idle_tc_early"].append(stats["idle_tc"]["early_game_s"])
                player_trend["first_military"].append(stats["military"]["first_military_time_s"])
                player_trend["total_military"].append(stats["military"]["total_produced"])

                # Win/loss tracking
                player_trend["wins"].append(p.get("winner"))

                # Timeseries final snapshot
                ts = p.get("timeseries", {})
                player_trend["final_resources"].append(ts.get("final_resources"))
                player_trend["final_objects"].append(ts.get("final_objects"))
                player_trend["peak_resources"].append(ts.get("peak_resources"))
                player_trend["peak_objects"].append(ts.get("peak_objects"))

                # Track civ usage
                player_trend["civs"].append(p.get("civ_name", "Unknown"))

                # Track AI difficulty
                player_trend["ai_difficulty"].append(gs["metadata"].get("difficulty_id", -1))

        trends[name] = player_trend

    return trends
