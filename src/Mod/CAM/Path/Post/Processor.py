# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *   Copyright (c) 2014 Yorik van Havre <yorik@uncreated.net>              *
# *   Copyright (c) 2014 sliptonic <shopinthewoods@gmail.com>               *
# *   Copyright (c) 2022 - 2025 Larry Woestman <LarryWoestman2@gmail.com>   *
# *   Copyright (c) 2024 Ondsel <development@ondsel.com>                    *
# *                                                                         *
# *   This file is part of the FreeCAD CAx development system.              *
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
"""
The base classes for post processors in the CAM workbench.
"""
import argparse
from dataclasses import dataclass, field
from enum import Enum
import importlib.util
import os
from PySide import QtCore, QtGui
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import Path.Base.Util as PathUtil
import Path.Geom as PathGeom
import Path.Post.UtilsArguments as PostUtilsArguments
import Path.Post.UtilsExport as PostUtilsExport
from Path.Machine.models.machine import (
    Machine,
    MachineUnits,
    MotionMode,
    OutputOptions,
    PrecisionSettings,
    LineFormatting,
    GCodeBlocks,
    ProcessingOptions,
    LinearAxis,
    RotaryAxis,
    Spindle,
)

import FreeCAD
import Path

translate = FreeCAD.Qt.translate

Path.Log.setLevel(Path.Log.Level.INFO, Path.Log.thisModule())

debug = False
if debug:
    Path.Log.setLevel(Path.Log.Level.DEBUG, Path.Log.thisModule())
    Path.Log.trackModule(Path.Log.thisModule())
else:
    Path.Log.setLevel(Path.Log.Level.INFO, Path.Log.thisModule())


class _TempObject:
    Path = None
    Name = "Fixture"
    InList = []
    Label = "Fixture"


# ============================================================================
# Typed State Classes - Now imported from unified Machine model
# ============================================================================
# MachineUnits, MotionMode, OutputOptions, PrecisionSettings, LineFormatting,
# GCodeBlocks, and ProcessingOptions are now imported from Path.Machine.models.machine

# Alias for backward compatibility - PostProcessorConfiguration is now the unified Machine class
PostProcessorConfiguration = Machine

# Legacy alias for compatibility
MachineConfiguration = Machine

# Create a stub MachineOptions class for backward compatibility with tests
# In the unified Machine class, these fields are at the top level
@dataclass
class MachineOptions:
    """
    Legacy compatibility class - fields now exist at top level in unified Machine.
    This stub exists only for backward compatibility with existing test imports.
    """
    name: str = "unknown machine"
    units: MachineUnits = MachineUnits.METRIC
    motion_mode: MotionMode = MotionMode.ABSOLUTE
    use_tlo: bool = True
    stop_spindle_for_tool_change: bool = True
    enable_coolant: bool = False
    enable_machine_specific_commands: bool = False


class StateConverter:
    """
    Bidirectional converter between legacy dictionary state and typed configuration.
    
    This enables gradual migration by allowing both formats to coexist.
    Legacy code can continue using dictionaries while new code uses typed configuration.
    """
    
    @staticmethod
    def from_dict(values: Dict[str, Any]) -> MachineConfiguration:
        """
        Convert legacy dictionary to typed configuration.
        
        Args:
            values: Legacy dictionary with string keys
            
        Returns:
            MachineConfiguration with all values populated
        """
        state = MachineConfiguration()
        
        # Output options
        state.output.comments = values.get("OUTPUT_COMMENTS", True)
        state.output.blank_lines = values.get("OUTPUT_BLANK_LINES", True)
        state.output.header = values.get("OUTPUT_HEADER", True)
        state.output.line_numbers = values.get("OUTPUT_LINE_NUMBERS", False)
        state.output.bcnc_blocks = values.get("OUTPUT_BCNC", False)
        state.output.path_labels = values.get("OUTPUT_PATH_LABELS", False)
        state.output.machine_name = values.get("OUTPUT_MACHINE_NAME", False)
        state.output.tool_change = values.get("OUTPUT_TOOL_CHANGE", True)
        state.output.doubles = values.get("OUTPUT_DOUBLES", True)
        state.output.adaptive = values.get("OUTPUT_ADAPTIVE", False)
        
        # Precision
        state.precision.axis_precision = values.get("AXIS_PRECISION", 3)
        state.precision.feed_precision = values.get("FEED_PRECISION", 3)
        state.precision.spindle_decimals = values.get("SPINDLE_DECIMALS", 0)
        state.precision.default_metric_axis = values.get("DEFAULT_AXIS_PRECISION", 3)
        state.precision.default_metric_feed = values.get("DEFAULT_FEED_PRECISION", 3)
        state.precision.default_imperial_axis = values.get("DEFAULT_INCH_AXIS_PRECISION", 4)
        state.precision.default_imperial_feed = values.get("DEFAULT_INCH_FEED_PRECISION", 4)
        
        # Formatting
        state.formatting.command_space = values.get("COMMAND_SPACE", " ")
        state.formatting.comment_symbol = values.get("COMMENT_SYMBOL", "(")
        state.formatting.line_increment = values.get("LINE_INCREMENT", 10)
        state.formatting.line_number_start = values.get("line_number", 100)
        state.formatting.end_of_line_chars = values.get("END_OF_LINE_CHARACTERS", "\n")
        state.formatting._current_line = values.get("line_number", 100)
        
        # Machine (now at top level in unified Machine class)
        state.name = values.get("MACHINE_NAME", "Default Machine")
        units_str = values.get("UNITS", "G21")
        state.units = "metric" if units_str == "G21" else "imperial"
        motion_str = values.get("MOTION_MODE", "G90")
        state.motion_mode = (
            MotionMode.ABSOLUTE if motion_str == "G90" else MotionMode.RELATIVE
        )
        state.use_tlo = values.get("USE_TLO", True)
        state.stop_spindle_for_tool_change = values.get(
            "STOP_SPINDLE_FOR_TOOL_CHANGE", True
        )
        state.enable_coolant = values.get("ENABLE_COOLANT", False)
        state.enable_machine_specific_commands = values.get(
            "ENABLE_MACHINE_SPECIFIC_COMMANDS", False
        )
        
        # Blocks
        state.blocks.pre_job = values.get("PRE_JOB", "")
        state.blocks.post_job = values.get("POST_JOB", "")
        state.blocks.preamble = values.get("PREAMBLE", "")
        state.blocks.postamble = values.get("POSTAMBLE", "")
        state.blocks.safetyblock = values.get("SAFETYBLOCK", "")
        state.blocks.pre_operation = values.get("PRE_OPERATION", "")
        state.blocks.post_operation = values.get("POST_OPERATION", "")
        state.blocks.pre_tool_change = values.get("PRE_TOOL_CHANGE", "")
        state.blocks.post_tool_change = values.get("POST_TOOL_CHANGE", "")
        state.blocks.tool_return = values.get("TOOLRETURN", "")
        state.blocks.pre_fixture_change = values.get("PRE_FIXTURE_CHANGE", "")
        state.blocks.post_fixture_change = values.get("POST_FIXTURE_CHANGE", "")
        state.blocks.pre_rotary_move = values.get("PRE_ROTARY_MOVE", "")
        state.blocks.post_rotary_move = values.get("POST_ROTARY_MOVE", "")
        state.blocks.pre_spindle_change = values.get("PRE_SPINDLE_CHANGE", "")
        state.blocks.post_spindle_change = values.get("POST_SPINDLE_CHANGE", "")
        state.blocks.finish_label = values.get("FINISH_LABEL", "Finish")
        
        # Processing
        state.processing.modal = values.get("MODAL", False)
        state.processing.translate_drill_cycles = values.get("TRANSLATE_DRILL_CYCLES", False)
        state.processing.split_arcs = values.get("SPLIT_ARCS", False)
        state.processing.show_editor = values.get("SHOW_EDITOR", True)
        state.processing.list_tools_in_preamble = values.get("LIST_TOOLS_IN_PREAMBLE", False)
        state.processing.show_machine_units = values.get("SHOW_MACHINE_UNITS", True)
        state.processing.show_operation_labels = values.get("SHOW_OPERATION_LABELS", True)
        state.processing.drill_cycles_to_translate = values.get(
            "DRILL_CYCLES_TO_TRANSLATE", ["G73", "G81", "G82", "G83"]
        )
        state.processing.suppress_commands = values.get("SUPPRESS_COMMANDS", [])
        state.processing.chipbreaking_amount = values.get("CHIPBREAKING_AMOUNT", 0.25)
        state.processing.spindle_wait = values.get("SPINDLE_WAIT", 0.0)
        state.processing.return_to = values.get("RETURN_TO")
        state.processing.tool_before_change = values.get("TOOL_BEFORE_CHANGE", False)
        
        # Dynamic state
        state.postprocessor_file_name = values.get("POSTPROCESSOR_FILE_NAME", "")
        state.parameter_functions = values.get("PARAMETER_FUNCTIONS", {})
        if "PARAMETER_ORDER" in values:
            state.parameter_order = values["PARAMETER_ORDER"]
        
        return state
    
    @staticmethod
    def to_dict(state: MachineConfiguration) -> Dict[str, Any]:
        """
        Convert typed configuration back to legacy dictionary format.
        
        This maintains backward compatibility with existing code that expects
        the dictionary format.
        
        Args:
            state: Typed MachineConfiguration
            
        Returns:
            Dictionary with all values in legacy format
        """
        return {
            # Output
            "OUTPUT_COMMENTS": state.output.comments,
            "OUTPUT_BLANK_LINES": state.output.blank_lines,
            "OUTPUT_HEADER": state.output.header,
            "OUTPUT_LINE_NUMBERS": state.output.line_numbers,
            "OUTPUT_BCNC": state.output.bcnc_blocks,
            "OUTPUT_PATH_LABELS": state.output.path_labels,
            "OUTPUT_MACHINE_NAME": state.output.machine_name,
            "OUTPUT_TOOL_CHANGE": state.output.tool_change,
            "OUTPUT_DOUBLES": state.output.doubles,
            "OUTPUT_ADAPTIVE": state.output.adaptive,
            
            # Precision
            "AXIS_PRECISION": state.precision.axis_precision,
            "FEED_PRECISION": state.precision.feed_precision,
            "SPINDLE_DECIMALS": state.precision.spindle_decimals,
            "DEFAULT_AXIS_PRECISION": state.precision.default_metric_axis,
            "DEFAULT_FEED_PRECISION": state.precision.default_metric_feed,
            "DEFAULT_INCH_AXIS_PRECISION": state.precision.default_imperial_axis,
            "DEFAULT_INCH_FEED_PRECISION": state.precision.default_imperial_feed,
            
            # Formatting
            "COMMAND_SPACE": state.formatting.command_space,
            "COMMENT_SYMBOL": state.formatting.comment_symbol,
            "LINE_INCREMENT": state.formatting.line_increment,
            "line_number": state.formatting.current_line_number,
            "END_OF_LINE_CHARACTERS": state.formatting.end_of_line_chars,
            
            # Machine (now at top level in unified Machine class)
            "MACHINE_NAME": state.name,
            "UNITS": state.machine_units.value,
            "UNIT_FORMAT": state.unit_format,
            "UNIT_SPEED_FORMAT": state.unit_speed_format,
            "MOTION_MODE": state.motion_mode.value,
            "USE_TLO": state.use_tlo,
            "STOP_SPINDLE_FOR_TOOL_CHANGE": state.stop_spindle_for_tool_change,
            "ENABLE_COOLANT": state.enable_coolant,
            "ENABLE_MACHINE_SPECIFIC_COMMANDS": state.enable_machine_specific_commands,
            
            # Blocks
            "PRE_JOB": state.blocks.pre_job,
            "POST_JOB": state.blocks.post_job,
            "PREAMBLE": state.blocks.preamble,
            "POSTAMBLE": state.blocks.postamble,
            "SAFETYBLOCK": state.blocks.safetyblock,
            "PRE_OPERATION": state.blocks.pre_operation,
            "POST_OPERATION": state.blocks.post_operation,
            "PRE_TOOL_CHANGE": state.blocks.pre_tool_change,
            "POST_TOOL_CHANGE": state.blocks.post_tool_change,
            "TOOL_CHANGE": state.blocks.pre_tool_change,  # Legacy key for backward compatibility
            "TOOLRETURN": state.blocks.tool_return,
            "PRE_FIXTURE_CHANGE": state.blocks.pre_fixture_change,
            "POST_FIXTURE_CHANGE": state.blocks.post_fixture_change,
            "PRE_ROTARY_MOVE": state.blocks.pre_rotary_move,
            "POST_ROTARY_MOVE": state.blocks.post_rotary_move,
            "PRE_SPINDLE_CHANGE": state.blocks.pre_spindle_change,
            "POST_SPINDLE_CHANGE": state.blocks.post_spindle_change,
            "FINISH_LABEL": state.blocks.finish_label,
            
            # Processing
            "MODAL": state.processing.modal,
            "TRANSLATE_DRILL_CYCLES": state.processing.translate_drill_cycles,
            "SPLIT_ARCS": state.processing.split_arcs,
            "SHOW_EDITOR": state.processing.show_editor,
            "LIST_TOOLS_IN_PREAMBLE": state.processing.list_tools_in_preamble,
            "SHOW_MACHINE_UNITS": state.processing.show_machine_units,
            "SHOW_OPERATION_LABELS": state.processing.show_operation_labels,
            "DRILL_CYCLES_TO_TRANSLATE": state.processing.drill_cycles_to_translate,
            "SUPPRESS_COMMANDS": state.processing.suppress_commands,
            "CHIPBREAKING_AMOUNT": state.processing.chipbreaking_amount,
            "SPINDLE_WAIT": state.processing.spindle_wait,
            "RETURN_TO": state.processing.return_to,
            "TOOL_BEFORE_CHANGE": state.processing.tool_before_change,
            
            # Dynamic
            "POSTPROCESSOR_FILE_NAME": state.postprocessor_file_name,
            "PARAMETER_FUNCTIONS": state.parameter_functions,
            "PARAMETER_ORDER": state.parameter_order,
            "MOTION_COMMANDS": state.motion_commands,
            "RAPID_MOVES": state.rapid_moves,
        }


# ============================================================================
# Legacy Type Definitions - Maintained for backward compatibility
# ============================================================================

Defaults = Dict[str, bool]
FormatHelp = str
GCodeOrNone = Optional[str]
GCodeSections = List[Tuple[str, GCodeOrNone]]
Parser = argparse.ArgumentParser
ParserArgs = Union[None, str, argparse.Namespace]
Postables = Union[List, List[Tuple[str, List]]]
Section = Tuple[str, List]
Sublist = List
Units = str
Values = Dict[str, Any]
Visible = Dict[str, bool]


class PostProcessorFactory:
    """Factory class for creating post processors."""

    @staticmethod
    def get_post_processor(job, postname):
        # Log initial debug message
        Path.Log.debug("PostProcessorFactory.get_post_processor()")

        # Posts have to be in a place we can find them
        paths = Path.Preferences.searchPathsPost()
        paths.extend(sys.path)

        module_name = f"{postname}_post"
        class_name = postname.title()
        Path.Log.debug(f"PostProcessorFactory.get_post_processor() - postname: {postname}")
        Path.Log.debug(f"PostProcessorFactory.get_post_processor() - module_name: {module_name}")
        Path.Log.debug(f"PostProcessorFactory.get_post_processor() - class_name: {class_name}")
        

        # Iterate all the paths to find the module
        for path in paths:
            module_path = os.path.join(path, f"{module_name}.py")
            spec = importlib.util.spec_from_file_location(module_name, module_path)

            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                    Path.Log.debug(f"found module {module_name} at {module_path}")

                except (FileNotFoundError, ImportError, ModuleNotFoundError):
                    continue

                try:
                    PostClass = getattr(module, class_name)
                    return PostClass(job)
                except AttributeError:
                    # Return an instance of WrapperPost if no valid module is found
                    Path.Log.debug(f"Post processor {postname} is a script")
                    return WrapperPost(job, module_path, module_name)

        return None


def needsTcOp(oldTc, newTc):
    return (
        oldTc is None
        or oldTc.ToolNumber != newTc.ToolNumber
        or oldTc.SpindleSpeed != newTc.SpindleSpeed
        or oldTc.SpindleDir != newTc.SpindleDir
    )


class PostProcessor:
    """Base Class.  All non-legacy postprocessors should inherit from this class."""

    def __init__(self, job, tooltip, tooltipargs, units, *args, **kwargs):
        self._tooltip = tooltip
        self._tooltipargs = tooltipargs
        self._units = units
        self._args = args
        self._kwargs = kwargs
        
        self.reinitialize()

        if isinstance(job, dict):
            # process only selected operations
            self._job = job["job"]
            self._operations = job["operations"]
        else:
            # get all operations from 'Operations' group
            self._job = job
            self._operations = getattr(job.Operations, "Group", []) if job is not None else []

    @classmethod
    def exists(cls, processor):
        return processor in Path.Preferences.allAvailablePostProcessors()

    @property
    def tooltip(self):
        """Get the tooltip text for the post processor."""
        raise NotImplementedError("Subclass must implement abstract method")
        # return self._tooltip

    @property
    def tooltipArgs(self) -> FormatHelp:
        return self.parser.format_help()

    @property
    def units(self):
        """Get the units used by the post processor."""
        return self._units

    def _create_fixture_setup(self, order: int, fixture: str) -> _TempObject:
        """Convert a Fixture setting to _TempObject instance.
        
        Creates a fixture setup with a G0 move to safe height for fixture changes.
        Skips the move for first fixture to avoid moving before tool compensation.
        
        Args:
            order: Fixture index (0 for first fixture)
            fixture: Fixture coordinate system (e.g., "G54", "G55")
            
        Returns:
            _TempObject with fixture setup commands
        """
        fobj = _TempObject()
        c1 = Path.Command(fixture)
        fobj.Path = Path.Path([c1])
        
        # Avoid any tool move after G49 in preamble and before tool change
        # and G43 in case tool height compensation is in use, to avoid
        # dangerous move without tool compensation.
        if order != 0:
            clearance_z = (
                self._job.Stock.Shape.BoundBox.ZMax + 
                self._job.SetupSheet.ClearanceHeightOffset.Value
            )
            c2 = Path.Command(f"G0 Z{clearance_z}")
            fobj.Path.addCommands(c2)
        
        fobj.InList.append(self._job)
        return fobj

    def _build_postlist_by_fixture(self) -> list:
        """Build post list ordered by fixture.
        
        All operations and tool changes are completed in one fixture
        before moving to the next.
        
        Returns:
            List of (fixture_name, operations) tuples
        """
        Path.Log.debug("Ordering by Fixture")
        postlist = []
        wcslist = self._job.Fixtures
        currTc = None
        
        for index, f in enumerate(wcslist):
            # Create fixture setup
            sublist = [self._create_fixture_setup(index, f)]
            
            # Add operations for this fixture
            for obj in self._operations:
                tc = PathUtil.toolControllerForOp(obj)
                if tc is not None and PathUtil.activeForOp(obj):
                    if needsTcOp(currTc, tc):
                        sublist.append(tc)
                        Path.Log.debug(f"Appending TC: {tc.Name}")
                        currTc = tc
                sublist.append(obj)
            
            postlist.append((f, sublist))
        
        return postlist

    def _build_postlist_by_tool(self) -> list:
        """Build post list ordered by tool.
        
        Tool changes are minimized - all operations with the current tool
        are processed in all fixtures before changing tools.
        
        Returns:
            List of (tool_name, operations) tuples
        """
        Path.Log.debug("Ordering by Tool")
        postlist = []
        wcslist = self._job.Fixtures
        toolstring = "None"
        currTc = None
        
        # Build the fixture list
        fixturelist = []
        for index, f in enumerate(wcslist):
            fixturelist.append(self._create_fixture_setup(index, f))
        
        # Generate operations grouped by tool
        curlist = []  # list of ops for current tool, will repeat for each fixture
        sublist = []  # list of ops for output splitting
        
        def commitToPostlist():
            """Commit current tool's operations to postlist."""
            if len(curlist) > 0:
                for fixture in fixturelist:
                    sublist.append(fixture)
                    sublist.extend(curlist)
                postlist.append((toolstring, sublist))
        
        Path.Log.track(self._job.PostProcessorOutputFile)
        for idx, obj in enumerate(self._operations):
            Path.Log.track(obj.Label)
            
            # Check if the operation is active
            if not PathUtil.activeForOp(obj):
                Path.Log.track()
                continue
            
            tc = PathUtil.toolControllerForOp(obj)
            
            # Operation has no ToolController or uses same ToolController
            if tc is None or not needsTcOp(currTc, tc):
                # Queue current operation
                curlist.append(obj)
            
            # Operation uses a different ToolController
            else:
                # Commit previous operations
                commitToPostlist()
                
                # Queue current ToolController and operation
                sublist = [tc]
                curlist = [obj]
                currTc = tc
                
                # Determine the proper string for the operation's ToolController
                if "%T" in self._job.PostProcessorOutputFile:
                    toolstring = f"{tc.ToolNumber}"
                else:
                    toolstring = re.sub(r"[^\w\d-]", "_", tc.Label)
        
        # Commit remaining operations
        commitToPostlist()
        
        return postlist

    def _build_postlist_by_operation(self) -> list:
        """Build post list ordered by operation.
        
        Operations are done in each fixture in sequence.
        
        Returns:
            List of (operation_name, operations) tuples
        """
        Path.Log.debug("Ordering by Operation")
        postlist = []
        wcslist = self._job.Fixtures
        currTc = None
        
        # Generate operations
        for obj in self._operations:
            # Check if the operation is active
            if not PathUtil.activeForOp(obj):
                continue
            
            sublist = []
            Path.Log.debug(f"obj: {obj.Name}")
            
            for index, f in enumerate(wcslist):
                sublist.append(self._create_fixture_setup(index, f))
                tc = PathUtil.toolControllerForOp(obj)
                if tc is not None:
                    if self._job.SplitOutput or needsTcOp(currTc, tc):
                        sublist.append(tc)
                        currTc = tc
                sublist.append(obj)
            
            postlist.append((obj.Label, sublist))
        
        return postlist

    def _buildPostList(self):
        """Determine the specific objects and order to postprocess.
        
        Returns a list of objects which can be passed to exportObjectsWith()
        for final posting. The ordering strategy is determined by the job's
        OrderOutputBy setting.
        
        Returns:
            List of (name, operations) tuples
        """
        orderby = self._job.OrderOutputBy
        Path.Log.debug(f"Ordering by {orderby}")
        
        postlist = []

        if orderby == "Fixture":
            postlist = self._build_postlist_by_fixture()
        elif orderby == "Tool":
            postlist = self._build_postlist_by_tool()
        elif orderby == "Operation":
            postlist = self._build_postlist_by_operation()

        Path.Log.debug(f"Postlist: {postlist}")

        if self._job.SplitOutput:
            Path.Log.track()
            return postlist

        Path.Log.track()
        finalpostlist = [("allitems", [item for slist in postlist for item in slist[1]])]
        Path.Log.debug(f"Postlist: {postlist}")
        return finalpostlist

    def export(self) -> Union[None, GCodeSections]:
        """Process the parser arguments, then postprocess the 'postables'."""
        args: ParserArgs
        flag: bool

        Path.Log.debug("Exporting the job")

        (flag, args) = self.process_arguments()
        #
        # If the flag is True, then continue postprocessing the 'postables'.
        #
        if flag:
            return self.process_postables()
        #
        # The flag is False meaning something unusual happened.
        #
        # If args is None then there was an error during argument processing.
        #
        if args is None:
            return None
        #
        # Otherwise args will contain the argument list formatted for output
        # instead of the "usual" gcode.
        #
        return [("allitems", args)]  # type: ignore

    def init_arguments(
        self,
        values: Values,
        argument_defaults: Defaults,
        arguments_visible: Visible,
    ) -> Parser:
        """Initialize the shared argument definitions."""
        _parser: Parser = PostUtilsArguments.init_shared_arguments(
            values, argument_defaults, arguments_visible
        )
        #
        # Add any argument definitions that are not shared with other postprocessors here.
        #
        return _parser

    def init_argument_defaults(self, argument_defaults: Defaults) -> None:
        """Initialize which arguments (in a pair) are shown as the default argument."""
        PostUtilsArguments.init_argument_defaults(argument_defaults)
        #
        # Modify which argument to show as the default in flag-type arguments here.
        # If the value is True, the first argument will be shown as the default.
        # If the value is False, the second argument will be shown as the default.
        #
        # For example, if you want to show Metric mode as the default, use:
        #   argument_defaults["metric_inch"] = True
        #
        # If you want to show that "Don't pop up editor for writing output" is
        # the default, use:
        #   argument_defaults["show-editor"] = False.
        #
        # Note:  You also need to modify the corresponding entries in the "values" hash
        #        to actually make the default value(s) change to match.
        #

    def init_arguments_visible(self, arguments_visible: Visible) -> None:
        """Initialize which argument pairs are visible in TOOLTIP_ARGS."""
        PostUtilsArguments.init_arguments_visible(arguments_visible)
        #
        # Modify the visibility of any arguments from the defaults here.
        #

    def init_values(self, values: Union[Values, MachineConfiguration]) -> None:
        """Initialize values that are used throughout the postprocessor.
        
        Args:
            values: Either a dict (legacy) or MachineConfiguration (modern)
        """
        # Handle both dict and typed state for backward compatibility
        if isinstance(values, dict):
            # Legacy path: initialize dict directly
            PostUtilsArguments.init_shared_values(values)
            values["UNITS"] = self._units
        else:
            # Modern path: initialize typed state
            state = values
            
            # Initialize shared defaults via dict conversion
            temp_dict = StateConverter.to_dict(state)
            PostUtilsArguments.init_shared_values(temp_dict)
            
            # Convert back to update state with initialized values
            initialized_state = StateConverter.from_dict(temp_dict)
            
            # Copy initialized values back to state
            state.output = initialized_state.output
            state.precision = initialized_state.precision
            state.formatting = initialized_state.formatting
            state.blocks = initialized_state.blocks
            state.processing = initialized_state.processing
            state.parameter_functions = initialized_state.parameter_functions
            state.parameter_order = initialized_state.parameter_order
            
            # Set units from constructor parameter (now at top level in unified Machine)
            if self._units == "Metric":
                state.units = "metric"
            else:
                state.units = "imperial"

    def process_arguments(self) -> Tuple[bool, ParserArgs]:
        """Process any arguments to the postprocessor."""
        #
        # This function is separated out to make it easier to inherit from this class.
        #
        args: ParserArgs
        flag: bool

        (flag, args) = PostUtilsArguments.process_shared_arguments(
            self.values, self.parser, self._job.PostProcessorArgs, self.all_visible, "-"
        )
        #
        # If the flag is True, then all of the arguments should be processed normally.
        #
        if flag:
            #
            # Process any additional arguments here.
            #
            #
            # Sync any dict changes from argument processing back to typed state
            # This ensures self.state and self.values stay synchronized
            #
            self._sync_dict_to_state()
        #
        # If the flag is False, then args is either None (indicating an error while
        # processing the arguments) or a string containing the argument list formatted
        # for output.  Either way the calling routine will need to handle the args value.
        #
        return (flag, args)
    
    def _sync_dict_to_state(self) -> None:
        """Sync changes from self.values dict back to self.state after argument processing."""
        # Sync units (now at top level in unified Machine)
        if self.values["UNITS"] == "G21":
            self.state.units = "metric"
            self._units = "Metric"
        else:
            self.state.units = "imperial"
            self._units = "Inch"
        
        # Sync blocks that may have been modified by command-line arguments
        self.state.blocks.preamble = self.values.get("PREAMBLE", "")
        self.state.blocks.postamble = self.values.get("POSTAMBLE", "")
        self.state.blocks.safetyblock = self.values.get("SAFETYBLOCK", "")
        
        # Sync other commonly modified values
        self.state.output.comments = self.values.get("OUTPUT_COMMENTS", True)
        self.state.output.header = self.values.get("OUTPUT_HEADER", True)
        self.state.processing.show_editor = self.values.get("SHOW_EDITOR", True)

    def process_postables(self) -> GCodeSections:
        """Postprocess the 'postables' in the job to g code sections."""
        #
        # This function is separated out to make it easier to inherit from this class.
        #
        gcode: GCodeOrNone
        g_code_sections: GCodeSections
        partname: str
        postables: Postables
        section: Section
        sublist: Sublist

        postables = self._buildPostList()

        Path.Log.debug(f"postables count: {len(postables)}")

        g_code_sections = []
        for _, section in enumerate(postables):
            partname, sublist = section
            gcode = PostUtilsExport.export_common(self.values, sublist, "-")
            g_code_sections.append((partname, gcode))

        return g_code_sections

    def reinitialize(self) -> None:
        """Initialize or reinitialize the 'core' data structures for the postprocessor."""
        #
        # This is also used to reinitialize the data structures between tests.
        #
        # Initialize typed state
        self.state = MachineConfiguration()
        self.init_values(self.state)
        
        # Create dict representation for backward compatibility
        self.values: Values = StateConverter.to_dict(self.state)
        
        self.argument_defaults: Defaults = {}
        self.init_argument_defaults(self.argument_defaults)
        self.arguments_visible: Visible = {}
        self.init_arguments_visible(self.arguments_visible)
        self.parser: Parser = self.init_arguments(
            self.values, self.argument_defaults, self.arguments_visible
        )
        #
        # Create another parser just to get a list of all possible arguments
        # that may be output using --output_all_arguments.
        #
        self.all_arguments_visible: Visible = {}
        for k in iter(self.arguments_visible):
            self.all_arguments_visible[k] = True
        self.all_visible: Parser = self.init_arguments(
            self.values, self.argument_defaults, self.all_arguments_visible
        )


class WrapperPost(PostProcessor):
    """Wrapper class for old post processors that are scripts."""

    def __init__(self, job, script_path, module_name, *args, **kwargs):
        super().__init__(job, tooltip=None, tooltipargs=None, units=None, *args, **kwargs)
        self.script_path = script_path
        self.module_name = module_name
        Path.Log.debug(f"WrapperPost.__init__({script_path})")
        self.load_script()

    def load_script(self):
        """Dynamically load the script as a module."""
        try:
            spec = importlib.util.spec_from_file_location(self.module_name, self.script_path)
            self.script_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.script_module)
        except Exception as e:
            raise ImportError(f"Failed to load script: {e}")

        if not hasattr(self.script_module, "export"):
            raise AttributeError("The script does not have an 'export' function.")

        # Set properties based on attributes of the module
        self._units = "Metric" if getattr(self.script_module, "UNITS", "G21") == "G21" else "Inch"
        self._tooltip = getattr(self.script_module, "TOOLTIP", "No tooltip provided")
        self._tooltipargs = getattr(self.script_module, "TOOLTIP_ARGS", [])

    def export(self):
        """Dynamically reload the module for the export to ensure up-to-date usage."""

        postables = self._buildPostList()
        Path.Log.debug(f"postables count: {len(postables)}")

        g_code_sections = []
        for idx, section in enumerate(postables):
            partname, sublist = section

            gcode = self.script_module.export(sublist, "-", self._job.PostProcessorArgs)
            Path.Log.debug(f"Exported {partname}")
            g_code_sections.append((partname, gcode))
        return g_code_sections

    @property
    def tooltip(self):
        return self._tooltip

    @property
    def tooltipArgs(self):
        return self._tooltipargs

    @property
    def units(self):
        return self._units
