# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *   Copyright (c) 2014 Yorik van Havre <yorik@uncreated.net>              *
# *   Copyright (c) 2014 sliptonic <shopinthewoods@gmail.com>               *
# *   Copyright (c) 2015 Dan Falck <ddfalck@gmail.com>                      *
# *   Copyright (c) 2018, 2019 Gauthier Briere                              *
# *   Copyright (c) 2019, 2020 Schildkroet                                  *
# *   Copyright (c) 2022 Larry Woestman <LarryWoestman2@gmail.com>          *
# *   Copyright (c) 2024 Carl Slater <CandLWorkshopLLC@gmail.com>           *
# *                                                                         *
# *   This file is part of the FreeCAD CAx development system.              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful,            *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Lesser General Public License for more details.                   *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with FreeCAD; if not, write to the Free Software        *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

import math
import re
from typing import Any, Callable, Dict, List, Tuple, Union, TYPE_CHECKING

import FreeCAD
from FreeCAD import Units

import Path
import Path.Geom as PathGeom
import Path.Post.Utils as PostUtils
import Path.Post.StateAccessors as SA

# Define some types that are used throughout this file
CommandLine = List[str]
Gcode = List[str]
PathParameter = float
PathParameters = Dict[str, PathParameter]
Values = Dict[str, Any]

# Forward declaration for type checking to avoid circular imports
if TYPE_CHECKING:
    from Path.Post.Processor import MachineConfiguration

# State type alias - can be either dict or typed state
State = Union[Values, "MachineConfiguration"]

ParameterFunction = Callable[[State, str, str, PathParameter, PathParameters], str]


def check_for_an_adaptive_op(
    values: State,
    command: str,
    command_line: CommandLine,
    adaptive_op_variables: Tuple[bool, float, float],
) -> str:
    """Check to see if the current command is an adaptive op."""
    adaptiveOp: bool
    opHorizRapid: float
    opVertRapid: float

    (adaptiveOp, opHorizRapid, opVertRapid) = adaptive_op_variables
    if SA.get_output_adaptive(values) and adaptiveOp and command in SA.get_rapid_moves(values):
        if opHorizRapid and opVertRapid:
            return "G1"
        command_line.append(f"(Tool Controller Rapid Values are unset)")
    return ""


def check_for_drill_translate(
    values: Values,
    gcode: Gcode,
    command: str,
    command_line: CommandLine,
    params: PathParameters,
    motion_location: PathParameters,
    drill_retract_mode: str,
) -> bool:
    """Check for drill commands to translate."""
    comment: str

    if SA.get_translate_drill_cycles(values) and command in SA.get_drill_cycles_to_translate(values):
        if SA.get_output_comments(values):  # Comment the original command
            comment = create_comment(values, format_command_line(values, command_line))
            gcode.append(f"{linenumber(values)}{comment}")
        # wrap this block to ensure that the value of MOTION_MODE
        # is restored in case of error
        try:
            drill_translate(
                values,
                gcode,
                command,
                params,
                motion_location,
                drill_retract_mode,
            )
        except (ArithmeticError, LookupError) as err:
            print("exception occurred", err)
        # drill_translate uses G90 mode internally, so need to
        # switch back to G91 mode if it was that way originally
        if SA.get_motion_mode(values) == "G91":
            gcode.append(f"{linenumber(values)}G91")
        return True
    return False


def check_for_machine_specific_commands(values: State, gcode: Gcode, command: str) -> None:
    """Check for comments containing machine-specific commands."""
    m: object
    raw_command: str

    if SA.get_enable_machine_specific_commands(values):
        m = re.match(r"^\(MC_RUN_COMMAND: ([^)]+)\)$", command)
        if m:
            raw_command = m.group(1)
            # pass literally to the controller
            gcode.append(f"{linenumber(values)}{raw_command}")


def check_for_spindle_wait(
    values: Values, gcode: Gcode, command: str, command_line: CommandLine
) -> None:
    """Check for commands that might need a wait command after them."""
    cmd: str

    spindle_wait = SA.get_spindle_wait(values)
    if spindle_wait > 0 and command in ("M3", "M03", "M4", "M04"):
        gcode.append(f"{linenumber(values)}{format_command_line(values, command_line)}")
        cmd = format_command_line(values, ["G4", f'P{spindle_wait}'])
        gcode.append(f"{linenumber(values)}{cmd}")


def check_for_suppressed_commands(
    values: Values, gcode: Gcode, command: str, command_line: CommandLine
) -> bool:
    """Check for commands that will be suppressed."""
    comment: str

    if command in SA.get_suppress_commands(values):
        if SA.get_output_comments(values):
            # convert the command to a comment
            comment = create_comment(values, format_command_line(values, command_line))
            gcode.append(f"{linenumber(values)}{comment}")
        # remove the command
        return True
    return False


def check_for_tlo(values: State, gcode: Gcode, command: str, params: PathParameters) -> None:
    """Output a tool length command if USE_TLO is True."""
    if command in ("M6", "M06") and SA.get_use_tlo(values):
        cmd = format_command_line(values, ["G43", f'H{str(int(params["T"]))}'])
        gcode.append(f"{linenumber(values)}{cmd}")


def check_for_tool_change(
    values: Values, gcode: Gcode, command: str, command_line: CommandLine
) -> bool:
    """Check for a tool change."""

    if command in ("M6", "M06"):
        if not SA.get_output_tool_change(values):
            # Tool change output is disabled - convert to comment if comments enabled
            if SA.get_output_comments(values):
                # Output "Begin toolchange" comment
                comment = create_comment(values, "Begin toolchange")
                gcode.append(f"{linenumber(values)}{comment}")
                # Convert the M6 command to a comment
                comment = create_comment(values, format_command_line(values, command_line))
                gcode.append(f"{linenumber(values)}{comment}")
            return True
        # Tool change output is enabled
        if SA.get_output_comments(values):
            # Output "Begin toolchange" comment FIRST
            comment = create_comment(values, "Begin toolchange")
            gcode.append(f"{linenumber(values)}{comment}")
        if SA.get_stop_spindle_for_tool_change(values):
            # Then output M5 spindle stop
            gcode.append(f"{linenumber(values)}M5")
        # Output TOOL_CHANGE block commands BEFORE M6
        tool_change_block = SA.get_tool_change_block(values)
        if tool_change_block:
            for line in tool_change_block.splitlines(False):
                gcode.append(f"{linenumber(values)}{line}")
        # Don't suppress the command - let it be output normally
        return False
    return False


def create_comment(values: State, comment_string: str) -> str:
    """Create a comment from a string using the correct comment symbol."""
    comment_symbol = SA.get_comment_symbol(values)
    if comment_symbol == "(":
        return f"({comment_string})"
    return comment_symbol + comment_string


def default_axis_parameter(
    values: Values,
    command: str,  # pylint: disable=unused-argument
    param: str,
    param_value: PathParameter,
    parameters: PathParameters,  # pylint: disable=unused-argument
    current_location: PathParameters,
) -> str:
    """Process an axis parameter."""
    #
    # used to compare two floating point numbers for "close-enough equality"
    #
    epsilon: float = 0.00001

    if (
        not SA.get_output_doubles(values)
        and param in current_location
        and math.fabs(current_location[param] - param_value) < epsilon
    ):
        return ""
    return format_for_axis(values, Units.Quantity(param_value, Units.Length))


def default_D_parameter(
    values: Values,
    command: str,
    param: str,  # pylint: disable=unused-argument
    param_value: PathParameter,
    parameters: PathParameters,  # pylint: disable=unused-argument
    current_location: PathParameters,  # pylint: disable=unused-argument
) -> str:
    """Process the D parameter."""
    if command in ("G41", "G42"):
        return str(int(param_value))
    if command in ("G41.1", "G42.1"):
        return format_for_axis(values, Units.Quantity(param_value, Units.Length))
    if command in ("G96", "G97"):
        return format_for_spindle(values, param_value)
    # anything else that is supported
    return str(float(param_value))


def default_F_parameter(
    values: Values,
    command: str,
    param: str,
    param_value: PathParameter,
    parameters: PathParameters,
    current_location: PathParameters,
) -> str:
    """Process the F parameter."""
    #
    # used to compare two floating point numbers for "close-enough equality"
    #
    epsilon: float = 0.00001
    found: bool

    if (
        not SA.get_output_doubles(values)
        and param in current_location
        and math.fabs(current_location[param] - param_value) < epsilon
    ):
        return ""
    # Many posts don't use rapid speeds, but eventually
    # there will be refactored posts that do, so this
    # "if statement" is being kept separate to make it
    # more obvious where to put that check.
    if command in SA.get_rapid_moves(values):
        return ""
    feed = Units.Quantity(param_value, Units.Velocity)
    if feed.getValueAs(SA.get_unit_speed_format(values)) <= 0.0:
        return ""
    # if any of X, Y, Z, U, V, or W are in the parameters
    # and any of their values is different than where the device currently should be
    # then feed is in linear units
    found = False
    for key in ("X", "Y", "Z", "U", "V", "W"):
        if key in parameters and math.fabs(current_location[key] - parameters[key]) > epsilon:
            found = True
    if found:
        return format_for_feed(values, feed)
    # else if any of A, B, or C are in the parameters, the feed is in degrees,
    #     which should not be converted when in --inches mode
    found = False
    for key in ("A", "B", "C"):
        if key in parameters:
            found = True
    if found:
        # converting from degrees per second to degrees per minute as well
        return format(float(feed * 60.0), f'.{str(SA.get_feed_precision(values))}f')
    # which leaves none of X, Y, Z, U, V, W, A, B, C,
    # which should not be valid but return a converted value just in case
    return format_for_feed(values, feed)


def default_int_parameter(
    values: Values,  # pylint: disable=unused-argument
    command: str,  # pylint: disable=unused-argument
    param: str,  # pylint: disable=unused-argument
    param_value: PathParameter,
    parameters: PathParameters,  # pylint: disable=unused-argument
    current_location: PathParameters,  # pylint: disable=unused-argument
) -> str:
    """Process a parameter that is treated like an integer."""
    return str(int(param_value))


def default_length_parameter(
    values: Values,
    command: str,  # pylint: disable=unused-argument
    param: str,  # pylint: disable=unused-argument
    param_value: PathParameter,
    parameters: PathParameters,  # pylint: disable=unused-argument
    current_location: PathParameters,  # pylint: disable=unused-argument
) -> str:
    """Process a parameter that is treated like a length."""
    return format_for_axis(values, Units.Quantity(param_value, Units.Length))


def default_P_parameter(
    values: Values,
    command: str,
    param: str,  # pylint: disable=unused-argument
    param_value: PathParameter,
    parameters: PathParameters,  # pylint: disable=unused-argument
    current_location: PathParameters,  # pylint: disable=unused-argument
) -> str:
    """Process the P parameter."""
    if command in ("G2", "G02", "G3", "G03", "G5.2", "G5.3", "G10", "G54.1", "G59"):
        return str(int(param_value))
    if command in ("G4", "G04", "G76", "G82", "G86", "G89"):
        return str(float(param_value))
    if command in ("G5", "G05", "G64"):
        return format_for_axis(values, Units.Quantity(param_value, Units.Length))
    # anything else that is supported
    return str(param_value)


def default_Q_parameter(
    values: Values,
    command: str,
    param: str,  # pylint: disable=unused-argument
    param_value: PathParameter,
    parameters: PathParameters,  # pylint: disable=unused-argument
    current_location: PathParameters,  # pylint: disable=unused-argument
) -> str:
    """Process the Q parameter."""
    if command == "G10":
        return str(int(param_value))
    if command in ("G64", "G73", "G83"):
        return format_for_axis(values, Units.Quantity(param_value, Units.Length))
    return ""


def default_rotary_parameter(
    values: Values,
    command: str,  # pylint: disable=unused-argument
    param: str,
    param_value: PathParameter,
    parameters: PathParameters,  # pylint: disable=unused-argument
    current_location: PathParameters,
) -> str:
    """Process a rotarty parameter (such as A, B, and C)."""
    #
    # used to compare two floating point numbers for "close-enough equality"
    #
    epsilon: float = 0.00001

    if (
        not SA.get_output_doubles(values)
        and param in current_location
        and math.fabs(current_location[param] - param_value) < epsilon
    ):
        return ""
    #  unlike other axis, rotary axis such as A, B, and C are always in degrees
    #  and should not be converted when in --inches mode
    return str(format(float(param_value), f'.{str(SA.get_axis_precision(values))}f'))


def default_S_parameter(
    values: Values,
    command: str,  # pylint: disable=unused-argument
    param: str,  # pylint: disable=unused-argument
    param_value: PathParameter,
    parameters: PathParameters,  # pylint: disable=unused-argument
    current_location: PathParameters,  # pylint: disable=unused-argument
) -> str:
    """Process the S parameter."""
    return format_for_spindle(values, param_value)


def determine_adaptive_op(values: State, pathobj) -> Tuple[bool, float, float]:
    """Determine if the pathobj contains an Adaptive operation."""
    nl = "\n"
    adaptiveOp: bool = False
    opHorizRapid: float = 0.0
    opVertRapid: float = 0.0

    if SA.get_output_adaptive(values) and "Adaptive" in pathobj.Name:
        adaptiveOp = True
        if hasattr(pathobj, "ToolController"):
            tc = pathobj.ToolController
            if hasattr(tc, "HorizRapid") and tc.HorizRapid > 0:
                opHorizRapid = Units.Quantity(tc.HorizRapid, Units.Velocity)
            else:
                FreeCAD.Console.PrintWarning(
                    f"Tool Controller Horizontal Rapid Values are unset{nl}"
                )
            if hasattr(tc, "VertRapid") and tc.VertRapid > 0:
                opVertRapid = Units.Quantity(tc.VertRapid, Units.Velocity)
            else:
                FreeCAD.Console.PrintWarning(f"Tool Controller Vertical Rapid Values are unset{nl}")
    return (adaptiveOp, opHorizRapid, opVertRapid)


def drill_translate(
    values: Values,
    gcode: Gcode,
    command: str,
    params: PathParameters,
    motion_location: PathParameters,
    drill_retract_mode: str,
) -> None:
    """Translate drill cycles.

    Currently only cycles in XY are provided (G17).
    XZ (G18) and YZ (G19) are not dealt with.
    In other words only Z drilling can be translated.
    """
    cmd: str
    comment: str
    drill_x: float
    drill_y: float
    drill_z: float
    motion_z: float
    retract_z: float
    F_feedrate: str
    G0_retract_z: str

    motion_mode = SA.get_motion_mode(values)
    if motion_mode == "G91":
        # force absolute coordinates during cycles
        gcode.append(f"{linenumber(values)}G90")

    drill_x = Units.Quantity(params["X"], Units.Length)
    drill_y = Units.Quantity(params["Y"], Units.Length)
    drill_z = Units.Quantity(params["Z"], Units.Length)
    retract_z = Units.Quantity(params["R"], Units.Length)
    if retract_z < drill_z:  # R less than Z is error
        comment = create_comment(values, "Drill cycle error: R less than Z")
        gcode.append(f"{linenumber(values)}{comment}")
        return
    motion_z = Units.Quantity(motion_location["Z"], Units.Length)
    if motion_mode == "G91":  # relative movements
        drill_x += Units.Quantity(motion_location["X"], Units.Length)
        drill_y += Units.Quantity(motion_location["Y"], Units.Length)
        drill_z += motion_z
        retract_z += motion_z
    if drill_retract_mode == "G98" and motion_z >= retract_z:
        retract_z = motion_z

    cmd = format_command_line(values, ["G0", f"Z{format_for_axis(values, retract_z)}"])
    G0_retract_z = f"{cmd}"
    cmd = format_for_feed(values, Units.Quantity(params["F"], Units.Velocity))
    F_feedrate = f'{SA.get_command_space(values)}F{cmd}'

    # preliminary movement(s)
    if motion_z < retract_z:
        gcode.append(f"{linenumber(values)}{G0_retract_z}")
    cmd = format_command_line(
        values,
        [
            "G0",
            f"X{format_for_axis(values, drill_x)}",
            f"Y{format_for_axis(values, drill_y)}",
        ],
    )
    gcode.append(f"{linenumber(values)}{cmd}")
    if motion_z > retract_z:
        # NIST GCODE 3.5.16.1 Preliminary and In-Between Motion says G0 to retract_z
        # Here use G1 since retract height may be below surface !
        cmd = format_command_line(values, ["G1", f"Z{format_for_axis(values, retract_z)}"])
        gcode.append(f"{linenumber(values)}{cmd}{F_feedrate}")

        # drill moves
    if command in ("G81", "G82"):
        output_G81_G82_drill_moves(
            values, gcode, command, params, drill_z, F_feedrate, G0_retract_z
        )
    elif command in ("G73", "G83"):
        output_G73_G83_drill_moves(
            values, gcode, command, params, drill_z, retract_z, F_feedrate, G0_retract_z
        )


def format_command_line(values: State, command_line: CommandLine) -> str:
    """Construct the command line for the final output."""
    return SA.get_command_space(values).join(command_line)


def format_for_axis(values: State, number) -> str:
    """Format a number using the precision for an axis value."""
    return str(
        format(
            float(number.getValueAs(SA.get_unit_format(values))),
            f'.{str(SA.get_axis_precision(values))}f',
        )
    )


def format_for_feed(values: State, number) -> str:
    """Format a number using the precision for a feed rate."""
    return str(
        format(
            float(number.getValueAs(SA.get_unit_speed_format(values))),
            f'.{str(SA.get_feed_precision(values))}f',
        )
    )


def format_for_spindle(values: State, number) -> str:
    """Format a number using the precision for a spindle speed."""
    return str(format(float(number), f'.{str(SA.get_spindle_decimals(values))}f'))


def init_parameter_functions(parameter_functions: Dict[str, ParameterFunction]) -> None:
    """Initialize a list of parameter functions.

    These functions are called in the UtilsParse.parse_a_path
    function to return the appropriate parameter value.
    """
    default_parameter_functions: Dict[str, ParameterFunction]
    parameter: str

    default_parameter_functions = {
        "A": default_rotary_parameter,
        "B": default_rotary_parameter,
        "C": default_rotary_parameter,
        "D": default_D_parameter,
        "E": default_length_parameter,
        "F": default_F_parameter,
        # "G" is reserved for G-code commands
        "H": default_int_parameter,
        "I": default_length_parameter,
        "J": default_length_parameter,
        "K": default_length_parameter,
        "L": default_int_parameter,
        # "M" is reserved for M-code commands
        # "N" is reserved for the line numbers
        # "O" is reserved for the line numbers for subroutines
        "P": default_P_parameter,
        "Q": default_Q_parameter,
        "R": default_length_parameter,
        "S": default_S_parameter,
        "T": default_int_parameter,
        "U": default_axis_parameter,
        "V": default_axis_parameter,
        "W": default_axis_parameter,
        "X": default_axis_parameter,
        "Y": default_axis_parameter,
        "Z": default_axis_parameter,
        # "$" is used by LinuxCNC (and others?) to designate which spindle
    }
    for parameter in default_parameter_functions:  # pylint: disable=consider-using-dict-items
        parameter_functions[parameter] = default_parameter_functions[parameter]


def linenumber(values: State, space: Union[str, None] = None) -> str:
    """Output the next line number if appropriate."""
    from Path.Post.Processor import MachineConfiguration
    
    if not SA.get_output_line_numbers(values):
        return ""
    if space is None:
        space = SA.get_command_space(values)
    
    # Handle mutable state: for dict, mutate directly; for typed state, use method
    if isinstance(values, MachineConfiguration):
        line_num = str(values.formatting.current_line_number)
        values.formatting.next_line_number()  # Increments internally
    else:
        line_num = str(values["line_number"])
        values["line_number"] += SA.get_line_increment(values)
    
    return f"N{line_num}{space}"


def output_G73_G83_drill_moves(
    values: Values,
    gcode: Gcode,
    command: str,
    params: PathParameters,
    drill_z: float,
    retract_z: float,
    F_feedrate: str,
    G0_retract_z: str,
) -> None:
    """Output the movement G code for G73 and G83."""
    a_bit: float
    chip_breaker_height: float
    clearance_depth: float
    cmd: str
    drill_step: float
    last_stop_z: float
    next_stop_z: float

    last_stop_z = retract_z
    drill_step = Units.Quantity(params["Q"], Units.Length)
    # NIST 3.5.16.4 G83 Cycle:  "current hole bottom, backed off a bit."
    a_bit = drill_step * 0.05
    if drill_step != 0:
        while True:
            if last_stop_z != retract_z:
                # rapid move to just short of last drilling depth
                clearance_depth = last_stop_z + a_bit
                cmd = format_command_line(
                    values,
                    ["G0", f"Z{format_for_axis(values, clearance_depth)}"],
                )
                gcode.append(f"{linenumber(values)}{cmd}")
            next_stop_z = last_stop_z - drill_step
            if next_stop_z > drill_z:
                cmd = format_command_line(
                    values, ["G1", f"Z{format_for_axis(values, next_stop_z)}"]
                )
                gcode.append(f"{linenumber(values)}{cmd}{F_feedrate}")
                if command == "G73":
                    # Rapid up "a small amount".
                    chip_breaker_height = next_stop_z + values["CHIPBREAKING_AMOUNT"]
                    cmd = format_command_line(
                        values,
                        [
                            "G0",
                            f"Z{format_for_axis(values, chip_breaker_height)}",
                        ],
                    )
                    gcode.append(f"{linenumber(values)}{cmd}")
                elif command == "G83":
                    # Rapid up to the retract height
                    gcode.append(f"{linenumber(values)}{G0_retract_z}")
                last_stop_z = next_stop_z
            else:
                cmd = format_command_line(values, ["G1", f"Z{format_for_axis(values, drill_z)}"])
                gcode.append(f"{linenumber(values)}{cmd}{F_feedrate}")
                gcode.append(f"{linenumber(values)}{G0_retract_z}")
                break


def output_G81_G82_drill_moves(
    values: Values,
    gcode: Gcode,
    command: str,
    params: PathParameters,
    drill_z: float,
    F_feedrate: str,
    G0_retract_z: str,
) -> None:
    """Output the movement G code for G81 and G82."""
    cmd: str

    cmd = format_command_line(values, ["G1", f"Z{format_for_axis(values, drill_z)}"])
    gcode.append(f"{linenumber(values)}{cmd}{F_feedrate}")
    # pause where applicable
    if command == "G82":
        cmd = format_command_line(values, ["G4", f'P{str(params["P"])}'])
        gcode.append(f"{linenumber(values)}{cmd}")
    gcode.append(f"{linenumber(values)}{G0_retract_z}")


def parse_a_group(values: State, gcode: Gcode, pathobj) -> None:
    """Parse a Group (compound, project, or simple path)."""
    comment: str

    if hasattr(pathobj, "Group"):  # We have a compound or project.
        if SA.get_output_comments(values):
            comment = create_comment(values, f"Compound: {pathobj.Label}")
            gcode.append(f"{linenumber(values)}{comment}")
        for p in pathobj.Group:
            parse_a_group(values, gcode, p)
    else:  # parsing simple path
        # groups might contain non-path things like stock.
        if not hasattr(pathobj, "Path"):
            return
        if SA.get_output_path_labels(values) and SA.get_output_comments(values):
            comment = create_comment(values, f"Path: {pathobj.Label}")
            gcode.append(f"{linenumber(values)}{comment}")
        parse_a_path(values, gcode, pathobj)


def _initialize_parse_state(values: State, pathobj) -> Tuple[bool, PathParameters, PathParameters, Tuple[bool, float, float]]:
    """Initialize state for parsing a path.
    
    Returns:
        Tuple of (swap_tool_change_order, current_location, motion_location, adaptive_op_variables)
    """
    from Path.Post.Processor import MachineConfiguration
    
    # Check if tool change order should be swapped
    swap_tool_change_order = False
    if isinstance(values, MachineConfiguration):
        swap_tool_change_order = values.processing.tool_before_change
    elif "TOOL_BEFORE_CHANGE" in values and values["TOOL_BEFORE_CHANGE"]:
        swap_tool_change_order = True
    
    # Initialize current_location with sentinel values
    current_location: PathParameters = {}
    current_location.update(
        Path.Command(
            "G0",
            {
                "X": 123456789.0,
                "Y": 123456789.0,
                "Z": 123456789.0,
                "U": 123456789.0,
                "V": 123456789.0,
                "W": 123456789.0,
                "A": 123456789.0,
                "B": 123456789.0,
                "C": 123456789.0,
                "F": 123456789.0,
            },
        ).Parameters
    )
    
    # Initialize motion_location for drill cycles
    motion_location: PathParameters = {"X": 0.0, "Y": 0.0, "Z": 0.0}
    
    # Determine if this is an adaptive operation
    adaptive_op_variables = determine_adaptive_op(values, pathobj)
    
    return swap_tool_change_order, current_location, motion_location, adaptive_op_variables


def _filter_and_prepare_command(values: State, command: str) -> tuple[str, bool]:
    """Filter and prepare a command for processing.
    
    Returns:
        Tuple of (modified command string, should_skip)
    """
    # Handle blank lines
    if not command:
        if not SA.get_output_blank_lines(values):
            return "", True  # Skip this command
        return command, False  # Keep blank line
    
    # Handle comment commands
    if command.startswith("("):
        if not SA.get_output_comments(values):
            return "", True  # Skip this command
        if SA.get_comment_symbol(values) != "(" and len(command) > 2:
            return create_comment(values, command[1:-1]), False
    
    return command, False


def _format_command_parameters(
    values: State,
    command: str,
    params: PathParameters,
    current_location: PathParameters,
) -> CommandLine:
    """Format command parameters according to parameter order.
    
    Returns:
        List of formatted parameter strings
    """
    command_line: CommandLine = []
    parameter_order = SA.get_parameter_order(values)
    parameter_functions = SA.get_parameter_functions(values)
    
    for parameter in parameter_order:
        if parameter in params:
            parameter_value = parameter_functions[parameter](
                values,
                command,
                parameter,
                params[parameter],
                params,
                current_location,
            )
            if parameter_value:
                command_line.append(f"{parameter}{parameter_value}")
    
    return command_line


def _update_runtime_state(
    values: State,
    command: str,
    params: PathParameters,
    current_location: PathParameters,
    motion_location: PathParameters,
    current_drill_retract_mode: str,
) -> str:
    """Update runtime state based on command.
    
    Args:
        current_drill_retract_mode: Current drill retract mode to update
    
    Returns:
        Updated drill_retract_mode ("G98" or "G99")
    """
    from Path.Post.Processor import MachineConfiguration
    
    # Update current location
    current_location.update(params)
    
    # Track motion mode
    if command in ("G90", "G91"):
        if not isinstance(values, MachineConfiguration):
            values["MOTION_MODE"] = command
    
    # Track drill retract mode
    if command in ("G98", "G99"):
        current_drill_retract_mode = command
    
    # Track motion location (but not for drill cycles)
    motion_commands = SA.get_motion_commands(values)
    if command in motion_commands and command not in PathGeom.CmdMoveDrill:
        motion_location.update(params)
    
    return current_drill_retract_mode


def _output_command(
    values: State,
    gcode: Gcode,
    command: str,
    command_line: CommandLine,
    params: PathParameters,
    swap_tool_change_order: bool,
) -> None:
    """Output the formatted command to gcode."""
    if not command_line:
        return
    
    # Special handling for tool change order swap
    if command in ("M6", "M06") and swap_tool_change_order and len(command_line) >= 2:
        swapped_command_line = [command_line[1], command_line[0]]
        gcode.append(
            f"{linenumber(values)}{format_command_line(values, swapped_command_line)}"
        )
    else:
        gcode.append(f"{linenumber(values)}{format_command_line(values, command_line)}")
    
    # Post-command processing
    check_for_tlo(values, gcode, command, params)
    check_for_machine_specific_commands(values, gcode, command)


def parse_a_path(values: State, gcode: Gcode, pathobj) -> None:
    """Parse a simple Path.
    
    This is the main entry point for parsing Path commands into G-code.
    The function has been refactored into smaller helper functions for clarity.
    """
    # Initialize parsing state
    swap_tool_change_order, current_location, motion_location, adaptive_op_variables = \
        _initialize_parse_state(values, pathobj)

    # Apply arc splitting if requested
    path_to_process = pathobj.Path
    if SA.get_split_arcs(values):
        path_to_process = PostUtils.splitArcs(path_to_process)
    
    # Process each command
    lastcommand = ""
    drill_retract_mode = "G98"
    
    for c in path_to_process.Commands:
        command = c.Name
        
        # Filter and prepare command
        command, should_skip = _filter_and_prepare_command(values, command)
        if should_skip:
            continue
        
        # Check for adaptive operation
        command_line: CommandLine = []
        cmd = check_for_an_adaptive_op(values, command, command_line, adaptive_op_variables)
        if cmd:
            command = cmd
        
        # Build command line
        command_line.append(command)
        
        # Apply modal suppression
        if SA.get_modal(values) and command == lastcommand:
            command_line.pop(0)
        
        # Format parameters
        formatted_params = _format_command_parameters(
            values, command, c.Parameters, current_location
        )
        command_line.extend(formatted_params)
        
        # Set adaptive operation speed
        set_adaptive_op_speed(values, command, command_line, c.Parameters, adaptive_op_variables)
        
        # Update runtime state
        drill_retract_mode = _update_runtime_state(
            values, command, c.Parameters, current_location, motion_location, drill_retract_mode
        )
        
        # Check for special command handling (may suppress output)
        if check_for_drill_translate(
            values, gcode, command, command_line, c.Parameters,
            motion_location, drill_retract_mode
        ):
            command_line = []
        
        check_for_spindle_wait(values, gcode, command, command_line)
        
        if check_for_tool_change(values, gcode, command, command_line):
            command_line = []
        
        if check_for_suppressed_commands(values, gcode, command, command_line):
            command_line = []
        
        # Output the command
        _output_command(values, gcode, command, command_line, c.Parameters, swap_tool_change_order)
        
        # Remember last command for modal suppression
        lastcommand = command


def set_adaptive_op_speed(
    values: Values,
    command: str,
    command_line: CommandLine,
    params: PathParameters,
    adaptive_op_variables: Tuple[bool, float, float],
) -> None:
    """Set the appropriate feed speed for an adaptive op."""
    adaptiveOp: bool
    opHorizRapid: float
    opVertRapid: float
    param_num: str

    (adaptiveOp, opHorizRapid, opVertRapid) = adaptive_op_variables
    if (
        SA.get_output_adaptive(values)
        and adaptiveOp
        and command in SA.get_rapid_moves(values)
        and opHorizRapid
        and opVertRapid
    ):
        if "Z" not in params:
            param_num = format_for_feed(values, opHorizRapid)
        else:
            param_num = format_for_feed(values, opVertRapid)
        command_line.append(f"F{param_num}")
