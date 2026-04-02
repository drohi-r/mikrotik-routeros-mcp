from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .models import DeviceConfig


_HIGH_RISK_TOKENS = (
    "remove",
    "disable",
    "reset",
    "reboot",
    "shutdown",
    "format-drive",
    "erase",
)

_MEDIUM_RISK_TOKENS = (
    "add",
    "set",
    "enable",
    "move",
)


@dataclass(slots=True)
class ScriptPlan:
    device: str
    reason: str
    risk: str
    writes_allowed: bool
    approval_code: str
    blocked: bool
    summary: str


def classify_script_risk(script: str) -> str:
    lowered = script.lower()
    if any(re.search(rf"\b{re.escape(token)}\b", lowered) for token in _HIGH_RISK_TOKENS):
        return "high"
    if any(re.search(rf"\b{re.escape(token)}\b", lowered) for token in _MEDIUM_RISK_TOKENS):
        return "medium"
    return "low"


def build_approval_code(device_name: str, script: str, reason: str) -> str:
    digest = hashlib.sha256(f"{device_name}\n{reason.strip()}\n{script.strip()}".encode("utf-8")).hexdigest()
    return digest[:12]


def plan_script_change(device: DeviceConfig, script: str, reason: str) -> ScriptPlan:
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValueError("reason is required for planned changes.")
    normalized_script = script.strip()
    if not normalized_script:
        raise ValueError("script must not be empty.")
    risk = classify_script_risk(normalized_script)
    writes_allowed = device.allow_writes
    blocked = not writes_allowed
    summary = (
        "Writes are disabled for this device. Set allow_writes: true to permit apply_script_change."
        if blocked
        else f"Script classified as {risk} risk for device {device.name}."
    )
    return ScriptPlan(
        device=device.name,
        reason=normalized_reason,
        risk=risk,
        writes_allowed=writes_allowed,
        approval_code=build_approval_code(device.name, normalized_script, normalized_reason),
        blocked=blocked,
        summary=summary,
    )


def verify_approval_code(device_name: str, script: str, reason: str, approval_code: str) -> None:
    expected = build_approval_code(device_name, script, reason)
    if approval_code != expected:
        raise ValueError("approval_code does not match the current device, reason, and script payload.")
