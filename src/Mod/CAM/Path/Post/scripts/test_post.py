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
Visible = Dict[str, bool]


class Test(PostProcessor):
    """The Test post processor class."""

    def __init__(
        self,
        job,
        tooltip=translate("CAM", "Test post processor"),
        tooltipargs=[""],
        units="Metric",
    ) -> None:
        super().__init__(
            job=job,
            tooltip=tooltip,
            tooltipargs=tooltipargs,
            units=units,
        )
        Path.Log.debug("Test post processor initialized")

    def init_values(self, state: PostProcessorState) -> None:
        """Initialize values that are used throughout the postprocessor."""
        super().init_values(state)
        
        # Machine configuration
        state.machine.name = "test"
        state.machine.stop_spindle_for_tool_change = False
        state.machine.use_tlo = False
        
        # Output options - minimal output for testing
        state.output.comments = False
        state.output.header = False
        state.output.tool_change = False
        
        # Processing options - minimal output for testing
        state.processing.show_editor = False
        state.processing.show_machine_units = False
        state.processing.show_operation_labels = False
        
        # Postprocessor identification
        state.postprocessor_file_name = __name__

    def init_arguments_visible(self, arguments_visible: Visible) -> None:
        """Initialize which argument pairs are visible in TOOLTIP_ARGS."""
        super().init_arguments_visible(arguments_visible)
        #
        # Modify the visibility of any arguments from the defaults here.
        #
        # Make all arguments invisible by default.
        #
        for key in iter(arguments_visible):
            arguments_visible[key] = False

    @property
    def tooltip(self):
        tooltip: str = """
        This is a postprocessor file for the CAM workbench.  It is used
        to test the postprocessor code.  It probably isn't useful for "real" gcode.
        """
        return tooltip
