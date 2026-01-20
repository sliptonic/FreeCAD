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


from Path.Post.Processor import PostProcessorFactory
import FreeCAD
import Path
import Path.Post.Command as PathCommand
import Path.Post.Utils as PostUtils
import Path.Main.Job as PathJob
import Path.Tool.Controller as PathToolController
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


class TestExport2Integration(unittest.TestCase):
    """Integration tests for the export2() function."""

    @classmethod
    def setUpClass(cls):
        FreeCAD.ConfigSet("SuppressRecomputeRequiredDialog", "True")
        cls.doc = FreeCAD.newDocument("export2_test")

        import Part
        box = cls.doc.addObject("Part::Box", "TestBox")
        box.Length = 100
        box.Width = 100
        box.Height = 20

        cls.job = PathJob.Create("Export2TestJob", [box], None)
        cls.job.PostProcessor = "generic"
        cls.job.PostProcessorOutputFile = ""
        cls.job.SplitOutput = False
        cls.job.OrderOutputBy = "Operation"
        cls.job.Fixtures = ["G54"]

        cls.job.addProperty("App::PropertyString", "Machine", "Job", "Machine name")
        cls.job.Machine = "Millstone"

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

        tc = PathToolController.Create("TC_Test_Tool", tool, 1)
        tc.Label = "TC: 6mm Endmill"
        cls.job.addObject(tc)

        profile_op = cls.doc.addObject("Path::FeaturePython", "TestProfile")
        profile_op.Label = "TestProfile"
        cls._default_path = Path.Path([
            Path.Command("G0", {"X": 0.0, "Y": 0.0, "Z": 5.0}),
            Path.Command("G1", {"X": 100.0, "Y": 0.0, "Z": -5.0, "F": 100.0}),
            Path.Command("G1", {"X": 100.0, "Y": 100.0, "Z": -5.0}),
            Path.Command("G1", {"X": 0.0, "Y": 100.0, "Z": -5.0}),
            Path.Command("G1", {"X": 0.0, "Y": 0.0, "Z": -5.0}),
            Path.Command("G0", {"X": 0.0, "Y": 0.0, "Z": 5.0}),
        ])
        profile_op.Path = cls._default_path
        cls.job.Operations.addObject(profile_op)

        cls.doc.recompute()

    @classmethod
    def tearDownClass(cls):
        FreeCAD.closeDocument(cls.doc.Name)
        FreeCAD.ConfigSet("SuppressRecomputeRequiredDialog", "")

    def _create_machine(self, **output_options):
        """Helper to create a machine with specified output options."""
        from Path.Machine.models.machine import Machine
        machine = Machine.create_3axis_config()
        machine.name = "TestMachine"
        for key, value in output_options.items():
            setattr(machine.output, key, value)
        return machine

    def _create_postprocessor(self, machine=None, job=None):
        """Helper to create a PostProcessor with optional machine config."""
        from Path.Post.Processor import PostProcessor
        if job is None:
            job = self.job
        post = PostProcessor(job, "", "", "mm")
        if machine:
            post._machine = machine
        return post

    def _run_export2(self, machine=None, job=None):
        """Helper to run export2 and return results."""
        post = self._create_postprocessor(machine, job)
        return post.export2()

    def _get_first_section_gcode(self, results):
        """Helper to extract first section's G-code from results."""
        if results and len(results) > 0:
            return results[0][1]
        return ""

    def _get_all_gcode(self, results):
        """Helper to combine all sections into single G-code string."""
        all_output = ""
        for section_name, gcode in results:
            all_output += f"\n--- {section_name} ---\n{gcode}"
        return all_output

    def _modify_operation_path(self, commands):
        """Context manager to temporarily modify operation path."""
        class PathModifier:
            def __init__(modifier_self, test_self, commands):
                modifier_self.test_self = test_self
                modifier_self.commands = commands
                modifier_self.profile_op = None
                modifier_self.original_path = None

            def __enter__(modifier_self):
                modifier_self.profile_op = modifier_self.test_self.doc.getObject("TestProfile")
                modifier_self.original_path = modifier_self.profile_op.Path
                modifier_self.profile_op.Path = Path.Path(modifier_self.commands)
                return modifier_self

            def __exit__(modifier_self, exc_type, exc_val, exc_tb):
                modifier_self.profile_op.Path = modifier_self.original_path

        return PathModifier(self, commands)

    @staticmethod
    def _get_full_machine_config():
        """Helper to get the complete machine config used in multiple tests."""
        return {
            "blocks": {
                "post_fixture_change": "(postfixture)",
                "post_job": "(postjob)",
                "post_operation": "(postoperation)",
                "post_rotary_move": "(Postrotary)",
                "post_tool_change": "(posttoolchange)",
                "postamble": "(postamble)",
                "pre_fixture_change": "(prefixture)",
                "pre_job": "(prejob)",
                "pre_operation": "(preoperation)",
                "pre_rotary_move": "(prerotary)",
                "pre_tool_change": "(pretoolchange)",
                "preamble": "(preamble)",
                "safetyblock": "(safety)",
                "tool_return": "(toolreturn)"
            },
            "freecad_version": "1.2.0",
            "machine": {
                "axes": {
                    "A": {
                        "joint": [[0, 0, 0], [0.0, 0.0, 1.0]],
                        "max": 180,
                        "max_velocity": 36000,
                        "min": -180,
                        "prefer_positive": True,
                        "sequence": 0,
                        "type": "angular"
                    },
                    "C": {
                        "joint": [[0, 0, 0], [0.0, 0.0, 1.0]],
                        "max": 180,
                        "max_velocity": 36000,
                        "min": -180,
                        "prefer_positive": True,
                        "sequence": 0,
                        "type": "angular"
                    },
                    "X": {
                        "joint": [[1.0, 0.0, 0.0], [0, 0, 0]],
                        "max": 500.0,
                        "max_velocity": 10000,
                        "min": 50.0,
                        "sequence": 0,
                        "type": "linear"
                    },
                    "Y": {
                        "joint": [[0.0, 1.0, 0.0], [0, 0, 0]],
                        "max": 1000,
                        "max_velocity": 10000,
                        "min": 0,
                        "sequence": 0,
                        "type": "linear"
                    },
                    "Z": {
                        "joint": [[0.0, 0.0, 1.0], [0, 0, 0]],
                        "max": 1000,
                        "max_velocity": 10000,
                        "min": 0,
                        "sequence": 0,
                        "type": "linear"
                    }
                },
                "description": "My linuxcnc mill",
                "manufacturer": "Supermax",
                "name": "MillStone",
                "spindles": [
                    {
                        "id": "spindle1",
                        "max_power_kw": 3.0,
                        "max_rpm": 24000,
                        "min_rpm": 6000,
                        "name": "Spindle 1",
                        "tool_axis": [0.0, 0.0, -1.0],
                        "tool_change": {"type": "manual"}
                    }
                ],
                "units": "metric"
            },
            "output": {
                "axis_precision": 3,
                "blank_lines": True,
                "command_space": " ",
                "comment_symbol": ";",
                "comments": False,
                "end_of_line_chars": "\n",
                "feed_precision": 3,
                "header": False,
                "line_increment": 10,
                "line_number_start": 100,
                "line_numbers": False,
                "list_tools_in_preamble": False,
                "machine_name": False,
                "output_bcnc_comments": True,
                "output_double_parameters": True,
                "output_units": "metric",
                "path_labels": False,
                "show_editor": True,
                "show_operation_labels": True,
                "spindle_decimals": 0
            },
            "postprocessor": {
                "args": "",
                "file_name": "",
                "motion_mode": "G90"
            },
            "processing": {
                "adaptive": False,
                "drill_cycles_to_translate": ["G73", "G81", "G82", "G83"],
                "modal": False,
                "show_machine_units": True,
                "spindle_wait": 0.0,
                "split_arcs": False,
                "suppress_commands": [],
                "tool_before_change": False,
                "tool_change": True,
                "translate_drill_cycles": False
            },
            "version": 1
        }

    def test010_export2_programmatic_job(self):
        """Test export2() with programmatically created job - prints G-code to console."""
        from Path.Post.Processor import PostProcessor

        # Create post processor
        post = PostProcessor(self.job, "", "", "mm")

        # Call export2 and get results
        results = post.export2()

        # Print results to console for inspection
        print("\n=== EXPORT2 PROGRAMMATIC JOB RESULTS ===")
        if results:
            for section_name, gcode in results:
                print(f"\n--- Section: {section_name} ---")
                if gcode:
                    print(gcode)
                else:
                    print("(No G-code generated)")
        else:
            print("No results returned from export2()")
        print("=== END EXPORT2 RESULTS ===\n")

        # Basic assertions
        self.assertIsNotNone(results)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

        # Check that first section contains header comments if header is enabled
        if results:
            first_section_name, first_section_gcode = results[0]
            if first_section_gcode:
                # Header comments should be at the beginning (if enabled)
                self.assertTrue(len(first_section_gcode) > 0)

    # def test020_export2_loaded_file(self):
    #     """Test export2() with job loaded from disk file."""
    #     from Path.Post.Processor import PostProcessor
    #     import os

    #     file_path = '/home/brad/.cache/FreeCAD/Cache/Ondsel-Lens/sliptonic/694957c6b87153fc831c6707/bosstest.FCStd'

    #     if not os.path.exists(file_path):
    #         self.skipTest(f"Test file not found: {file_path}")

    #     # Load the document
    #     try:
    #         loaded_doc = FreeCAD.openDocument(file_path)
    #     except Exception as e:
    #         self.skipTest(f"Could not load document: {e}")

    #     try:
    #         # Find the job in the loaded document
    #         job = loaded_doc.getObject("Job")
    #         # Create post processor
    #         post = PostProcessor(job, "", "", "mm")

    #         # Call export2 and get results
    #         results = post.export2()

    #         # Print results to console for inspection
    #         print("\n=== EXPORT2 LOADED FILE RESULTS ===")
    #         if results:
    #             for section_name, gcode in results:
    #                 print(f"\n--- Section: {section_name} ---")
    #                 if gcode:
    #                     # Print first 1000 characters to avoid overwhelming output
    #                     print(gcode[:1000])
    #                     if len(gcode) > 1000:
    #                         print(f"... ({len(gcode) - 1000} more characters)")
    #                 else:
    #                     print("(No G-code generated)")
    #         else:
    #             print("No results returned from export2()")
    #         print("=== END EXPORT2 LOADED FILE RESULTS ===\n")

    #         # Basic assertions
    #         self.assertIsNotNone(results)
    #         self.assertIsInstance(results, list)
    #         self.assertGreater(len(results), 0)

    #         # Check that first section contains header comments if header is enabled
    #         if results:
    #             first_section_name, first_section_gcode = results[0]
    #             if first_section_gcode:
    #                 # Header comments should be at the beginning (if enabled)
    #                 self.assertTrue(len(first_section_gcode) > 0)

    #     finally:
    #         # Clean up loaded document
    #         FreeCAD.closeDocument(loaded_doc.Name)

    def test030_header_true_comments_false(self):
        """Test that header:true and comments:false shows header but suppresses inline comments."""
        machine = self._create_machine(
            output_header=True,
            output_comments=False,
            line_numbers=False
        )

        results = self._run_export2(machine)
        self.assertIsNotNone(results)
        self.assertGreater(len(results), 0)

        first_section_gcode = self._get_first_section_gcode(results)
        lines = first_section_gcode.split('\n')

        header_comments = [line for line in lines if line.startswith('(') and 'Machine' in line]
        self.assertGreater(len(header_comments), 0, "Header comments should be present")

        with self._modify_operation_path([
            Path.Command("(Test inline comment)"),
            Path.Command("G0", {"X": 0.0, "Y": 0.0, "Z": 5.0}),
        ]):
            results = self._run_export2(machine)
            first_section_gcode = self._get_first_section_gcode(results)
            self.assertNotIn("Test inline comment", first_section_gcode,
                            "Inline comments should be suppressed when comments:false")

    def test040_header_false_comments_true(self):
        """Test that header:false and comments:true suppresses header but shows inline comments."""
        machine = self._create_machine(
            output_header=False,
            output_comments=True,
            line_numbers=False
        )

        with self._modify_operation_path([
            Path.Command("(Test inline comment)"),
            Path.Command("G0", {"X": 0.0, "Y": 0.0, "Z": 5.0}),
        ]):
            results = self._run_export2(machine)
            self.assertIsNotNone(results)
            self.assertGreater(len(results), 0)

            first_section_gcode = self._get_first_section_gcode(results)
            lines = first_section_gcode.split('\n')

            header_comments = [line for line in lines if line.startswith('(') and 'Machine' in line]
            self.assertEqual(len(header_comments), 0, "Header comments should be suppressed when header:false")

            self.assertIn("Test inline comment", first_section_gcode,
                         "Inline comments should be present when comments:true")

    def test050_line_numbers_exclude_header(self):
        """Test that line numbers are applied to G-code but not header comments."""
        machine = self._create_machine(
            output_header=True,
            output_comments=False,
            line_numbers=True,
            line_number_start=100,
            line_increment=10
        )

        results = self._run_export2(machine)
        self.assertIsNotNone(results)
        self.assertGreater(len(results), 0)

        first_section_gcode = self._get_first_section_gcode(results)
        lines = first_section_gcode.split('\n')

        header_lines = [line for line in lines if line.strip().startswith('(')]
        gcode_lines = [line for line in lines if line.strip().startswith('N') or line.strip().startswith('G')]

        for line in header_lines:
            self.assertFalse(line.strip().startswith('N'),
                           f"Header comment should not have line number: {line}")

        numbered_lines = [line for line in gcode_lines if line.strip().startswith('N')]
        self.assertGreater(len(numbered_lines), 0, "G-code lines should have line numbers")

        if numbered_lines:
            first_numbered = numbered_lines[0].strip()
            self.assertTrue(first_numbered.startswith('N100'),
                          f"First line number should be N100, got: {first_numbered}")

    def test060_line_numbers_from_config(self):
        """Test that line numbering settings are read from machine config."""
        machine = self._create_machine(
            line_numbers=True,
            line_number_start=50,
            line_increment=5
        )

        results = self._run_export2(machine)
        first_section_gcode = self._get_first_section_gcode(results)
        lines = first_section_gcode.split('\n')

        numbered_lines = [line.strip() for line in lines if line.strip().startswith('N')]

        if numbered_lines:
            self.assertTrue(numbered_lines[0].startswith('N50'),
                          f"First line should be N50, got: {numbered_lines[0]}")

            if len(numbered_lines) >= 2:
                self.assertTrue(numbered_lines[1].startswith('N55'),
                              f"Second line should be N55, got: {numbered_lines[1]}")

    def test070_precision_from_config(self):
        """Test that axis_precision and feed_precision settings are read from machine config."""
        machine = self._create_machine(
            axis_precision=4,
            feed_precision=1,
            line_numbers=False
        )

        with self._modify_operation_path([
            Path.Command("G0", {"X": 10.12345, "Y": 20.98765, "Z": 5.5}),
            Path.Command("G1", {"X": 100.123456, "Y": 0.0, "Z": -5.0, "F": 100.123}),
        ]):
            results = self._run_export2(machine)
            first_section_gcode = self._get_first_section_gcode(results)

            self.assertIn("X10.1235", first_section_gcode,
                         "X coordinate should have 4 decimal places (rounded)")
            self.assertIn("Y20.9876", first_section_gcode,
                         "Y coordinate should have 4 decimal places (rounded)")
            self.assertIn("Z5.5000", first_section_gcode,
                         "Z coordinate should have 4 decimal places")
            self.assertIn("F6007.4", first_section_gcode,
                         "Feed should have 1 decimal place")

    def test080_comment_symbol_from_config(self):
        """Test that comment_symbol setting formats comments correctly."""
        machine1 = self._create_machine(
            comment_symbol='(',
            output_comments=True,
            output_header=False,
            line_numbers=False
        )

        machine2 = self._create_machine(
            comment_symbol=';',
            output_comments=True,
            output_header=False,
            line_numbers=False
        )

        with self._modify_operation_path([
            Path.Command("(Test comment)"),
            Path.Command("G0", {"X": 0.0, "Y": 0.0, "Z": 5.0}),
        ]):
            results1 = self._run_export2(machine1)
            first_section_gcode1 = self._get_first_section_gcode(results1)
            self.assertIn("(Test comment)", first_section_gcode1,
                         "Comments should be surrounded by parentheses when comment_symbol='('")

            results2 = self._run_export2(machine2)
            first_section_gcode2 = self._get_first_section_gcode(results2)
            self.assertIn("; Test comment", first_section_gcode2,
                         "Comments should be prefixed with semicolon when comment_symbol=';'")

    def test082_output_double_parameters_false(self):
        """Test that output_double_parameters=false suppresses duplicate parameters."""
        machine = self._create_machine(
            filter_double_parameters=False,
            line_numbers=False,
            output_comments=False,
            output_header=False
        )

        with self._modify_operation_path([
            Path.Command("G0", {"X": 10.0, "Y": 10.0, "Z": 5.0, "F": 1000.0}),
            Path.Command("G1", {"X": 20.0, "Y": 10.0, "Z": 5.0, "F": 1000.0}),
            Path.Command("G1", {"X": 20.0, "Y": 20.0, "Z": 5.0, "F": 1000.0}),
        ]):
            results = self._run_export2(machine)
            first_section_gcode = self._get_first_section_gcode(results)
            lines = [line.strip() for line in first_section_gcode.split('\n') if line.strip()]
            gcode_lines = [line for line in lines if not line.startswith('(')]

            self.assertTrue(any('G0 X10.000 Y10.000 Z5.000 F60000.000' in line for line in gcode_lines),
                            "First command should have all parameters")

            second_commands = [line for line in gcode_lines if 'G1' in line and 'X20.000' in line]
            self.assertTrue(len(second_commands) > 0, "Should have G1 command with X20.000")
            second_cmd = second_commands[0]
            self.assertNotIn('Y', second_cmd, "Y should be suppressed (unchanged)")
            self.assertNotIn('Z', second_cmd, "Z should be suppressed (unchanged)")
            self.assertNotIn('F', second_cmd, "F should be suppressed (unchanged)")

            third_commands = [line for line in gcode_lines if 'G1' in line and 'Y20.000' in line]
            self.assertTrue(len(third_commands) > 0, "Should have G1 command with Y20.000")

    def test083_output_double_parameters_true(self):
        """Test that output_double_parameters=true shows all parameters (default behavior)."""
        machine = self._create_machine(
            filter_double_parameters=True,
            line_numbers=False,
            output_comments=False,
            output_header=False
        )

        with self._modify_operation_path([
            Path.Command("G0", {"X": 10.0, "Y": 10.0, "Z": 5.0, "F": 1000.0}),
            Path.Command("G1", {"X": 20.0, "Y": 10.0, "Z": 5.0, "F": 1000.0}),
        ]):
            post = self._create_postprocessor(machine)
            post.values['OUTPUT_DOUBLES'] = True
            results = post.export2()

            first_section_gcode = self._get_first_section_gcode(results)
            lines = [line.strip() for line in first_section_gcode.split('\n') if line.strip()]
            gcode_lines = [line for line in lines if not line.startswith('(')]

            self.assertTrue(any('G0 X10.000 Y10.000 Z5.000 F60000.000' in line for line in gcode_lines),
                            "First command should have all parameters")

    def test084_gcode_blocks_insertion(self):
        """Test that all G-code blocks from machine config are properly inserted."""
        from Path.Machine.models.machine import Machine

        machine_config = self._get_full_machine_config()
        machine = Machine.from_dict(machine_config)

        with self._modify_operation_path([
            Path.Command("G0", {"X": 10.0, "Y": 10.0, "Z": 5.0, "F": 1000.0}),
            Path.Command("G1", {"X": 20.0, "Y": 10.0, "Z": 5.0, "F": 1000.0}),
        ]):
            results = self._run_export2(machine)
            all_output = self._get_all_gcode(results)

            self.assertIn("(safety)", all_output, "Safetyblock should appear in output")
            self.assertIn("(preamble)", all_output, "Preamble should appear in output")
            self.assertIn("(prejob)", all_output, "Pre-job should appear in output")
            self.assertIn("(preoperation)", all_output, "Pre-operation should appear in output")
            self.assertIn("(postoperation)", all_output, "Post-operation should appear in output")
            self.assertIn("(postjob)", all_output, "Post-job should appear in output")
            self.assertIn("(postamble)", all_output, "Postamble should appear in output")

    def test085_rotary_blocks_insertion(self):
        """Test that pre/post rotary blocks are inserted around rotary axis moves."""
        from Path.Machine.models.machine import Machine

        machine_config = self._get_full_machine_config()
        machine = Machine.from_dict(machine_config)

        with self._modify_operation_path([
            Path.Command("G1", {"X": 10.0}),
            Path.Command("G0", {"A": 45.0}),
            Path.Command("G0", {"C": 90.0, "Y": 11.0}),
            Path.Command("G1", {"Y": 10.0}),
            Path.Command("G0", {"B": 30.0}),
            Path.Command("G1", {"X": 20.0}),
        ]):
            results = self._run_export2(machine)
            all_output = "\n".join(gcode for _, gcode in results)

            self.assertIn("(prerotary)", all_output, "Pre-rotary block should appear in output")
            self.assertIn("(Postrotary)", all_output, "Post-rotary block should appear in output")

            prerotary_count = all_output.count("(prerotary)")
            postrotary_count = all_output.count("(Postrotary)")
            self.assertEqual(prerotary_count, 2, "Should have 2 pre-rotary blocks (one per rotary group)")
            self.assertEqual(postrotary_count, 2, "Should have 2 post-rotary blocks (one per rotary group)")

            lines = all_output.split('\n')
            prerotary_indices = [i for i, line in enumerate(lines) if '(prerotary)' in line]
            postrotary_indices = [i for i, line in enumerate(lines) if '(Postrotary)' in line]
            
            for pre_idx, post_idx in zip(prerotary_indices, postrotary_indices):
                self.assertTrue(pre_idx < post_idx, "Pre-rotary should appear before post-rotary")

            print(f"\nDEBUG test085: Rotary blocks output:\n{all_output}")
