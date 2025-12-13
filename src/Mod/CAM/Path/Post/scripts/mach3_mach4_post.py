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


class Mach3_Mach4(PostProcessor):
    """
    The Mach3_Mach4 post processor class.
    
    This post processor is configured for Mach3 and Mach4 CNC controllers with
    the following specific characteristics:
    - Excludes K parameter from parameter order (not needed for XY plane arcs)
    - Coolant commands (M7/M8/M9) enabled
    - Adaptive clearing output enabled
    - Machine name included in output header
    - Axis modal mode option available
    - Standard preamble: G17 G54 G40 G49 G80 G90
    - Postamble includes M05, mode resets, and M2 program end
    
    """

    def __init__(
        self,
        job,
        tooltip=translate("CAM", "Mach3_Mach4 post processor"),
        tooltipargs=[""],
        units="Metric",
    ) -> None:
        super().__init__(
            job=job,
            tooltip=tooltip,
            tooltipargs=tooltipargs,
            units=units,
        )
        Path.Log.debug("Mach3_Mach4 post processor initialized.")

    def init_values(self, state: MachineConfiguration) -> None:
        """Initialize values that are used throughout the postprocessor."""
        super().init_values(state)
        
        # Machine configuration
        state.name = "mach3_4"
        state.enable_coolant = True
        
        # Output options
        state.output.adaptive = True
        state.output.machine_name = True
        
        # Processing options
        state.processing.show_machine_units = False
        
        # Parameter order - mach3_mach4 doesn't want K properties on XY plane
        state.parameter_order = [
            "X", "Y", "Z", "A", "B", "C",
            "I", "J", "F", "S", "T", "Q",
            "R", "L", "H", "D", "P",
        ]
        
        # G-code blocks
        state.blocks.preamble = "G17 G54 G40 G49 G80 G90"
        state.blocks.postamble = """M05
G17 G54 G90 G80 G40
M2"""
        
        # Postprocessor identification
        state.postprocessor_file_name = __name__

    def init_arguments_visible(self, arguments_visible: Visible) -> None:
        """Initialize which argument pairs are visible in TOOLTIP_ARGS."""
        super().init_arguments_visible(arguments_visible)
        #
        # Modify the visibility of any arguments from the defaults here.
        #
        arguments_visible["axis-modal"] = True

    @property
    def tooltip(self):
        tooltip: str = """
        This is a postprocessor file for the CAM workbench.
        It is used to take a pseudo-gcode fragment from a CAM object
        and output 'real' GCode suitable for a Mach3_4 3 axis mill.
        """
        return tooltip
