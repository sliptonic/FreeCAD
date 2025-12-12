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
Values = Dict[str, Any]
Visible = Dict[str, bool]


class Centroid(PostProcessor):
    """
    The Centroid post processor class.
    
    This post processor is configured for Centroid 3-axis mill controllers with
    the following specific characteristics:
    - Uses 4 decimal places for axis coordinates and 1 for feed rates
    - Excludes K parameter from parameter order (not needed for XY plane arcs)
    - Uses M25 command for spindle retraction (Centroid-specific)
    - Tool length offset (G43) disabled by default
    - Semicolon (;) for comments
    - Custom machine blocks: G53 G00 G17 preamble, M99 postamble
    
    """

    def __init__(
        self,
        job,
        tooltip=translate("CAM", "Centroid post processor"),
        tooltipargs=[""],
        units="Metric",
    ) -> None:
        super().__init__(
            job=job,
            tooltip=tooltip,
            tooltipargs=tooltipargs,
            units=units,
        )
        Path.Log.debug("Centroid post processor initialized.")

    def init_values(self, state: MachineConfiguration) -> None:
        """Initialize values that are used throughout the postprocessor."""
        super().init_values(state)
        
        # Precision settings
        state.precision.axis_precision = 4
        state.precision.default_metric_axis = 4
        state.precision.default_imperial_axis = 4
        state.precision.feed_precision = 1
        state.precision.default_metric_feed = 1
        state.precision.default_imperial_feed = 1
        
        # Formatting
        state.formatting.comment_symbol = ";"
        
        # Machine configuration
        state.machine.name = "Centroid"
        state.machine.stop_spindle_for_tool_change = False
        
        # Parameter order - centroid doesn't want K properties on XY plane
        state.parameter_order = [
            "X", "Y", "Z", "A", "B",
            "I", "J", "F", "S", "T",
            "Q", "R", "L", "H",
        ]
        
        # G-code blocks
        state.blocks.preamble = "G53 G00 G17"
        state.blocks.postamble = "M99"
        state.blocks.safetyblock = "G90 G80 G40 G49"
        state.blocks.finish_label = "End"
        
        # Processing options
        state.processing.list_tools_in_preamble = True
        state.processing.show_machine_units = False
        state.processing.show_operation_labels = False
        
        # Postprocessor identification
        state.postprocessor_file_name = __name__
        
        # Custom Centroid setting (stored as instance attribute)
        self._remove_messages = False
        
        # Tool return block - spindle off, height offset canceled, spindle retracted
        # (M25 is a centroid command to retract spindle)
        state.blocks.tool_return = """M5
M25
G49 H0"""
        
        # Default to not outputting a G43 following tool changes
        state.machine.use_tlo = False
        #
        # This was in the original centroid postprocessor file
        # but does not appear to be used anywhere.
        #
        # ZAXISRETURN = """G91 G28 X0 Z0 G90"""
        #

    def init_arguments_visible(self, arguments_visible: Visible) -> None:
        """Initialize which argument pairs are visible in TOOLTIP_ARGS."""
        super().init_arguments_visible(arguments_visible)
        #
        # Modify the visibility of any arguments from the defaults here.
        #
        arguments_visible["axis-modal"] = False
        arguments_visible["precision"] = False
        arguments_visible["tlo"] = False

    @property
    def tooltip(self):
        tooltip: str = """
        This is a postprocessor file for the CAM workbench.
        It is used to take a pseudo-gcode fragment from a CAM object
        and output 'real' GCode suitable for a centroid 3 axis mill.
        """
        return tooltip
