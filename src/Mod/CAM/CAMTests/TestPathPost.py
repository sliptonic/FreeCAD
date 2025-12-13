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

from Path.Post.Command import DlgSelectPostProcessor
from Path.Post.Processor import (
    PostProcessor,
    PostProcessorFactory,
    MachineConfiguration,
    StateConverter,
    MachineUnits,
    MotionMode,
    OutputOptions,
    PrecisionSettings,
    LineFormatting,
    MachineOptions,
    GCodeBlocks,
    ProcessingOptions,
)
from unittest.mock import patch, MagicMock
import FreeCAD
import Path
import Path.Post.Command as PathCommand
import Path.Post.Processor as PathPost
import Path.Post.Utils as PostUtils
import Path.Main.Job as PathJob
import Path.Tool.Controller as PathToolController
import difflib
import os
import unittest

from .FilePathTestUtils import assertFilePathsEqual

PathCommand.LOG_MODULE = Path.Log.thisModule()
Path.Log.setLevel(Path.Log.Level.INFO, PathCommand.LOG_MODULE)


class TestFileNameGenerator(unittest.TestCase):
    r"""
    String substitution allows the following:
    %D ... directory of the active document
    %d ... name of the active document (with extension)
    %M ... user macro directory
    %j ... name of the active Job object


    The Following can be used if output is being split. If Output is not split
    these will be ignored.

    %S ... Sequence Number (default)

    Either:
    %T ... Tool Number
    %t ... Tool Controller label

    %W ... Work Coordinate System
    %O ... Operation Label

    |split on| use | Ignore |
    |-----------|-------|--------|
    |fixture | %W | %O %T %t |
    |Operation| %O | %T %t %W |
    |Tool| **Either %T or %t** | %O %W |

    The confusing bit is that for split on tool,  it will use EITHER the tool number or the tool label.
    If you include both, the second one overrides the first.
    And for split on operation, where including the tool should be possible, it ignores it altogether.

        self.job.Fixtures = ["G54"]
        self.job.SplitOutput = False
        self.job.OrderOutputBy = "Fixture"

    Assume:
    active document: self.assertTrue(filename, f"{home}/testdoc.fcstd
    user macro: ~/.local/share/FreeCAD/Macro
    Job:  MainJob
    Operations:
        OutsideProfile
        DrillAllHoles
    TC: 7/16" two flute  (5)
    TC: Drill (2)
    Fixtures: (G54, G55)

    Strings should be sanitized like this to ensure valid filenames
    # import re
    # filename="TC: 7/16" two flute"
    # >>> re.sub(r"[^\w\d-]","_",filename)
    # "TC__7_16__two_flute"

    """

    @classmethod
    def setUpClass(cls):
        FreeCAD.ConfigSet("SuppressRecomputeRequiredDialog", "True")

        # Create a new document instead of opening external file
        cls.doc = FreeCAD.newDocument("TestFileNaming")
        cls.testfilename = cls.doc.Name
        cls.testfilepath = os.getcwd()
        cls.macro = FreeCAD.getUserMacroDir()

        # Create a simple geometry object for the job
        import Part

        box = cls.doc.addObject("Part::Box", "TestBox")
        box.Length = 100
        box.Width = 100
        box.Height = 20

        # Create CAM job programmatically
        cls.job = PathJob.Create("MainJob", [box], None)
        cls.job.PostProcessor = "linuxcnc"
        cls.job.PostProcessorOutputFile = ""
        cls.job.SplitOutput = False
        cls.job.OrderOutputBy = "Operation"
        cls.job.Fixtures = ["G54", "G55"]

        # Create a tool controller for testing tool-related substitutions
        from Path.Tool.toolbit import ToolBit

        tool_attrs = {
            "name": "TestTool",
            "shape": "endmill.fcstd",
            "parameter": {"Diameter": 6.0},
            "attribute": {},
        }
        toolbit = ToolBit.from_dict(tool_attrs)
        tool = toolbit.attach_to_doc(doc=cls.doc)
        tool.Label = "6mm_Endmill"

        tc = PathToolController.Create("TC_Test_Tool", tool, 5)
        tc.Label = "TC: 6mm Endmill"
        cls.job.addObject(tc)

        # Create a simple mock operation for testing operation-related substitutions
        profile_op = cls.doc.addObject("Path::FeaturePython", "TestProfile")
        profile_op.Label = "OutsideProfile"
        # Path::FeaturePython objects already have a Path property
        profile_op.Path = Path.Path()
        cls.job.Operations.addObject(profile_op)

        cls.doc.recompute()

    @classmethod
    def tearDownClass(cls):
        FreeCAD.closeDocument(cls.doc.Name)
        FreeCAD.ConfigSet("SuppressRecomputeRequiredDialog", "")

    def test000(self):
        # Test basic name generation with empty string
        FreeCAD.setActiveDocument(self.doc.Label)
        teststring = ""
        self.job.PostProcessorOutputFile = teststring
        Path.Preferences.setOutputFileDefaults(teststring, "Append Unique ID on conflict")

        generator = PostUtils.FilenameGenerator(job=self.job)
        filename_generator = generator.generate_filenames()
        filename = next(filename_generator)
        Path.Log.debug(filename)
        assertFilePathsEqual(
            self, filename, os.path.join(self.testfilepath, f"{self.testfilename}.nc")
        )

    def test010(self):
        # Substitute current file path
        teststring = "%D/testfile.nc"
        self.job.PostProcessorOutputFile = teststring
        Path.Preferences.setOutputFileDefaults(teststring, "Append Unique ID on conflict")

        generator = PostUtils.FilenameGenerator(job=self.job)
        filename_generator = generator.generate_filenames()
        filename = next(filename_generator)

        print(os.path.normpath(filename))
        assertFilePathsEqual(self, filename, f"{self.testfilepath}/testfile.nc")

    def test015(self):
        # Test basic string substitution without splitting
        teststring = "~/Desktop/%j.nc"
        self.job.PostProcessorOutputFile = teststring
        Path.Preferences.setOutputFileDefaults(teststring, "Append Unique ID on conflict")

        generator = PostUtils.FilenameGenerator(job=self.job)
        filename_generator = generator.generate_filenames()
        filename = next(filename_generator)

        assertFilePathsEqual(self, filename, "~/Desktop/MainJob.nc")

    def test020(self):
        teststring = "%d.nc"
        self.job.PostProcessorOutputFile = teststring
        Path.Preferences.setOutputFileDefaults(teststring, "Append Unique ID on conflict")

        generator = PostUtils.FilenameGenerator(job=self.job)
        filename_generator = generator.generate_filenames()
        filename = next(filename_generator)

        expected = os.path.join(self.testfilepath, f"{self.testfilename}.nc")

        assertFilePathsEqual(self, filename, expected)

    def test030(self):
        teststring = "%M/outfile.nc"
        self.job.PostProcessorOutputFile = teststring
        Path.Preferences.setOutputFileDefaults(teststring, "Append Unique ID on conflict")

        generator = PostUtils.FilenameGenerator(job=self.job)
        filename_generator = generator.generate_filenames()
        filename = next(filename_generator)

        assertFilePathsEqual(self, filename, f"{self.macro}outfile.nc")

    def test040(self):
        # unused substitution strings should be ignored
        teststring = "%d%T%t%W%O/testdoc.nc"
        self.job.PostProcessorOutputFile = teststring
        Path.Preferences.setOutputFileDefaults(teststring, "Append Unique ID on conflict")

        generator = PostUtils.FilenameGenerator(job=self.job)
        filename_generator = generator.generate_filenames()
        filename = next(filename_generator)

        assertFilePathsEqual(self, filename, f"{self.testfilename}/testdoc.nc")

    def test045(self):
        """Testing the sequence number substitution"""
        generator = PostUtils.FilenameGenerator(job=self.job)
        filename_generator = generator.generate_filenames()
        expected_filenames = [f"TestFileNaming{os.sep}testdoc.nc"] + [
            f"TestFileNaming{os.sep}testdoc-{i}.nc" for i in range(1, 5)
        ]
        for expected_filename in expected_filenames:
            filename = next(filename_generator)
            assertFilePathsEqual(self, filename, expected_filename)

    def test046(self):
        """Testing the sequence number substitution"""
        teststring = "%S-%d.nc"
        self.job.PostProcessorOutputFile = teststring
        generator = PostUtils.FilenameGenerator(job=self.job)
        filename_generator = generator.generate_filenames()
        expected_filenames = [
            os.path.join(self.testfilepath, f"{i}-TestFileNaming.nc") for i in range(5)
        ]
        for expected_filename in expected_filenames:
            filename = next(filename_generator)
            assertFilePathsEqual(self, filename, expected_filename)

    def test050(self):
        # explicitly using the sequence number should include it where indicated.
        teststring = "%S-%d.nc"
        self.job.PostProcessorOutputFile = teststring
        Path.Preferences.setOutputFileDefaults(teststring, "Append Unique ID on conflict")

        generator = PostUtils.FilenameGenerator(job=self.job)
        filename_generator = generator.generate_filenames()
        filename = next(filename_generator)

        assertFilePathsEqual(self, filename, os.path.join(self.testfilepath, "0-TestFileNaming.nc"))

    def test060(self):
        """Test subpart naming"""
        teststring = "%M/outfile.nc"
        self.job.PostProcessorOutputFile = teststring
        Path.Preferences.setOutputFileDefaults(teststring, "Append Unique ID on conflict")

        generator = PostUtils.FilenameGenerator(job=self.job)
        generator.set_subpartname("Tool")
        filename_generator = generator.generate_filenames()
        filename = next(filename_generator)

        assertFilePathsEqual(self, filename, f"{self.macro}outfile-Tool.nc")

    def test070(self):
        """Test %T substitution (tool number) with actual tool controller"""
        teststring = "%T.nc"
        self.job.PostProcessorOutputFile = teststring

        generator = PostUtils.FilenameGenerator(job=self.job)
        generator.set_subpartname("5")  # Tool number from our test tool controller
        filename_generator = generator.generate_filenames()
        filename = next(filename_generator)

        assertFilePathsEqual(self, filename, os.path.join(self.testfilepath, "5.nc"))

    def test071(self):
        """Test %t substitution (tool description) with actual tool controller"""
        teststring = "%t.nc"
        self.job.PostProcessorOutputFile = teststring

        generator = PostUtils.FilenameGenerator(job=self.job)
        generator.set_subpartname("TC__6mm_Endmill")  # Sanitized tool label
        filename_generator = generator.generate_filenames()
        filename = next(filename_generator)

        assertFilePathsEqual(self, filename, os.path.join(self.testfilepath, "TC__6mm_Endmill.nc"))

    def test072(self):
        """Test %W substitution (work coordinate system/fixture)"""
        teststring = "%W.nc"
        self.job.PostProcessorOutputFile = teststring

        generator = PostUtils.FilenameGenerator(job=self.job)
        generator.set_subpartname("G54")  # First fixture from our job setup
        filename_generator = generator.generate_filenames()
        filename = next(filename_generator)

        assertFilePathsEqual(self, filename, os.path.join(self.testfilepath, "G54.nc"))

    def test073(self):
        """Test %O substitution (operation label)"""
        teststring = "%O.nc"
        self.job.PostProcessorOutputFile = teststring

        generator = PostUtils.FilenameGenerator(job=self.job)
        generator.set_subpartname("OutsideProfile")  # Operation label from our test setup
        filename_generator = generator.generate_filenames()
        filename = next(filename_generator)

        assertFilePathsEqual(self, filename, os.path.join(self.testfilepath, "OutsideProfile.nc"))

    def test075(self):
        """Test path and filename substitutions together"""
        teststring = "%D/%j_%S.nc"
        self.job.PostProcessorOutputFile = teststring

        generator = PostUtils.FilenameGenerator(job=self.job)
        filename_generator = generator.generate_filenames()
        filename = next(filename_generator)

        # %D should resolve to document directory (empty since doc has no filename)
        # %j should resolve to job name "MainJob"
        # %S should resolve to sequence number "0"
        assertFilePathsEqual(self, filename, os.path.join(".", "MainJob_0.nc"))

    def test076(self):
        """Test invalid substitution characters are ignored"""
        teststring = "%X%Y%Z/invalid_%Q.nc"
        self.job.PostProcessorOutputFile = teststring

        generator = PostUtils.FilenameGenerator(job=self.job)
        filename_generator = generator.generate_filenames()
        filename = next(filename_generator)

        # Invalid substitutions should be removed, leaving "invalid_.nc"
        assertFilePathsEqual(self, filename, os.path.join(self.testfilepath, "invalid_.nc"))


class TestResolvingPostProcessorName(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        FreeCAD.ConfigSet("SuppressRecomputeRequiredDialog", "True")
        # Create a new document instead of opening external file
        cls.doc = FreeCAD.newDocument("boxtest")

        # Create a simple geometry object for the job
        import Part

        box = cls.doc.addObject("Part::Box", "TestBox")
        box.Length = 100
        box.Width = 100
        box.Height = 20

        # Create CAM job programmatically
        cls.job = PathJob.Create("MainJob", [box], None)
        cls.job.PostProcessorOutputFile = ""
        cls.job.SplitOutput = False
        cls.job.OrderOutputBy = "Operation"
        cls.job.Fixtures = ["G54", "G55"]

    @classmethod
    def tearDownClass(cls):
        FreeCAD.closeDocument(cls.doc.Name)
        FreeCAD.ConfigSet("SuppressRecomputeRequiredDialog", "")

    def setUp(self):
        pref = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/CAM")
        pref.SetString("PostProcessorDefault", "")

    def tearDown(self):
        pass

    def test010(self):
        # Test if post is defined in job
        self.job.PostProcessor = "linuxcnc"
        with patch("Path.Post.Processor.PostProcessor.exists", return_value=True):
            postname = PathCommand._resolve_post_processor_name(self.job)
            self.assertEqual(postname, "linuxcnc")

    def test020(self):
        # Test if post is invalid
        with patch("Path.Post.Processor.PostProcessor.exists", return_value=False):
            with self.assertRaises(ValueError):
                PathCommand._resolve_post_processor_name(self.job)

    def test030(self):
        # Test if post is defined in prefs
        self.job.PostProcessor = ""
        pref = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/CAM")
        pref.SetString("PostProcessorDefault", "grbl")

        with patch("Path.Post.Processor.PostProcessor.exists", return_value=True):
            postname = PathCommand._resolve_post_processor_name(self.job)
            self.assertEqual(postname, "grbl")

    def test040(self):
        # Test if user interaction is correctly handled
        if FreeCAD.GuiUp:
            with patch("Path.Post.Command.DlgSelectPostProcessor") as mock_dlg, patch(
                "Path.Post.Processor.PostProcessor.exists", return_value=True
            ):
                mock_dlg.return_value.exec_.return_value = "generic"
                postname = PathCommand._resolve_post_processor_name(self.job)
                self.assertEqual(postname, "generic")
        else:
            with patch.object(self.job, "PostProcessor", ""):
                with self.assertRaises(ValueError):
                    PathCommand._resolve_post_processor_name(self.job)


class TestPostProcessorFactory(unittest.TestCase):
    """Test creation of postprocessor objects."""

    @classmethod
    def setUpClass(cls):
        FreeCAD.ConfigSet("SuppressRecomputeRequiredDialog", "True")
        # Create a new document instead of opening external file
        cls.doc = FreeCAD.newDocument("boxtest")

        # Create a simple geometry object for the job
        import Part

        box = cls.doc.addObject("Part::Box", "TestBox")
        box.Length = 100
        box.Width = 100
        box.Height = 20

        # Create CAM job programmatically
        cls.job = PathJob.Create("MainJob", [box], None)
        cls.job.PostProcessor = "linuxcnc"
        cls.job.PostProcessorOutputFile = ""
        cls.job.SplitOutput = False
        cls.job.OrderOutputBy = "Operation"
        cls.job.Fixtures = ["G54", "G55"]

    @classmethod
    def tearDownClass(cls):
        FreeCAD.closeDocument(cls.doc.Name)
        FreeCAD.ConfigSet("SuppressRecomputeRequiredDialog", "")

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test020(self):
        # test creation of postprocessor object
        post = PostProcessorFactory.get_post_processor(self.job, "generic")
        self.assertTrue(post is not None)
        self.assertTrue(hasattr(post, "export"))
        self.assertTrue(hasattr(post, "_buildPostList"))

    def test030(self):
        # test wrapping of old school postprocessor scripts
        post = PostProcessorFactory.get_post_processor(self.job, "linuxcnc_legacy")
        self.assertTrue(post is not None)
        self.assertTrue(hasattr(post, "_buildPostList"))

    def test040(self):
        """Test that the __name__ of the postprocessor is correct."""
        post = PostProcessorFactory.get_post_processor(self.job, "linuxcnc_legacy")
        self.assertEqual(post.script_module.__name__, "linuxcnc_legacy_post")


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
        print(f"DEBUG test030: postlist length={len(firstoplist)}, expected=14")
        print(f"DEBUG test030: firstoplist={[str(item) for item in firstoplist]}")
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
        print(f"DEBUG test040: firstoutputitem[0]={firstoutputitem[0]}, expected='5'")
        print(f"DEBUG test040: tool numbers={[tc.ToolNumber for tc in self.job.Tools.Group]}")
        self.assertTrue(firstoutputitem[0] == str(5))

        # check length of output
        firstoplist = firstoutputitem[1]
        print(f"DEBUG test040: postlist length={len(firstoplist)}, expected=5")
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


class TestMachineConfiguration(unittest.TestCase):
    """Test the typed MachineConfiguration dataclass."""

    def test010_default_initialization(self):
        """Test that MachineConfiguration initializes with correct defaults."""
        state = MachineConfiguration()
        
        # Check default values
        self.assertEqual(state.postprocessor_file_name, "")
        self.assertTrue(state.output.comments)
        self.assertEqual(state.precision.axis_precision, 3)
        self.assertEqual(state.formatting.command_space, " ")
        self.assertEqual(state.name, "Default Machine")
        self.assertEqual(state.machine_units, MachineUnits.METRIC)
        self.assertEqual(state.motion_mode, MotionMode.ABSOLUTE)
        self.assertEqual(state.blocks.finish_label, "Finish")
        self.assertFalse(state.processing.modal)

    def test020_computed_properties(self):
        """Test computed properties work correctly."""
        state = MachineConfiguration()
        
        # Test metric properties
        state.units = "metric"
        self.assertEqual(state.unit_format, "mm")
        self.assertEqual(state.unit_speed_format, "mm/min")
        
        # Test imperial properties
        state.units = "imperial"
        self.assertEqual(state.unit_format, "in")
        self.assertEqual(state.unit_speed_format, "in/min")
        
        # Test command lists
        self.assertIn("G0", state.rapid_moves)
        self.assertIn("G1", state.motion_commands)
        self.assertNotIn("G1", state.rapid_moves)
        self.assertIn("G0", state.motion_commands)  # Now included in CmdMoveAll
        # CmdMoveAll has 13 items: 2 rapid + 2 straight + 4 arc + 5 drill
        self.assertEqual(len(state.motion_commands), 13)

    def test030_line_formatting_state(self):
        """Test LineFormatting mutable state for line numbering."""
        formatting = LineFormatting()
        formatting.line_number_start = 100
        formatting.line_increment = 10
        
        # Test line number progression
        self.assertEqual(formatting.next_line_number(), 100)
        self.assertEqual(formatting.next_line_number(), 110)
        self.assertEqual(formatting.next_line_number(), 120)
        
        # Test reset
        formatting.reset_line_numbers()
        self.assertEqual(formatting.next_line_number(), 100)

    def test040_enum_values(self):
        """Test enum values are correct."""
        self.assertEqual(MachineUnits.METRIC.value, "G21")
        self.assertEqual(MachineUnits.IMPERIAL.value, "G20")
        self.assertEqual(MotionMode.ABSOLUTE.value, "G90")
        self.assertEqual(MotionMode.RELATIVE.value, "G91")

    def test050_nested_dataclass_modification(self):
        """Test that nested dataclasses can be modified independently."""
        state = MachineConfiguration()
        
        # Modify output options
        state.output.comments = False
        state.output.line_numbers = True
        self.assertFalse(state.output.comments)
        self.assertTrue(state.output.line_numbers)
        
        # Modify precision
        state.precision.axis_precision = 5
        self.assertEqual(state.precision.axis_precision, 5)
        
        # Modify machine settings
        state.units = "imperial"
        state.motion_mode = MotionMode.RELATIVE
        self.assertEqual(state.machine_units, MachineUnits.IMPERIAL)
        self.assertEqual(state.motion_mode, MotionMode.RELATIVE)


class TestStateConverter(unittest.TestCase):
    """Test bidirectional conversion between dict and typed state."""

    def test010_from_dict_basic(self):
        """Test converting a basic dictionary to typed state."""
        values = {
            "OUTPUT_COMMENTS": False,
            "OUTPUT_LINE_NUMBERS": True,
            "AXIS_PRECISION": 4,
            "MACHINE_NAME": "Test Machine",
            "UNITS": "G20",
            "MOTION_MODE": "G91",
        }
        
        state = StateConverter.from_dict(values)
        
        self.assertFalse(state.output.comments)
        self.assertTrue(state.output.line_numbers)
        self.assertEqual(state.precision.axis_precision, 4)
        self.assertEqual(state.name, "Test Machine")
        self.assertEqual(state.machine_units, MachineUnits.IMPERIAL)
        self.assertEqual(state.motion_mode, MotionMode.RELATIVE)

    def test020_from_dict_complete(self):
        """Test converting a complete dictionary with all fields."""
        values = {
            "POSTPROCESSOR_FILE_NAME": "test_post",
            "OUTPUT_COMMENTS": True,
            "OUTPUT_BLANK_LINES": False,
            "OUTPUT_HEADER": True,
            "OUTPUT_LINE_NUMBERS": True,
            "OUTPUT_BCNC": True,
            "OUTPUT_PATH_LABELS": True,
            "OUTPUT_MACHINE_NAME": True,
            "OUTPUT_TOOL_CHANGE": False,
            "OUTPUT_DOUBLES": False,
            "OUTPUT_ADAPTIVE": True,
            "AXIS_PRECISION": 5,
            "FEED_PRECISION": 4,
            "SPINDLE_DECIMALS": 2,
            "COMMAND_SPACE": "",
            "COMMENT_SYMBOL": ";",
            "LINE_INCREMENT": 5,
            "line_number": 200,
            "END_OF_LINE_CHARACTERS": "\r\n",
            "MACHINE_NAME": "CNC Router",
            "UNITS": "G21",
            "MOTION_MODE": "G90",
            "USE_TLO": False,
            "STOP_SPINDLE_FOR_TOOL_CHANGE": False,
            "ENABLE_COOLANT": True,
            "ENABLE_MACHINE_SPECIFIC_COMMANDS": True,
            "PREAMBLE": "G17 G54",
            "POSTAMBLE": "M30",
            "SAFETYBLOCK": "G40 G49",
            "PRE_OPERATION": "M8",
            "POST_OPERATION": "M9",
            "TOOL_CHANGE": "M6",
            "TOOLRETURN": "G53 G0 Z0",
            "FINISH_LABEL": "End",
            "MODAL": True,
            "TRANSLATE_DRILL_CYCLES": True,
            "SPLIT_ARCS": True,
            "SHOW_EDITOR": False,
            "LIST_TOOLS_IN_PREAMBLE": True,
            "SHOW_MACHINE_UNITS": False,
            "SHOW_OPERATION_LABELS": False,
            "SUPPRESS_COMMANDS": ["G43", "G49"],
            "SPINDLE_WAIT": 2.5,
            "RETURN_TO": (0.0, 0.0, 10.0),
        }
        
        state = StateConverter.from_dict(values)
        
        # Verify all conversions
        self.assertEqual(state.postprocessor_file_name, "test_post")
        self.assertTrue(state.output.comments)
        self.assertFalse(state.output.blank_lines)
        self.assertTrue(state.output.adaptive)
        self.assertEqual(state.precision.axis_precision, 5)
        self.assertEqual(state.precision.feed_precision, 4)
        self.assertEqual(state.formatting.command_space, "")
        self.assertEqual(state.formatting.comment_symbol, ";")
        self.assertEqual(state.formatting.line_increment, 5)
        self.assertEqual(state.formatting.end_of_line_chars, "\r\n")
        self.assertEqual(state.name, "CNC Router")
        self.assertEqual(state.machine_units, MachineUnits.METRIC)
        self.assertTrue(state.enable_coolant)
        self.assertEqual(state.blocks.preamble, "G17 G54")
        self.assertEqual(state.blocks.postamble, "M30")
        self.assertEqual(state.blocks.finish_label, "End")
        self.assertTrue(state.processing.modal)
        self.assertTrue(state.processing.translate_drill_cycles)
        self.assertEqual(state.processing.spindle_wait, 2.5)
        self.assertEqual(state.processing.return_to, (0.0, 0.0, 10.0))
        self.assertIn("G43", state.processing.suppress_commands)

    def test030_to_dict_basic(self):
        """Test converting typed state back to dictionary."""
        state = MachineConfiguration()
        state.output.comments = False
        state.precision.axis_precision = 6
        state.name = "My Machine"
        state.units = "imperial"
        
        values = StateConverter.to_dict(state)
        
        self.assertFalse(values["OUTPUT_COMMENTS"])
        self.assertEqual(values["AXIS_PRECISION"], 6)
        self.assertEqual(values["MACHINE_NAME"], "My Machine")
        self.assertEqual(values["UNITS"], "G20")
        self.assertEqual(values["UNIT_FORMAT"], "in")

    def test040_roundtrip_conversion(self):
        """Test that dict -> state -> dict preserves values."""
        original_values = {
            "OUTPUT_COMMENTS": False,
            "AXIS_PRECISION": 4,
            "MACHINE_NAME": "Test",
            "UNITS": "G20",
            "MOTION_MODE": "G91",
            "PREAMBLE": "G17",
            "MODAL": True,
            "SPINDLE_WAIT": 1.5,
        }
        
        # Convert to state and back
        state = StateConverter.from_dict(original_values)
        result_values = StateConverter.to_dict(state)
        
        # Check key values are preserved
        self.assertEqual(result_values["OUTPUT_COMMENTS"], False)
        self.assertEqual(result_values["AXIS_PRECISION"], 4)
        self.assertEqual(result_values["MACHINE_NAME"], "Test")
        self.assertEqual(result_values["UNITS"], "G20")
        self.assertEqual(result_values["MOTION_MODE"], "G91")
        self.assertEqual(result_values["PREAMBLE"], "G17")
        self.assertEqual(result_values["MODAL"], True)
        self.assertEqual(result_values["SPINDLE_WAIT"], 1.5)

    def test050_default_values_handling(self):
        """Test that missing dictionary keys use defaults."""
        values = {}  # Empty dictionary
        
        state = StateConverter.from_dict(values)
        
        # Should have all defaults
        self.assertTrue(state.output.comments)
        self.assertEqual(state.precision.axis_precision, 3)
        self.assertEqual(state.machine_units, MachineUnits.METRIC)
        self.assertEqual(state.formatting.command_space, " ")

    def test060_computed_properties_in_dict(self):
        """Test that computed properties are included in to_dict output."""
        state = MachineConfiguration()
        state.units = "metric"
        
        values = StateConverter.to_dict(state)
        
        # Check computed properties
        self.assertIn("UNIT_FORMAT", values)
        self.assertIn("UNIT_SPEED_FORMAT", values)
        self.assertIn("MOTION_COMMANDS", values)
        self.assertIn("RAPID_MOVES", values)
        self.assertEqual(values["UNIT_FORMAT"], "mm")
        self.assertEqual(values["UNIT_SPEED_FORMAT"], "mm/min")


class TestStateConverterEdgeCases(unittest.TestCase):
    """Test edge cases and error handling in state conversion."""

    def test010_partial_dict_conversion(self):
        """Test conversion with only some fields populated."""
        values = {
            "MACHINE_NAME": "Partial Machine",
            "AXIS_PRECISION": 7,
        }
        
        state = StateConverter.from_dict(values)
        
        # Specified values should be set
        self.assertEqual(state.name, "Partial Machine")
        self.assertEqual(state.precision.axis_precision, 7)
        
        # Unspecified values should have defaults
        self.assertTrue(state.output.comments)
        self.assertEqual(state.machine_units, MachineUnits.METRIC)

    def test020_list_fields_conversion(self):
        """Test conversion of list fields."""
        values = {
            "SUPPRESS_COMMANDS": ["G98", "G99", "G80"],
            "DRILL_CYCLES_TO_TRANSLATE": ["G81", "G82"],
            "PARAMETER_ORDER": ["X", "Y", "Z", "F"],
        }
        
        state = StateConverter.from_dict(values)
        
        self.assertEqual(state.processing.suppress_commands, ["G98", "G99", "G80"])
        self.assertEqual(state.processing.drill_cycles_to_translate, ["G81", "G82"])
        self.assertEqual(state.parameter_order, ["X", "Y", "Z", "F"])

    def test030_none_values_handling(self):
        """Test handling of None values in dictionary."""
        values = {
            "RETURN_TO": None,
            "MACHINE_NAME": "Test",
        }
        
        state = StateConverter.from_dict(values)
        
        self.assertIsNone(state.processing.return_to)
        self.assertEqual(state.name, "Test")  # name is now at top level in unified Machine

    def test040_line_number_state_preservation(self):
        """Test that line number state is preserved in conversion."""
        values = {"line_number": 500}
        
        state = StateConverter.from_dict(values)
        
        # Line number should be set correctly
        self.assertEqual(state.formatting.current_line_number, 500)
        
        # Convert back
        result = StateConverter.to_dict(state)
        self.assertEqual(result["line_number"], 500)


class TestTypedStateIntegration(unittest.TestCase):
    """Integration tests for typed state with existing postprocessor code."""

    def test010_state_can_replace_values_dict(self):
        """Test that MachineConfiguration can be used where values dict was used."""
        state = MachineConfiguration()
        
        # Set some values
        state.output.comments = True
        state.precision.axis_precision = 4
        state.name = "Integration Test"  # name is now at top level in unified Machine
        
        # Convert to dict for legacy code
        values = StateConverter.to_dict(state)
        
        # Verify legacy code can access values
        self.assertTrue(values["OUTPUT_COMMENTS"])
        self.assertEqual(values["AXIS_PRECISION"], 4)
        self.assertEqual(values["MACHINE_NAME"], "Integration Test")

    def test020_state_modification_isolation(self):
        """Test that modifying one state doesn't affect another."""
        state1 = MachineConfiguration()
        state2 = MachineConfiguration()
        
        # Modify state1
        state1.output.comments = False
        state1.precision.axis_precision = 10
        
        # state2 should be unchanged
        self.assertTrue(state2.output.comments)
        self.assertEqual(state2.precision.axis_precision, 3)
