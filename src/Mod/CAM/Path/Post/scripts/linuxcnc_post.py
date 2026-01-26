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
#
# DEPRECATED: This post processor is deprecated and replaced by the generic
# post processor with Generic_LinuxCNC.fcm machine configuration file.
# Use the generic post processor instead.

from typing import Any, Dict

from Path.Post.Processor import PostProcessor

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

    @classmethod
    def get_common_property_schema(cls):
        """Override common properties with LinuxCNC-specific defaults."""
        common_props = super().get_common_property_schema()
        
        # Override defaults for LinuxCNC
        for prop in common_props:
            if prop["name"] == "supports_tool_radius_compensation":
                prop["default"] = True
            elif prop["name"] == "preamble":
                prop["default"] = "G17 G54 G40 G49 G80 G90"
            elif prop["name"] == "postamble":
                prop["default"] = "M05\nG17 G54 G90 G80 G40\nM2"
            elif prop["name"] == "safetyblock":
                prop["default"] = "G40 G49 G80"
        
        return common_props

    @classmethod
    def get_property_schema(cls):
        """Return schema for LinuxCNC-specific configurable properties."""
        return [
            {
                "name": "blend_mode",
                "type": "choice",
                "label": translate("CAM", "Path Blending Mode"),
                "default": "BLEND",
                "choices": ["EXACT_PATH", "EXACT_STOP", "BLEND"],
                "help": translate("CAM", 
                    "Path blending mode: EXACT_PATH (G61) stops at each point, "
                    "EXACT_STOP (G61.1) stops at path ends, BLEND (G64) allows smooth motion")
            },
            {
                "name": "blend_tolerance",
                "type": "float",
                "label": translate("CAM", "Blend Tolerance"),
                "default": 0.0,
                "min": 0.0,
                "max": 10.0,
                "decimals": 4,
                "help": translate("CAM",
                    "Tolerance for BLEND mode (P value): 0 = no tolerance (G64), "
                    ">0 = tolerance (G64 P-), in current units")
            }
        ]

    def __init__(
        self,
        job,
        tooltip=translate("CAM", "LinuxCNC post processor"),
        tooltipargs=["blend-mode", "blend-tolerance"],
        units="Metric",
    ) -> None:
        super().__init__(
            job_or_jobs=job,
            tooltip=tooltip,
            tooltipargs=tooltipargs,
            units=units,
        )
        Path.Log.debug("LinuxCNC post processor initialized.")

    def init_values(self, values: Values) -> None:
        """Initialize values that are used throughout the postprocessor."""
        #
        super().init_values(values)
        #
        # Set any values here that need to override the default values set
        # in the parent routine.
        #
        values["ENABLE_COOLANT"] = True
        #
        # The order of parameters.
        #
        # linuxcnc doesn't want K properties on XY plane; Arcs need work.
        #
        values["PARAMETER_ORDER"] = [
            "X",
            "Y",
            "Z",
            "A",
            "B",
            "C",
            "I",
            "J",
            "F",
            "S",
            "T",
            "Q",
            "R",
            "L",
            "H",
            "D",
            "P",
        ]
        #
        # Used in the argparser code as the "name" of the postprocessor program.
        #
        values["MACHINE_NAME"] = "LinuxCNC"
        #
        # Any commands in this value will be output as the last commands
        # in the G-code file.
        #
        values[
            "POSTAMBLE"
        ] = """M05
G17 G54 G90 G80 G40
M2"""
        values["POSTPROCESSOR_FILE_NAME"] = __name__
        #
        # Path blending mode configuration (LinuxCNC-specific)
        # Load from machine configuration if available, otherwise use defaults
        #
        if self._machine and hasattr(self._machine, 'postprocessor_properties'):
            props = self._machine.postprocessor_properties
            values["BLEND_MODE"] = props.get("blend_mode", "BLEND")
            values["BLEND_TOLERANCE"] = props.get("blend_tolerance", 0.0)
        else:
            # Fallback to defaults if no machine configuration
            values["BLEND_MODE"] = "BLEND"
            values["BLEND_TOLERANCE"] = 0.0
        #
        # Any commands in this value will be output after the header and
        # safety block at the beginning of the G-code file.
        #
        values["PREAMBLE"] = """G17 G54 G40 G49 G80 G90 """

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
        """Process arguments and update values, including blend mode handling."""
        flag, args = super().process_arguments()

        if flag and args:
            # Update blend mode values from parsed arguments
            if hasattr(args, "blend_mode"):
                self.values["BLEND_MODE"] = args.blend_mode
            if hasattr(args, "blend_tolerance"):
                self.values["BLEND_TOLERANCE"] = args.blend_tolerance

            # Update PREAMBLE with blend command
            blend_cmd = self._get_blend_command()
            self.values["PREAMBLE"] += f"\n{blend_cmd}"

        return flag, args

    def _get_blend_command(self) -> str:
        """Generate the path blending G-code command based on current settings."""
        mode = self.values.get("BLEND_MODE", "BLEND")

        if mode == "EXACT_PATH":
            return "G61"
        elif mode == "EXACT_STOP":
            return "G61.1"
        else:  # BLEND
            tolerance = self.values.get("BLEND_TOLERANCE", 0.0)
            if tolerance > 0:
                return f"G64 P{tolerance:.4f}"
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
