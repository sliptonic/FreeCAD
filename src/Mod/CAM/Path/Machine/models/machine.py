# SPDX-License-Identifier: LGPL-2.1-or-later
# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2025 Billy Huddleston <billy@ivdc.com>                  *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************
import json
import Path
import FreeCAD
import pathlib
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Callable
from collections import namedtuple
from enum import Enum


if False:
    Path.Log.setLevel(Path.Log.Level.DEBUG, Path.Log.thisModule())
    Path.Log.trackModule(Path.Log.thisModule())
else:
    Path.Log.setLevel(Path.Log.Level.INFO, Path.Log.thisModule())


# Reference axis vectors
RefAxes = namedtuple("RefAxes", ["x", "y", "z"])
refAxis = RefAxes(
    FreeCAD.Vector(1, 0, 0),  # x: linear direction
    FreeCAD.Vector(0, 1, 0),  # y: linear direction
    FreeCAD.Vector(0, 0, 1),  # z: linear direction
)

RefRotAxes = namedtuple("RefRotAxes", ["a", "b", "c"])
refRotAxis = RefRotAxes(
    FreeCAD.Vector(1, 0, 0),  # a: rotational direction
    FreeCAD.Vector(0, 1, 0),  # b: rotational direction
    FreeCAD.Vector(0, 0, 1),  # c: rotational direction
)


# ============================================================================
# Enums for Machine Configuration
# ============================================================================


class MachineUnits(Enum):
    """Machine unit system."""
    METRIC = "G21"
    IMPERIAL = "G20"


class MotionMode(Enum):
    """Motion mode for machine movements."""
    ABSOLUTE = "G90"
    RELATIVE = "G91"


# ============================================================================
# Post-Processor Configuration Dataclasses
# ============================================================================


@dataclass
class OutputOptions:
    """Controls what gets included in the G-code output."""
    comments: bool = True
    blank_lines: bool = True
    header: bool = True
    line_numbers: bool = False
    bcnc_blocks: bool = False
    path_labels: bool = False
    machine_name: bool = False
    tool_change: bool = True
    doubles: bool = True  # Output duplicate axis values
    adaptive: bool = False


@dataclass
class PrecisionSettings:
    """Numeric precision and formatting settings."""
    axis_precision: int = 3
    feed_precision: int = 3
    spindle_decimals: int = 0
    
    # Defaults by unit system
    default_metric_axis: int = 3
    default_metric_feed: int = 3
    default_imperial_axis: int = 4
    default_imperial_feed: int = 4


@dataclass
class LineFormatting:
    """Line formatting and numbering options."""
    command_space: str = " "
    comment_symbol: str = "("
    line_increment: int = 10
    line_number_start: int = 100
    end_of_line_chars: str = "\n"
    
    # Mutable state for line numbering
    _current_line: int = field(default=100, init=False, repr=False)
    
    def __post_init__(self):
        """Initialize mutable line number."""
        self._current_line = self.line_number_start
    
    @property
    def current_line_number(self) -> int:
        """Get current line number."""
        return self._current_line
    
    def next_line_number(self) -> int:
        """Get current line number and increment for next call."""
        current = self._current_line
        self._current_line += self.line_increment
        return current
    
    def reset_line_numbers(self) -> None:
        """Reset line numbering to start value."""
        self._current_line = self.line_number_start


@dataclass
class GCodeBlocks:
    """
    G-code block templates for various lifecycle hooks.
    
    These templates are inserted at specific points during postprocessing
    to provide customization points for machine-specific behavior.
    """
    # Job lifecycle
    pre_job: str = ""
    post_job: str = ""
    
    # Legacy aliases (maintained for compatibility)
    preamble: str = ""  # Typically inserted at start of job
    postamble: str = ""  # Typically inserted at end of job
    safetyblock: str = ""  # Safety commands (G40, G49, etc.)
    
    # Operation lifecycle
    pre_operation: str = ""
    post_operation: str = ""
    
    # Tool change lifecycle
    pre_tool_change: str = ""
    post_tool_change: str = ""
    tool_return: str = ""  # Return to tool change position
    
    # Fixture/WCS change lifecycle
    pre_fixture_change: str = ""
    post_fixture_change: str = ""
    
    # Rotary axis lifecycle
    pre_rotary_move: str = ""
    post_rotary_move: str = ""
    
    # Spindle lifecycle
    pre_spindle_change: str = ""
    post_spindle_change: str = ""
    
    # Miscellaneous
    finish_label: str = "Finish"


@dataclass
class ProcessingOptions:
    """Processing and transformation options."""
    modal: bool = False  # Suppress repeated commands
    translate_drill_cycles: bool = False
    split_arcs: bool = False
    show_editor: bool = True
    list_tools_in_preamble: bool = False
    show_machine_units: bool = True
    show_operation_labels: bool = True
    tool_before_change: bool = False  # Output T before M6 (e.g., T1 M6 instead of M6 T1)
    
    # Lists of commands
    drill_cycles_to_translate: List[str] = field(
        default_factory=lambda: ["G73", "G81", "G82", "G83"]
    )
    suppress_commands: List[str] = field(default_factory=list)
    
    # Numeric settings
    chipbreaking_amount: float = 0.25  # mm
    spindle_wait: float = 0.0  # seconds
    return_to: Optional[Tuple[float, float, float]] = None  # (x, y, z) or None


# ============================================================================
# Machine Component Dataclasses
# ============================================================================


@dataclass
class LinearAxis:
    """Represents a single linear axis in a machine configuration"""
    name: str
    direction_vector: FreeCAD.Vector
    min_limit: float = 0
    max_limit: float = 1000
    max_velocity: float = 10000
    sequence: int = 0
    
    def __post_init__(self):
        """Normalize direction vector after initialization"""
        self.direction_vector = self.direction_vector.normalize()

    def is_valid_position(self, position):
        """Check if a position is within this axis's limits"""
        return self.min_limit <= position <= self.max_limit

    def to_dict(self):
        """Serialize to dictionary for JSON persistence"""
        return {
            "name": self.name,
            "direction_vector": [
                self.direction_vector.x,
                self.direction_vector.y,
                self.direction_vector.z,
            ],
            "min_limit": self.min_limit,
            "max_limit": self.max_limit,
            "max_velocity": self.max_velocity,
            "sequence": self.sequence,
        }

    @classmethod
    def from_dict(cls, data):
        """Deserialize from dictionary"""
        vec = FreeCAD.Vector(
            data["direction_vector"][0], data["direction_vector"][1], data["direction_vector"][2]
        )
        return cls(
            data["name"],
            vec,
            data.get("min_limit", 0),
            data.get("max_limit", 1000),
            data.get("max_velocity", 10000),
            data.get("sequence", 0),
        )


@dataclass
class RotaryAxis:
    """Represents a single rotary axis in a machine configuration"""
    name: str
    rotation_vector: FreeCAD.Vector
    min_limit: float = -360
    max_limit: float = 360
    max_velocity: float = 36000
    sequence: int = 0
    prefer_positive: bool = True
    
    def __post_init__(self):
        """Normalize rotation vector after initialization"""
        self.rotation_vector = self.rotation_vector.normalize()

    def is_valid_angle(self, angle):
        """Check if an angle is within this axis's limits"""
        return self.min_limit <= angle <= self.max_limit

    def to_dict(self):
        """Serialize to dictionary for JSON persistence"""
        return {
            "name": self.name,
            "rotation_vector": [
                self.rotation_vector.x,
                self.rotation_vector.y,
                self.rotation_vector.z,
            ],
            "min_limit": self.min_limit,
            "max_limit": self.max_limit,
            "max_velocity": self.max_velocity,
            "sequence": self.sequence,
            "prefer_positive": self.prefer_positive,
        }

    @classmethod
    def from_dict(cls, data):
        """Deserialize from dictionary"""
        vec = FreeCAD.Vector(
            data["rotation_vector"][0], data["rotation_vector"][1], data["rotation_vector"][2]
        )
        return cls(
            data["name"],
            vec,
            data["min_limit"],
            data["max_limit"],
            data.get("max_velocity", 36000),
            data.get("sequence", 0),
            data.get("prefer_positive", True),
        )


@dataclass
class Spindle:
    """Represents a single spindle in a machine configuration"""
    name: str
    id: Optional[str] = None
    max_power_kw: float = 0
    max_rpm: float = 0
    min_rpm: float = 0
    tool_change: str = "manual"
    tool_axis: Optional[FreeCAD.Vector] = None
    
    def __post_init__(self):
        """Set default tool axis if not provided"""
        if self.tool_axis is None:
            self.tool_axis = FreeCAD.Vector(0, 0, -1)

    def to_dict(self):
        """Serialize to dictionary for JSON persistence"""
        data = {
            "name": self.name,
            "max_power_kw": self.max_power_kw,
            "max_rpm": self.max_rpm,
            "min_rpm": self.min_rpm,
            "tool_change": self.tool_change,
            "tool_axis": [self.tool_axis.x, self.tool_axis.y, self.tool_axis.z],
        }
        if self.id is not None:
            data["id"] = self.id
        return data

    @classmethod
    def from_dict(cls, data):
        """Deserialize from dictionary"""
        tool_axis_data = data.get("tool_axis", [0, 0, -1])
        tool_axis = FreeCAD.Vector(tool_axis_data[0], tool_axis_data[1], tool_axis_data[2])
        return cls(
            data["name"],
            data.get("id"),
            data.get("max_power_kw", 0),
            data.get("max_rpm", 0),
            data.get("min_rpm", 0),
            data.get("tool_change", "manual"),
            tool_axis,
        )


@dataclass
class Machine:
    """
    Unified machine configuration combining physical machine definition
    with post-processor settings.
    
    This is the single source of truth for all machine-related configuration,
    including physical capabilities (axes, spindles) and G-code generation
    preferences (output options, formatting, processing).
    """
    # ========================================================================
    # PHYSICAL MACHINE DEFINITION
    # ========================================================================
    
    # Basic identification
    name: str = "Default Machine"
    manufacturer: str = ""
    description: str = ""
    machine_type: str = "custom"  # xyz, xyzac, xyzbc, xyza, xyzb
    
    # Machine components
    linear_axes: Dict[str, LinearAxis] = field(default_factory=dict)
    rotary_axes: Dict[str, RotaryAxis] = field(default_factory=dict)
    spindles: List[Spindle] = field(default_factory=list)
    
    # Coordinate system
    reference_system: Dict[str, FreeCAD.Vector] = field(default_factory=lambda: {
        "X": FreeCAD.Vector(1, 0, 0),
        "Y": FreeCAD.Vector(0, 1, 0),
        "Z": FreeCAD.Vector(0, 0, 1),
    })
    tool_axis: FreeCAD.Vector = field(default_factory=lambda: FreeCAD.Vector(0, 0, -1))
    
    # Rotary axis configuration
    primary_rotary_axis: Optional[str] = None
    secondary_rotary_axis: Optional[str] = None
    compound_moves: bool = True
    prefer_positive_rotation: bool = True
    
    # Units and versioning
    units: str = "metric"  # "metric" or "imperial"
    version: int = 1
    freecad_version: str = field(init=False)
    
    # ========================================================================
    # POST-PROCESSOR CONFIGURATION
    # ========================================================================
    
    # Output options
    output: OutputOptions = field(default_factory=OutputOptions)
    precision: PrecisionSettings = field(default_factory=PrecisionSettings)
    formatting: LineFormatting = field(default_factory=LineFormatting)
    blocks: GCodeBlocks = field(default_factory=GCodeBlocks)
    processing: ProcessingOptions = field(default_factory=ProcessingOptions)
    
    # Post-processor selection
    postprocessor_file_name: str = ""
    postprocessor_args: str = ""
    
    # Motion mode
    motion_mode: MotionMode = MotionMode.ABSOLUTE
    use_tlo: bool = True  # Tool length offset
    stop_spindle_for_tool_change: bool = True
    enable_coolant: bool = False
    enable_machine_specific_commands: bool = False
    
    # Dynamic state (for runtime)
    parameter_functions: Dict[str, Callable] = field(default_factory=dict)
    parameter_order: List[str] = field(default_factory=lambda: [
        "D", "H", "L", "X", "Y", "Z", "A", "B", "C",
        "U", "V", "W", "I", "J", "K", "R", "P", "E", "Q", "F", "S", "T"
    ])
    
    def __post_init__(self):
        """Initialize computed fields"""
        self.freecad_version = ".".join(FreeCAD.Version()[0:3])
    
    # ========================================================================
    # PROPERTIES - Bridge between physical machine and post-processor
    # ========================================================================
    
    @property
    def machine_units(self) -> MachineUnits:
        """Get machine units as enum for post-processor"""
        return MachineUnits.METRIC if self.units == "metric" else MachineUnits.IMPERIAL
    
    @property
    def unit_format(self) -> str:
        """Get unit format string (mm or in)"""
        return "mm" if self.units == "metric" else "in"
    
    @property
    def unit_speed_format(self) -> str:
        """Get unit speed format string (mm/min or in/min)"""
        return "mm/min" if self.units == "metric" else "in/min"
    
    @property
    def has_rotary_axes(self) -> bool:
        """Check if machine has any rotary axes"""
        return len(self.rotary_axes) > 0
    
    @property
    def is_5axis(self) -> bool:
        """Check if machine is 5-axis (2 rotary axes)"""
        return len(self.rotary_axes) >= 2
    
    @property
    def is_4axis(self) -> bool:
        """Check if machine is 4-axis (1 rotary axis)"""
        return len(self.rotary_axes) == 1
    
    @property
    def motion_commands(self) -> List[str]:
        """Get list of motion commands that change position"""
        import Path.Geom as PathGeom
        return PathGeom.CmdMoveAll
    
    @property
    def rapid_moves(self) -> List[str]:
        """Get list of rapid move commands"""
        import Path.Geom as PathGeom
        return PathGeom.CmdMoveRapid
    
    # ========================================================================
    # BUILDER METHODS - Fluent interface for machine construction
    # ========================================================================

    def add_linear_axis(
        self, name, direction_vector, min_limit=0, max_limit=1000, max_velocity=10000
    ):
        """Add a linear axis to the configuration"""
        self.linear_axes[name] = LinearAxis(
            name, direction_vector, min_limit, max_limit, max_velocity
        )
        return self

    def add_rotary_axis(
        self, name, rotation_vector, min_limit=-360, max_limit=360, max_velocity=36000
    ):
        """Add a rotary axis to the configuration"""
        self.rotary_axes[name] = RotaryAxis(
            name, rotation_vector, min_limit, max_limit, max_velocity
        )
        return self

    def add_spindle(
        self,
        name,
        id=None,
        max_power_kw=0,
        max_rpm=0,
        min_rpm=0,
        tool_change="manual",
        tool_axis=None,
    ):
        """Add a spindle to the configuration"""
        if tool_axis is None:
            tool_axis = FreeCAD.Vector(0, 0, -1)
        self.spindles.append(
            Spindle(name, id, max_power_kw, max_rpm, min_rpm, tool_change, tool_axis)
        )
        return self

    def save(self, filepath):
        """Save this configuration to a file

        Args:
            filepath: Path to save the configuration file

        Returns:
            Path object of saved file
        """
        filepath = pathlib.Path(filepath)
        data = self.to_dict()

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            Path.Log.debug(f"Saved machine configuration to {filepath}")
            return filepath
        except Exception as e:
            Path.Log.error(f"Failed to save configuration: {e}")
            raise Exception(f"Failed to save machine file {filepath}: {e}")

    def set_alignment_axes(self, primary, secondary=None):
        """Set the primary and secondary rotary axes for alignment strategy

        For 4-axis machines, secondary can be None (single rotary axis)
        For 5-axis machines, both primary and secondary are required
        """
        if primary not in self.rotary_axes:
            raise ValueError(f"Primary axis {primary} not found in configuration")

        if secondary is not None and secondary not in self.rotary_axes:
            raise ValueError(f"Secondary axis {secondary} not found in configuration")

        self.primary_rotary_axis = primary
        self.secondary_rotary_axis = secondary
        return self

    def get_axis_by_name(self, name):
        """Get a rotary axis by name"""
        return self.rotary_axes.get(name)

    def get_spindle_by_index(self, index):
        """Get a spindle by its index in the list"""
        if 0 <= index < len(self.spindles):
            return self.spindles[index]
        raise ValueError(f"Spindle index {index} out of range")

    def get_spindle_by_name(self, name):
        """Get a spindle by name (case-insensitive)"""
        name_lower = name.lower()
        for spindle in self.spindles:
            if spindle.name.lower() == name_lower:
                return spindle
        raise ValueError(f"Spindle with name '{name}' not found")

    def get_spindle_by_id(self, id):
        """Get a spindle by ID (if present)"""
        if id is None:
            raise ValueError("ID cannot be None")
        for spindle in self.spindles:
            if spindle.id == id:
                return spindle
        raise ValueError(f"Spindle with ID '{id}' not found")

    @classmethod
    def create_AC_table_config(cls, a_limits=(-120, 120), c_limits=(-360, 360)):
        """Create standard A/C table configuration"""
        config = cls("AC Table Configuration")
        config.machine_type = "xyzac"
        config.add_linear_axis("X", FreeCAD.Vector(1, 0, 0))
        config.add_linear_axis("Y", FreeCAD.Vector(0, 1, 0))
        config.add_linear_axis("Z", FreeCAD.Vector(0, 0, 1))
        config.add_rotary_axis("A", FreeCAD.Vector(1, 0, 0), a_limits[0], a_limits[1])
        config.add_rotary_axis("C", FreeCAD.Vector(0, 0, 1), c_limits[0], c_limits[1])
        config.set_alignment_axes("C", "A")
        return config

    @classmethod
    def create_BC_head_config(cls, b_limits=(-120, 120), c_limits=(-360, 360)):
        """Create standard B/C head configuration"""
        config = cls("BC Head Configuration")
        config.machine_type = "xyzbc"
        config.add_linear_axis("X", FreeCAD.Vector(1, 0, 0))
        config.add_linear_axis("Y", FreeCAD.Vector(0, 1, 0))
        config.add_linear_axis("Z", FreeCAD.Vector(0, 0, 1))
        config.add_rotary_axis("B", FreeCAD.Vector(0, 1, 0), b_limits[0], b_limits[1])
        config.add_rotary_axis("C", FreeCAD.Vector(0, 0, 1), c_limits[0], c_limits[1])
        config.set_alignment_axes("C", "B")
        config.compound_moves = True  # Ensure compound moves are enabled for test compatibility
        return config

    @classmethod
    def create_AB_table_config(cls, a_limits=(-120, 120), b_limits=(-120, 120)):
        """Create standard A/B table configuration"""
        config = cls("AB Table Configuration")
        config.machine_type = "custom"  # AB is not a standard type in MACHINE_TYPES
        config.add_linear_axis("X", FreeCAD.Vector(1, 0, 0))
        config.add_linear_axis("Y", FreeCAD.Vector(0, 1, 0))
        config.add_linear_axis("Z", FreeCAD.Vector(0, 0, 1))
        config.add_rotary_axis("A", FreeCAD.Vector(1, 0, 0), a_limits[0], a_limits[1])
        config.add_rotary_axis("B", FreeCAD.Vector(0, 1, 0), b_limits[0], b_limits[1])
        config.set_alignment_axes("A", "B")
        return config

    @classmethod
    def create_4axis_A_config(cls, a_limits=(-120, 120)):
        """Create standard 4-axis XYZA configuration (rotary table around X)"""
        config = cls("4-Axis XYZA Configuration")
        config.machine_type = "xyza"
        config.add_linear_axis("X", FreeCAD.Vector(1, 0, 0))
        config.add_linear_axis("Y", FreeCAD.Vector(0, 1, 0))
        config.add_linear_axis("Z", FreeCAD.Vector(0, 0, 1))
        config.add_rotary_axis("A", FreeCAD.Vector(1, 0, 0), a_limits[0], a_limits[1])
        config.set_alignment_axes("A", None)
        config.description = "4-axis machine with A-axis rotary table (rotation around X-axis)"
        return config

    @classmethod
    def create_4axis_B_config(cls, b_limits=(-120, 120)):
        """Create standard 4-axis XYZB configuration (rotary table around Y)"""
        config = cls("4-Axis XYZB Configuration")
        config.machine_type = "xyzb"
        config.add_linear_axis("X", FreeCAD.Vector(1, 0, 0))
        config.add_linear_axis("Y", FreeCAD.Vector(0, 1, 0))
        config.add_linear_axis("Z", FreeCAD.Vector(0, 0, 1))
        config.add_rotary_axis("B", FreeCAD.Vector(0, 1, 0), b_limits[0], b_limits[1])
        config.set_alignment_axes("B", None)
        config.description = "4-axis machine with B-axis rotary table (rotation around Y-axis)"
        return config

    @classmethod
    def create_3axis_config(cls):
        """Create standard 3-axis XYZ configuration (no rotary axes)"""
        config = cls("3-Axis XYZ Configuration")
        config.machine_type = "xyz"
        config.add_linear_axis("X", FreeCAD.Vector(1, 0, 0))
        config.add_linear_axis("Y", FreeCAD.Vector(0, 1, 0))
        config.add_linear_axis("Z", FreeCAD.Vector(0, 0, 1))
        config.description = "Standard 3-axis machine with no rotary axes"
        # No rotary axes to add, no alignment axes to set
        return config

    def to_dict(self):
        """Serialize configuration to dictionary for JSON persistence"""
        # Build flattened axes structure
        axes = {}

        # Add linear axes from LinearAxis objects
        for axis_name, axis_obj in self.linear_axes.items():
            dir_vec = axis_obj.direction_vector
            joint = [[dir_vec.x, dir_vec.y, dir_vec.z], [0, 0, 0]]

            axes[axis_name] = {
                "type": "linear",
                "min": axis_obj.min_limit,
                "max": axis_obj.max_limit,
                "max_velocity": axis_obj.max_velocity,
                "joint": joint,
                "sequence": axis_obj.sequence,
            }

        # Add rotary axes
        for axis_name, axis_obj in self.rotary_axes.items():
            rot_vec = axis_obj.rotation_vector
            joint = [[0, 0, 0], [rot_vec.x, rot_vec.y, rot_vec.z]]
            axes[axis_name] = {
                "type": "angular",
                "min": axis_obj.min_limit,
                "max": axis_obj.max_limit,
                "max_velocity": axis_obj.max_velocity,
                "joint": joint,
                "sequence": axis_obj.sequence,
                "prefer_positive": axis_obj.prefer_positive,
            }

        data = {
            "freecad_version": self.freecad_version,
            "machine": {
                "name": self.name,
                "manufacturer": self.manufacturer,
                "description": self.description,
                "type": self.machine_type,
                "units": self.units,
                "axes": axes,
                "spindles": [spindle.to_dict() for spindle in self.spindles],
            },
            "version": self.version,
        }

        # Add post-processor configuration
        data["postprocessor"] = {
            "file_name": self.postprocessor_file_name,
            "args": self.postprocessor_args,
            "motion_mode": self.motion_mode.value,
            "use_tlo": self.use_tlo,
            "stop_spindle_for_tool_change": self.stop_spindle_for_tool_change,
            "enable_coolant": self.enable_coolant,
            "enable_machine_specific_commands": self.enable_machine_specific_commands,
        }
        
        # Output options
        data["output"] = {
            "comments": self.output.comments,
            "blank_lines": self.output.blank_lines,
            "header": self.output.header,
            "line_numbers": self.output.line_numbers,
            "bcnc_blocks": self.output.bcnc_blocks,
            "path_labels": self.output.path_labels,
            "machine_name": self.output.machine_name,
            "tool_change": self.output.tool_change,
            "doubles": self.output.doubles,
            "adaptive": self.output.adaptive,
        }
        
        # Precision settings
        data["precision"] = {
            "axis_precision": self.precision.axis_precision,
            "feed_precision": self.precision.feed_precision,
            "spindle_decimals": self.precision.spindle_decimals,
        }
        
        # Formatting
        data["formatting"] = {
            "command_space": self.formatting.command_space,
            "comment_symbol": self.formatting.comment_symbol,
            "line_increment": self.formatting.line_increment,
            "line_number_start": self.formatting.line_number_start,
            "end_of_line_chars": self.formatting.end_of_line_chars,
        }
        
        # G-code blocks (only non-empty ones)
        blocks = {}
        if self.blocks.preamble:
            blocks["preamble"] = self.blocks.preamble
        if self.blocks.postamble:
            blocks["postamble"] = self.blocks.postamble
        if self.blocks.safetyblock:
            blocks["safetyblock"] = self.blocks.safetyblock
        if self.blocks.pre_operation:
            blocks["pre_operation"] = self.blocks.pre_operation
        if self.blocks.post_operation:
            blocks["post_operation"] = self.blocks.post_operation
        if self.blocks.tool_return:
            blocks["tool_return"] = self.blocks.tool_return
        if blocks:
            data["blocks"] = blocks
        
        # Processing options
        data["processing"] = {
            "modal": self.processing.modal,
            "translate_drill_cycles": self.processing.translate_drill_cycles,
            "split_arcs": self.processing.split_arcs,
            "show_editor": self.processing.show_editor,
            "list_tools_in_preamble": self.processing.list_tools_in_preamble,
            "show_machine_units": self.processing.show_machine_units,
            "show_operation_labels": self.processing.show_operation_labels,
            "tool_before_change": self.processing.tool_before_change,
            "chipbreaking_amount": self.processing.chipbreaking_amount,
            "spindle_wait": self.processing.spindle_wait,
        }
        if self.processing.return_to:
            data["processing"]["return_to"] = list(self.processing.return_to)

        return data

    @classmethod
    def from_dict(cls, data):
        """Deserialize configuration from dictionary (supports both old and new formats)"""
        # Handle new flattened format
        if "machine" in data:
            machine = data["machine"]
            config = cls(machine.get("name", "Loaded Machine"))
            config.manufacturer = machine.get("manufacturer", "")
            config.description = machine.get("description", "")
            config.machine_type = machine.get("type", "custom")
            config.units = machine.get("units", "metric")
            config.version = data.get("version", 1)
            config.freecad_version = data.get("freecad_version", ".".join(FreeCAD.Version()[0:3]))

            # Parse axes from new flattened structure
            axes = machine.get("axes", {})
            config.linear_axes = {}
            config.rotary_axes = {}

            # Determine primary/secondary rotary axes
            rotary_axis_names = [
                name for name, axis_data in axes.items() if axis_data.get("type") == "angular"
            ]
            rotary_axis_names.sort()  # Sort to get consistent ordering

            for axis_name, axis_data in axes.items():
                axis_type = axis_data.get("type", "linear")

                if axis_type == "linear":
                    # Extract direction vector from joint
                    joint = axis_data.get("joint", [[1, 0, 0], [0, 0, 0]])
                    direction_vec = FreeCAD.Vector(joint[0][0], joint[0][1], joint[0][2])

                    min_limit = axis_data.get("min", 0)
                    max_limit = axis_data.get("max", 1000)
                    max_velocity = axis_data.get("max_velocity", 10000)
                    sequence = axis_data.get("sequence", 0)

                    config.linear_axes[axis_name] = LinearAxis(
                        axis_name, direction_vec, min_limit, max_limit, max_velocity, sequence
                    )
                else:  # angular
                    # Extract rotation vector from joint
                    joint = axis_data.get("joint", [[0, 0, 0], [1, 0, 0]])
                    rotation_vec = FreeCAD.Vector(joint[1][0], joint[1][1], joint[1][2])

                    min_limit = axis_data.get("min", -360)
                    max_limit = axis_data.get("max", 360)
                    max_velocity = axis_data.get("max_velocity", 36000)
                    sequence = axis_data.get("sequence", 0)
                    prefer_positive = axis_data.get("prefer_positive", True)

                    config.rotary_axes[axis_name] = RotaryAxis(
                        axis_name,
                        rotation_vec,
                        min_limit,
                        max_limit,
                        max_velocity,
                        sequence,
                        prefer_positive,
                    )

            # Set primary/secondary based on sequence numbers
            if len(rotary_axis_names) >= 1:
                # Sort rotary axes by sequence number
                rotary_axes_by_sequence = sorted(
                    [(name, config.rotary_axes[name].sequence) for name in rotary_axis_names],
                    key=lambda x: x[1],
                )

                # Primary is the one with lowest sequence number (0)
                config.primary_rotary_axis = rotary_axes_by_sequence[0][0]

                # Secondary is the one with next sequence number (1), if it exists
                if len(rotary_axes_by_sequence) >= 2:
                    config.secondary_rotary_axis = rotary_axes_by_sequence[1][0]
                else:
                    config.secondary_rotary_axis = None
            else:
                config.primary_rotary_axis = None
                config.secondary_rotary_axis = None

            config.compound_moves = True  # Default for new format

            # Deserialize spindles
            spindles_data = machine.get("spindles", [])
            config.spindles = [Spindle.from_dict(spindle_data) for spindle_data in spindles_data]

            # Load post-processor configuration
            if "postprocessor" in data:
                pp = data["postprocessor"]
                config.postprocessor_file_name = pp.get("file_name", "")
                config.postprocessor_args = pp.get("args", "")
                motion_mode_str = pp.get("motion_mode", "G90")
                config.motion_mode = MotionMode.ABSOLUTE if motion_mode_str == "G90" else MotionMode.RELATIVE
                config.use_tlo = pp.get("use_tlo", True)
                config.stop_spindle_for_tool_change = pp.get("stop_spindle_for_tool_change", True)
                config.enable_coolant = pp.get("enable_coolant", False)
                config.enable_machine_specific_commands = pp.get("enable_machine_specific_commands", False)
            
            # Load output options
            if "output" in data:
                out = data["output"]
                config.output.comments = out.get("comments", True)
                config.output.blank_lines = out.get("blank_lines", True)
                config.output.header = out.get("header", True)
                config.output.line_numbers = out.get("line_numbers", False)
                config.output.bcnc_blocks = out.get("bcnc_blocks", False)
                config.output.path_labels = out.get("path_labels", False)
                config.output.machine_name = out.get("machine_name", False)
                config.output.tool_change = out.get("tool_change", True)
                config.output.doubles = out.get("doubles", True)
                config.output.adaptive = out.get("adaptive", False)
            
            # Load precision settings
            if "precision" in data:
                prec = data["precision"]
                config.precision.axis_precision = prec.get("axis_precision", 3)
                config.precision.feed_precision = prec.get("feed_precision", 3)
                config.precision.spindle_decimals = prec.get("spindle_decimals", 0)
            
            # Load formatting
            if "formatting" in data:
                fmt = data["formatting"]
                config.formatting.command_space = fmt.get("command_space", " ")
                config.formatting.comment_symbol = fmt.get("comment_symbol", "(")
                config.formatting.line_increment = fmt.get("line_increment", 10)
                config.formatting.line_number_start = fmt.get("line_number_start", 100)
                config.formatting.end_of_line_chars = fmt.get("end_of_line_chars", "\n")
                config.formatting._current_line = config.formatting.line_number_start
            
            # Load G-code blocks
            if "blocks" in data:
                blk = data["blocks"]
                config.blocks.preamble = blk.get("preamble", "")
                config.blocks.postamble = blk.get("postamble", "")
                config.blocks.safetyblock = blk.get("safetyblock", "")
                config.blocks.pre_operation = blk.get("pre_operation", "")
                config.blocks.post_operation = blk.get("post_operation", "")
                config.blocks.tool_return = blk.get("tool_return", "")
            
            # Load processing options
            if "processing" in data:
                proc = data["processing"]
                config.processing.modal = proc.get("modal", False)
                config.processing.translate_drill_cycles = proc.get("translate_drill_cycles", False)
                config.processing.split_arcs = proc.get("split_arcs", False)
                config.processing.show_editor = proc.get("show_editor", True)
                config.processing.list_tools_in_preamble = proc.get("list_tools_in_preamble", False)
                config.processing.show_machine_units = proc.get("show_machine_units", True)
                config.processing.show_operation_labels = proc.get("show_operation_labels", True)
                config.processing.tool_before_change = proc.get("tool_before_change", False)
                config.processing.chipbreaking_amount = proc.get("chipbreaking_amount", 0.25)
                config.processing.spindle_wait = proc.get("spindle_wait", 0.0)
                if "return_to" in proc:
                    rt = proc["return_to"]
                    config.processing.return_to = tuple(rt) if rt else None

        return config


class MachineFactory:
    """Factory class for creating, loading, and saving machine configurations"""

    # Default configuration directory
    _config_dir = None

    @classmethod
    def set_config_directory(cls, directory):
        """Set the directory for storing machine configuration files"""
        cls._config_dir = pathlib.Path(directory)
        cls._config_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_config_directory(cls):
        """Get the configuration directory, creating default if not set"""
        if cls._config_dir is None:
            # Use FreeCAD user data directory + CAM/Machines
            try:
                cls._config_dir = Path.Preferences.getAssetPath() / "Machines"
                cls._config_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                Path.Log.warning(f"Could not create default config directory: {e}")
                cls._config_dir = pathlib.Path.cwd() / "Machines"
                cls._config_dir.mkdir(parents=True, exist_ok=True)
        return cls._config_dir

    @classmethod
    def save_configuration(cls, config, filename=None):
        """
        Save a machine configuration to a JSON file

        Args:
            config: Machine object to save
            filename: Optional filename (without path). If None, uses sanitized config name

        Returns:
            Path to the saved file
        """
        if filename is None:
            # Sanitize the config name for use as filename
            filename = config.name.replace(" ", "_").replace("/", "_") + ".fcm"

        config_dir = cls.get_config_directory()
        filepath = config_dir / filename

        try:
            data = config.to_dict()
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, sort_keys=True, indent=4)
            Path.Log.debug(f"Saved machine file: {filepath}")
            return filepath
        except Exception as e:
            Path.Log.error(f"Failed to save configuration: {e}")
            raise Exception(f"Failed to save machine file {filepath}: {e}")

    @classmethod
    def load_configuration(cls, filename):
        """
        Load a machine configuration from a JSON file

        Args:
            filename: Filename (with or without path). If no path, searches config directory

        Returns:
            Dictionary containing machine configuration data (new format) or
            Machine object if loading old format

        Raises:
            FileNotFoundError: If the file does not exist
            json.JSONDecodeError: If the file is not valid JSON
            Exception: For other I/O errors
        """
        filepath = pathlib.Path(filename)

        # If no directory specified, look in config directory
        if not filepath.parent or filepath.parent == pathlib.Path("."):
            filepath = cls.get_config_directory() / filename

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            Path.Log.debug(f"Loaded machine file: {filepath}")
            machine = Machine.from_dict(data)
            Path.Log.debug(f"Loaded machine configuration from {filepath}")
            return machine

        except FileNotFoundError:
            raise FileNotFoundError(f"Machine file not found: {filepath}")
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Invalid JSON in machine file {filepath}: {e}")
        except Exception as e:
            raise Exception(f"Failed to load machine file {filepath}: {e}")

    @classmethod
    def list_configuration_files(cls) -> list[tuple[str, pathlib.Path]]:
        """Get list of available machine files from the asset directory.

        Scans the Machine subdirectory of the asset path for .fcm files
        and returns tuples of (display_name, file_path).

        Returns:
            list: List of (name, path) tuples for discovered machine files
        """
        machines = [("<any>", None)]
        try:
            asset_base = cls.get_config_directory()
            if asset_base.exists():
                for p in sorted(asset_base.glob("*.fcm")):
                    name = cls.get_machine_display_name(p.name)
                    machines.append((name, p.name))
        except Exception:
            pass
        return machines

    @classmethod
    def list_configurations(cls) -> list[str]:
        """Get list of available machines from the asset directory.

        Scans the Machine subdirectory of the asset path for .fcm files
        and extracts machine names. Returns ["<any>"] plus discovered machine names.

        Returns:
            list: List of machine names starting with "<any>"
        """
        machines = cls.list_configuration_files()
        return [name for name, path in machines]

    @classmethod
    def delete_configuration(cls, filename):
        """
        Delete a machine configuration file

        Args:
            filename: Name of the configuration file to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        filepath = cls.get_config_directory() / filename
        try:
            if filepath.exists():
                filepath.unlink()
                Path.Log.debug(f"Deleted machine: {filepath}")
                return True
            else:
                Path.Log.warning(f"Machine file not found: {filepath}")
                return False
        except Exception as e:
            Path.Log.error(f"Failed to delete machine: {e}")
            return False

    @classmethod
    def create_standard_configs(cls):
        """
        Create and save all standard machine configurations

        Returns:
            Dictionary mapping config names to file paths
        """
        configs = {
            "XYZ": Machine.create_3axis_config(),
            "XYZAC": Machine.create_AC_table_config(),
            "XYZBC": Machine.create_BC_head_config(),
            "XYZA": Machine.create_4axis_A_config(),
            "XYZB": Machine.create_4axis_B_config(),
        }

        saved_paths = {}
        for name, config in configs.items():
            try:
                filepath = cls.save_configuration(config, f"{name}.fcm")
                saved_paths[name] = filepath
            except Exception as e:
                Path.Log.error(f"Failed to save {name}: {e}")

        return saved_paths

    @classmethod
    def get_builtin_config(cls, config_type):
        """
        Get a built-in machine configuration without loading from disk

        Args:
            config_type: One of "XYZ", "XYZAC", "XYZBC", "XYZA", "XYZB"

        Returns:
            Machine object
        """
        config_map = {
            "XYZ": Machine.create_3axis_config,
            "XYZAC": Machine.create_AC_table_config,
            "XYZBC": Machine.create_BC_head_config,
            "XYZA": Machine.create_4axis_A_config,
            "XYZB": Machine.create_4axis_B_config,
        }

        if config_type not in config_map:
            raise ValueError(
                f"Unknown config type: {config_type}. Available: {list(config_map.keys())}"
            )

        return config_map[config_type]()

    @classmethod
    def get_machine(cls, machine_name):
        """
        Get a machine configuration by name from the assets folder

        Args:
            machine_name: Name of the machine to load (without .fcm extension)

        Returns:
            Machine object

        Raises:
            FileNotFoundError: If no machine with that name is found
            ValueError: If the loaded data is not a valid machine configuration
        """
        # Get list of available machine files
        machine_files = cls.list_configuration_files()

        # Find the file matching the machine name (case-insensitive)
        target_path = None
        machine_name_lower = machine_name.lower()
        for name, path in machine_files:
            if name.lower() == machine_name_lower and path is not None:
                target_path = path
                break

        if target_path is None:
            available = [name for name, path in machine_files if path is not None]
            raise FileNotFoundError(
                f"Machine '{machine_name}' not found. Available machines: {available}"
            )

        # Load the configuration using the path from list_configuration_files()
        data = cls.load_configuration(target_path)

        # If load_configuration returned a dict (new format), convert to Machine
        if isinstance(data, dict):
            return Machine.from_dict(data)
        else:
            # Already a Machine object (old format)
            return data

    @classmethod
    def get_machine_display_name(cls, filename):
        """
        Get the display name for a machine from its filename in the config directory.

        Args:
            filename: Name of the machine file (without path)

        Returns:
            str: Display name (machine name from JSON or filename stem)
        """
        filepath = cls.get_config_directory() / filename
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("machine", {}).get("name", filepath.stem)
        except Exception:
            return filepath.stem
