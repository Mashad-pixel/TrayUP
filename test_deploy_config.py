"""Deployment settings that drift silently.

The blueprint and the Vercel rewrite are read as text, so these checks need no YAML parser and no
running server. The config check runs the real app.config module in a subprocess; it needs the
project's requirements installed (CI does this) and assumes no local .env sets the two variables it
clears.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RENDER_YAML = (ROOT / "render.yaml").read_text(encoding="utf-8")
VERCEL = json.loads((ROOT / "frontend" / "vercel.json").read_text(encoding="utf-8"))


def _render_service_name(kind):
    match = re.search(rf"- type: {kind}\s*\n\s*name:\s*(\S+)", RENDER_YAML)
    assert match, f"render.yaml has no {kind} service"
    return match.group(1)


def _env_entries():
    """Map each envVars key in render.yaml to the stripped lines that follow it."""
    entries, current = {}, None
    for line in RENDER_YAML.splitlines():
        key = re.match(r"^\s*- key:\s*(\S+)\s*$", line)
        if key:
            current = key.group(1)
            entries[current] = []
        elif re.match(r"^\s*- (type|name):", line) or re.match(r"^\S", line):
            current = None
        elif current and line.strip() and not line.strip().startswith("#"):
            entries[current].append(line.strip())
    return entries


def test_vercel_rewrite_targets_the_render_web_service():
    host = _render_service_name("web") + ".onrender.com"
    destination = VERCEL["rewrites"][0]["destination"]
    assert destination.startswith(f"https://{host}/"), destination


def test_firebase_is_an_explicit_operator_choice():
    assert _env_entries().get("FIREBASE_ENABLED") == ["sync: false"], "FIREBASE_ENABLED must be sync: false"


def test_rate_limit_store_is_the_shared_keyvalue_service():
    entries = _env_entries()
    keyvalue = _render_service_name("keyvalue")
    assert entries["RATELIMIT_STORAGE_URI"] == [
        "fromService:",
        "type: keyvalue",
        f"name: {keyvalue}",
        "property: connectionString",
    ]


def test_in_memory_rate_limit_fallback_is_off_in_the_blueprint():
    assert _env_entries().get("RATELIMIT_ALLOW_MEMORY") == ['value: "false"'], "RATELIMIT_ALLOW_MEMORY must be false"


def test_canteen_location_is_supplied_by_the_operator():
    entries = _env_entries()
    assert entries.get("CANTEEN_LATITUDE") == ["sync: false"], "CANTEEN_LATITUDE must be sync: false"
    assert entries.get("CANTEEN_LONGITUDE") == ["sync: false"], "CANTEEN_LONGITUDE must be sync: false"


def test_no_duplicate_modules_at_repo_root():
    for name in ("session_service.py", "user.py", "admin_staff.py", "staff_service.py"):
        assert not (ROOT / name).exists(), f"{name} duplicates a module under app/"


def test_migration_filenames_start_with_their_revision_id():
    for path in sorted((ROOT / "migrations" / "versions").glob("*.py")):
        match = re.search(r"^revision\s*=\s*[\"']([0-9a-f]+)[\"']", path.read_text(encoding="utf-8"), re.M)
        assert match, f"{path.name} declares no revision"
        assert path.name.startswith(match.group(1) + "_"), path.name


def test_config_defaults_do_not_depend_on_the_render_variable():
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("RATELIMIT_ALLOW_MEMORY", "CANTEEN_LATITUDE", "CANTEEN_LONGITUDE")
    }
    env["RENDER"] = "true"
    code = (
        "from app.config import Config; "
        "print(Config.RATELIMIT_ALLOW_MEMORY, Config.CANTEEN_LATITUDE, Config.CANTEEN_LONGITUDE)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, check=True
    )
    assert result.stdout.split() == ["False", "None", "None"], result.stdout
