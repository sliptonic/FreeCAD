# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *   Copyright (c) 2026 sliptonic <shopinthewoods@gmail.com>               *
# *                                                                         *
# *   This file is part of the FreeCAD CAx development system.              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# ***************************************************************************

"""Operation-picker registry and filter engine.

Prototype (v0) of the unified "Create Operation..." picker. See
``src/Mod/CAM/research/unified_op_creation_plan.md`` for the design rationale
and the full-rollout backlog.

Prototype constraints intentionally reflected here:
- Pilot op set only (Profile, Pocket Shape, Drilling, Mill Facing, Engrave).
- Entries are declared inline in this module — no per-op file edits yet.
- ``tool_match_fn`` is a simple shape-hint check. Full rollout binds it to
  each op class's ``isToolSupported``.
- ``machine_predicate`` is always-True for the pilot set; rotary/5-axis gating
  is deferred.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Tuple

import Path.Op.Gui.Selection as PathOpSelection

# --------------------------------------------------------------------------- #
# Tier constants
# --------------------------------------------------------------------------- #

TIER_GREEN = "green"  # at least one TC in the Job satisfies tool_shape_hint
TIER_YELLOW = "yellow"  # creatable but no matching TC in the Job
TIER_RED = "red"  # selection or machine gate hard-fails
TIER_NEUTRAL = "neutral"  # Job has zero TCs — tool-tier is meaningless


# --------------------------------------------------------------------------- #
# Registry dataclass
# --------------------------------------------------------------------------- #


@dataclass
class OpRegistryEntry:
    """Declarative metadata for an operation in the picker.

    Full-rollout fields (``machine_predicate``, ``help_url``) are included
    here so that the dataclass shape is the API contract for migration.
    """

    name: str  # human-readable, e.g. "Profile"
    command: str  # FreeCAD command ID, e.g. "CAM_Profile"
    category: str  # "2D", "3D", "Drilling", "Engraving"
    description: str  # info-pane text
    selection_gate: Optional[Any] = None  # PathBaseGate instance or None
    tool_shape_hint: Optional[List[str]] = None  # e.g. ["drill"]; None = any
    machine_predicate: Callable[[Any], bool] = field(default_factory=lambda: (lambda machine: True))
    pixmap: str = ""  # icon resource name
    help_url: Optional[str] = None


# --------------------------------------------------------------------------- #
# Filter context
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FilterContext:
    """Live state the filter engine considers.

    ``selection`` is a list of (obj, sublist) tuples where ``sublist`` may be
    empty for whole-object selection. This matches the shape returned by
    ``FreeCADGui.Selection.getSelectionEx()`` reduced to
    ``(obj, list(sel.SubElementNames))``.
    """

    job: Any = None
    selection: Tuple = ()


# --------------------------------------------------------------------------- #
# Helpers (pure, no Qt)
# --------------------------------------------------------------------------- #


def _tool_shape_name(tool) -> str:
    """Lowercase shape name for a ToolBit. Empty string if unresolvable.

    Duplicates ``PathUtils.getToolShapeName`` to avoid pulling PathScripts
    into unit-test import paths. Kept in sync by the drift-guard test.
    """
    if tool is None:
        return ""
    if hasattr(tool, "ShapeName") and tool.ShapeName:
        return str(tool.ShapeName).lower()
    if hasattr(tool, "ShapeType") and tool.ShapeType:
        return str(tool.ShapeType).lower()
    return ""


def _tool_matches_hint(tool, shape_hint: Optional[List[str]]) -> bool:
    if shape_hint is None:
        return True
    name = _tool_shape_name(tool)
    if not name:
        return False
    hints = [s.lower() for s in shape_hint]
    return name in hints


def _selection_accepted(entry: OpRegistryEntry, selection) -> bool:
    """Does any sub-element of the current selection pass the entry's gate?

    Empty selection always returns True — an op with no selection is
    creatable, it just won't appear in the Suggested band.
    """
    if not selection:
        return True
    gate = entry.selection_gate
    if gate is None:
        return True
    for obj, subs in selection:
        doc = getattr(obj, "Document", None)
        if not subs:
            try:
                if gate.allow(doc, obj, ""):
                    return True
            except Exception:
                pass
            continue
        for sub in subs:
            try:
                if gate.allow(doc, obj, sub):
                    return True
            except Exception:
                pass
    return False


def _is_suggested(entry: OpRegistryEntry, selection) -> bool:
    """Suggested = there IS a selection AND the gate accepts it."""
    if not selection:
        return False
    return _selection_accepted(entry, selection)


def _classify_tool_tier(entry: OpRegistryEntry, job) -> str:
    if job is None:
        return TIER_NEUTRAL
    tools_group = None
    tools_obj = getattr(job, "Tools", None)
    if tools_obj is not None:
        tools_group = getattr(tools_obj, "Group", None)
    if not tools_group:
        return TIER_NEUTRAL
    if entry.tool_shape_hint is None:
        return TIER_GREEN
    for tc in tools_group:
        tool = getattr(tc, "Tool", None)
        if _tool_matches_hint(tool, entry.tool_shape_hint):
            return TIER_GREEN
    return TIER_YELLOW


def _shape_hint_text(entry: OpRegistryEntry) -> str:
    if not entry.tool_shape_hint:
        return "a suitable tool"
    names = list(entry.tool_shape_hint)
    if len(names) == 1:
        return f"a {names[0]} tool"
    return "a " + "/".join(names) + " tool"


# --------------------------------------------------------------------------- #
# Filter engine
# --------------------------------------------------------------------------- #


@dataclass
class FilterResult:
    entry: OpRegistryEntry
    tier: str
    suggested: bool
    reason: Optional[str] = None  # present when tier is Yellow or Red


def filter_ops(entries: List[OpRegistryEntry], context: FilterContext) -> List[FilterResult]:
    """Classify every entry against the live context.

    Sort key: Suggested first, then by tier priority (Green > Yellow > Red),
    then by category then name.
    """
    results: List[FilterResult] = []
    for entry in entries:
        # Machine gate (hard fail → Red)
        machine = None
        if context.job is not None:
            machine = getattr(context.job, "Machine", None)
        try:
            machine_ok = bool(entry.machine_predicate(machine))
        except Exception:
            machine_ok = True  # prototype: predicate bugs shouldn't hide ops

        # Selection gate (hard fail → Red)
        selection_ok = _selection_accepted(entry, context.selection)

        if not machine_ok:
            results.append(
                FilterResult(
                    entry=entry,
                    tier=TIER_RED,
                    suggested=False,
                    reason="operation not supported by this machine",
                )
            )
            continue
        if not selection_ok:
            results.append(
                FilterResult(
                    entry=entry,
                    tier=TIER_RED,
                    suggested=False,
                    reason="current selection is not accepted",
                )
            )
            continue

        tier = _classify_tool_tier(entry, context.job)
        reason = None
        if tier == TIER_YELLOW:
            reason = "needs " + _shape_hint_text(entry)

        results.append(
            FilterResult(
                entry=entry,
                tier=tier,
                suggested=_is_suggested(entry, context.selection),
                reason=reason,
            )
        )

    tier_rank = {TIER_GREEN: 0, TIER_NEUTRAL: 1, TIER_YELLOW: 2, TIER_RED: 3}
    results.sort(
        key=lambda r: (
            0 if r.suggested else 1,
            tier_rank.get(r.tier, 99),
            r.entry.category,
            r.entry.name,
        )
    )
    return results


# --------------------------------------------------------------------------- #
# Pilot REGISTRY
# --------------------------------------------------------------------------- #

REGISTRY: List[OpRegistryEntry] = [
    OpRegistryEntry(
        name="Profile",
        command="CAM_Profile",
        category="2D",
        description=(
            "Cuts along the edge or face of a model. Typical choice for cutting out "
            "the outside perimeter of a part, or finishing an inside pocket wall."
        ),
        selection_gate=PathOpSelection.PROFILEGate(),
        tool_shape_hint=None,  # most shapes work (endmill, ballend, etc.)
        pixmap="CAM_Profile",
    ),
    OpRegistryEntry(
        name="Pocket Shape",
        command="CAM_Pocket_Shape",
        category="2D",
        description=(
            "Clears material from inside a selected face, pocket, or closed shape. "
            "Supports rest machining."
        ),
        selection_gate=PathOpSelection.POCKETGate(),
        tool_shape_hint=["endmill", "ballend"],
        pixmap="CAM_Pocket",
    ),
    OpRegistryEntry(
        name="Mill Facing",
        command="CAM_MillFacing",
        category="2D",
        description=(
            "Faces off the top of stock or a selected surface. Removes material in "
            "horizontal passes using a flat-end or face mill."
        ),
        selection_gate=PathOpSelection.POCKETGate(),
        tool_shape_hint=["endmill"],
        pixmap="CAM_Face",
    ),
    OpRegistryEntry(
        name="Drilling",
        command="CAM_Drilling",
        category="Drilling",
        description=(
            "Drills holes at selected circular edges or cylindrical faces using "
            "standard drill cycles (peck, dwell, feed-retract)."
        ),
        selection_gate=PathOpSelection.DRILLGate(),
        tool_shape_hint=["drill"],
        pixmap="CAM_Drilling",
    ),
    OpRegistryEntry(
        name="Engrave",
        command="CAM_Engrave",
        category="Engraving",
        description=(
            "Traces edges or ShapeStrings with a fine-pointed tool. Used for "
            "lettering, decoration, and light scoring cuts."
        ),
        selection_gate=PathOpSelection.ENGRAVEGate(),
        tool_shape_hint=["vbit", "v-bit", "engraver", "chamfer"],
        pixmap="CAM_Engrave",
    ),
]


# Ordered list of category headings the picker renders. "Suggested" is
# synthetic — populated at filter time from any category.
CATEGORIES = ["2D", "Drilling", "Engraving", "3D"]
