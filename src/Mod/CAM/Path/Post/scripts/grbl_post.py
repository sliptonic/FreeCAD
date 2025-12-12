# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
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

import argparse

from typing import Any, Dict

from Path.Post.Processor import PostProcessor, MachineConfiguration

import Path
import FreeCAD

translate = FreeCAD.Qt.translate

DEBUG = False
if DEBUG:
    Path.Log.setLevel(Path.Log.Level.DEBUG, Path.Log.thisModule())
    Path.Log.trackModule(Path.Log.thisModule())
else:
    Path.Log.setLevel(Path.Log.Level.INFO, Path.Log.thisModule())

#
# Define some types that are used throughout this file.
#
Defaults = Dict[str, bool]
Values = Dict[str, Any]
Visible = Dict[str, bool]


class Grbl(PostProcessor):
    """
    The Grbl post processor class.
    
    This post processor is configured for Grbl CNC controllers (typically 3-axis mills)
    with the following specific characteristics:
    - Arc commands (G2/G3) may only work reliably on the XY plane
    - Tool change commands disabled (manual tool changes assumed)
    - Tool length offset (G43) not supported
    - Coolant commands (M7/M8/M9) enabled
    - Path labels included in output for operation tracking
    - Machine-specific commands enabled for Grbl features
    - Special options for bCNC compatibility, spindle wait, and drill translation
    
    """

    def __init__(
        self,
        job,
        tooltip=translate("CAM", "Grbl post processor"),
        tooltipargs=[""],
        units="Metric",
    ) -> None:
        super().__init__(
            job=job,
            tooltip=tooltip,
            tooltipargs=tooltipargs,
            units=units,
        )
        Path.Log.debug("Grbl post processor initialized.")

    def init_values(self, state: MachineConfiguration) -> None:
        """Initialize values that are used throughout the postprocessor."""
        super().init_values(state)
        
        # Machine configuration
        state.machine.name = "Grbl"
        state.machine.enable_coolant = True
        state.machine.enable_machine_specific_commands = True
        state.machine.use_tlo = False
        
        # Output options
        state.output.path_labels = True
        state.output.tool_change = False
        
        # Processing options
        state.processing.show_machine_units = False
        
        # Parameter order - Arcs may only work on the XY plane
        state.parameter_order = [
            "X", "Y", "Z", "A", "B", "C",
            "U", "V", "W", "I", "J", "F",
            "S", "T", "Q", "R", "L", "P",
        ]
        
        # G-code blocks
        state.blocks.preamble = "G17 G90"
        state.blocks.postamble = """M5
G17 G90
M2"""
        
        # Postprocessor identification
        state.postprocessor_file_name = __name__

    def init_argument_defaults(self, argument_defaults: Defaults) -> None:
        """Initialize which arguments (in a pair) are shown as the default argument."""
        super().init_argument_defaults(argument_defaults)
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
        argument_defaults["tlo"] = False
        argument_defaults["tool_change"] = False

    def init_arguments_visible(self, arguments_visible: Visible) -> None:
        """Initialize which argument pairs are visible in TOOLTIP_ARGS."""
        super().init_arguments_visible(arguments_visible)
        #
        # Modify the visibility of any arguments from the defaults here.
        #
        arguments_visible["bcnc"] = True
        arguments_visible["axis-modal"] = False
        arguments_visible["return-to"] = True
        arguments_visible["tlo"] = False
        arguments_visible["tool_change"] = True
        arguments_visible["translate_drill"] = True
        arguments_visible["wait-for-spindle"] = True

    @property
    def tooltip(self):
        tooltip: str = """
        This is a postprocessor file for the CAM workbench.
        It is used to take a pseudo-gcode fragment from a CAM object
        and output 'real' GCode suitable for a Grbl 3 axis mill.
        """
        return tooltip
