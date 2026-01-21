# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *   Copyright (c) 2016 sliptonic <shopinthewoods@gmail.com>               *
# *   Copyright (c) 2022 Larry Woestman <LarryWoestman2@gmail.com>          *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************


import FreeCAD
import Path
import Path.Post.Command as PathCommand
import Path.Post.Processor as PathPost
import Path.Post.Utils as PostUtils
import Path.Main.Job as PathJob
import Path.Tool.Controller as PathToolController
import unittest

PathCommand.LOG_MODULE = Path.Log.thisModule()
Path.Log.setLevel(Path.Log.Level.INFO, PathCommand.LOG_MODULE)


class TestPathPostUtils(unittest.TestCase):
    def test010(self):
        """Test the utility functions in the PostUtils.py file."""
        commands = [
            Path.Command("G1 X-7.5 Y5.0 Z0.0"),
            Path.Command("G2 I2.5 J0.0 K0.0 X-5.0 Y7.5 Z0.0"),
            Path.Command("G1 X5.0 Y7.5 Z0.0"),
            Path.Command("G2 I0.0 J-2.5 K0.0 X7.5 Y5.0 Z0.0"),
            Path.Command("G1 X7.5 Y-5.0 Z0.0"),
            Path.Command("G2 I-2.5 J0.0 K0.0 X5.0 Y-7.5 Z0.0"),
            Path.Command("G1 X-5.0 Y-7.5 Z0.0"),
            Path.Command("G2 I0.0 J2.5 K0.0 X-7.5 Y-5.0 Z0.0"),
            Path.Command("G1 X-7.5 Y0.0 Z0.0"),
        ]

        testpath = Path.Path(commands)
        self.assertTrue(len(testpath.Commands) == 9)
        self.assertTrue(len([c for c in testpath.Commands if c.Name in ["G2", "G3"]]) == 4)

        results = PostUtils.splitArcs(testpath)
        # self.assertTrue(len(results.Commands) == 117)
        self.assertTrue(len([c for c in results.Commands if c.Name in ["G2", "G3"]]) == 0)

    def test020(self):
        """Test Termination of Canned Cycles"""
        # Test basic cycle termination when parameters change
        cmd1 = Path.Command("G81", {"X": 1.0, "Y": 1.0, "Z": -0.5, "R": 0.1, "F": 10.0})
        cmd1.Annotations = {"RetractMode": "G98"}
        cmd2 = Path.Command("G81", {"X": 2.0, "Y": 2.0, "Z": -1.0, "R": 0.2, "F": 10.0})
        cmd2.Annotations = {"RetractMode": "G98"}

        test_path = Path.Path(
            [
                Path.Command("G0", {"Z": 1.0}),
                cmd1,
                cmd2,  # Different Z depth
                Path.Command("G1", {"X": 3.0, "Y": 3.0}),
            ]
        )

        expected_path = Path.Path(
            [
                Path.Command("G0", {"Z": 1.0}),
                Path.Command("G98"),  # Retract mode for first cycle
                Path.Command("G81", {"X": 1.0, "Y": 1.0, "Z": -0.5, "R": 0.1, "F": 10.0}),
                Path.Command("G80"),  # Terminate due to parameter change
                Path.Command("G98"),  # Retract mode for second cycle
                Path.Command("G81", {"X": 2.0, "Y": 2.0, "Z": -1.0, "R": 0.2, "F": 10.0}),
                Path.Command("G80"),  # Final termination
                Path.Command("G1", {"X": 3.0, "Y": 3.0}),
            ]
        )

        result = PostUtils.cannedCycleTerminator(test_path)

        self.assertEqual(len(result.Commands), len(expected_path.Commands))
        for i, (res, exp) in enumerate(zip(result.Commands, expected_path.Commands)):
            self.assertEqual(res.Name, exp.Name, f"Command {i}: name mismatch")
            self.assertEqual(res.Parameters, exp.Parameters, f"Command {i}: parameters mismatch")

    def test030_canned_cycle_termination_with_non_cycle_commands(self):
        """Test cycle termination when non-cycle commands are encountered"""
        cmd1 = Path.Command("G81", {"X": 1.0, "Y": 1.0, "Z": -0.5, "R": 0.1, "F": 10.0})
        cmd1.Annotations = {"RetractMode": "G98"}
        cmd2 = Path.Command("G82", {"X": 3.0, "Y": 3.0, "Z": -1.0, "R": 0.2, "P": 1.0, "F": 10.0})
        cmd2.Annotations = {"RetractMode": "G98"}

        test_path = Path.Path(
            [
                cmd1,
                Path.Command("G0", {"X": 2.0, "Y": 2.0}),  # Non-cycle command
                cmd2,
            ]
        )

        expected_path = Path.Path(
            [
                Path.Command("G98"),  # Retract mode for first cycle
                Path.Command("G81", {"X": 1.0, "Y": 1.0, "Z": -0.5, "R": 0.1, "F": 10.0}),
                Path.Command("G80"),  # Terminate before non-cycle command
                Path.Command("G0", {"X": 2.0, "Y": 2.0}),
                Path.Command("G98"),  # Retract mode for second cycle
                Path.Command("G82", {"X": 3.0, "Y": 3.0, "Z": -1.0, "R": 0.2, "P": 1.0, "F": 10.0}),
                Path.Command("G80"),  # Final termination
            ]
        )

        result = PostUtils.cannedCycleTerminator(test_path)
        self.assertEqual(len(result.Commands), len(expected_path.Commands))
        for i, (res, exp) in enumerate(zip(result.Commands, expected_path.Commands)):
            self.assertEqual(res.Name, exp.Name, f"Command {i}: name mismatch")
            self.assertEqual(res.Parameters, exp.Parameters, f"Command {i}: parameters mismatch")

    def test040_canned_cycle_modal_same_parameters(self):
        """Test modal cycles with same parameters don't get terminated"""
        cmd1 = Path.Command("G81", {"X": 1.0, "Y": 1.0, "Z": -0.5, "R": 0.1, "F": 10.0})
        cmd1.Annotations = {"RetractMode": "G98"}
        cmd2 = Path.Command("G81", {"X": 2.0, "Y": 2.0, "Z": -0.5, "R": 0.1, "F": 10.0})
        cmd2.Annotations = {"RetractMode": "G98"}
        cmd3 = Path.Command("G81", {"X": 3.0, "Y": 3.0, "Z": -0.5, "R": 0.1, "F": 10.0})
        cmd3.Annotations = {"RetractMode": "G98"}

        test_path = Path.Path(
            [
                cmd1,
                cmd2,  # Modal - same parameters
                cmd3,  # Modal - same parameters
            ]
        )

        expected_path = Path.Path(
            [
                Path.Command("G98"),  # Retract mode at start of cycle
                Path.Command("G81", {"X": 1.0, "Y": 1.0, "Z": -0.5, "R": 0.1, "F": 10.0}),
                Path.Command(
                    "G81", {"X": 2.0, "Y": 2.0, "Z": -0.5, "R": 0.1, "F": 10.0}
                ),  # No termination - same params
                Path.Command(
                    "G81", {"X": 3.0, "Y": 3.0, "Z": -0.5, "R": 0.1, "F": 10.0}
                ),  # No termination - same params
                Path.Command("G80"),  # Final termination
            ]
        )

        result = PostUtils.cannedCycleTerminator(test_path)
        self.assertEqual(len(result.Commands), len(expected_path.Commands))
        for i, (res, exp) in enumerate(zip(result.Commands, expected_path.Commands)):
            self.assertEqual(res.Name, exp.Name, f"Command {i}: name mismatch")
            self.assertEqual(res.Parameters, exp.Parameters, f"Command {i}: parameters mismatch")

    def test050_canned_cycle_feed_rate_change(self):
        """Test cycle termination when feed rate changes"""
        cmd1 = Path.Command("G81", {"X": 1.0, "Y": 1.0, "Z": -0.5, "R": 0.1, "F": 10.0})
        cmd1.Annotations = {"RetractMode": "G98"}
        cmd2 = Path.Command("G81", {"X": 2.0, "Y": 2.0, "Z": -0.5, "R": 0.1, "F": 20.0})
        cmd2.Annotations = {"RetractMode": "G98"}

        test_path = Path.Path(
            [
                cmd1,
                cmd2,  # Different feed rate
            ]
        )

        expected_path = Path.Path(
            [
                Path.Command("G98"),  # Retract mode for first cycle
                Path.Command("G81", {"X": 1.0, "Y": 1.0, "Z": -0.5, "R": 0.1, "F": 10.0}),
                Path.Command("G80"),  # Terminate due to feed rate change
                Path.Command("G98"),  # Retract mode for second cycle
                Path.Command("G81", {"X": 2.0, "Y": 2.0, "Z": -0.5, "R": 0.1, "F": 20.0}),
                Path.Command("G80"),  # Final termination
            ]
        )

        result = PostUtils.cannedCycleTerminator(test_path)
        self.assertEqual(len(result.Commands), len(expected_path.Commands))
        for i, (res, exp) in enumerate(zip(result.Commands, expected_path.Commands)):
            self.assertEqual(res.Name, exp.Name, f"Command {i}: name mismatch")
            self.assertEqual(res.Parameters, exp.Parameters, f"Command {i}: parameters mismatch")

    def test060_canned_cycle_retract_plane_change(self):
        """Test cycle termination when retract plane changes"""
        cmd1 = Path.Command("G81", {"X": 1.0, "Y": 1.0, "Z": -0.5, "R": 0.1, "F": 10.0})
        cmd1.Annotations = {"RetractMode": "G98"}
        cmd2 = Path.Command("G81", {"X": 2.0, "Y": 2.0, "Z": -0.5, "R": 0.2, "F": 10.0})
        cmd2.Annotations = {"RetractMode": "G98"}

        test_path = Path.Path(
            [
                cmd1,
                cmd2,  # Different R plane
            ]
        )

        expected_path = Path.Path(
            [
                Path.Command("G98"),  # Retract mode for first cycle
                Path.Command("G81", {"X": 1.0, "Y": 1.0, "Z": -0.5, "R": 0.1, "F": 10.0}),
                Path.Command("G80"),  # Terminate due to R plane change
                Path.Command("G98"),  # Retract mode for second cycle
                Path.Command("G81", {"X": 2.0, "Y": 2.0, "Z": -0.5, "R": 0.2, "F": 10.0}),
                Path.Command("G80"),  # Final termination
            ]
        )

        result = PostUtils.cannedCycleTerminator(test_path)
        self.assertEqual(len(result.Commands), len(expected_path.Commands))
        for i, (res, exp) in enumerate(zip(result.Commands, expected_path.Commands)):
            self.assertEqual(res.Name, exp.Name, f"Command {i}: name mismatch")
            self.assertEqual(res.Parameters, exp.Parameters, f"Command {i}: parameters mismatch")

    def test070_canned_cycle_mixed_cycle_types(self):
        """Test termination between different cycle types"""
        cmd1 = Path.Command("G81", {"X": 1.0, "Y": 1.0, "Z": -0.5, "R": 0.1, "F": 10.0})
        cmd1.Annotations = {"RetractMode": "G98"}
        cmd2 = Path.Command("G82", {"X": 2.0, "Y": 2.0, "Z": -0.5, "R": 0.1, "P": 1.0, "F": 10.0})
        cmd2.Annotations = {"RetractMode": "G98"}

        test_path = Path.Path(
            [
                cmd1,
                cmd2,  # Different cycle type
            ]
        )

        expected_path = Path.Path(
            [
                Path.Command("G98"),  # Retract mode for first cycle
                Path.Command("G81", {"X": 1.0, "Y": 1.0, "Z": -0.5, "R": 0.1, "F": 10.0}),
                Path.Command("G80"),  # Terminate due to different cycle type (different parameters)
                Path.Command("G98"),  # Retract mode for second cycle
                Path.Command("G82", {"X": 2.0, "Y": 2.0, "Z": -0.5, "R": 0.1, "P": 1.0, "F": 10.0}),
                Path.Command("G80"),  # Final termination
            ]
        )

        result = PostUtils.cannedCycleTerminator(test_path)
        self.assertEqual(len(result.Commands), len(expected_path.Commands))
        for i, (res, exp) in enumerate(zip(result.Commands, expected_path.Commands)):
            self.assertEqual(res.Name, exp.Name, f"Command {i}: name mismatch")
            self.assertEqual(res.Parameters, exp.Parameters, f"Command {i}: parameters mismatch")

    def test080_canned_cycle_retract_mode_change(self):
        """Test cycle termination and retract mode insertion when RetractMode annotation changes"""
        # Create commands with RetractMode annotations
        cmd1 = Path.Command("G81", {"X": 1.0, "Y": 1.0, "Z": -0.5, "R": 0.1, "F": 10.0})
        cmd1.Annotations = {"RetractMode": "G98"}

        cmd2 = Path.Command("G81", {"X": 2.0, "Y": 2.0, "Z": -0.5, "R": 0.1, "F": 10.0})
        cmd2.Annotations = {"RetractMode": "G98"}

        cmd3 = Path.Command("G81", {"X": 3.0, "Y": 3.0, "Z": -0.5, "R": 0.1, "F": 10.0})
        cmd3.Annotations = {"RetractMode": "G99"}  # Mode change

        test_path = Path.Path([cmd1, cmd2, cmd3])

        result = PostUtils.cannedCycleTerminator(test_path)

        # Expected: G98, G81, G81 (modal), G80 (terminate), G99, G81, G80 (final)
        self.assertEqual(result.Commands[0].Name, "G98")
        self.assertEqual(result.Commands[1].Name, "G81")
        self.assertEqual(result.Commands[2].Name, "G81")
        self.assertEqual(result.Commands[3].Name, "G80")  # Terminate due to mode change
        self.assertEqual(result.Commands[4].Name, "G99")  # New retract mode
        self.assertEqual(result.Commands[5].Name, "G81")
        self.assertEqual(result.Commands[6].Name, "G80")  # Final termination
        self.assertEqual(len(result.Commands), 7)


class TestBuildPostList(unittest.TestCase):
    """
    The postlist is the list of postprocessable elements from the job.
    The list varies depending on
        -The operations
        -The tool controllers
        -The work coordinate systems (WCS) or 'fixtures'
        -How the job is ordering the output (WCS, tool, operation)
        -Whether or not the output is being split to multiple files
    This test case ensures that the correct sequence of postable objects is
    created.

    The list will be comprised of a list of tuples. Each tuple consists of
    (subobject string, [list of objects])
    The subobject string can be used in output name generation if splitting output
    the list of objects is all postable elements to be written to that file

    """

    # Set to True to enable verbose debug output for test validation
    debug = False

    @classmethod
    def _format_postables(cls, postables, title="Postables"):
        """Format postables for readable debug output, following dumper_post.py pattern."""
        output = []
        output.append("=" * 80)
        output.append(title)
        output.append("=" * 80)
        output.append("")

        for idx, postable in enumerate(postables, 1):
            group_key = postable[0]
            objects = postable[1]

            # Format the group key display
            if group_key == "":
                display_key = "(empty string)"
            elif group_key == "allitems":
                display_key = '"allitems" (combined output)'
            else:
                display_key = f'"{group_key}"'

            output.append(f"[{idx}] Group: {display_key}")
            output.append(f"    Objects: {len(objects)}")
            output.append("")

            for obj_idx, obj in enumerate(objects, 1):
                obj_label = getattr(obj, "Label", str(type(obj).__name__))
                output.append(f"    [{obj_idx}] {obj_label}")

                # Determine object type/role
                obj_type = type(obj).__name__
                if obj_type == "_FixtureSetupObject":
                    output.append(f"        Type: Fixture Setup")
                    if hasattr(obj, "Path") and obj.Path and len(obj.Path.Commands) > 0:
                        fixture_cmd = obj.Path.Commands[0]
                        output.append(f"        Fixture: {fixture_cmd.Name}")
                elif obj_type == "_CommandObject":
                    output.append(f"        Type: Command Object")
                    if hasattr(obj, "Path") and obj.Path and len(obj.Path.Commands) > 0:
                        cmd = obj.Path.Commands[0]
                        params = " ".join(
                            f"{k}:{v}"
                            for k, v in zip(
                                cmd.Parameters.keys() if hasattr(cmd.Parameters, "keys") else [],
                                (
                                    cmd.Parameters.values()
                                    if hasattr(cmd.Parameters, "values")
                                    else cmd.Parameters
                                ),
                            )
                        )
                        output.append(f"        Command: {cmd.Name} {params}")
                elif hasattr(obj, "TypeId"):
                    # Check if it's a tool controller
                    if hasattr(obj, "Proxy") and hasattr(obj.Proxy, "__class__"):
                        proxy_name = obj.Proxy.__class__.__name__
                        if "ToolController" in proxy_name:
                            output.append(f"        Type: Tool Controller")
                            if hasattr(obj, "ToolNumber"):
                                output.append(f"        Tool Number: {obj.ToolNumber}")
                            if hasattr(obj, "Path") and obj.Path and obj.Path.Commands:
                                for cmd in obj.Path.Commands:
                                    if cmd.Name == "M6":
                                        params = " ".join(
                                            f"{k}:{v}"
                                            for k, v in zip(
                                                (
                                                    cmd.Parameters.keys()
                                                    if hasattr(cmd.Parameters, "keys")
                                                    else []
                                                ),
                                                (
                                                    cmd.Parameters.values()
                                                    if hasattr(cmd.Parameters, "values")
                                                    else cmd.Parameters
                                                ),
                                            )
                                        )
                                        output.append(f"        M6 Command: {cmd.Name} {params}")
                        else:
                            output.append(f"        Type: Operation")
                            if hasattr(obj, "ToolController") and obj.ToolController:
                                tc = obj.ToolController
                                output.append(
                                    f"        ToolController: {tc.Label} (T{tc.ToolNumber})"
                                )
                    else:
                        output.append(f"        Type: {obj.TypeId}")
                else:
                    output.append(f"        Type: {obj_type}")

            output.append("")

        output.append("=" * 80)
        output.append(f"Total Groups: {len(postables)}")
        total_objects = sum(len(p[1]) for p in postables)
        output.append(f"Total Objects: {total_objects}")
        output.append("=" * 80)

        return "\n".join(output)

    @classmethod
    def setUpClass(cls):
        FreeCAD.ConfigSet("SuppressRecomputeRequiredDialog", "True")
        # Create a new document instead of opening external file
        cls.doc = FreeCAD.newDocument("test_filenaming")

        # Create a simple geometry object for the job
        import Part

        box = cls.doc.addObject("Part::Box", "TestBox")
        box.Length = 100
        box.Width = 100
        box.Height = 20

        # Create CAM job programmatically
        cls.job = PathJob.Create("MainJob", [box], None)
        cls.job.PostProcessor = "generic"
        cls.job.PostProcessorOutputFile = ""
        cls.job.SplitOutput = False
        cls.job.OrderOutputBy = "Operation"
        cls.job.Fixtures = ["G54", "G55"]  # 2 fixtures as expected by tests

        # Create additional tool controllers to match original file structure
        # Original had 2 tool controllers both with "TC: 7/16\" two flute" label

        # Modify the first tool controller to have the expected values
        cls.job.Tools.Group[0].ToolNumber = 5
        cls.job.Tools.Group[0].Label = (
            'TC: 7/16" two flute'  # test050 expects this sanitized to "TC__7_16__two_flute"
        )

        # Add second tool controller with same label but different number
        tc2 = PathToolController.Create()
        tc2.ToolNumber = 2
        tc2.Label = 'TC: 7/16" two flute'  # Same label as first tool controller
        cls.job.Proxy.addToolController(tc2)

        # Recompute tool controllers to populate their Path.Commands with M6 commands
        cls.job.Tools.Group[0].recompute()
        cls.job.Tools.Group[1].recompute()

        # Create mock operations to match original file structure
        # Original had 3 operations: outsideprofile, DrillAllHoles, Comment
        # The Comment operation has no tool controller
        operation_names = ["outsideprofile", "DrillAllHoles", "Comment"]

        for i, name in enumerate(operation_names):
            # Create a simple document object that mimics an operation
            op = cls.doc.addObject("Path::FeaturePython", name)
            op.Label = name
            # Path::FeaturePython objects already have a Path property
            op.Path = Path.Path()

            # Only add ToolController property for operations that need it
            if name != "Comment":
                # Add ToolController property to the operation
                op.addProperty(
                    "App::PropertyLink",
                    "ToolController",
                    "Base",
                    "Tool controller for this operation",
                )
                # Assign operations to tool controllers
                if i == 0:  # outsideprofile uses first tool controller (tool 5)
                    op.ToolController = cls.job.Tools.Group[0]
                elif i == 1:  # DrillAllHoles uses second tool controller (tool 2)
                    op.ToolController = cls.job.Tools.Group[1]
            # Comment operation has no tool controller (None)

            # Add to job operations
            cls.job.Operations.addObject(op)

    @classmethod
    def tearDownClass(cls):
        FreeCAD.closeDocument(cls.doc.Name)
        FreeCAD.ConfigSet("SuppressRecomputeRequiredDialog", "")

    def setUp(self):
        self.pp = PathPost.PostProcessor(self.job, "generic", "", "")

    def tearDown(self):
        pass

    def test000(self):

        # check that the test file is structured correctly
        self.assertEqual(len(self.job.Tools.Group), 2)
        self.assertEqual(len(self.job.Fixtures), 2)
        self.assertEqual(
            len(self.job.Operations.Group), 3
        )  # Updated back to 3 operations, Comment has no tool controller

        self.job.SplitOutput = False
        self.job.OrderOutputBy = "Operation"

    def test010(self):
        postlist = self.pp._buildPostList()

        self.assertTrue(type(postlist) is list)

        firstoutputitem = postlist[0]
        self.assertTrue(type(firstoutputitem) is tuple)
        self.assertTrue(type(firstoutputitem[0]) is str)
        self.assertTrue(type(firstoutputitem[1]) is list)

    def test020(self):
        # Without splitting, result should be list of one item
        self.job.SplitOutput = False
        self.job.OrderOutputBy = "Operation"
        postlist = self.pp._buildPostList()
        self.assertEqual(len(postlist), 1)

    def test030(self):
        # No splitting should include all ops, tools, and fixtures
        self.job.SplitOutput = False
        self.job.OrderOutputBy = "Operation"
        postlist = self.pp._buildPostList()
        firstoutputitem = postlist[0]
        firstoplist = firstoutputitem[1]
        if self.debug:
            print(self._format_postables(postlist, "test030: No splitting, order by Operation"))
        self.assertEqual(len(firstoplist), 14)

    def test040(self):
        # Test splitting by tool
        # ordering by tool with toolnumber for string
        teststring = "%T.nc"
        self.job.SplitOutput = True
        self.job.PostProcessorOutputFile = teststring
        self.job.OrderOutputBy = "Tool"
        postlist = self.pp._buildPostList()

        firstoutputitem = postlist[0]
        if self.debug:
            print(self._format_postables(postlist, "test040: Split by tool, order by Tool"))
        self.assertTrue(firstoutputitem[0] == str(5))

        # check length of output
        firstoplist = firstoutputitem[1]
        self.assertEqual(len(firstoplist), 5)

    def test050(self):
        # ordering by tool with tool description for string
        teststring = "%t.nc"
        self.job.SplitOutput = True
        self.job.PostProcessorOutputFile = teststring
        self.job.OrderOutputBy = "Tool"
        postlist = self.pp._buildPostList()

        firstoutputitem = postlist[0]
        self.assertTrue(firstoutputitem[0] == "TC__7_16__two_flute")

    def test060(self):
        # Ordering by fixture and splitting
        teststring = "%W.nc"
        self.job.SplitOutput = True
        self.job.PostProcessorOutputFile = teststring
        self.job.OrderOutputBy = "Fixture"
        postlist = self.pp._buildPostList()

        firstoutputitem = postlist[0]
        firstoplist = firstoutputitem[1]
        self.assertEqual(len(firstoplist), 6)
        self.assertTrue(firstoutputitem[0] == "G54")

    def test070(self):
        self.job.SplitOutput = True
        self.job.PostProcessorOutputFile = "%T.nc"
        self.job.OrderOutputBy = "Tool"
        postables = self.pp._buildPostList(early_tool_prep=True)
        _, sublist = postables[0]

        if self.debug:
            print(self._format_postables(postables, "test070: Early tool prep, split by tool"))

        # Extract all commands from the postables
        commands = []
        if self.debug:
            print("\n=== Extracting commands from postables ===")
        for item in sublist:
            if self.debug:
                item_type = type(item).__name__
                has_path = hasattr(item, "Path")
                path_exists = item.Path if has_path else None
                has_commands = path_exists and item.Path.Commands if path_exists else False
                print(
                    f"Item: {getattr(item, 'Label', item_type)}, Type: {item_type}, HasPath: {has_path}, PathExists: {path_exists is not None}, HasCommands: {bool(has_commands)}"
                )
                if has_commands:
                    print(f"  Commands: {[cmd.Name for cmd in item.Path.Commands]}")
            if hasattr(item, "Path") and item.Path and item.Path.Commands:
                commands.extend(item.Path.Commands)

        if self.debug:
            print(f"\nTotal commands extracted: {len(commands)}")
            print("=" * 40)

        # Should have M6 command with tool parameter
        m6_commands = [cmd for cmd in commands if cmd.Name == "M6"]
        self.assertTrue(len(m6_commands) > 0, "Should have M6 command")

        # First M6 should have T parameter for tool 5
        first_m6 = m6_commands[0]
        self.assertTrue("T" in first_m6.Parameters, "First M6 should have T parameter")
        self.assertEqual(first_m6.Parameters["T"], 5.0, "First M6 should be for tool 5")

        # Should have T2 prep command (early prep for next tool)
        t2_commands = [cmd for cmd in commands if cmd.Name == "T2"]
        self.assertTrue(len(t2_commands) > 0, "Should have T2 early prep command")

        # T2 prep should come after first M6
        first_m6_index = next((i for i, cmd in enumerate(commands) if cmd.Name == "M6"), None)
        t2_index = next((i for i, cmd in enumerate(commands) if cmd.Name == "T2"), None)
        self.assertIsNotNone(first_m6_index, "M6 should exist")
        self.assertIsNotNone(t2_index, "T2 should exist")
        self.assertLess(first_m6_index, t2_index, "M6 should come before T2 prep")

    def test080(self):
        self.job.SplitOutput = False
        self.job.OrderOutputBy = "Tool"

        postables = self.pp._buildPostList(early_tool_prep=True)
        _, sublist = postables[0]

        if self.debug:
            print(self._format_postables(postables, "test080: Early tool prep, combined output"))

        # Extract all commands from the postables
        commands = []
        if self.debug:
            print("\n=== Extracting commands from postables ===")
        for item in sublist:
            if self.debug:
                item_type = type(item).__name__
                has_path = hasattr(item, "Path")
                path_exists = item.Path if has_path else None
                has_commands = path_exists and item.Path.Commands if path_exists else False
                print(
                    f"Item: {getattr(item, 'Label', item_type)}, Type: {item_type}, HasPath: {has_path}, PathExists: {path_exists is not None}, HasCommands: {bool(has_commands)}"
                )
                if has_commands:
                    print(f"  Commands: {[cmd.Name for cmd in item.Path.Commands]}")
            if hasattr(item, "Path") and item.Path and item.Path.Commands:
                commands.extend(item.Path.Commands)

        if self.debug:
            print(f"\nTotal commands extracted: {len(commands)}")

        # Expected command sequence with early_tool_prep=True:
        # M6 T5     <- change to tool 5 (standard format)
        # T2        <- prep next tool immediately (early prep)
        # (ops with T5...)
        # M6 T2     <- change to tool 2 (was prepped early)
        # (ops with T2...)

        if self.debug:
            print("\n=== Command Sequence ===")
            for i, cmd in enumerate(commands):
                params = " ".join(
                    f"{k}:{v}"
                    for k, v in zip(
                        cmd.Parameters.keys() if hasattr(cmd.Parameters, "keys") else [],
                        (
                            cmd.Parameters.values()
                            if hasattr(cmd.Parameters, "values")
                            else cmd.Parameters
                        ),
                    )
                )
                print(f"{i:3d}: {cmd.Name} {params}")
            print("=" * 40)

        # Find M6 and T2 commands
        m6_commands = [(i, cmd) for i, cmd in enumerate(commands) if cmd.Name == "M6"]
        t2_commands = [(i, cmd) for i, cmd in enumerate(commands) if cmd.Name == "T2"]

        self.assertTrue(len(m6_commands) >= 2, "Should have at least 2 M6 commands")
        self.assertTrue(len(t2_commands) >= 1, "Should have at least 1 T2 early prep command")

        first_m6_idx, first_m6_cmd = m6_commands[0]
        second_m6_idx, second_m6_cmd = m6_commands[1] if len(m6_commands) >= 2 else (None, None)
        first_t2_idx = t2_commands[0][0]

        # First M6 should have T parameter for tool 5
        self.assertTrue("T" in first_m6_cmd.Parameters, "First M6 should have T parameter")
        self.assertEqual(first_m6_cmd.Parameters["T"], 5.0, "First M6 should be for tool 5")

        # Second M6 should have T parameter for tool 2
        if second_m6_cmd is not None:
            self.assertTrue("T" in second_m6_cmd.Parameters, "Second M6 should have T parameter")
            self.assertEqual(second_m6_cmd.Parameters["T"], 2.0, "Second M6 should be for tool 2")

        # T2 (early prep) should come shortly after first M6 (within a few commands)
        self.assertLess(first_m6_idx, first_t2_idx, "T2 prep should come after first M6")
        self.assertLess(
            first_t2_idx - first_m6_idx, 5, "T2 prep should be within a few commands of first M6"
        )

        # T2 early prep should come before second M6
        if second_m6_idx is not None:
            self.assertLess(
                first_t2_idx, second_m6_idx, "T2 early prep should come before second M6"
            )


# ==============================================================================
# DEPRECATED: TestConvertCommandToGcode
# ==============================================================================
# This test class is deprecated and commented out because it provides redundant
# coverage that is already handled by the integration tests in TestExport2Integration.
# The integration tests provide better coverage by testing the entire export2()
# pipeline end-to-end with real jobs and machine configurations.
#
# Reason for deprecation:
# - Low-level unit tests of convert_command_to_gcode() method in isolation
# - Already covered by integration tests - every export2() call exercises this method
# - Brittle setup requiring mocking and manual configuration
# - Limited scope - only tests command formatting, not full context
# - Maintenance burden - duplicates assertions in integration tests
#
# If you need to test command conversion behavior, add integration tests to
# TestExport2Integration in TestPostOutput.py instead.
# ==============================================================================

# class TestConvertCommandToGcode(unittest.TestCase):
#     """Test the convert_command_to_gcode method of PostProcessor."""
# 
#     def setUp(self):
    #     """Set up test fixtures."""
    #     from Path.Post.Processor import PostProcessor
        
    #     # Create a basic postprocessor for testing with dummy arguments
    #     # PostProcessor requires: job, tooltip, tooltipargs, units
    #     dummy_job = None  # We'll use None for testing
    #     dummy_tooltip = "Test Post Processor"
    #     dummy_tooltipargs = {}
    #     dummy_units = "mm"
        
    #     self.processor = PostProcessor(dummy_job, dummy_tooltip, dummy_tooltipargs, dummy_units)
    #     self.processor.reinitialize()  # Initialize state
        
    #     # Mock machine with OutputOptions
    #     mock_output_options = type('MockOutputOptions', (), {'suppress_commands': []})()
    #     self.processor._machine = type('MockMachine', (), {'OutputOptions': mock_output_options})()
        
    #     # Set up basic configuration
    #     self.processor.values['precision'] = 3
    #     self.processor.values['OUTPUT_COMMENTS'] = True
    #     self.processor.values['SUPPRESS_COMMANDS'] = []
    #     self.processor.values['COMMAND_SPACE'] = " "
    #     self.processor.values['END_OF_LINE_CHARACTERS'] = ""
    #     self.processor.values['PARAMETER_SEPARATOR'] = ""
    #     self.processor.values['PARAMETER_ORDER'] = ['X', 'Y', 'Z', 'F', 'I', 'J', 'K', 'R', 'Q', 'P']
    #     self.processor.values['UNITS'] = 'G21'  # Metric units
    #     self.processor.values['UNIT_FORMAT'] = 'mm'
    #     self.processor.values['UNIT_SPEED_FORMAT'] = 'mm/min'

    # def test010_supported_motion_commands(self):
    #     """Test supported motion commands (G0, G1, G2, G3)."""
    #     # Test G0/G00 rapid move
    #     cmd = Path.Command("G0", {"X": 10.0, "Y": 20.0, "Z": 5.0})
    #     result = self.processor.convert_command_to_gcode(cmd)
    #     self.assertIn("G0", result)
    #     self.assertIn("X10.000", result)
    #     self.assertIn("Y20.000", result)
    #     self.assertIn("Z5.000", result)
        
    #     # Test G1/G01 feed move
    #     cmd = Path.Command("G1", {"X": 15.5, "Y": 25.5, "F": 100.0})
    #     result = self.processor.convert_command_to_gcode(cmd)
    #     self.assertIn("G1", result)
    #     self.assertIn("X15.500", result)
    #     self.assertIn("Y25.500", result)
    #     # Feed rates are converted from mm/min input to proper units (appears as 6000.000)
    #     self.assertIn("F6000.000", result)
        
    #     # Test G2/G02 clockwise arc
    #     cmd = Path.Command("G2", {"X": 20.0, "Y": 30.0, "I": 5.0, "J": 0.0})
    #     result = self.processor.convert_command_to_gcode(cmd)
    #     self.assertIn("G2", result)
    #     self.assertIn("X20.000", result)
    #     self.assertIn("Y30.000", result)
    #     self.assertIn("I5.000", result)
    #     self.assertIn("J0.000", result)
        
    #     # Test G3/G03 counterclockwise arc
    #     cmd = Path.Command("G3", {"X": 25.0, "Y": 35.0, "I": 0.0, "J": 5.0})
    #     result = self.processor.convert_command_to_gcode(cmd)
    #     self.assertIn("G3", result)

    # def test020_supported_drill_commands(self):
    #     """Test supported drilling/canned cycle commands."""
    #     # Test G81 drill cycle
    #     cmd = Path.Command("G81", {"X": 10.0, "Y": 20.0, "Z": -5.0, "R": 2.0, "F": 50.0})
    #     result = self.processor.convert_command_to_gcode(cmd)
    #     self.assertIn("G81", result)
    #     self.assertIn("X10.000", result)
    #     self.assertIn("Y20.000", result)
    #     self.assertIn("Z-5.000", result)
    #     self.assertIn("R2.000", result)
    #     # Feed rates are converted (50 * 60 = 3000)
    #     self.assertIn("F3000.000", result)
        
    #     # Test G83 peck drill cycle
    #     cmd = Path.Command("G83", {"X": 15.0, "Y": 25.0, "Z": -10.0, "R": 2.0, "Q": 1.0, "F": 75.0})
    #     result = self.processor.convert_command_to_gcode(cmd)
    #     self.assertIn("G83", result)
    #     self.assertIn("Q1.000", result)

    # def test030_comments(self):
    #     """Test comment handling."""
    #     # Test regular comment
    #     cmd = Path.Command("(This is a comment)")
    #     result = self.processor.convert_command_to_gcode(cmd)
    #     self.assertIn("(This is a comment)", result)
        
    #     # Test comment with output disabled
    #     self.processor.values['OUTPUT_COMMENTS'] = False
    #     cmd = Path.Command("(This is a comment)")
    #     result = self.processor.convert_command_to_gcode(cmd)
    #     self.assertIsNone(result)
        
    #     # Reset for other tests
    #     self.processor.values['OUTPUT_COMMENTS'] = True

    # def test040_blockdelete_annotation(self):
    #     """Test blockdelete annotation handling."""
    #     cmd = Path.Command("G0", {"X": 10.0, "Y": 20.0})
    #     cmd.Annotations = {"blockdelete": True}
    #     result = self.processor.convert_command_to_gcode(cmd)
    #     self.assertTrue(result.startswith("/"))
    #     self.assertIn("G0", result)

    # def test050_bcnc_annotation(self):
    #     """Test bCNC annotation handling."""
    #     # Note: This test assumes bcnc_blocks is enabled and formmatted_bcnc_block function exists
    #     # For now, just test that the annotation is recognized
    #     cmd = Path.Command("(BCNC comment)")
    #     cmd.Annotations = {"bcnc": True}
    #     result = self.processor.convert_command_to_gcode(cmd)
    #     # Just check it returns something for now
    #     self.assertIsNotNone(result)

    # def test060_suppressed_commands(self):
    #     """Test suppressed command handling."""
    #     cmd = Path.Command("G0", {"X": 10.0})
        
    #     # Suppress G0 commands
    #     self.processor._machine.OutputOptions.suppress_commands = ["G0"]
    #     result = self.processor.convert_command_to_gcode(cmd)
    #     self.assertIsNone(result)
        
    #     # Reset for other tests
    #     self.processor._machine.OutputOptions.suppress_commands = []

    # def test070_unsupported_commands(self):
    #     """Test that unsupported commands raise ValueError."""
    #     unsupported_commands = ["G4", "G17", "G90", "M3", "M5", "T1", "S1000"]
        
    #     for cmd_name in unsupported_commands:
    #         with self.subTest(cmd_name=cmd_name):
    #             cmd = Path.Command(cmd_name, {})
    #             try:
    #                 result = self.processor.convert_command_to_gcode(cmd)
    #             except ValueError as e:
    #                 self.assertIn("Unsupported command", str(e))

    # def test080_parameter_ordering(self):
    #     """Test that parameters are output in correct order."""
    #     cmd = Path.Command("G1", {"Y": 20.0, "X": 10.0, "F": 100.0, "Z": 5.0})
    #     result = self.processor.convert_command_to_gcode(cmd)
        
    #     # Parameters should appear in the order defined in parameter_order
    #     # X, Y, Z, F should appear before any others
    #     x_pos = result.find("X10.000")
    #     y_pos = result.find("Y20.000")
    #     z_pos = result.find("Z5.000")
    #     f_pos = result.find("F6000.000")  # Feed rate is converted (100 * 60 = 6000)
        
    #     self.assertLess(x_pos, y_pos, "X should come before Y")
    #     self.assertLess(y_pos, z_pos, "Y should come before Z")
    #     self.assertLess(z_pos, f_pos, "Z should come before F")

    # def test090_precision_formatting(self):
    #     """Test parameter precision formatting."""
    #     cmd = Path.Command("G0", {"X": 10.123456, "Y": 20.987654, "Z": 5.5})
    #     result = self.processor.convert_command_to_gcode(cmd)
        
    #     # With precision=3, should format to 3 decimal places
    #     self.assertIn("X10.123", result)
    #     self.assertIn("Y20.988", result)  # Note: rounding
    #     self.assertIn("Z5.500", result)

    # def test100_empty_parameters(self):
    #     """Test command with no parameters."""
    #     cmd = Path.Command("G0", {})
    #     result = self.processor.convert_command_to_gcode(cmd)
        
    #     self.assertIn("G0", result)
    #     # Should not have extra spaces or separators
    #     self.assertEqual(result.strip(), "G0")

