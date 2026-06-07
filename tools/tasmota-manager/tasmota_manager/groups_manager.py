"""Region/user group management for MQTT topic hierarchy.

Topic format: {user_id}/{region_id}/%topic%/%prefix%/
Example: juhosv/hu_eszak/proba_123/tele/SENSOR
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

GROUPS_FILE = Path(__file__).parent.parent / "groups.json"

_DEFAULT_GROUPS: dict = {"regions": []}


# ---------------------------------------------------------------------------
# Load / Save
# ---------------------------------------------------------------------------

def load_groups() -> dict:
    """Load groups from groups.json; return empty structure if missing."""
    if not GROUPS_FILE.exists():
        return {"regions": []}
    try:
        return json.loads(GROUPS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"regions": []}


def save_groups(data: dict) -> None:
    GROUPS_FILE.parent.mkdir(exist_ok=True)
    GROUPS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def list_regions() -> list[tuple[str, str]]:
    """Return list of (id, name) tuples for all regions."""
    data = load_groups()
    return [(r["id"], r.get("name", r["id"])) for r in data.get("regions", [])]


def list_users(region_id: str) -> list[tuple[str, str]]:
    """Return list of (id, name) tuples for users in the given region."""
    data = load_groups()
    for region in data.get("regions", []):
        if region["id"] == region_id:
            return [(u["id"], u.get("name", u["id"])) for u in region.get("users", [])]
    return []


def get_region_name(region_id: str) -> str:
    for rid, rname in list_regions():
        if rid == region_id:
            return rname
    return region_id


def get_user_name(region_id: str, user_id: str) -> str:
    for uid, uname in list_users(region_id):
        if uid == user_id:
            return uname
    return user_id


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def add_region(region_id: str, name: str) -> bool:
    """Add a new region. Returns False if id already exists."""
    region_id = region_id.strip()
    name = name.strip()
    if not region_id:
        return False
    data = load_groups()
    for r in data["regions"]:
        if r["id"] == region_id:
            return False
    data["regions"].append({"id": region_id, "name": name or region_id, "users": []})
    save_groups(data)
    return True


def update_region(old_id: str, new_id: str, new_name: str) -> bool:
    """Update a region's id and/or name. Returns False if not found or new_id conflicts."""
    new_id = new_id.strip()
    new_name = new_name.strip()
    if not new_id:
        return False
    data = load_groups()
    # Check id conflict (only if renaming)
    if new_id != old_id:
        for r in data["regions"]:
            if r["id"] == new_id:
                return False
    for region in data["regions"]:
        if region["id"] == old_id:
            region["id"] = new_id
            region["name"] = new_name or new_id
            save_groups(data)
            return True
    return False


def delete_region(region_id: str) -> bool:
    """Delete a region and all its users. Returns False if not found."""
    data = load_groups()
    before = len(data["regions"])
    data["regions"] = [r for r in data["regions"] if r["id"] != region_id]
    if len(data["regions"]) == before:
        return False
    save_groups(data)
    return True


def add_user(region_id: str, user_id: str, name: str) -> bool:
    """Add a user to a region. Returns False if region not found or user exists."""
    user_id = user_id.strip()
    name = name.strip()
    if not user_id:
        return False
    data = load_groups()
    for region in data["regions"]:
        if region["id"] == region_id:
            for u in region.get("users", []):
                if u["id"] == user_id:
                    return False
            region.setdefault("users", []).append(
                {"id": user_id, "name": name or user_id}
            )
            save_groups(data)
            return True
    return False


def update_user(region_id: str, old_id: str, new_id: str, new_name: str) -> bool:
    """Update a user's id and/or name within a region. Returns False if not found or conflict."""
    new_id = new_id.strip()
    new_name = new_name.strip()
    if not new_id:
        return False
    data = load_groups()
    for region in data["regions"]:
        if region["id"] == region_id:
            # Check id conflict (only if renaming)
            if new_id != old_id:
                for u in region.get("users", []):
                    if u["id"] == new_id:
                        return False
            for user in region.get("users", []):
                if user["id"] == old_id:
                    user["id"] = new_id
                    user["name"] = new_name or new_id
                    save_groups(data)
                    return True
    return False


def delete_user(region_id: str, user_id: str) -> bool:
    """Delete a user from a region. Returns False if not found."""
    data = load_groups()
    for region in data["regions"]:
        if region["id"] == region_id:
            before = len(region.get("users", []))
            region["users"] = [u for u in region.get("users", []) if u["id"] != user_id]
            if len(region["users"]) == before:
                return False
            save_groups(data)
            return True
    return False


# ---------------------------------------------------------------------------
# FullTopic builder
# ---------------------------------------------------------------------------

def build_fulltopic(region_id: str, user_id: str) -> str:
    """Build Tasmota FullTopic string.

    Format: {user_id}/{region_id}/%topic%/%prefix%/
    Example: juhosv/hu_eszak/%topic%/%prefix%/

    Results in topics like:
        juhosv/hu_eszak/AABBCCDD/tele/SENSOR
        juhosv/hu_eszak/AABBCCDD/cmnd/Power

    This way subscribing to all messages from one device is simply:
        juhosv/hu_eszak/AABBCCDD/#
    """
    if not region_id or not user_id:
        return "%prefix%/%topic%/"
    return f"{user_id}/{region_id}/%topic%/%prefix%/"


def build_mqtt_subscribe_topic(region_id: str, user_id: str, device_topic: str) -> str:
    """Build the MQTT subscription wildcard for a specific device.

    With group:    juhosv/hu_eszak/AABBCCDD/#
    Without group: +/AABBCCDD/#  (legacy flat topic)
    """
    if not region_id or not user_id:
        if device_topic:
            return f"+/{device_topic}/#"
        return "#"
    if device_topic:
        return f"{user_id}/{region_id}/{device_topic}/#"
    return f"{user_id}/{region_id}/#"
