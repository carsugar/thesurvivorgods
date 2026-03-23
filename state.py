"""
state.py — Persistent game state for TheSurvivorGods.

Each season is stored in data/season_<N>.json.
Structure:
{
  "season": 1,
  "phase": "pregame" | "tribal" | "merged" | "finale" | "ended",
  "players": {
    "discord_user_id": {
      "username": "...",
      "name": "...",          # display name chosen by hosts
      "tribe": "tribe_name",  # current tribe or null
      "status": "active" | "premerge" | "jury" | "winner" | "runner_up",
      "confessional_id": channel_id,
      "submissions_id": channel_id,
      "advantages": []        # list of advantage keys held
    }
  },
  "tribes": {
    "tribe_name": {
      "color": 0xHEXCOLOR,
      "role_id": ...,
      "category_id": ...,         # alliance category
      "tribe_chat_id": ...,
      "ones_category_id": ...,    # 1:1 channels category
      "ones_channels": {          # "uid1-uid2": channel_id
        "player_a-player_b": channel_id
      },
      "members": ["uid1", "uid2"]
    }
  },
  "advantages": {
    "advantage_key": {
      "type": "idol" | "extra_vote" | "steal_a_vote" | "block_a_vote" | "nullifier",
      "holder_uid": "...",
      "given_at": "tribal_N",
      "expires": "tribal_N" | null,  # null = never
      "played": false,
      "notes": "..."
    }
  },
  "jury": ["uid1", "uid2"],
  "premerge_boot_order": ["uid1", "uid2"],
  "confessionals_category_id": null,
  "subs_category_id": null,
  "ponderosa_channel_id": null,
  "jury_lounge_channel_id": null,
  "jury_voting_channel_id": null,
  "host_role_id": null,
  "spectator_role_id": null
}
"""

import json
import os
import asyncio
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

_LOCKS: dict[int, asyncio.Lock] = {}


def _season_path(season: int) -> Path:
    return DATA_DIR / f"season_{season}.json"


DEFAULT_THEME = {
    # Category emojis
    "tribe_emoji":    "🏕",
    "alliance_emoji": "🤝",
    "ones_emoji":     "💬",
    "merge_emoji":    "🏆",
    # Category / channel labels
    "tribe_chat_label":      "tribe-chat",
    "alliances_label":       "Alliances",
    "ones_label":            "1:1s",
    "merge_chat_label":      "merge-chat",
    "confessionals_label":   "Confessionals",
    "submissions_label":     "Submissions",
    # Role labels
    "player_role_label": "Player",
    # Elimination flavor text
    "snuff_title":  "The tribe has spoken.",
    "snuff_suffix": "'s torch has been snuffed.",
}


def _default_state(season: int) -> dict:
    return {
        "season": season,
        "phase": "pregame",
        "players": {},
        "tribes": {},
        "advantages": {},
        "jury": [],
        "premerge_boot_order": [],
        "confessionals_category_id": None,
        "subs_category_id": None,
        "ponderosa_channel_id": None,
        "jury_lounge_channel_id": None,
        "jury_voting_channel_id": None,
        "host_role_id": None,
        "spectator_role_id": None,
        "theme": dict(DEFAULT_THEME),
    }


def get_theme(game: dict) -> dict:
    """Return the season theme, filling in any missing keys with defaults."""
    return {**DEFAULT_THEME, **game.get("theme", {})}


def _get_lock(season: int) -> asyncio.Lock:
    if season not in _LOCKS:
        _LOCKS[season] = asyncio.Lock()
    return _LOCKS[season]


def load(season: int) -> dict:
    """Load state for a season (sync). Creates default if missing."""
    path = _season_path(season)
    if not path.exists():
        state = _default_state(season)
        _save_sync(season, state)
        return state
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_sync(season: int, state: dict):
    path = _season_path(season)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    tmp.replace(path)


async def save(season: int, state: dict):
    """Async-safe save via per-season lock."""
    lock = _get_lock(season)
    async with lock:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _save_sync, season, state)


def list_seasons() -> list[int]:
    return sorted(
        int(p.stem.split("_")[1])
        for p in DATA_DIR.glob("season_*.json")
        if p.stem.split("_")[1].isdigit()
    )


def current_season() -> int:
    """Return the current active (non-ended) season number, or 1 if none exist yet."""
    seasons = list_seasons()
    if not seasons:
        return 1
    for n in reversed(seasons):
        s = load(n)
        if s.get("phase") != "ended":
            return n
    return seasons[-1]


# ── Convenience accessors ────────────────────────────────────────────────────

def get_player(state: dict, uid: str) -> Optional[dict]:
    return state["players"].get(str(uid))


def get_tribe(state: dict, name: str) -> Optional[dict]:
    return state["tribes"].get(name)


def active_players(state: dict) -> list[tuple[str, dict]]:
    return [(uid, p) for uid, p in state["players"].items() if p["status"] == "active"]


def players_in_tribe(state: dict, tribe_name: str) -> list[tuple[str, dict]]:
    return [(uid, p) for uid, p in state["players"].items()
            if p.get("tribe") == tribe_name and p["status"] == "active"]


def get_advantage(state: dict, key: str) -> Optional[dict]:
    return state["advantages"].get(key)


def advantages_held_by(state: dict, uid: str) -> list[tuple[str, dict]]:
    return [(k, v) for k, v in state["advantages"].items()
            if v["holder_uid"] == str(uid) and not v["played"]]
