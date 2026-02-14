# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 sliptonic
# SPDX-FileNotice: Part of the FreeCAD project.

################################################################################
#                                                                              #
#   FreeCAD is free software: you can redistribute it and/or modify            #
#   it under the terms of the GNU Lesser General Public License as             #
#   published by the Free Software Foundation, either version 2.1              #
#   of the License, or (at your option) any later version.                     #
#                                                                              #
#   FreeCAD is distributed in the hope that it will be useful,                 #
#   but WITHOUT ANY WARRANTY; without even the implied warranty                #
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.                    #
#   See the GNU Lesser General Public License for more details.                #
#                                                                              #
#   You should have received a copy of the GNU Lesser General Public           #
#   License along with FreeCAD. If not, see https://www.gnu.org/licenses       #
#                                                                              #
################################################################################

"""
Generic Postprocessor for plasma, laser, and waterjet cutters that require a pierce delay
"""

from typing import Any, Dict
import copy

from Path.Post.Processor import PostProcessor

import Path
import FreeCAD

translate = FreeCAD.Qt.translate

DEBUG = True
if DEBUG:
    Path.Log.setLevel(Path.Log.Level.DEBUG, Path.Log.thisModule())
    Path.Log.trackModule(Path.Log.thisModule())
else:
    Path.Log.setLevel(Path.Log.Level.INFO, Path.Log.thisModule())

Path.Log.debug("generic_plasma_post.py module loaded")

# Define some types that are used throughout this file.
Values = Dict[str, Any]


class GenericPlasma(PostProcessor):
    """
    The GenericPlasma post processor class.
    """

    @classmethod
    def get_common_property_schema(cls):
        Path.Log.debug("GenericPlasma.get_common_property_schema() called")
        common_props = copy.deepcopy(super().get_common_property_schema())
        
        # Override defaults for GenericPlasma
        for prop in common_props:
            if prop["name"] == "file_extension":
                prop["default"] = "nc"
            elif prop["name"] == "supports_tool_radius_compensation":
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
        """Return schema for plasma-specific configurable properties."""
        return [
            {
                "name": "pierce_delay",
                "type": "integer",
                "label": translate("CAM", "Pierce Delay"),
                "default": 1000,
                "min": 0,
                "max": 10000,
                "help": translate("CAM", 
                    "Pierce delay in milliseconds to wait after torch ignites (M3/M4) before starting movement")
            },
            {
                "name": "cooling_delay",
                "type": "integer",
                "label": translate("CAM", "Cooling Delay"),
                "default": 500,
                "min": 0,
                "max": 10000,
                "help": translate("CAM", 
                    "Cooling delay in milliseconds to wait after torch extinguishes (M5) before movement")
            },
            {
                "name": "torch_zaxis_control",
                "type": "bool",
                "label": translate("CAM", "Torch Z-Axis Control"),
                "default": True,
                "help": translate("CAM", 
                    "Torch ignites (M3) on Z- movement and extinguishes (M5) on Z+ movement. "
                    "When disabled, M3/M5 commands are output as-is.")
            },
            {
                "name": "mark_entry_only",
                "type": "bool",
                "label": translate("CAM", "Mark Entry Only"),
                "default": False,
                "help": translate("CAM", 
                    "Only mark first entry points (first Z- movement to start depth). "
                    "Subsequent movements will not trigger torch ignition.")
            },
            {
                "name": "force_rapid_feeds",
                "type": "bool",
                "label": translate("CAM", "Force Rapid Feeds"),
                "default": False,
                "help": translate("CAM", 
                    "Force rapid-feed speeds for all feed specified commands. "
                    "Useful for dry runs to verify paths without cutting.")
            },
        ]

    def __init__(
        self,
        job,
        tooltip=translate("CAM", "Generic Plasma post processor"),
        tooltipargs=[],
        units="Metric",
    ) -> None:
        super().__init__(
            job=job,
            tooltip=tooltip,
            tooltipargs=tooltipargs,
            units=units,
        )
        Path.Log.debug("Generic Plasma post processor initialized.")
        
        # State tracking for plasma-specific features
        self._first_entry_done = False
        self._torch_active = False
        self._last_z_direction = None  # Track Z movement direction

    def _get_property_value(self, name, default):
        """Get a property value from machine configuration with fallback to default."""
        if self._machine and hasattr(self._machine, 'postprocessor_properties'):
            return self._machine.postprocessor_properties.get(name, default)
        return default

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
        
        values["MACHINE_NAME"] = "GenericPlasma"
        values["POSTPROCESSOR_FILE_NAME"] = __name__
        #
        # Load preamble from machine configuration if available
        #
        if self._machine and hasattr(self._machine, 'postprocessor_properties'):
            props = self._machine.postprocessor_properties
            values["PREAMBLE"] = props.get("preamble", "")
        else:
            values["PREAMBLE"] = ""
        

    def _inject_pierce_delay(self, postables):
        """Inject pierce delay after M3/M4 commands when torch is activated."""
        pierce_delay_ms = self._get_property_value("pierce_delay", 1000)
        if pierce_delay_ms <= 0:
            return
            
        # Convert milliseconds to seconds for G4 command
        pierce_delay_sec = pierce_delay_ms / 1000.0
            
        for section_name, sublist in postables:
            for item in sublist:
                if hasattr(item, 'Path') and item.Path:
                    new_commands = []
                    for cmd in item.Path.Commands:
                        new_commands.append(cmd)
                        # After torch on commands, inject G4 pause
                        if cmd.Name in ['M3', 'M4']:
                            # Create G4 dwell command with P parameter (seconds)
                            pause_cmd = Path.Command('G4', {'P': pierce_delay_sec})
                            new_commands.append(pause_cmd)
                    # Replace Path with modified command list
                    item.Path = Path.Path(new_commands)

    def _inject_cooling_delay(self, postables):
        """Inject cooling delay after M5 commands when torch is extinguished."""
        cooling_delay_ms = self._get_property_value("cooling_delay", 500)
        if cooling_delay_ms <= 0:
            return
            
        # Convert milliseconds to seconds for G4 command
        cooling_delay_sec = cooling_delay_ms / 1000.0
            
        for section_name, sublist in postables:
            for item in sublist:
                if hasattr(item, 'Path') and item.Path:
                    new_commands = []
                    for cmd in item.Path.Commands:
                        new_commands.append(cmd)
                        # After torch off command, inject G4 pause
                        if cmd.Name == 'M5':
                            # Create G4 dwell command with P parameter (seconds)
                            pause_cmd = Path.Command('G4', {'P': cooling_delay_sec})
                            new_commands.append(pause_cmd)
                    # Replace Path with modified command list
                    item.Path = Path.Path(new_commands)

    def _inject_torch_control(self, postables):
        """Handle torch ignition/extinguishment based on Z-axis movement."""
        if not self._get_property_value("torch_zaxis_control", True):
            return
            
        for section_name, sublist in postables:
            for item in sublist:
                if hasattr(item, 'Path') and item.Path:
                    new_commands = []
                    for cmd in item.Path.Commands:
                        # Track Z movement direction
                        z_direction = None
                        if 'Z' in cmd.Parameters:
                            # This is a Z move - determine direction
                            if hasattr(self, '_last_z') and 'Z' in cmd.Parameters:
                                if cmd.Parameters['Z'] < self._last_z:
                                    z_direction = 'down'
                                elif cmd.Parameters['Z'] > self._last_z:
                                    z_direction = 'up'
                            self._last_z = cmd.Parameters['Z']
                        
                        # Handle torch control based on Z movement
                        if z_direction == 'down' and not self._torch_active:
                            if not self._get_property_value("mark_entry_only", False) or not self._first_entry_done:
                                # Insert M3 before Z- move (torch ignition)
                                new_commands.append(Path.Command('M3'))
                                self._torch_active = True
                                self._first_entry_done = True
                        elif z_direction == 'up' and self._torch_active:
                            # Insert M5 after Z+ move (torch extinguish)
                            new_commands.append(Path.Command('M5'))
                            self._torch_active = False
                        
                        new_commands.append(cmd)
                    # Replace Path with modified command list
                    item.Path = Path.Path(new_commands)

    def _force_rapid_feeds(self, postables):
        """Replace all feed rates with rapid speeds for dry runs."""
        if not self._get_property_value("force_rapid_feeds", False):
            return
            
        for section_name, sublist in postables:
            for item in sublist:
                if hasattr(item, 'Path') and item.Path:
                    new_commands = []
                    for cmd in item.Path.Commands:
                        new_cmd = cmd
                        # Remove F parameter from all movement commands
                        if cmd.Name in ['G0', 'G1', 'G2', 'G3'] and 'F' in cmd.Parameters:
                            # Create new command without F parameter
                            new_params = dict(cmd.Parameters)
                            del new_params['F']
                            new_cmd = Path.Command(cmd.Name, new_params)
                        new_commands.append(new_cmd)
                    # Replace Path with modified command list
                    item.Path = Path.Path(new_commands)

    def export2(self):
        """Override export2 to inject plasma-specific commands before parent processing.
        
        This handles torch control, pierce delays, cooling delays, and rapid feeds
        before the parent's export2() processes the commands.
        """
        # Get the postables list from parent (before processing)
        postables = self._buildPostList()
        
        # Apply plasma-specific transformations
        self._inject_torch_control(postables)
        self._inject_pierce_delay(postables)
        self._inject_cooling_delay(postables)
        self._force_rapid_feeds(postables)
        
        # Call parent export2 with modified postables
        return super().export2()


    @property
    def tooltip(self):
        tooltip: str = """
        This is a postprocessor file for the CAM workbench.
        It is used to take a pseudo-gcode fragment from a CAM object
        and output 'real' GCode suitable for a plasma cutter. 
        """
        return tooltip


# Class aliases for PostProcessorFactory
# The factory looks for a class with title-cased postname (e.g., "Generic_Plasma")
Generic_Plasma = GenericPlasma
Genericplasma = GenericPlasma  # Fallback for different title() behavior
