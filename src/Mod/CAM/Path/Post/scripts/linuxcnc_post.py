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


class Linuxcnc(PostProcessor):
    """
    The LinuxCNC post processor class.
    LinuxCNC supports various trajectory control methods (path blending) as
    described at https://linuxcnc.org/docs/2.4/html/common_User_Concepts.html#r1_1_2

    This post processor implements the following trajectory control methods:
    - Exact Path (G61)
    - Exact Stop (G64)
    - Blend (G61.1)


    """

    def __init__(
        self,
        job,
        tooltip=translate("CAM", "LinuxCNC post processor"),
        tooltipargs=["blend-mode", "blend-tolerance"],
        units="Metric",
    ) -> None:
        super().__init__(
            job=job,
            tooltip=tooltip,
            tooltipargs=tooltipargs,
            units=units,
        )
        Path.Log.debug("LinuxCNC post processor initialized.")

    def init_values(self, state: MachineConfiguration) -> None:
        """Initialize values that are used throughout the postprocessor."""
        super().init_values(state)
        
        # Machine configuration
        state.name = "LinuxCNC"
        state.enable_coolant = True
        
        # Parameter order - linuxcnc doesn't want K properties on XY plane
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
        
        # LinuxCNC-specific: Path blending mode configuration
        # Store as custom attributes (will be in dict conversion)
        self._blend_mode = "BLEND"  # Options: EXACT_PATH, EXACT_STOP, BLEND
        self._blend_tolerance = 0.0  # P value for BLEND mode

    def init_arguments(self, values, argument_defaults, arguments_visible):
        """Initialize command-line arguments, including LinuxCNC-specific options."""
        parser = super().init_arguments(values, argument_defaults, arguments_visible)

        # Add LinuxCNC-specific argument group
        linuxcnc_group = parser.add_argument_group("LinuxCNC-specific arguments")

        linuxcnc_group.add_argument(
            "--blend-mode",
            choices=["EXACT_PATH", "EXACT_STOP", "BLEND"],
            default="BLEND",
            help="Path blending mode: EXACT_PATH (G61), EXACT_STOP (G61.1), "
            "BLEND (G64/G64 P-) (default: BLEND)",
        )

        linuxcnc_group.add_argument(
            "--blend-tolerance",
            type=float,
            default=0.0,
            help="Tolerance for BLEND mode (P value): 0 = no tolerance (G64), "
            ">0 = tolerance (G64 P-), in current units (default: 0.0)",
        )
        return parser

    def process_arguments(self):
        """Process arguments and update state, including blend mode handling."""
        flag, args = super().process_arguments()

        if flag and args:
            # Update blend mode from parsed arguments
            if hasattr(args, "blend_mode"):
                self._blend_mode = args.blend_mode
            if hasattr(args, "blend_tolerance"):
                self._blend_tolerance = args.blend_tolerance

            # Append blend command to preamble (which may have been overridden by --preamble arg)
            # Base class _sync_dict_to_state() has already synced command-line args to self.state
            blend_cmd = self._get_blend_command()
            self.state.blocks.preamble += f"\n{blend_cmd}"
            
            # Sync back to dict for backward compatibility
            self.values["PREAMBLE"] = self.state.blocks.preamble

        return flag, args

    def _get_blend_command(self) -> str:
        """Generate the path blending G-code command based on current settings."""
        if self._blend_mode == "EXACT_PATH":
            return "G61"
        elif self._blend_mode == "EXACT_STOP":
            return "G61.1"
        else:  # BLEND
            if self._blend_tolerance > 0:
                return f"G64 P{self._blend_tolerance:.4f}"
            else:
                return "G64"

    # tooltipArgs is inherited from base class and automatically includes
    # all arguments from init_arguments() via parser.format_help()

    @property
    def tooltip(self):
        tooltip: str = """
        This is a postprocessor file for the CAM workbench.
        It is used to take a pseudo-gcode fragment from a CAM object
        and output 'real' GCode suitable for a linuxcnc 3 axis mill.
        """
        return tooltip
