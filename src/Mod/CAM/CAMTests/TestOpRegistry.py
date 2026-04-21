# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *   Copyright (c) 2026 sliptonic <shopinthewoods@gmail.com>               *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# ***************************************************************************

"""Unit tests for the operation-picker registry and filter engine.

Covers prototype (v0) behaviour only. Full-rollout drift-guards and
integration tests against the live dialog land later. See
``src/Mod/CAM/research/unified_op_creation_plan.md``.
"""

from types import SimpleNamespace

import FreeCAD

import Path.Op.Gui.Registry as Registry
from CAMTests.PathTestUtils import PathTestBase


def _tc(shape_name):
    """Fake ToolController carrying a fake ToolBit with the given ShapeName."""
    return SimpleNamespace(Tool=SimpleNamespace(ShapeName=shape_name))


def _job(tcs, machine=None):
    """Fake Job exposing Tools.Group and Machine."""
    return SimpleNamespace(Tools=SimpleNamespace(Group=list(tcs)), Machine=machine)


# --------------------------------------------------------------------------- #
# Pure-function tests (no document)
# --------------------------------------------------------------------------- #


class TestRegistryHelpers(PathTestBase):
    def test_tool_shape_name_reads_shapename(self):
        tool = SimpleNamespace(ShapeName="EndMill")
        self.assertEqual(Registry._tool_shape_name(tool), "endmill")

    def test_tool_shape_name_falls_back_to_shapetype(self):
        tool = SimpleNamespace(ShapeType="Drill")
        self.assertEqual(Registry._tool_shape_name(tool), "drill")

    def test_tool_shape_name_empty_when_missing(self):
        tool = SimpleNamespace()
        self.assertEqual(Registry._tool_shape_name(tool), "")

    def test_tool_shape_name_handles_none(self):
        self.assertEqual(Registry._tool_shape_name(None), "")

    def test_matches_hint_none_accepts_any(self):
        self.assertTrue(Registry._tool_matches_hint(SimpleNamespace(ShapeName="drill"), None))

    def test_matches_hint_case_insensitive(self):
        self.assertTrue(
            Registry._tool_matches_hint(SimpleNamespace(ShapeName="EndMill"), ["endmill"])
        )

    def test_matches_hint_rejects_non_member(self):
        self.assertFalse(
            Registry._tool_matches_hint(SimpleNamespace(ShapeName="endmill"), ["drill"])
        )


class TestToolTierClassification(PathTestBase):
    def setUp(self):
        self.drill_entry = Registry.OpRegistryEntry(
            name="Drilling",
            command="CAM_Drilling",
            category="Drilling",
            description="",
            tool_shape_hint=["drill"],
        )
        self.any_entry = Registry.OpRegistryEntry(
            name="Profile",
            command="CAM_Profile",
            category="2D",
            description="",
            tool_shape_hint=None,
        )

    def test_green_when_matching_tc_present(self):
        job = _job([_tc("drill")])
        self.assertEqual(Registry._classify_tool_tier(self.drill_entry, job), Registry.TIER_GREEN)

    def test_yellow_when_no_matching_tc(self):
        job = _job([_tc("endmill")])
        self.assertEqual(Registry._classify_tool_tier(self.drill_entry, job), Registry.TIER_YELLOW)

    def test_neutral_when_zero_tcs(self):
        job = _job([])
        self.assertEqual(Registry._classify_tool_tier(self.drill_entry, job), Registry.TIER_NEUTRAL)

    def test_neutral_when_job_is_none(self):
        self.assertEqual(
            Registry._classify_tool_tier(self.drill_entry, None), Registry.TIER_NEUTRAL
        )

    def test_any_shape_hint_green_with_any_tc(self):
        job = _job([_tc("endmill")])
        self.assertEqual(Registry._classify_tool_tier(self.any_entry, job), Registry.TIER_GREEN)

    def test_multi_hint_matches_any_listed_shape(self):
        entry = Registry.OpRegistryEntry(
            name="Pocket",
            command="CAM_Pocket_Shape",
            category="2D",
            description="",
            tool_shape_hint=["endmill", "ballend"],
        )
        self.assertEqual(
            Registry._classify_tool_tier(entry, _job([_tc("ballend")])), Registry.TIER_GREEN
        )
        self.assertEqual(
            Registry._classify_tool_tier(entry, _job([_tc("drill")])), Registry.TIER_YELLOW
        )


# --------------------------------------------------------------------------- #
# Selection-gate integration (real Part shapes)
# --------------------------------------------------------------------------- #


class TestFilterWithSelection(PathTestBase):
    """Exercise filter_ops against real Part geometry to cover the gates."""

    def setUp(self):
        self.doc = FreeCAD.newDocument("TestOpRegistry")
        self.box = self.doc.addObject("Part::Box", "Box")
        self.box.Length = 20
        self.box.Width = 20
        self.box.Height = 10
        # Box with a drillable hole
        self.cyl = self.doc.addObject("Part::Cylinder", "Cyl")
        self.cyl.Radius = 2
        self.cyl.Height = 10
        self.cut = self.doc.addObject("Part::Cut", "Cut")
        self.cut.Base = self.box
        self.cut.Tool = self.cyl
        self.doc.recompute()

    def tearDown(self):
        FreeCAD.closeDocument("TestOpRegistry")

    def _by_name(self, results, name):
        for r in results:
            if r.entry.name == name:
                return r
        self.fail("No result for op {!r}".format(name))

    def test_empty_selection_all_accepted_none_suggested(self):
        ctx = Registry.FilterContext(job=_job([_tc("endmill")]), selection=())
        results = Registry.filter_ops(Registry.REGISTRY, ctx)
        self.assertEqual(len(results), len(Registry.REGISTRY))
        for r in results:
            self.assertNotEqual(r.tier, Registry.TIER_RED)
            self.assertFalse(r.suggested)

    def test_face_selection_suggests_face_ops(self):
        # Top face of Box (Face6 on Part::Box is typically the top; pick any face)
        obj = self.box
        subs = ["Face1"]
        ctx = Registry.FilterContext(job=_job([_tc("endmill")]), selection=((obj, subs),))
        results = Registry.filter_ops(Registry.REGISTRY, ctx)
        # Profile, Pocket Shape, Mill Facing should all accept a face
        self.assertTrue(self._by_name(results, "Profile").suggested)
        self.assertTrue(self._by_name(results, "Pocket Shape").suggested)
        self.assertTrue(self._by_name(results, "Mill Facing").suggested)

    def test_drill_selection_suggests_drilling(self):
        # A cylindrical face on the cut body should be drillable
        obj = self.cut
        # Find a circular edge/face by trying edges (DRILLGate uses isDrillable)
        drillable_sub = None
        for i in range(1, len(obj.Shape.Edges) + 1):
            name = "Edge{}".format(i)
            gate = Registry.REGISTRY[3].selection_gate  # Drilling entry
            if gate.allow(obj.Document, obj, name):
                drillable_sub = name
                break
        self.assertIsNotNone(drillable_sub, "test fixture has no drillable edge")
        ctx = Registry.FilterContext(job=_job([_tc("drill")]), selection=((obj, [drillable_sub]),))
        results = Registry.filter_ops(Registry.REGISTRY, ctx)
        self.assertTrue(self._by_name(results, "Drilling").suggested)
        self.assertEqual(self._by_name(results, "Drilling").tier, Registry.TIER_GREEN)

    def test_endmill_only_job_marks_drilling_yellow(self):
        ctx = Registry.FilterContext(job=_job([_tc("endmill")]), selection=())
        results = Registry.filter_ops(Registry.REGISTRY, ctx)
        drilling = self._by_name(results, "Drilling")
        self.assertEqual(drilling.tier, Registry.TIER_YELLOW)
        self.assertIsNotNone(drilling.reason)
        self.assertIn("drill", drilling.reason.lower())
        # Profile has no shape constraint → Green
        self.assertEqual(self._by_name(results, "Profile").tier, Registry.TIER_GREEN)

    def test_drill_only_job_marks_pocket_yellow(self):
        ctx = Registry.FilterContext(job=_job([_tc("drill")]), selection=())
        results = Registry.filter_ops(Registry.REGISTRY, ctx)
        self.assertEqual(self._by_name(results, "Drilling").tier, Registry.TIER_GREEN)
        self.assertEqual(self._by_name(results, "Pocket Shape").tier, Registry.TIER_YELLOW)
        self.assertEqual(self._by_name(results, "Mill Facing").tier, Registry.TIER_YELLOW)

    def test_zero_tc_job_is_neutral(self):
        ctx = Registry.FilterContext(job=_job([]), selection=())
        results = Registry.filter_ops(Registry.REGISTRY, ctx)
        for r in results:
            self.assertEqual(r.tier, Registry.TIER_NEUTRAL, r.entry.name)

    def test_machine_predicate_red_failure(self):
        entry = Registry.OpRegistryEntry(
            name="FakeRotary",
            command="CAM_FakeRotary",
            category="Rotary",
            description="",
            machine_predicate=lambda m: False,
        )
        ctx = Registry.FilterContext(job=_job([_tc("endmill")]), selection=())
        (result,) = Registry.filter_ops([entry], ctx)
        self.assertEqual(result.tier, Registry.TIER_RED)
        self.assertIsNotNone(result.reason)

    def test_sort_order_suggested_first(self):
        # Select a face → Pocket/Profile/MillFacing suggested; Drilling not.
        ctx = Registry.FilterContext(
            job=_job([_tc("endmill")]),
            selection=((self.box, ["Face1"]),),
        )
        results = Registry.filter_ops(Registry.REGISTRY, ctx)
        suggested_positions = [i for i, r in enumerate(results) if r.suggested]
        non_suggested_positions = [i for i, r in enumerate(results) if not r.suggested]
        self.assertTrue(suggested_positions, "expected at least one suggested op")
        self.assertLess(max(suggested_positions), min(non_suggested_positions))


# --------------------------------------------------------------------------- #
# Pilot-registry sanity
# --------------------------------------------------------------------------- #


class TestPilotRegistry(PathTestBase):
    def test_pilot_registry_loads(self):
        self.assertEqual(len(Registry.REGISTRY), 5)
        names = {e.name for e in Registry.REGISTRY}
        self.assertEqual(names, {"Profile", "Pocket Shape", "Mill Facing", "Drilling", "Engrave"})

    def test_every_entry_has_command_and_category(self):
        for e in Registry.REGISTRY:
            self.assertTrue(e.command.startswith("CAM_"), e.name)
            self.assertIn(e.category, Registry.CATEGORIES, e.name)
            self.assertTrue(e.description, e.name)
