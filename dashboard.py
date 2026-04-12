"""Generate HTML dashboard from game stats."""

import json
import os
import shutil

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def generate_dashboard(all_game_stats, trend_stats, output_path):
    """Generate a self-contained HTML dashboard."""
    template_path = os.path.join(TEMPLATE_DIR, "dashboard.html")
    with open(template_path) as f:
        template = f.read()

    # Copy banner image to output directory
    output_dir = os.path.dirname(output_path) or "."
    banner_src = os.path.join(TEMPLATE_DIR, "banner.png")
    if os.path.exists(banner_src):
        os.makedirs(output_dir, exist_ok=True)
        shutil.copy2(banner_src, os.path.join(output_dir, "banner.png"))

    # Embed data as JSON
    html = template.replace(
        "/*__GAME_DATA__*/",
        json.dumps(all_game_stats, default=str),
    ).replace(
        "/*__TREND_DATA__*/",
        json.dumps(trend_stats, default=str),
    )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path
