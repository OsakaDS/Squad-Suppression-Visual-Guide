#!/usr/bin/env bash
# Rebuild everything from the game assets. Takes about a second.
set -euo pipefail
cd "$(dirname "$0")"
python3 extract_all.py      # every weapon asset      -> all_weapons_raw.json
python3 build_all.py        # group + extract icons   -> all_weapons.json
python3 dump_all.py         # every profile + curve   -> all_profiles.json
python3 report.py           # ten-rifle sample        -> squad_rifle_suppression.{csv,json}
python3 build_gui_data.py   # profiles + soldier data -> gui_data.json
python3 build_payload.py    # page base payload       -> payload.json
python3 merge_payload.py    # + weapons and icons     -> page_payload.json
python3 build_page.py       # template + payload      -> suppression.html
python3 make_site.py        # standalone document     -> site/index.html
echo "done — serve it with: python3 serve.py"
