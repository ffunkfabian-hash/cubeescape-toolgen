"""Authoring contracts shared by the tool generator, QA, and Unity export."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List


DEFAULT_SCHEMA: Dict[str, Any] = {
    "contract_version": 1,
    "tool_id": "tool_id",
    "name": "Tool",
    "category": "interactive",
    "verb": "USE",
    "use_type": "interaction",
    "unity_name": "Tool",
    "pivot": "grip",
    "bounds_m": {"size": [0.0, 0.0, 0.0], "center": [0.0, 0.0, 0.0]},
    "hand_socket": {"name": "Socket_Hand", "position": [0.0, 0.0, 0.0]},
    "muzzle_socket": {"name": "Muzzle", "position": [0.0, 0.0, 0.0]},
    "support_hand_socket": {"name": "Socket_SupportHand", "position": [0.0, 0.0, 0.0]},
    "fps_root": {"name": "FPS_Root", "position": [0.0, 0.0, 0.0]},
    "fps_hand_socket": {"name": "Socket_Hand_FPS", "position": [0.0, 0.0, 0.0]},
    "materials": ["M_White", "M_Accent"],
    "qa": {
        "mesh_closed": True,
        "positive_volume": True,
        "finite_coordinates": True,
        "uvs_valid": True,
        "meter_scale": True,
        "facing": "-Y",
    },
}


PRESETS: Dict[str, Dict[str, Any]] = {
    "portal_emitter": {
        "tool_id": "portal_emitter",
        "name": "Portal Emitter",
        "category": "interactive",
        "verb": "VERBINDEN",
        "use_type": "aim",
        "unity_name": "PortalEmitter",
        "pivot": "grip",
        "bounds_m": {"size": [0.315, 0.86, 0.5], "center": [0.0, -0.349, 0.07]},
        "hand_socket": {"name": "Socket_Hand", "position": [0.0, 0.0, 0.0]},
        "muzzle_socket": {"name": "Muzzle", "position": [0.0, -0.77, 0.14]},
        "support_hand_socket": {"name": "Socket_SupportHand", "position": [0.0, -0.18, 0.23]},
        "fps_root": {"name": "FPS_Root", "position": [0.0, 0.0, 0.0]},
        "fps_hand_socket": {"name": "Socket_Hand_FPS", "position": [0.0, 0.0, 0.0]},
        "materials": ["M_RobotDark", "M_White", "M_GlowCyan"],
        "qa": {
            "mesh_closed": True,
            "positive_volume": True,
            "finite_coordinates": True,
            "uvs_valid": True,
            "meter_scale": True,
            "facing": "-Y",
        },
    },
    "magnet_gripper": {
        "tool_id": "magnet_gripper",
        "name": "Magnet Gripper",
        "category": "interactive",
        "verb": "BEWEGEN",
        "use_type": "interaction",
        "unity_name": "MagnetGripper",
        "pivot": "center",
        "bounds_m": {"size": [0.72, 0.32, 0.92], "center": [0.0, 0.0, 0.15]},
        "hand_socket": {"name": "Socket_Hand", "position": [0.0, -0.1, 0.0]},
        "muzzle_socket": {"name": "Socket_Muzzle", "position": [0.0, -0.52, 0.0]},
        "support_hand_socket": {"name": "Socket_SupportHand", "position": [0.0, 0.06, -0.18]},
        "fps_root": {"name": "FPS_Root", "position": [0.0, 0.0, 0.0]},
        "fps_hand_socket": {"name": "Socket_Hand_FPS", "position": [-0.26, -0.66, -0.5]},
        "materials": ["M_White", "M_Accent_Blue", "M_Metal"],
        "qa": {
            "mesh_closed": True,
            "positive_volume": True,
            "finite_coordinates": True,
            "uvs_valid": True,
            "meter_scale": True,
            "facing": "-Y",
        },
    },
    "flashlight": {
        "tool_id": "flashlight",
        "name": "Flashlight",
        "category": "interactive",
        "verb": "LEUCHTEN",
        "use_type": "tool_key",
        "unity_name": "Flashlight",
        "pivot": "center",
        "bounds_m": {"size": [0.3, 0.2, 0.8], "center": [0.0, 0.0, 0.12]},
        "hand_socket": {"name": "Socket_Hand", "position": [0.0, -0.1, 0.02]},
        "muzzle_socket": {"name": "Socket_Muzzle", "position": [0.0, -0.36, 0.0]},
        "support_hand_socket": {"name": "Socket_SupportHand", "position": [0.0, 0.0, -0.18]},
        "fps_root": {"name": "FPS_Root", "position": [0.0, 0.0, 0.0]},
        "fps_hand_socket": {"name": "Socket_Hand_FPS", "position": [0.05, -0.25, -0.22]},
        "materials": ["M_White", "M_Accent_Orange", "M_Emissive_Forward"],
        "qa": {
            "mesh_closed": True,
            "positive_volume": True,
            "finite_coordinates": True,
            "uvs_valid": True,
            "meter_scale": True,
            "facing": "-Y",
        },
    },
    "bow": {
        "tool_id": "bow",
        "name": "Bow",
        "category": "interactive",
        "verb": "SCHIEßEN",
        "use_type": "aim",
        "unity_name": "Bow",
        "pivot": "center",
        "bounds_m": {"size": [0.4, 0.8, 0.14], "center": [0.0, 0.18, 0.0]},
        "hand_socket": {"name": "Socket_Hand", "position": [0.0, 0.15, 0.0]},
        "muzzle_socket": {"name": "Socket_Muzzle", "position": [0.0, 0.55, 0.0]},
        "support_hand_socket": {"name": "Socket_SupportHand", "position": [0.0, -0.1, 0.0]},
        "fps_root": {"name": "FPS_Root", "position": [0.0, 0.0, 0.0]},
        "fps_hand_socket": {"name": "Socket_Hand_FPS", "position": [-0.15, -0.3, -0.1]},
        "materials": ["M_White", "M_Accent_Orange", "M_Metal"],
        "qa": {
            "mesh_closed": True,
            "positive_volume": True,
            "finite_coordinates": True,
            "uvs_valid": True,
            "meter_scale": True,
            "facing": "-Y",
        },
    },
}


def build_tool_contract(tool_id: str, overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if tool_id not in PRESETS:
        raise KeyError(f"unknown tool preset: {tool_id}")
    template = deepcopy(DEFAULT_SCHEMA)
    template.update(deepcopy(PRESETS[tool_id]))
    if overrides:
        template.update(overrides)
    return template


def validate_contract(contract: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    required = [
        "contract_version",
        "tool_id",
        "name",
        "category",
        "verb",
        "use_type",
        "unity_name",
        "pivot",
        "bounds_m",
        "hand_socket",
        "muzzle_socket",
        "support_hand_socket",
        "fps_root",
        "fps_hand_socket",
        "materials",
        "qa",
    ]
    for key in required:
        if key not in contract:
            issues.append(f"missing key: {key}")

    bounds = contract.get("bounds_m")
    if isinstance(bounds, dict):
        for field in ("size", "center"):
            value = bounds.get(field)
            if not isinstance(value, list) or len(value) != 3:
                issues.append(f"bounds_m.{field} must contain three numbers")
            elif any(not isinstance(item, (int, float)) for item in value):
                issues.append(f"bounds_m.{field} must contain only numbers")
        size = bounds.get("size")
        if isinstance(size, list) and len(size) == 3 and any(
            not isinstance(item, (int, float)) or item <= 0 for item in size
        ):
            issues.append("bounds_m.size values must be positive")
    elif bounds is not None:
        issues.append("bounds_m must be an object")

    for field in ("hand_socket", "muzzle_socket", "support_hand_socket", "fps_root", "fps_hand_socket"):
        socket = contract.get(field)
        if not isinstance(socket, dict):
            if socket is not None:
                issues.append(f"{field} must be an object")
            continue
        if not isinstance(socket.get("name"), str) or not socket["name"]:
            issues.append(f"{field}.name must be a non-empty string")
        position = socket.get("position")
        if not isinstance(position, list) or len(position) != 3:
            issues.append(f"{field}.position must contain three numbers")
        elif any(not isinstance(item, (int, float)) for item in position):
            issues.append(f"{field}.position must contain only numbers")

    if contract.get("use_type") not in {"interaction", "tool_key", "aim"}:
        issues.append("use_type must be interaction, tool_key, or aim")
    if not isinstance(contract.get("materials"), list) or not contract.get("materials"):
        issues.append("materials must be a non-empty list")
    return issues
