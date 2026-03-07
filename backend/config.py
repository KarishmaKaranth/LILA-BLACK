from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT_DIR
MINIMAP_SIZE = 1024

MAP_CONFIG = {
    "AmbroseValley": {"scale": 900.0, "origin_x": -370.0, "origin_z": -473.0, "image": "AmbroseValley_Minimap.png"},
    "GrandRift": {"scale": 581.0, "origin_x": -290.0, "origin_z": -290.0, "image": "GrandRift_Minimap.png"},
    "Lockdown": {"scale": 1000.0, "origin_x": -500.0, "origin_z": -500.0, "image": "Lockdown_Minimap.jpg"},
}

POSITION_EVENTS = {"Position", "BotPosition"}
EVENT_MARKERS = {
    "Kill": "kill",
    "BotKill": "kill",
    "Killed": "death",
    "BotKilled": "death",
    "KilledByStorm": "storm",
    "Loot": "loot",
}
