"""
conftest.py for cs_team tests.

Registers the .claude/hooks modules into sys.modules so that the
relative import path used in test_hooks_red.py resolves correctly:

    from .claude.hooks.injection_screen import screen_for_injection

resolves to tests.cs_team + '.claude' → which Python cannot import
directly because the directory name starts with a dot (not a valid
Python identifier).

This conftest bridges the gap by loading each hook module via
importlib and registering it under the dotted path that the relative
import expands to at collection time.

The mapping is:
    tests.cs_team..claude  →  (virtual package backed by .claude/__init__.py)
    tests.cs_team..claude.hooks  →  (virtual package backed by .claude/hooks/__init__.py)
    tests.cs_team..claude.hooks.injection_screen  →  .claude/hooks/injection_screen.py
    ... (and so on for each hook)
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

# Root of the worktree (two levels up from tests/cs_team/)
_REPO_ROOT = Path(__file__).parent.parent.parent

# The package prefix that relative imports inside tests/cs_team expand to
_PKG_PREFIX = "tests.cs_team"

# Mapping: dotted suffix → actual file path (relative to repo root)
_HOOK_MODULES: dict[str, Path] = {
    ".claude.hooks.injection_screen": _REPO_ROOT / ".claude" / "hooks" / "injection_screen.py",
    ".claude.hooks.pre_send_guard":   _REPO_ROOT / ".claude" / "hooks" / "pre_send_guard.py",
    ".claude.hooks.escalation_gate":  _REPO_ROOT / ".claude" / "hooks" / "escalation_gate.py",
    ".claude.hooks.grounding_check":  _REPO_ROOT / ".claude" / "hooks" / "grounding_check.py",
    ".claude.hooks.pii_redact":       _REPO_ROOT / ".claude" / "hooks" / "pii_redact.py",
}


def _make_namespace_package(full_name: str) -> types.ModuleType:
    """Create and register a namespace package for *full_name* if not present."""
    if full_name not in sys.modules:
        pkg = types.ModuleType(full_name)
        pkg.__path__ = []  # type: ignore[attr-defined]
        pkg.__package__ = full_name
        pkg.__spec__ = importlib.util.spec_from_loader(full_name, loader=None)  # type: ignore[assignment]
        sys.modules[full_name] = pkg
    return sys.modules[full_name]


def _register_hook_modules() -> None:
    """Load each hook file and register it under the relative-import path."""
    # Ensure parent packages exist in sys.modules
    _make_namespace_package(f"{_PKG_PREFIX}..claude")
    _make_namespace_package(f"{_PKG_PREFIX}..claude.hooks")

    for dotted_suffix, file_path in _HOOK_MODULES.items():
        full_name = f"{_PKG_PREFIX}.{dotted_suffix}"
        if full_name in sys.modules:
            continue  # already loaded

        if not file_path.exists():
            continue  # hook not yet built (RED phase) — let tests xfail naturally

        # Load the module from the actual file path
        module_name_for_load = file_path.stem  # e.g. "injection_screen"
        spec = importlib.util.spec_from_file_location(module_name_for_load, file_path)
        if spec is None or spec.loader is None:
            continue

        module = importlib.util.module_from_spec(spec)
        # Add repo root to sys.path so the hook can do `from src.guards.pii import redact_text`
        repo_root_str = str(_REPO_ROOT)
        if repo_root_str not in sys.path:
            sys.path.insert(0, repo_root_str)

        spec.loader.exec_module(module)  # type: ignore[union-attr]

        # Register under the full dotted path so relative imports resolve
        sys.modules[full_name] = module


# Run at import time (conftest loaded before test collection)
_register_hook_modules()
