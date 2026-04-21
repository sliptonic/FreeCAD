# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 sliptonic <shopinthewoods@gmail.com>
# SPDX-FileNotice: Part of the FreeCAD project.

################################################################################
#                                                                              #
#   FreeCAD is free software: you can redistribute it and/or modify            #
#   it under the terms of the GNU Lesser General Public License as             #
#   published by the Free Software Foundation, either version 2.1              #
#   of the License, or (at your option) any later version.                     #
#                                                                              #
#   FreeCAD is distributed in the hope that it will be useful,                 #
#   but WITHOUT ANY WARRANTY; without even the implied warranty                #
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.                    #
#   See the GNU Lesser General Public License for more details.                #
#                                                                              #
#   You should have received a copy of the GNU Lesser General Public           #
#   License along with FreeCAD. If not, see https://www.gnu.org/licenses       #
#                                                                              #
################################################################################

"""Dressup-picker registry and filter engine.

Parallel to ``Path.Op.Gui.Registry``. See
``src/Mod/CAM/research/unified_op_creation_plan.md`` for design rationale.

Dressup mode activates in the unified picker when the user has exactly one
Path operation or existing dressup selected in the tree. Each entry declares
an ``applies_to_path_predicate(path) -> bool`` that determines whether the
dressup is meaningful for the selected path.

Predicates are intentionally coarse for v0:
- "Always applies" for replication / correction dressups (Array, Mirror,
  ZCorrect, AxisMap, DragKnife) — they have no real op-type constraint.
- Attribute-based for the dressups whose existing ``IsActive`` already
  inspects base-op attributes (Boundary, LeadInOut, RampEntry).
- Class-name match for the 2D-only dressups (Dogbone, Tag).

Refining these predicates (e.g. inspecting actual path geometry for
plunges, planar moves, or rotary motion) is full-rollout work.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

# --------------------------------------------------------------------------- #
# Tier constants — dressups have only "applies" / "does not apply"
# --------------------------------------------------------------------------- #

TIER_GREEN = "green"  # predicate accepts the selected path
TIER_RED = "red"  # predicate rejects (hidden unless "Show all")


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #

CATEGORIES = ["Modify", "Entry/Exit", "Replicate", "Correct"]


# --------------------------------------------------------------------------- #
# Registry dataclass
# --------------------------------------------------------------------------- #


@dataclass
class DressupRegistryEntry:
    """Declarative metadata for a dressup in the picker."""

    name: str  # human-readable, e.g. "Dogbone"
    command: str  # FreeCAD command ID, e.g. "CAM_DressupDogbone"
    category: str  # one of CATEGORIES
    description: str  # info-pane text
    applies_to_path_predicate: Callable[[Any], bool] = field(
        default_factory=lambda: (lambda path: path is not None)
    )
    pixmap: str = ""  # icon resource name
    help_url: Optional[str] = None


@dataclass(frozen=True)
class FilterContext:
    """``path`` is the selected operation or existing dressup."""

    path: Any = None


# --------------------------------------------------------------------------- #
# Predicate helpers (pure, no Qt)
# --------------------------------------------------------------------------- #

# Class names of the proxy classes that represent 2D milling operations.
# Dressups like Dogbone and Tag are only meaningful for these.
_OP_CLASSES_2D = {
    "ObjectProfile",
    "ObjectPocket",
    "ObjectShape",  # Pocket Shape proxy
    "ObjectMillFacing",
    "ObjectFacing",
    "ObjectEngrave",
    "ObjectVcarve",
}


def _base_op(path):
    """Recursively unwrap dressups to the underlying operation."""
    if path is None:
        return None
    name = getattr(path, "Name", "")
    if name and "Dressup" in str(name) and hasattr(path, "Base"):
        return _base_op(path.Base)
    return path


def _base_op_class_name(path) -> str:
    base = _base_op(path)
    if base is None or not hasattr(base, "Proxy") or base.Proxy is None:
        return ""
    return type(base.Proxy).__name__


def _has_attrs(path, *attrs) -> bool:
    base = _base_op(path)
    if base is None:
        return False
    return all(hasattr(base, a) for a in attrs)


def _is_2d_op(path) -> bool:
    return _base_op_class_name(path) in _OP_CLASSES_2D


# --------------------------------------------------------------------------- #
# Per-dressup applicability predicates
# --------------------------------------------------------------------------- #


def _applies_array(path) -> bool:
    return path is not None


def _applies_axismap(path) -> bool:
    # Machine-class filtering (rotary capability) is deferred to full rollout.
    return path is not None


def _applies_boundary(path) -> bool:
    # Mirrors the existing IsActive in Path/Dressup/Gui/Boundary.py.
    return _has_attrs(path, "ClearanceHeight", "SafeHeight")


def _applies_dogbone(path) -> bool:
    return _is_2d_op(path)


def _applies_dragknife(path) -> bool:
    return path is not None


def _applies_leadinout(path) -> bool:
    # Mirrors the existing IsActive in Path/Dressup/Gui/LeadInOut.py.
    return _has_attrs(path, "ClearanceHeight", "SafeHeight", "StartDepth")


def _applies_mirror(path) -> bool:
    return path is not None


def _applies_rampentry(path) -> bool:
    # Ramps need depth bracketing; ops without StartDepth/FinalDepth (e.g.
    # pure rotary post-processors) have nothing to ramp into.
    return _has_attrs(path, "StartDepth", "FinalDepth")


def _applies_tags(path) -> bool:
    return _is_2d_op(path)


def _applies_zcorrect(path) -> bool:
    return path is not None


# --------------------------------------------------------------------------- #
# Filter engine
# --------------------------------------------------------------------------- #


@dataclass
class FilterResult:
    entry: DressupRegistryEntry
    tier: str
    suggested: bool = False
    reason: Optional[str] = None


def filter_dressups(
    entries: List[DressupRegistryEntry], context: FilterContext
) -> List[FilterResult]:
    """Classify every dressup entry against the live context.

    Sort key: applicable first, then by category then name.
    """
    results: List[FilterResult] = []
    for entry in entries:
        try:
            applies = bool(entry.applies_to_path_predicate(context.path))
        except Exception:
            applies = False
        if applies:
            results.append(FilterResult(entry=entry, tier=TIER_GREEN, suggested=True))
        else:
            results.append(
                FilterResult(
                    entry=entry,
                    tier=TIER_RED,
                    suggested=False,
                    reason="not applicable to the selected path",
                )
            )

    tier_rank = {TIER_GREEN: 0, TIER_RED: 1}
    results.sort(
        key=lambda r: (
            tier_rank.get(r.tier, 99),
            r.entry.category,
            r.entry.name,
        )
    )
    return results


# --------------------------------------------------------------------------- #
# Pilot REGISTRY
# --------------------------------------------------------------------------- #

REGISTRY: List[DressupRegistryEntry] = [
    DressupRegistryEntry(
        name="Array",
        command="CAM_DressupArray",
        category="Replicate",
        description=(
            "Replicates the selected toolpath in a linear or polar array. "
            "Useful for repeated features like bolt-hole patterns."
        ),
        applies_to_path_predicate=_applies_array,
        pixmap="CAM_DressupArray",
    ),
    DressupRegistryEntry(
        name="Axis Map",
        command="CAM_DressupAxisMap",
        category="Correct",
        description=(
            "Remaps one axis to another (e.g. Y → A) for rotary or " "multi-axis machines."
        ),
        applies_to_path_predicate=_applies_axismap,
        pixmap="CAM_DressupAxisMap",
    ),
    DressupRegistryEntry(
        name="Boundary",
        command="CAM_DressupPathBoundary",
        category="Correct",
        description=(
            "Trims the toolpath to a 2D boundary. Useful when the path "
            "exceeds the area you actually want machined."
        ),
        applies_to_path_predicate=_applies_boundary,
        pixmap="CAM_DressupPathBoundary",
    ),
    DressupRegistryEntry(
        name="Dogbone",
        command="CAM_DressupDogbone",
        category="Modify",
        description=(
            "Adds dogbone or T-bone notches to internal sharp corners so "
            "a round endmill can fit a square pocket."
        ),
        applies_to_path_predicate=_applies_dogbone,
        pixmap="CAM_DressupDogbone",
    ),
    DressupRegistryEntry(
        name="Drag Knife",
        command="CAM_DressupDragKnife",
        category="Modify",
        description=(
            "Adds corner-action moves so a trailing drag-knife tool tracks "
            "the path correctly through corners."
        ),
        applies_to_path_predicate=_applies_dragknife,
        pixmap="CAM_DressupDragKnife",
    ),
    DressupRegistryEntry(
        name="Lead In/Out",
        command="CAM_DressupLeadInOut",
        category="Entry/Exit",
        description=(
            "Adds tangent entry and exit motions to the toolpath, reducing "
            "tool marks and cut-start dwell."
        ),
        applies_to_path_predicate=_applies_leadinout,
        pixmap="CAM_DressupLeadInOut",
    ),
    DressupRegistryEntry(
        name="Mirror",
        command="CAM_DressupMirror",
        category="Replicate",
        description=(
            "Mirrors the toolpath across an axis. Useful for symmetric "
            "parts or for converting setup orientations."
        ),
        applies_to_path_predicate=_applies_mirror,
        pixmap="CAM_DressupMirror",
    ),
    DressupRegistryEntry(
        name="Ramp Entry",
        command="CAM_DressupRampEntry",
        category="Entry/Exit",
        description=(
            "Replaces vertical plunges with ramped or helical entries to "
            "reduce tool load and avoid plunge stress."
        ),
        applies_to_path_predicate=_applies_rampentry,
        pixmap="CAM_DressupRampEntry",
    ),
    DressupRegistryEntry(
        name="Tag",
        command="CAM_DressupTag",
        category="Modify",
        description=(
            "Inserts holding tags into 2D profile cuts so the part stays "
            "fixtured until the cut is complete."
        ),
        applies_to_path_predicate=_applies_tags,
        pixmap="CAM_DressupTag",
    ),
    DressupRegistryEntry(
        name="Z Depth Correction",
        command="CAM_DressupZCorrect",
        category="Correct",
        description=(
            "Adjusts Z heights along the path using a probe map to "
            "compensate for non-flat stock surfaces."
        ),
        applies_to_path_predicate=_applies_zcorrect,
        pixmap="CAM_DressupZCorrect",
    ),
]
