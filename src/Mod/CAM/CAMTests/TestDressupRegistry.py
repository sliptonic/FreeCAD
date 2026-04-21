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

"""Unit tests for the dressup-picker registry and filter engine.

Covers prototype (v0) behaviour only. See
``src/Mod/CAM/research/unified_op_creation_plan.md``.
"""

from types import SimpleNamespace

import Path.Dressup.Gui.Registry as DressupRegistry
from CAMTests.PathTestUtils import PathTestBase


def _proxy(class_name):
    """Build a fake op proxy whose type's ``__name__`` matches ``class_name``."""
    cls = type(class_name, (), {})
    return cls()


def _op(class_name, **attrs):
    """Fake operation object with a Proxy named ``class_name`` and arbitrary attrs."""
    return SimpleNamespace(Name="Profile", Proxy=_proxy(class_name), **attrs)


def _dressup(name, base):
    """Fake dressup wrapping ``base``. Name must contain 'Dressup' for unwrap."""
    return SimpleNamespace(Name=name, Base=base, Proxy=_proxy(name + "Proxy"))


# --------------------------------------------------------------------------- #
# Helper-function tests
# --------------------------------------------------------------------------- #


class TestDressupRegistryHelpers(PathTestBase):
    def test_base_op_returns_path_when_not_dressup(self):
        op = _op("ObjectProfile")
        self.assertIs(DressupRegistry._base_op(op), op)

    def test_base_op_unwraps_single_dressup(self):
        op = _op("ObjectProfile")
        d = _dressup("Dressup", base=op)
        self.assertIs(DressupRegistry._base_op(d), op)

    def test_base_op_unwraps_stacked_dressups(self):
        op = _op("ObjectProfile")
        inner = _dressup("DressupDogbone", base=op)
        outer = _dressup("DressupTag", base=inner)
        self.assertIs(DressupRegistry._base_op(outer), op)

    def test_base_op_handles_none(self):
        self.assertIsNone(DressupRegistry._base_op(None))

    def test_class_name_returns_proxy_class_name(self):
        op = _op("ObjectPocket")
        self.assertEqual(DressupRegistry._base_op_class_name(op), "ObjectPocket")

    def test_class_name_empty_when_no_proxy(self):
        path = SimpleNamespace(Name="Stub")
        self.assertEqual(DressupRegistry._base_op_class_name(path), "")

    def test_has_attrs_true_when_all_present(self):
        op = _op("ObjectProfile", ClearanceHeight=10, SafeHeight=5, StartDepth=0)
        self.assertTrue(DressupRegistry._has_attrs(op, "ClearanceHeight", "SafeHeight"))

    def test_has_attrs_false_when_any_missing(self):
        op = _op("ObjectProfile", ClearanceHeight=10)
        self.assertFalse(DressupRegistry._has_attrs(op, "ClearanceHeight", "SafeHeight"))

    def test_is_2d_op_recognises_known_classes(self):
        for cls in ("ObjectProfile", "ObjectPocket", "ObjectShape", "ObjectMillFacing"):
            self.assertTrue(DressupRegistry._is_2d_op(_op(cls)), cls)

    def test_is_2d_op_rejects_3d_or_unknown(self):
        for cls in ("ObjectSurface", "ObjectAdaptive", "Whatever"):
            self.assertFalse(DressupRegistry._is_2d_op(_op(cls)), cls)


# --------------------------------------------------------------------------- #
# Per-dressup predicate tests
# --------------------------------------------------------------------------- #


class TestDressupPredicates(PathTestBase):
    def test_array_always_applies_to_a_path(self):
        self.assertTrue(DressupRegistry._applies_array(_op("ObjectProfile")))

    def test_array_rejects_none(self):
        self.assertFalse(DressupRegistry._applies_array(None))

    def test_boundary_requires_clearance_and_safe_heights(self):
        ok = _op("ObjectProfile", ClearanceHeight=10, SafeHeight=5)
        nok = _op("ObjectProfile", ClearanceHeight=10)
        self.assertTrue(DressupRegistry._applies_boundary(ok))
        self.assertFalse(DressupRegistry._applies_boundary(nok))

    def test_leadinout_requires_three_attrs(self):
        ok = _op("ObjectProfile", ClearanceHeight=10, SafeHeight=5, StartDepth=0)
        partial = _op("ObjectProfile", ClearanceHeight=10, SafeHeight=5)
        self.assertTrue(DressupRegistry._applies_leadinout(ok))
        self.assertFalse(DressupRegistry._applies_leadinout(partial))

    def test_dogbone_only_applies_to_2d_ops(self):
        self.assertTrue(DressupRegistry._applies_dogbone(_op("ObjectProfile")))
        self.assertTrue(DressupRegistry._applies_dogbone(_op("ObjectPocket")))
        self.assertFalse(DressupRegistry._applies_dogbone(_op("ObjectSurface")))

    def test_dogbone_unwraps_dressups_for_class_check(self):
        op = _op("ObjectProfile")
        d = _dressup("DressupTag", base=op)
        self.assertTrue(DressupRegistry._applies_dogbone(d))

    def test_tags_only_applies_to_2d_ops(self):
        self.assertTrue(DressupRegistry._applies_tags(_op("ObjectPocket")))
        self.assertFalse(DressupRegistry._applies_tags(_op("ObjectAdaptive")))

    def test_rampentry_requires_depth_bracket(self):
        ok = _op("ObjectProfile", StartDepth=0, FinalDepth=-5)
        nok = _op("ObjectProfile", StartDepth=0)
        self.assertTrue(DressupRegistry._applies_rampentry(ok))
        self.assertFalse(DressupRegistry._applies_rampentry(nok))


# --------------------------------------------------------------------------- #
# Filter engine tests
# --------------------------------------------------------------------------- #


class TestFilterDressups(PathTestBase):
    def setUp(self):
        super().setUp()
        self._registry = DressupRegistry.REGISTRY

    def _result_for(self, results, name):
        for r in results:
            if r.entry.name == name:
                return r
        self.fail("expected dressup {} in results".format(name))

    def test_no_path_marks_attribute_predicates_red(self):
        ctx = DressupRegistry.FilterContext(path=None)
        results = DressupRegistry.filter_dressups(self._registry, ctx)
        # Predicates that check attributes (Boundary, LeadInOut, RampEntry,
        # Dogbone, Tag) all reject None.
        for name in ("Boundary", "Lead In/Out", "Ramp Entry", "Dogbone", "Tag"):
            r = self._result_for(results, name)
            self.assertEqual(r.tier, DressupRegistry.TIER_RED, name)

    def test_2d_op_with_full_heights_lights_up_lead_inout(self):
        op = _op("ObjectProfile", ClearanceHeight=10, SafeHeight=5, StartDepth=0, FinalDepth=-5)
        ctx = DressupRegistry.FilterContext(path=op)
        results = DressupRegistry.filter_dressups(self._registry, ctx)
        for name in ("Lead In/Out", "Boundary", "Dogbone", "Tag", "Ramp Entry", "Array", "Mirror"):
            r = self._result_for(results, name)
            self.assertEqual(r.tier, DressupRegistry.TIER_GREEN, name)

    def test_3d_op_excludes_2d_only_dressups(self):
        op = _op("ObjectSurface", ClearanceHeight=10, SafeHeight=5, StartDepth=0, FinalDepth=-5)
        ctx = DressupRegistry.FilterContext(path=op)
        results = DressupRegistry.filter_dressups(self._registry, ctx)
        # Dogbone and Tag specifically require 2D ops.
        self.assertEqual(self._result_for(results, "Dogbone").tier, DressupRegistry.TIER_RED)
        self.assertEqual(self._result_for(results, "Tag").tier, DressupRegistry.TIER_RED)
        # Boundary and Lead In/Out only need attributes; they apply.
        self.assertEqual(self._result_for(results, "Boundary").tier, DressupRegistry.TIER_GREEN)
        self.assertEqual(self._result_for(results, "Lead In/Out").tier, DressupRegistry.TIER_GREEN)

    def test_predicate_exception_is_treated_as_red(self):
        def boom(_path):
            raise RuntimeError("predicate bug")

        entry = DressupRegistry.DressupRegistryEntry(
            name="Broken",
            command="CAM_DressupBroken",
            category="Modify",
            description="",
            applies_to_path_predicate=boom,
        )
        ctx = DressupRegistry.FilterContext(path=_op("ObjectProfile"))
        results = DressupRegistry.filter_dressups([entry], ctx)
        self.assertEqual(results[0].tier, DressupRegistry.TIER_RED)

    def test_results_sorted_with_green_first(self):
        op = _op("ObjectProfile", ClearanceHeight=10, SafeHeight=5, StartDepth=0, FinalDepth=-5)
        ctx = DressupRegistry.FilterContext(path=op)
        results = DressupRegistry.filter_dressups(self._registry, ctx)
        last_green_idx = -1
        first_red_idx = len(results)
        for i, r in enumerate(results):
            if r.tier == DressupRegistry.TIER_GREEN:
                last_green_idx = i
            elif r.tier == DressupRegistry.TIER_RED and i < first_red_idx:
                first_red_idx = i
        if last_green_idx >= 0 and first_red_idx < len(results):
            self.assertLess(last_green_idx, first_red_idx)


# --------------------------------------------------------------------------- #
# Pilot REGISTRY sanity
# --------------------------------------------------------------------------- #


class TestPilotDressupRegistry(PathTestBase):
    def test_registry_loads(self):
        self.assertGreater(len(DressupRegistry.REGISTRY), 0)

    def test_every_entry_has_command_and_category(self):
        for entry in DressupRegistry.REGISTRY:
            self.assertTrue(entry.command, entry.name)
            self.assertIn(entry.category, DressupRegistry.CATEGORIES, entry.name)
            self.assertTrue(entry.description, entry.name)

    def test_entries_cover_every_dressup_command(self):
        # The unified picker must register one entry per existing dressup
        # command. If a new dressup is added, this test fails until it's
        # registered here.
        expected = {
            "CAM_DressupArray",
            "CAM_DressupAxisMap",
            "CAM_DressupPathBoundary",
            "CAM_DressupDogbone",
            "CAM_DressupDragKnife",
            "CAM_DressupLeadInOut",
            "CAM_DressupMirror",
            "CAM_DressupRampEntry",
            "CAM_DressupTag",
            "CAM_DressupZCorrect",
        }
        registered = {e.command for e in DressupRegistry.REGISTRY}
        self.assertEqual(registered, expected)
