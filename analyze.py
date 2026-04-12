"""AoE2 Replay Analyzer — CLI entry point."""

import glob
import os
import sys

from parser import parse_replay
from stats import compute_game_stats, compute_trend_stats
from dashboard import generate_dashboard


# Default AoE2 DE directory
USERNAME = os.environ.get("USERNAME", os.environ.get("USER", "pauls"))
AOE2_DE_DIR = os.path.join("C:\\Users", USERNAME, "Games", "Age of Empires 2 DE")


def find_default_savegame_dir():
    """Auto-detect the savegame directory by finding the Steam ID folder."""
    if not os.path.isdir(AOE2_DE_DIR):
        return None
    # Look for numeric subdirectories (Steam IDs)
    steam_ids = [
        d for d in os.listdir(AOE2_DE_DIR)
        if os.path.isdir(os.path.join(AOE2_DE_DIR, d)) and d.isdigit()
    ]
    if not steam_ids:
        return None
    if len(steam_ids) == 1:
        savegame = os.path.join(AOE2_DE_DIR, steam_ids[0], "savegame")
        if os.path.isdir(savegame):
            return savegame
    # Multiple Steam IDs — pick the one with the most recent savegame folder
    best = None
    best_mtime = 0
    for sid in steam_ids:
        savegame = os.path.join(AOE2_DE_DIR, sid, "savegame")
        if os.path.isdir(savegame):
            mtime = os.path.getmtime(savegame)
            if mtime > best_mtime:
                best = savegame
                best_mtime = mtime
    return best


def find_replays(path=None, include_sp=False):
    """Find .aoe2record files in the given path or current directory.

    By default, skips single-player replays (filenames starting with 'SP').
    """
    if path and os.path.isfile(path):
        return [path]
    search_dir = path or "."
    pattern = os.path.join(search_dir, "*.aoe2record")
    files = glob.glob(pattern)
    if not include_sp:
        before = len(files)
        files = [f for f in files if not os.path.basename(f).startswith("SP ")]
        skipped = before - len(files)
        if skipped:
            print(f"Skipped {skipped} single-player replay(s)")
    files.sort(key=lambda f: os.path.basename(f))
    return files


def print_help():
    print("""AoE2 Replay Analyzer — Generate an HTML dashboard from recorded games.

Usage:
  python analyze.py [options] [file.aoe2record]

Options:
  --dir <path>       Directory containing .aoe2record files
  --output <path>    Output HTML file (default: docs/dashboard.html)
  --include-sp       Include single-player replays (skipped by default)
  --help             Show this help message

Examples:
  python analyze.py                              Auto-detect AoE2 savegame folder
  python analyze.py --dir "C:\\path\\to\\replays"   Analyze replays in a specific folder
  python analyze.py game.aoe2record              Analyze a single replay file
  python analyze.py --include-sp                 Include single-player games too

If no directory or file is specified, the tool auto-detects your AoE2 DE
savegame folder at:
  C:\\Users\\<username>\\Games\\Age of Empires 2 DE\\<steam_id>\\savegame
""")


def main():
    # Parse CLI args
    path = None
    output = os.path.join("docs", "dashboard.html")
    args = sys.argv[1:]

    include_sp = False
    for i, arg in enumerate(args):
        if arg in ("--help", "-h"):
            print_help()
            sys.exit(0)
        elif arg == "--dir" and i + 1 < len(args):
            path = args[i + 1]
        elif arg == "--output" and i + 1 < len(args):
            output = args[i + 1]
        elif arg == "--include-sp":
            include_sp = True
        elif not arg.startswith("--") and arg.endswith(".aoe2record"):
            path = arg

    # If no path given, try auto-detecting AoE2 savegame directory
    if path is None:
        default_dir = find_default_savegame_dir()
        if default_dir:
            path = default_dir
            print(f"Auto-detected savegame dir: {path}")
        else:
            print(f"Could not find AoE2 DE savegame folder, using current directory")

    replays = find_replays(path, include_sp=include_sp)
    if not replays:
        print("No .aoe2record files found.")
        sys.exit(1)

    print(f"Found {len(replays)} replay(s)")

    all_game_stats = []
    for i, replay_path in enumerate(replays):
        basename = os.path.basename(replay_path)
        print(f"  [{i+1}/{len(replays)}] Parsing: {basename}...", end=" ", flush=True)
        try:
            parsed = parse_replay(replay_path)
            game_stats = compute_game_stats(parsed)
            all_game_stats.append(game_stats)

            # Print summary
            humans = [p for p in game_stats["players"] if p["is_human"]]
            for p in humans:
                s = p["stats"]
                f_time = s["age_ups"]["feudal"]["time_str"]
                c_time = s["age_ups"]["castle"]["time_str"]
                print(f"{p['name']}({p['civ_name']}) F:{f_time} C:{c_time}", end="  ")
            print()
        except Exception as e:
            print(f"ERROR: {e}")

    if not all_game_stats:
        print("No replays could be parsed.")
        sys.exit(1)

    # Sort by game date
    all_game_stats.sort(key=lambda g: g["metadata"].get("game_date") or "", reverse=True)

    # Compute trends
    trend_stats = compute_trend_stats(all_game_stats)

    # Generate dashboard
    dashboard_path = generate_dashboard(all_game_stats, trend_stats, output)
    abs_path = os.path.abspath(dashboard_path)
    print(f"\nDashboard generated: {abs_path}")
    print(f"Open in browser: file:///{abs_path.replace(os.sep, '/')}")

    # Print trend summary
    print("\n--- Trend Summary ---")
    for name, trend in trend_stats.items():
        feudals = [t for t in trend["feudal_times"] if t is not None]
        castles = [t for t in trend["castle_times"] if t is not None]
        apms = trend["apm"]
        print(f"\n  {name} ({len(trend['games'])} games):")
        if feudals:
            from stats import format_time
            best_f = min(feudals)
            avg_f = sum(feudals) / len(feudals)
            print(f"    Feudal:  best {format_time(best_f)}, avg {format_time(avg_f)}")
        if castles:
            best_c = min(castles)
            avg_c = sum(castles) / len(castles)
            print(f"    Castle:  best {format_time(best_c)}, avg {format_time(avg_c)}")
        if apms:
            print(f"    APM:     avg {sum(apms)/len(apms):.0f}")


if __name__ == "__main__":
    main()
