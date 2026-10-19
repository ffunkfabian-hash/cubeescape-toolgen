"""Spurgewehr (trace_rifle): launcher into the weapon GIF module (scripts/tool_assets/weapon_gif.py)."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import weapon_gif

weapon_gif.make()
