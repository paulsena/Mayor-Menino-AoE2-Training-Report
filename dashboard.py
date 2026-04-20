"""Generate HTML dashboard from game stats."""

import json
import os
import shutil

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def generate_dashboard(all_game_stats, trend_stats, output_path):
    """Generate HTML dashboard with separate JSON data files."""
    template_path = os.path.join(TEMPLATE_DIR, "dashboard.html")
    with open(template_path) as f:
        html = f.read()

    # Create output directories
    output_dir = os.path.dirname(output_path) or "."
    data_dir = os.path.join(output_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    # Copy banner image to output directory
    banner_src = os.path.join(TEMPLATE_DIR, "banner.png")
    if os.path.exists(banner_src):
        shutil.copy2(banner_src, os.path.join(output_dir, "banner.png"))

    # Write JSON data files
    games_path = os.path.join(data_dir, "games.json")
    trends_path = os.path.join(data_dir, "trends.json")

    with open(games_path, "w", encoding="utf-8") as f:
        json.dump(all_game_stats, f, default=str)

    with open(trends_path, "w", encoding="utf-8") as f:
        json.dump(trend_stats, f, default=str)

    # Write HTML (template loads JSON via fetch)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path
