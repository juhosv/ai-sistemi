"""Region/user group management for MQTT topic hierarchy.

Topic format: {user_id}/{region_id}/%topic%/%prefix%/
Example: juhosv/hu_eszak/proba_123/tele/SENSOR

Data model (user-first):
    {
        "users": [
            {
                "id": "juhosv",
                "name": "Juhos Viktor",
                "regions": [
                    {"id": "hu_eszak", "name": "Észak régió"}
                ]
            }
        ]
    }
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

GROUPS_FILE = Path(__file__).parent.parent / "groups.json"

# Characters forbidden in MQTT topic segments
_TOPIC_FORBIDDEN = str.maketrans({
    " ": "_",
    "\t": "_",
    "#": "",
    "+": "",
    "/": "",
    "\x00": "",
})


def sanitize_id(value: str) -> str:
    """Replace or remove characters not allowed in MQTT topic segments.

    Rules:
        space / tab  → underscore
        #, +, /      → removed (topic wildcards / separator)
        null char    → removed
    """
    return value.strip().translate(_TOPIC_FORBIDDEN)


# ---------------------------------------------------------------------------
# Load / Save / Migrate
# ---------------------------------------------------------------------------

def _migrate_if_needed(data: dict) -> dict:
    """Convert old region-first format to user-first format if necessary.

    Old format: {"regions": [{"id": ..., "users": [...]}]}
    New format: {"users": [{"id": ..., "regions": [...]}]}
    """
    if "users" in data:
        return data  # already new format
    if "regions" not in data:
        return {"users": []}
    # Build a flat set of users across all regions, collecting their regions
    users_map: dict[str, dict] = {}
    for region in data.get("regions", []):
        rid = region.get("id", "")
        rname = region.get("name", rid)
        for user in region.get("users", []):
            uid = user.get("id", "")
            uname = user.get("name", uid)
            if uid not in users_map:
                users_map[uid] = {"id": uid, "name": uname, "regions": []}
            users_map[uid]["regions"].append({"id": rid, "name": rname})
    return {"users": list(users_map.values())}


def load_groups() -> dict:
    """Load groups from groups.json; migrate old format and return user-first structure."""
    if not GROUPS_FILE.exists():
        return {"users": []}
    try:
        raw = json.loads(GROUPS_FILE.read_text(encoding="utf-8"))
        migrated = _migrate_if_needed(raw)
        if "regions" in raw and "users" not in raw:
            # Save migrated version back
            save_groups(migrated)
        return migrated
    except Exception:
        return {"users": []}


def save_groups(data: dict) -> None:
    GROUPS_FILE.parent.mkdir(exist_ok=True)
    GROUPS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def list_users() -> list[tuple[str, str]]:
    """Return list of (id, name) tuples for all top-level users."""
    data = load_groups()
    return [(u["id"], u.get("name", u["id"])) for u in data.get("users", [])]


def list_regions(user_id: str) -> list[tuple[str, str]]:
    """Return list of (id, name) tuples for regions belonging to a user."""
    data = load_groups()
    for user in data.get("users", []):
        if user["id"] == user_id:
            return [(r["id"], r.get("name", r["id"])) for r in user.get("regions", [])]
    return []


def get_user_name(user_id: str) -> str:
    """Return display name for a user id."""
    for uid, uname in list_users():
        if uid == user_id:
            return uname
    return user_id


def get_region_name(user_id: str, region_id: str) -> str:
    """Return display name for a region within a user."""
    for rid, rname in list_regions(user_id):
        if rid == region_id:
            return rname
    return region_id


# ---------------------------------------------------------------------------
# CRUD — Users
# ---------------------------------------------------------------------------

def add_user(user_id: str, name: str) -> bool:
    """Add a new top-level user. Returns False if id already exists."""
    user_id = sanitize_id(user_id)
    name = name.strip()
    if not user_id:
        return False
    data = load_groups()
    for u in data.get("users", []):
        if u["id"] == user_id:
            return False
    data.setdefault("users", []).append(
        {"id": user_id, "name": name or user_id, "regions": []}
    )
    save_groups(data)
    return True


def update_user(old_id: str, new_id: str, new_name: str) -> bool:
    """Update a user's id and/or name. Returns False if not found or new_id conflicts."""
    new_id = sanitize_id(new_id)
    new_name = new_name.strip()
    if not new_id:
        return False
    data = load_groups()
    if new_id != old_id:
        for u in data.get("users", []):
            if u["id"] == new_id:
                return False
    for user in data.get("users", []):
        if user["id"] == old_id:
            user["id"] = new_id
            user["name"] = new_name or new_id
            save_groups(data)
            return True
    return False


def delete_user(user_id: str) -> bool:
    """Delete a user and all their regions. Returns False if not found."""
    data = load_groups()
    before = len(data.get("users", []))
    data["users"] = [u for u in data.get("users", []) if u["id"] != user_id]
    if len(data["users"]) == before:
        return False
    save_groups(data)
    return True


# ---------------------------------------------------------------------------
# CRUD — Regions (within a user)
# ---------------------------------------------------------------------------

def add_region(user_id: str, region_id: str, name: str) -> bool:
    """Add a region to a user. Returns False if user not found or region exists."""
    region_id = sanitize_id(region_id)
    name = name.strip()
    if not region_id:
        return False
    data = load_groups()
    for user in data.get("users", []):
        if user["id"] == user_id:
            for r in user.get("regions", []):
                if r["id"] == region_id:
                    return False
            user.setdefault("regions", []).append(
                {"id": region_id, "name": name or region_id}
            )
            save_groups(data)
            return True
    return False


def update_region(user_id: str, old_id: str, new_id: str, new_name: str) -> bool:
    """Update a region within a user. Returns False if not found or id conflict."""
    new_id = sanitize_id(new_id)
    new_name = new_name.strip()
    if not new_id:
        return False
    data = load_groups()
    for user in data.get("users", []):
        if user["id"] == user_id:
            if new_id != old_id:
                for r in user.get("regions", []):
                    if r["id"] == new_id:
                        return False
            for region in user.get("regions", []):
                if region["id"] == old_id:
                    region["id"] = new_id
                    region["name"] = new_name or new_id
                    save_groups(data)
                    return True
    return False


def delete_region(user_id: str, region_id: str) -> bool:
    """Delete a region from a user. Returns False if not found."""
    data = load_groups()
    for user in data.get("users", []):
        if user["id"] == user_id:
            before = len(user.get("regions", []))
            user["regions"] = [r for r in user.get("regions", []) if r["id"] != region_id]
            if len(user["regions"]) == before:
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
    """
    if not region_id or not user_id:
        return "%prefix%/%topic%/"
    return f"{user_id}/{region_id}/%topic%/%prefix%/"


# ---------------------------------------------------------------------------
# Device registry  (profiles/device_registry.json)
# ---------------------------------------------------------------------------

DEVICE_REGISTRY_FILE = GROUPS_FILE.parent / "profiles" / "device_registry.json"


def load_device_registry() -> list[dict]:
    """Return list of registered device dicts."""
    try:
        if DEVICE_REGISTRY_FILE.exists():
            return json.loads(DEVICE_REGISTRY_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def save_device_to_registry(
    user_id: str,
    region_id: str,
    device_id: str,
    mac: str = "",
    board_type: str = "",
) -> None:
    """Upsert a device entry in the registry (keyed by user/region/device_id)."""
    if not user_id or not region_id or not device_id:
        return
    try:
        DEVICE_REGISTRY_FILE.parent.mkdir(exist_ok=True)
        devices = load_device_registry()
        import datetime as _dt
        today = _dt.date.today().isoformat()
        for entry in devices:
            if (entry.get("user_id") == user_id
                    and entry.get("region_id") == region_id
                    and entry.get("device_id") == device_id):
                if mac:
                    entry["mac"] = mac
                if board_type:
                    entry["board_type"] = board_type
                entry["last_configured"] = today
                break
        else:
            devices.append({
                "user_id": user_id,
                "region_id": region_id,
                "device_id": device_id,
                "mac": mac,
                "board_type": board_type,
                "last_configured": today,
            })
        DEVICE_REGISTRY_FILE.write_text(
            json.dumps(devices, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def get_devices_for_region(user_id: str, region_id: str) -> list[dict]:
    """Return registered devices for a given user/region."""
    return [
        d for d in load_device_registry()
        if d.get("user_id") == user_id and d.get("region_id") == region_id
    ]


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
