# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *   Copyright (c) 2025 FreeCAD CAM development team                       *
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
State accessor functions for postprocessor configuration.

This module provides helper functions to access postprocessor state properties
in a type-safe way that works with both the legacy dict format and the modern
PostProcessorState dataclass format.

The goal is to eliminate the overhead of converting between formats while
maintaining backward compatibility during the transition period.
"""

from typing import Any, Callable, Dict, List, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from Path.Post.Processor import PostProcessorState

# State can be either dict or typed state
State = Union[Dict[str, Any], "PostProcessorState"]


# =============================================================================
# Output Options Accessors
# =============================================================================

def get_output_comments(state: State) -> bool:
    """Get whether to output comments."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.output.comments
    return state.get("OUTPUT_COMMENTS", True)


def get_output_blank_lines(state: State) -> bool:
    """Get whether to output blank lines."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.output.blank_lines
    return state.get("OUTPUT_BLANK_LINES", True)


def get_output_header(state: State) -> bool:
    """Get whether to output header."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.output.header
    return state.get("OUTPUT_HEADER", True)


def get_output_line_numbers(state: State) -> bool:
    """Get whether to output line numbers."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.output.line_numbers
    return state.get("OUTPUT_LINE_NUMBERS", False)


def get_output_bcnc(state: State) -> bool:
    """Get whether to output BCNC blocks."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.output.bcnc_blocks
    return state.get("OUTPUT_BCNC", False)


def get_output_path_labels(state: State) -> bool:
    """Get whether to output path labels."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.output.path_labels
    return state.get("OUTPUT_PATH_LABELS", False)


def get_output_machine_name(state: State) -> bool:
    """Get whether to output machine name."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.output.machine_name
    return state.get("OUTPUT_MACHINE_NAME", False)


def get_output_tool_change(state: State) -> bool:
    """Get whether to output tool change commands."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.output.tool_change
    return state.get("OUTPUT_TOOL_CHANGE", True)


def get_output_doubles(state: State) -> bool:
    """Get whether to output duplicate axis values."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.output.doubles
    return state.get("OUTPUT_DOUBLES", True)


def get_output_adaptive(state: State) -> bool:
    """Get whether to handle adaptive operations specially."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.output.adaptive
    return state.get("OUTPUT_ADAPTIVE", False)


# =============================================================================
# Precision Settings Accessors
# =============================================================================

def get_axis_precision(state: State) -> int:
    """Get axis precision (decimal places)."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.precision.axis_precision
    return state.get("AXIS_PRECISION", 3)


def get_feed_precision(state: State) -> int:
    """Get feed rate precision (decimal places)."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.precision.feed_precision
    return state.get("FEED_PRECISION", 3)


def get_spindle_decimals(state: State) -> int:
    """Get spindle speed precision (decimal places)."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.precision.spindle_decimals
    return state.get("SPINDLE_DECIMALS", 0)


# =============================================================================
# Formatting Accessors
# =============================================================================

def get_command_space(state: State) -> str:
    """Get command space separator."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.formatting.command_space
    return state.get("COMMAND_SPACE", " ")


def get_comment_symbol(state: State) -> str:
    """Get comment symbol."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.formatting.comment_symbol
    return state.get("COMMENT_SYMBOL", "(")


def get_line_increment(state: State) -> int:
    """Get line number increment."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.formatting.line_increment
    return state.get("LINE_INCREMENT", 10)


def get_current_line_number(state: State) -> int:
    """Get current line number."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.formatting.current_line_number
    return state.get("line_number", 100)


def get_end_of_line_chars(state: State) -> str:
    """Get end of line characters."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.formatting.end_of_line_chars
    return state.get("END_OF_LINE_CHARACTERS", "\n")


# =============================================================================
# Machine Settings Accessors
# =============================================================================

def get_machine_name(state: State) -> str:
    """Get machine name."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.machine.name
    return state.get("MACHINE_NAME", "unknown machine")


def get_units(state: State) -> str:
    """Get units (G21 or G20)."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.machine.units.value
    return state.get("UNITS", "G21")


def get_unit_format(state: State) -> str:
    """Get unit format string (mm or in)."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.unit_format
    return state.get("UNIT_FORMAT", "mm")


def get_unit_speed_format(state: State) -> str:
    """Get unit speed format string (mm/min or in/min)."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.unit_speed_format
    return state.get("UNIT_SPEED_FORMAT", "mm/min")


def get_motion_mode(state: State) -> str:
    """Get motion mode (G90 or G91)."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.machine.motion_mode.value
    return state.get("MOTION_MODE", "G90")


def get_use_tlo(state: State) -> bool:
    """Get whether to use tool length offset."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.machine.use_tlo
    return state.get("USE_TLO", True)


def get_stop_spindle_for_tool_change(state: State) -> bool:
    """Get whether to stop spindle for tool change."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.machine.stop_spindle_for_tool_change
    return state.get("STOP_SPINDLE_FOR_TOOL_CHANGE", True)


def get_enable_coolant(state: State) -> bool:
    """Get whether coolant is enabled."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.machine.enable_coolant
    return state.get("ENABLE_COOLANT", False)


def get_enable_machine_specific_commands(state: State) -> bool:
    """Get whether machine-specific commands are enabled."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.machine.enable_machine_specific_commands
    return state.get("ENABLE_MACHINE_SPECIFIC_COMMANDS", False)


# =============================================================================
# G-code Blocks Accessors
# =============================================================================

def get_preamble(state: State) -> str:
    """Get preamble block."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.blocks.preamble
    return state.get("PREAMBLE", "")


def get_postamble(state: State) -> str:
    """Get postamble block."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.blocks.postamble
    return state.get("POSTAMBLE", "")


def get_safetyblock(state: State) -> str:
    """Get safety block."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.blocks.safetyblock
    return state.get("SAFETYBLOCK", "")


def get_pre_operation(state: State) -> str:
    """Get pre-operation block."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.blocks.pre_operation
    return state.get("PRE_OPERATION", "")


def get_post_operation(state: State) -> str:
    """Get post-operation block."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.blocks.post_operation
    return state.get("POST_OPERATION", "")


def get_tool_change(state: State) -> str:
    """Get tool change block."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.blocks.pre_tool_change
    return state.get("TOOL_CHANGE", "")


def get_toolreturn(state: State) -> str:
    """Get tool return block."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.blocks.tool_return
    return state.get("TOOLRETURN", "")


def get_tool_change_block(state: State) -> str:
    """Get tool change block."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.blocks.pre_tool_change if hasattr(state.blocks, 'pre_tool_change') else ""
    return state.get("TOOL_CHANGE", "")


def get_finish_label(state: State) -> str:
    """Get finish label."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.blocks.finish_label
    return state.get("FINISH_LABEL", "Finish")


# =============================================================================
# Processing Options Accessors
# =============================================================================

def get_modal(state: State) -> bool:
    """Get whether modal command suppression is enabled."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.processing.modal
    return state.get("MODAL", False)


def get_translate_drill_cycles(state: State) -> bool:
    """Get whether to translate drill cycles."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.processing.translate_drill_cycles
    return state.get("TRANSLATE_DRILL_CYCLES", False)


def get_split_arcs(state: State) -> bool:
    """Get whether to split arcs."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.processing.split_arcs
    return state.get("SPLIT_ARCS", False)


def get_show_editor(state: State) -> bool:
    """Get whether to show editor."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.processing.show_editor
    return state.get("SHOW_EDITOR", True)


def get_list_tools_in_preamble(state: State) -> bool:
    """Get whether to list tools in preamble."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.processing.list_tools_in_preamble
    return state.get("LIST_TOOLS_IN_PREAMBLE", False)


def get_show_machine_units(state: State) -> bool:
    """Get whether to show machine units."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.processing.show_machine_units
    return state.get("SHOW_MACHINE_UNITS", True)


def get_show_operation_labels(state: State) -> bool:
    """Get whether to show operation labels."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.processing.show_operation_labels
    return state.get("SHOW_OPERATION_LABELS", True)


def get_suppress_commands(state: State) -> List[str]:
    """Get list of commands to suppress."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.processing.suppress_commands
    return state.get("SUPPRESS_COMMANDS", [])


def get_drill_cycles_to_translate(state: State) -> List[str]:
    """Get list of drill cycles to translate."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.processing.drill_cycles_to_translate
    return state.get("DRILL_CYCLES_TO_TRANSLATE", ["G73", "G81", "G82", "G83"])


def get_chipbreaking_amount(state: State) -> float:
    """Get chipbreaking amount."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.processing.chipbreaking_amount
    return state.get("CHIPBREAKING_AMOUNT", 0.25)


def get_spindle_wait(state: State) -> float:
    """Get spindle wait time."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.processing.spindle_wait
    return state.get("SPINDLE_WAIT", 0.0)


# =============================================================================
# Dynamic State Accessors
# =============================================================================

def get_postprocessor_file_name(state: State) -> str:
    """Get postprocessor file name."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.postprocessor_file_name
    return state.get("POSTPROCESSOR_FILE_NAME", "")


def get_parameter_functions(state: State) -> Dict[str, Callable]:
    """Get parameter functions dict."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.parameter_functions
    return state.get("PARAMETER_FUNCTIONS", {})


def get_parameter_order(state: State) -> List[str]:
    """Get parameter order list."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.parameter_order
    return state.get("PARAMETER_ORDER", [
        "D", "H", "L", "X", "Y", "Z", "A", "B", "C",
        "U", "V", "W", "I", "J", "K", "R", "P", "E", "Q", "F", "S", "T"
    ])


def get_motion_commands(state: State) -> List[str]:
    """Get list of motion commands."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.motion_commands
    return state.get("MOTION_COMMANDS", [])


def get_return_to(state: State):
    """Get return to coordinates (tuple/list of [x, y, z] or None)."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        # RETURN_TO is stored in processing options but may not exist
        return getattr(state.processing, 'return_to', None)
    return state.get("RETURN_TO")


def get_rapid_moves(state: State) -> List[str]:
    """Get list of rapid move commands."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        return state.rapid_moves
    return state.get("RAPID_MOVES", [])


# =============================================================================
# Mutable State Setters (for dict only - to be refactored)
# =============================================================================

def set_motion_mode(state: State, mode: str) -> None:
    """Set motion mode (only works with dict state)."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        # For typed state, this should be handled differently
        # For now, we'll raise an error to catch usage
        raise TypeError("Cannot mutate PostProcessorState - use dict for mutable state")
    state["MOTION_MODE"] = mode


def set_units(state: State, units: str) -> None:
    """Set units (only works with dict state)."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        raise TypeError("Cannot mutate PostProcessorState - use dict for mutable state")
    state["UNITS"] = units


def set_unit_format(state: State, unit_format: str) -> None:
    """Set unit format (only works with dict state)."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        raise TypeError("Cannot mutate PostProcessorState - use dict for mutable state")
    state["UNIT_FORMAT"] = unit_format


def set_unit_speed_format(state: State, unit_speed_format: str) -> None:
    """Set unit speed format (only works with dict state)."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        raise TypeError("Cannot mutate PostProcessorState - use dict for mutable state")
    state["UNIT_SPEED_FORMAT"] = unit_speed_format


def increment_line_number(state: State) -> None:
    """Increment line number (only works with dict state)."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        # Use the built-in method
        state.formatting.next_line_number()
    else:
        state["line_number"] += state.get("LINE_INCREMENT", 10)


def append_suppress_command(state: State, command: str) -> None:
    """Append to suppress commands list (only works with dict state)."""
    from Path.Post.Processor import PostProcessorState
    if isinstance(state, PostProcessorState):
        raise TypeError("Cannot mutate PostProcessorState - use dict for mutable state")
    if "SUPPRESS_COMMANDS" not in state:
        state["SUPPRESS_COMMANDS"] = []
    state["SUPPRESS_COMMANDS"].append(command)
