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
import importlib.util
import os
from PySide import QtCore, QtGui
import re
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
from Path.Post.DrillCycleExpander import DrillCycleExpander, EXPANDABLE_DRILL_CYCLES

import Path.Base.Util as PathUtil
import Path.Post.UtilsArguments as PostUtilsArguments
import Path.Post.UtilsExport as PostUtilsExport
import Path.Post.PostList as PostList

import FreeCAD
import Path

import Path.Post.Utils as PostUtils
from Path.Machine.models.machine import (
    Machine,
    Spindle,
    OutputOptions,
    GCodeBlocks,
    ProcessingOptions,
    MachineFactory,
)

translate = FreeCAD.Qt.translate

Path.Log.setLevel(Path.Log.Level.INFO, Path.Log.thisModule())

debug = False
if debug:
    Path.Log.setLevel(Path.Log.Level.DEBUG, Path.Log.thisModule())
    Path.Log.trackModule(Path.Log.thisModule())
else:
    Path.Log.setLevel(Path.Log.Level.INFO, Path.Log.thisModule())



class _HeaderBuilder:
    """Builder class for constructing G-code header with structured data storage."""

    def __init__(self):
        """Initialize the header builder with empty data structures."""
        self._exporter = None
        self._machine = None
        self._post_processor = None
        self._cam_file = None
        self._author = None
        self._output_time = None
        self._tools = []  # List of (tool_number, tool_name) tuples
        self._fixtures = []  # List of fixture names
        self._notes = []  # list of notes

    def add_exporter_info(self, exporter: str = "FreeCAD"):
        """Add exporter information to the header."""
        self._exporter = exporter

    def add_machine_info(self, machine: str):
        """Add machine information to the header."""
        self._machine = machine

    def add_post_processor(self, name: str):
        """Add post processor name to the header."""
        self._post_processor = name

    def add_cam_file(self, filename: str):
        """Add CAM file information to the header."""
        self._cam_file = filename

    def add_author(self, author: str):
        """Add author information to the header."""
        self._author = author

    def add_output_time(self, timestamp: str):
        """Add output timestamp to the header."""
        self._output_time = timestamp

    def add_tool(self, tool_number: int, tool_name: str):
        """Add a tool to the header."""
        self._tools.append((tool_number, tool_name))

    def add_fixture(self, fixture_name: str):
        """Add a fixture to the header."""
        self._fixtures.append(fixture_name)

    def add_note(self, note: str):
        """Add a note to the header."""
        self._notes.append(note)

    @property
    def Path(self) -> Path.Path:
        """Return a Path.Path containing Path.Commands as G-code comments for the header."""
        commands = []

        # Add exporter info
        if self._exporter:
            commands.append(Path.Command(f"(Exported by {self._exporter})"))

        # Add machine info
        if self._machine:
            commands.append(Path.Command(f"(Machine: {self._machine})"))

        # Add post processor info
        if self._post_processor:
            commands.append(Path.Command(f"(Post Processor: {self._post_processor})"))

        # Add CAM file info
        if self._cam_file:
            commands.append(Path.Command(f"(Cam File: {self._cam_file})"))

        # Add author info
        if self._author:
            commands.append(Path.Command(f"(Author: {self._author})"))

        # Add output time
        if self._output_time:
            commands.append(Path.Command(f"(Output Time: {self._output_time})"))

        # Add tools
        for tool_number, tool_name in self._tools:
            commands.append(Path.Command(f"(T{tool_number}={tool_name})"))

        # Add fixtures (if needed in header)
        for fixture in self._fixtures:
            commands.append(Path.Command(f"(Fixture: {fixture})"))

        # Add notes
        for note in self._notes:
            commands.append(Path.Command(f"(Note: {note})"))

        return Path.Path(commands)

#
# Define some types that are used throughout this file.
#
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
    return PostList.needsTcOp(oldTc, newTc)


class PostProcessor:
    """Base Class.  All non-legacy postprocessors should inherit from this class."""

    def __init__(self, job_or_jobs, tooltip, tooltipargs, units, *args, **kwargs):
        self._tooltip = tooltip
        self._tooltipargs = tooltipargs
        self._units = units
        self._args = args
        self._kwargs = kwargs

        # Handle job_or_jobs: can be single job or list of jobs
        if isinstance(job_or_jobs, list):
            self._jobs = job_or_jobs
            if len(self._jobs) == 0:
                raise ValueError("At least one job must be provided")
            # Validate all jobs have the same machine
            machine_name = self._jobs[0].Machine
            for job in self._jobs[1:]:
                if job.Machine != machine_name:
                    raise ValueError("All jobs must have the same machine")
            # For now, only single job supported
            if len(self._jobs) > 1:
                raise NotImplementedError("Multiple jobs are not yet supported. Please process one job at a time.")
            self._job = self._jobs[0]  # For backward compatibility
        else:
            self._jobs = [job_or_jobs]
            self._job = job_or_jobs

        # Get machine
        if self._job is None:
            self._machine = None
        else:
            machine = MachineFactory.get_machine(self._job.Machine)
            if machine is None:
                raise ValueError(f"Machine '{self._job.Machine}' not found")
            self._machine = machine
        self._modal_state = {
            'X': None, 'Y': None, 'Z': None,
            'A': None, 'B': None, 'C': None,
            'U': None, 'V': None, 'W': None,
            'F': None, 'S': None
        }
        self.reinitialize()

        if isinstance(job_or_jobs, dict):
            # process only selected operations
            self._job = job_or_jobs["job"]
            self._operations = job_or_jobs["operations"]
        else:
            # get all operations from 'Operations' group
            self._operations = getattr(self._job.Operations, "Group", []) if self._job is not None else []

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

    def _buildPostList(self, early_tool_prep=False):
        """Determine the specific objects and order to postprocess.

        Args:
            early_tool_prep: If True, split tool changes into separate prep (Tn)
                           and change (M6) commands for better machine efficiency

        Returns:
            List of (name, operations) tuples
        """
        return PostList.buildPostList(self, early_tool_prep)

    def export2(self) -> Union[None, GCodeSections]:
        """
        Process jobs through all postprocessing stages to produce final G-code.
        
        Assumes Stage 0 (Configuration) is complete.
        
        Stages:
        1. Ordering - Build ordered list of postables
        2. Command Expansion - Canned cycles, arc splitting
        3. Command Conversion - Convert Path.Commands to G-code strings
        4. G-code Optimization - Deduplication, line numbering
        5. Output Production - Assemble final structure
        """
        from Path.Op.Drilling import ObjectDrilling
        from Path.Post.GcodeProcessingUtils import (
            deduplicate_repeated_commands,
            suppress_redundant_axes_words,
            filter_inefficient_moves,
            insert_line_numbers,
        )
        
        # Merge machine configuration into values dict
        if self._machine and hasattr(self._machine, 'output'):
            # Map machine config to values dict keys
            output_options = self._machine.output
            if hasattr(output_options, 'line_numbers'):
                self.values['OUTPUT_LINE_NUMBERS'] = output_options.line_numbers
            if hasattr(output_options, 'line_number_start'):
                self.values['line_number'] = output_options.line_number_start
            if hasattr(output_options, 'line_increment'):
                self.values['LINE_INCREMENT'] = output_options.line_increment
            # Support both old and new field names for backward compatibility
            if hasattr(output_options, 'output_comments'):
                self.values['OUTPUT_COMMENTS'] = output_options.output_comments
            elif hasattr(output_options, 'comments'):
                self.values['OUTPUT_COMMENTS'] = output_options.comments
            if hasattr(output_options, 'output_header'):
                self.values['OUTPUT_HEADER'] = output_options.output_header
            elif hasattr(output_options, 'header'):
                self.values['OUTPUT_HEADER'] = output_options.header
            if hasattr(output_options, 'axis_precision'):
                self.values['AXIS_PRECISION'] = output_options.axis_precision
            if hasattr(output_options, 'feed_precision'):
                self.values['FEED_PRECISION'] = output_options.feed_precision
            if hasattr(output_options, 'spindle_precision'):
                self.values['SPINDLE_DECIMALS'] = output_options.spindle_precision
            elif hasattr(output_options, 'spindle_decimals'):
                self.values['SPINDLE_DECIMALS'] = output_options.spindle_decimals
            if hasattr(output_options, 'comment_symbol'):
                self.values['COMMENT_SYMBOL'] = output_options.comment_symbol
            if hasattr(output_options, 'filter_double_parameters'):
                self.values['OUTPUT_DOUBLES'] = output_options.filter_double_parameters
            elif hasattr(output_options, 'output_double_parameters'):
                self.values['OUTPUT_DOUBLES'] = output_options.output_double_parameters
        
        # ===== STAGE 1: ORDERING =====
        # Process all jobs (currently only first job supported)
        all_job_sections = []
        
        for job in self._jobs:
            # Build ordered postables for this job
            postables = self._buildPostList(job)
            
            # ===== STAGE 2: COMMAND EXPANSION =====
            # Expand commands and collect header information
            gcodeheader = _HeaderBuilder()
            if self.values.get('OUTPUT_HEADER', True):
                if self._machine:
                    gcodeheader.add_machine_info(self._machine.name if hasattr(self._machine, 'name') else str(self._machine))
            
            # Process each section's postables
            for section_name, sublist in postables:
                for item in sublist:
                    # Canned cycle termination and expansion
                    if hasattr(item, 'Proxy') and isinstance(item.Proxy, ObjectDrilling):
                        item.Path = PostUtils.cannedCycleTerminator(item.Path)
                        
                        if self._machine and hasattr(self._machine, 'processing') and self._machine.processing.translate_drill_cycles:
                            item.Path = DrillCycleExpander.expand_commands(item)
                    
                    # Arc splitting
                    if hasattr(item, 'Path') and item.Path:
                        if self._machine and hasattr(self._machine, 'processing') and self._machine.processing.split_arcs:
                            item.Path = PostUtils.splitArcs(item.Path)
                    
                    # Collect header information
                    if self.values.get('OUTPUT_HEADER', True):
                        if hasattr(item, 'ToolNumber'):  # Tool controller
                            gcodeheader.add_tool(item.ToolNumber, item.Label)
                        elif hasattr(item, 'Label') and item.Label == "Fixture":  # Fixture
                            if hasattr(item, 'Path') and item.Path and item.Path.Commands:
                                fixture_name = item.Path.Commands[0].Name
                                gcodeheader.add_fixture(fixture_name)
            
            # ===== STAGE 3: COMMAND CONVERSION =====
            job_sections = []
            
            # Collect HEADER lines (comment-only) - controlled by OUTPUT_HEADER
            header_lines = []
            if self.values.get('OUTPUT_HEADER', True):
                header_commands = gcodeheader.Path.Commands if hasattr(gcodeheader, 'Path') else []
                comment_symbol = self.values.get('COMMENT_SYMBOL', '(')
                for cmd in header_commands:
                    if cmd.Name.startswith("("):
                        comment_text = cmd.Name[1:-1] if cmd.Name.startswith("(") and cmd.Name.endswith(")") else cmd.Name[1:]
                        if comment_symbol == '(':
                            header_lines.append(f"({comment_text})")
                        else:
                            header_lines.append(f"{comment_symbol} {comment_text}")
            
            # Collect PREAMBLE lines
            preamble_lines = []
            if self._machine and hasattr(self._machine, 'blocks') and self._machine.blocks.preamble:
                preamble_lines = [line for line in self._machine.blocks.preamble.split('\n') if line.strip()]
            
            # Collect PRE-JOB lines
            pre_job_lines = []
            if self._machine and hasattr(self._machine, 'blocks') and self._machine.blocks.pre_job:
                pre_job_lines = [line for line in self._machine.blocks.pre_job.split('\n') if line.strip()]
            
            # Process each section (BODY)
            for section_name, sublist in postables:
                gcode_lines = []
                
                # Add header, preamble, and pre-job lines only to first section
                if section_name == postables[0][0]:
                    # Header comments first (no line numbers)
                    gcode_lines.extend(header_lines)
                    # Then preamble
                    gcode_lines.extend(preamble_lines)
                    # Then pre-job
                    gcode_lines.extend(pre_job_lines)
                
                for item in sublist:
                    # Determine item type and add appropriate pre-blocks
                    if hasattr(item, 'ToolNumber'):  # TOOLCHANGE
                        if self._machine and hasattr(self._machine, 'blocks') and self._machine.blocks.pre_tool_change:
                            pre_lines = [line for line in self._machine.blocks.pre_tool_change.split('\n') if line.strip()]
                            gcode_lines.extend(pre_lines)
                    elif hasattr(item, 'Label') and item.Label == "Fixture":  # FIXTURE
                        if self._machine and hasattr(self._machine, 'blocks') and self._machine.blocks.pre_fixture_change:
                            pre_lines = [line for line in self._machine.blocks.pre_fixture_change.split('\n') if line.strip()]
                            gcode_lines.extend(pre_lines)
                    elif hasattr(item, 'Proxy'):  # OPERATION
                        if self._machine and hasattr(self._machine, 'blocks') and self._machine.blocks.pre_operation:
                            pre_lines = [line for line in self._machine.blocks.pre_operation.split('\n') if line.strip()]
                            gcode_lines.extend(pre_lines)
                    
                    # Convert Path commands to G-code
                    if hasattr(item, 'Path') and item.Path:
                        # Group consecutive rotary moves together
                        in_rotary_group = False
                        
                        for cmd in item.Path.Commands:
                            try:
                                # Check if this command involves a rotary axis move
                                has_rotary = any(param in cmd.Parameters for param in ['A', 'B', 'C'])
                                
                                # Start a new rotary group if needed
                                if has_rotary and not in_rotary_group:
                                    if self._machine and hasattr(self._machine, 'blocks') and self._machine.blocks.pre_rotary_move:
                                        pre_rotary_lines = [line for line in self._machine.blocks.pre_rotary_move.split('\n') if line.strip()]
                                        gcode_lines.extend(pre_rotary_lines)
                                    in_rotary_group = True
                                
                                # End rotary group if we're leaving rotary moves
                                elif not has_rotary and in_rotary_group:
                                    if self._machine and hasattr(self._machine, 'blocks') and self._machine.blocks.post_rotary_move:
                                        post_rotary_lines = [line for line in self._machine.blocks.post_rotary_move.split('\n') if line.strip()]
                                        gcode_lines.extend(post_rotary_lines)
                                    in_rotary_group = False
                                
                                gcode = self.convert_command_to_gcode(cmd)
                                if gcode is not None and gcode.strip():
                                    gcode_lines.append(gcode)
                                
                            except (ValueError, AttributeError) as e:
                                # Skip unsupported commands or log error
                                Path.Log.debug(f"Skipping command {cmd.Name}: {e}")
                        
                        # Close rotary group if we ended while still in one
                        if in_rotary_group:
                            if self._machine and hasattr(self._machine, 'blocks') and self._machine.blocks.post_rotary_move:
                                post_rotary_lines = [line for line in self._machine.blocks.post_rotary_move.split('\n') if line.strip()]
                                gcode_lines.extend(post_rotary_lines)
                    
                    # Add appropriate post-blocks
                    if hasattr(item, 'ToolNumber'):  # TOOLCHANGE
                        if self._machine and hasattr(self._machine, 'blocks') and self._machine.blocks.post_tool_change:
                            post_lines = [line for line in self._machine.blocks.post_tool_change.split('\n') if line.strip()]
                            gcode_lines.extend(post_lines)
                        # Add tool_return after tool change
                        if self._machine and hasattr(self._machine, 'blocks') and self._machine.blocks.tool_return:
                            return_lines = [line for line in self._machine.blocks.tool_return.split('\n') if line.strip()]
                            gcode_lines.extend(return_lines)
                    elif hasattr(item, 'Label') and item.Label == "Fixture":  # FIXTURE
                        if self._machine and hasattr(self._machine, 'blocks') and self._machine.blocks.post_fixture_change:
                            post_lines = [line for line in self._machine.blocks.post_fixture_change.split('\n') if line.strip()]
                            gcode_lines.extend(post_lines)
                    elif hasattr(item, 'Proxy'):  # OPERATION
                        if self._machine and hasattr(self._machine, 'blocks') and self._machine.blocks.post_operation:
                            post_lines = [line for line in self._machine.blocks.post_operation.split('\n') if line.strip()]
                            gcode_lines.extend(post_lines)
                
                # ===== STAGE 4: G-CODE OPTIMIZATION =====
                if gcode_lines:
                    # Separate header comments from numbered lines
                    num_header_lines = len(header_lines) if section_name == postables[0][0] else 0
                    header_part = gcode_lines[:num_header_lines]
                    body_part = gcode_lines[num_header_lines:]
                    
                    # Apply optimizations to body only (not header comments)
                    if body_part and self._machine and hasattr(self._machine, 'output'):
                        # Modal command deduplication
                        if self._machine.output.filter_double_commands:
                            body_part = deduplicate_repeated_commands(body_part)
                        
                        # Suppress redundant axis words
                        body_part = suppress_redundant_axes_words(body_part)
                        
                        # Filter inefficient moves
                        body_part = filter_inefficient_moves(body_part)
                    
                    # Line numbering (only on body, not header comments)
                    if body_part and self.values.get('OUTPUT_LINE_NUMBERS', False):
                        start = 10
                        increment = 10
                        if self._machine and hasattr(self._machine, 'output'):
                            start = self._machine.output.line_number_start
                            increment = self._machine.output.line_increment
                        body_part = insert_line_numbers(body_part, start=start, increment=increment)
                    
                    # Recombine header and body
                    final_lines = header_part + body_part
                    
                    # Add section to output
                    job_sections.append((section_name, "\n".join(final_lines)))
            
            # Add POST-JOB block
            if self._machine and hasattr(self._machine, 'blocks') and self._machine.blocks.post_job:
                post_job_lines = [line for line in self._machine.blocks.post_job.split('\n') if line.strip()]
                if post_job_lines:
                    job_sections.append(("post_job", "\n".join(post_job_lines)))
            
            # Add POSTAMBLE section
            if self._machine and hasattr(self._machine, 'blocks') and self._machine.blocks.postamble:
                postamble_lines = [line for line in self._machine.blocks.postamble.split('\n') if line.strip()]
                if postamble_lines:
                    job_sections.append(("postamble", "\n".join(postamble_lines)))
            
            # Add FOOTER section (comment-only)
            # TODO: Add footer generation if needed
            
            all_job_sections.extend(job_sections)
        
        # ===== STAGE 5: OUTPUT PRODUCTION =====
        # Return sections (file writing happens elsewhere)
        
        # Add safetyblock at the very beginning if present
        if self._machine and hasattr(self._machine, 'blocks') and self._machine.blocks.safetyblock:
            safety_lines = [line for line in self._machine.blocks.safetyblock.split('\n') if line.strip()]
            if safety_lines:
                all_job_sections.insert(0, ("safetyblock", "\n".join(safety_lines)))
        
        return all_job_sections 
        

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

    def init_values(self, values: Values) -> None:
        """Initialize values that are used throughout the postprocessor."""
        #
        PostUtilsArguments.init_shared_values(values)
        #
        # Set any values here that need to override the default values set
        # in the init_shared_values routine.
        #
        values["UNITS"] = self._units

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
            # Update any variables that might have been modified while processing the arguments.
            #
            self._units = self.values["UNITS"]
        #
        # If the flag is False, then args is either None (indicating an error while
        # processing the arguments) or a string containing the argument list formatted
        # for output.  Either way the calling routine will need to handle the args value.
        #
        return (flag, args)

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

        # Process canned cycles for drilling operations
        for _, section in enumerate(postables):
            _, sublist = section
            for obj in sublist:
                if hasattr(obj, "Path"):
                    obj.Path = PostUtils.cannedCycleTerminator(obj.Path)

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
        self.values: Values = {}
        self.init_values(self.values)
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


    def convert_command_to_gcode(self, command: Path.Command) -> str:
        """
        Converts a single-line commands to gcode.
        Specifically, this method considers 
          - the command name,
          - units,
          - required precision

        The method looks for the blockdelete annotation and adds the leading slash if necessary.
        The method evaluates commments and looks for the bCNC annotation to process them.
        For highly unusual postprocessors this method may be overridden.

        This method handles the following commmands
          - Comments (Message)
          - G0/G00 Rapid moves
          - G1/G01 Feed Moves
          - G2/G02/G3/G03 arc moves
          - G73, G74, G81, G82, G83, G84, G38.2
        """
        from Path.Post.UtilsParse import (
            linenumber,
            format_command_line,
            create_comment,
        )

        # reject unhandled commands
        supported_commands = ["G0", "G00", "G1", "G01", "G2", "G02", "G3", "G03", "G73", "G74", "G81", "G82", "G83", "G84", "G38.2"]
        if command.Name not in supported_commands and not command.Name.startswith("("):
            raise ValueError(f"Unsupported command: {command.Name}")

        # Extract command name and parameters
        command_name = command.Name
        params = command.Parameters
        annotations = command.Annotations

        # skip suppressed commands        
        if self._machine and hasattr(self._machine, 'OutputOptions') and self._machine.OutputOptions.suppress_commands:
            if command_name in self._machine.OutputOptions.suppress_commands:
                return None

        # handle comments
        if command_name.startswith("("):  # comment
            if self.values.get('OUTPUT_BCNC', False) and annotations.get("bcnc"):
                # For now, treat bCNC comments as regular comments
                # TODO: Implement proper bCNC block formatting when available
                if self.values.get('OUTPUT_COMMENTS', True):
                    # Format comment according to comment_symbol
                    comment_text = command_name[1:-1] if command_name.startswith("(") and command_name.endswith(")") else command_name[1:]
                    comment_symbol = self.values.get('COMMENT_SYMBOL', '(')
                    if comment_symbol == '(':
                        return f"({comment_text})"
                    else:
                        return f"{comment_symbol} {comment_text}"
                return None
            else:
                if self.values.get('OUTPUT_COMMENTS', True):
                    # Format comment according to comment_symbol
                    comment_text = command_name[1:-1] if command_name.startswith("(") and command_name.endswith(")") else command_name[1:]
                    comment_symbol = self.values.get('COMMENT_SYMBOL', '(')
                    if comment_symbol == '(':
                        return f"({comment_text})"
                    else:
                        return f"{comment_symbol} {comment_text}"
                return None
        
        # Check for blockdelete annotation
        block_delete_string = "/" if annotations.get("blockdelete") else "" 
        
        # Filter and prepare command (simple version)
        filtered_command = command_name
        should_skip = False
        if should_skip:
            return ""
        
        # Build command line
        command_line: CommandLine = []
        command_line.append(filtered_command)
        
        # Format parameters with clean, stateless implementation
        parameter_order = self.values.get('PARAMETER_ORDER', ['X', 'Y', 'Z', 'F', 'I', 'J', 'K', 'R', 'Q', 'P'])
        
        def format_axis_param(value):
            """Format axis parameter with unit conversion and precision."""
            # Apply unit conversion if needed
            units = self.values.get('UNITS', 'G21')
            if units == 'G20':  # Imperial units
                converted_value = value / 25.4  # Convert mm to inches
            else:  # G21 or default - metric units
                converted_value = value  # Keep as mm
            
            precision = self.values.get('AXIS_PRECISION', 3)
            return f"{converted_value:.{precision}f}"
        
        def format_feed_param(value):
            """Format feed parameter with speed precision."""
            # Convert from mm/sec to mm/min (multiply by 60)
            feed_value = value * 60.0
            precision = self.values.get('FEED_PRECISION', 3)
            return f"{feed_value:.{precision}f}"
        
        def format_spindle_param(value):
            """Format spindle parameter with spindle decimals."""
            decimals = self.values.get('SPINDLE_DECIMALS', 0)
            return f"{value:.{decimals}f}"
        
        def format_int_param(value):
            """Format integer parameter."""
            return str(int(value))
        
        # Parameter type mappings
        param_formatters = {
            # Axis parameters
            'X': format_axis_param, 'Y': format_axis_param, 'Z': format_axis_param,
            'U': format_axis_param, 'V': format_axis_param, 'W': format_axis_param,
            'A': format_axis_param, 'B': format_axis_param, 'C': format_axis_param,
            # Arc parameters
            'I': format_axis_param, 'J': format_axis_param, 'K': format_axis_param,
            'R': format_axis_param, 'Q': format_axis_param,
            # Feed and spindle
            'F': format_feed_param, 'S': format_spindle_param,
            # Integer parameters
            'D': format_int_param, 'H': format_int_param, 'L': format_int_param,
            'T': format_int_param, 'P': format_int_param,
        }
        
        for parameter in parameter_order:
            if parameter in params:
                # Check if we should suppress duplicate parameters
                if not self.values.get('OUTPUT_DOUBLES', False):  # Changed default value to False
                    # Suppress parameters that haven't changed
                    current_value = params[parameter]
                    if parameter in self._modal_state and self._modal_state[parameter] == current_value:
                        continue  # Skip this parameter
                
                if parameter in param_formatters:
                    formatted_value = param_formatters[parameter](params[parameter])
                    command_line.append(f"{parameter}{formatted_value}")
                    # Update modal state
                    self._modal_state[parameter] = params[parameter]
                else:
                    # Default formatting for unhandled parameters
                    command_line.append(f"{parameter}{params[parameter]}")
                    # Update modal state for unhandled parameters too
                    self._modal_state[parameter] = params[parameter]
        
        # Format the command line
        formatted_line = format_command_line(self.values, command_line)
        
        # Combine block delete and formatted command (no line numbers)
        gcode_string = f"{block_delete_string}{formatted_line}"
        
        return gcode_string


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
