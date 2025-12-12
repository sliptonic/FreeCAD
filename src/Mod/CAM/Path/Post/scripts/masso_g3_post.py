# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *   Copyright (c) 2014 sliptonic <shopinthewoods@gmail.com>               *
# *   Copyright (c) 2022 - 2025 Larry Woestman <LarryWoestman2@gmail.com>   *
# *   Copyright (c) 2024 Ondsel <development@ondsel.com>                    *
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

from typing import Any, Dict

from Path.Post.Processor import PostProcessor, PostProcessorState

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


class Masso_G3(PostProcessor):
    """The Masso G3 post processor class."""

    def __init__(
        self,
        job,
        tooltip=translate("CAM", "Masso G3 post processor"),
        tooltipargs=[""],
        units="Metric",
    ) -> None:
        super().__init__(
            job=job,
            tooltip=tooltip,
            tooltipargs=tooltipargs,
            units=units,
        )
        Path.Log.debug("Masso G3 post processor initialized.")

    def init_values(self, state: PostProcessorState) -> None:
        """Initialize values that are used throughout the postprocessor."""
        super().init_values(state)
        
        # Machine configuration
        state.machine.name = "Masso G3"
        state.machine.enable_coolant = True
        
        # Parameter order
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
        
        # Masso G3 specific: Output T before M6 (T1 M6 instead of M6 T1)
        state.processing.tool_before_change = True

    @property
    def tooltip(self):
        tooltip: str = """
        This is a postprocessor file for the CAM workbench.
        It is used to take a pseudo-gcode fragment from a CAM object
        and output 'real' GCode suitable for a Masso G3 3 axis mill.
        """
        return tooltip
