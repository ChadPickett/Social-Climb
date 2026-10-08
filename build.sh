#!/usr/bin/env sh
# Packages Social Climb into a single executable in dist/. Used by CI; works locally too.
set -e
pyinstaller --noconfirm --clean --onefile --name SocialClimb \
  --add-data "web:web" \
  --collect-submodules uvicorn \
  --collect-data tzdata \
  ${ICON:+--icon "$ICON"} \
  run.py
