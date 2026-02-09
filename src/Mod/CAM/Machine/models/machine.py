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


class OutputUnits(Enum):
    """Output unit system for G-code generation."""

    METRIC = "metric"
    IMPERIAL = "imperial"


# ============================================================================
# Post-Processor Configuration Dataclasses
# ============================================================================


@dataclass
class HeaderOptions:
    """Controls what gets included in the G-code header."""
    
    include_date: bool = True
    include_description: bool = True
    include_document_name: bool = True
    include_machine_name: bool = True
    include_project_file: bool = True
    include_units: bool = True
    include_tool_list: bool = True
    include_fixture_list: bool = True


@dataclass
class CommentOptions:
    """Controls comment formatting and inclusion."""
    
    enabled: bool = True
    symbol: str = "("
    include_operation_labels: bool = False
    include_blank_lines: bool = True
    output_bcnc_comments: bool = False


@dataclass
class FormattingOptions:
    """Controls line numbering and spacing."""
    
    line_numbers: bool = False
    line_number_start: int = 100
    line_number_prefix: str = "N"
    line_increment: int = 10
    command_space: str = " "
    end_of_line_chars: str = "\n"


@dataclass
class PrecisionOptions:
    """Controls numeric precision settings."""
    
    axis: int = 3
    feed: int = 3
    spindle: int = 0


@dataclass
class DuplicateOptions:
    """Controls duplicate output (positive framing: True = output duplicates, False = suppress)."""
    
    commands: bool = True  # When False, suppress repeated G/M codes (modal)
    parameters: bool = True  # When False, suppress repeated parameter values (modal)


@dataclass
class OutputOptions:
    """Controls what gets included in the G-code output and its formatting."""

    # Main output options
    units: OutputUnits = OutputUnits.METRIC  # G-code output units
    output_tool_length_offset: bool = True  # Output G43 H{tool} after M6 tool changes
    remote_post: bool = False  # Enable remote posting to network endpoint
    output_header: bool = True  # Control entire header output independently of comments

    # Nested configuration sections
    header: HeaderOptions = field(default_factory=HeaderOptions)
    comments: CommentOptions = field(default_factory=CommentOptions)
    formatting: FormattingOptions = field(default_factory=FormattingOptions)
    precision: PrecisionOptions = field(default_factory=PrecisionOptions)
    duplicates: DuplicateOptions = field(default_factory=DuplicateOptions)


@dataclass
class ProcessingOptions:
    """Processing and transformation options."""

    # Conversion and expansion of Path Objects. Does not affect final gcode generation

    early_tool_prep: bool = False  # Prepare tool before operation (affects postlist ordering)
    filter_inefficient_moves: bool = False  # Collapse redundant G0 rapid move chains
    split_arcs: bool = False
    tool_change: bool = True  # Enable tool change commands
    translate_rapid_moves: bool = False
    xy_before_z_after_tool_change: bool = False  # Decompose first move after tool change: XY first, then Z

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
        """Normalize direction vector and validate parameters after initialization"""
        self.direction_vector = self.direction_vector.normalize()

        # Validate limits
        if self.min_limit >= self.max_limit:
            Path.Log.warning(
                f"LinearAxis {self.name}: min_limit ({self.min_limit}) >= max_limit ({self.max_limit})"
            )

        # Validate velocity
        if self.max_velocity <= 0:
            Path.Log.warning(
                f"LinearAxis {self.name}: max_velocity must be positive, got {self.max_velocity}"
            )

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
        """Normalize rotation vector and validate parameters after initialization"""
        if self.rotation_vector is None or self.rotation_vector.Length < 1e-6:
            # Default to Z-axis rotation if vector is null or zero-length
            self.rotation_vector = FreeCAD.Vector(0, 0, 1)
        else:
            self.rotation_vector = self.rotation_vector.normalize()

        # Validate limits
        if self.min_limit >= self.max_limit:
            Path.Log.warning(
                f"RotaryAxis {self.name}: min_limit ({self.min_limit}) >= max_limit ({self.max_limit})"
            )

        # Validate velocity
        if self.max_velocity <= 0:
            Path.Log.warning(
                f"RotaryAxis {self.name}: max_velocity must be positive, got {self.max_velocity}"
            )

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


from enum import Enum


class SpindleType(Enum):
    """Types of spindles/tools supported by the machine."""
    ROTARY = "rotary"           # Traditional rotary spindle (router, drill, etc.)
    LASER = "laser"            # Laser cutting/engraving
    WATERJET = "waterjet"      # Waterjet cutting
    PLASMA = "plasma"          # Plasma cutting



@dataclass
class SpindleCapabilities:
    """Defines the capabilities of a spindle based on its type."""
    
    # Motion capabilities
    can_rotate: bool = True
    can_move_z: bool = True
    can_move_xy: bool = False
    
    # Power control
    has_power_control: bool = True
    has_speed_control: bool = True
    has_pulse_control: bool = False  # For lasers
    
    # Coolant/support systems
    uses_coolant: bool = False
    uses_assist_gas: bool = False    # For plasma/laser
    uses_water: bool = False          # For waterjet
    
    # Special capabilities
    can_turn_on_off: bool = True
    has_probing: bool = False
    has_auto_focus: bool = False     # For lasers
    
    @classmethod
    def for_type(cls, spindle_type: SpindleType) -> "SpindleCapabilities":
        """Get default capabilities for a given spindle type."""
        capabilities = {
            SpindleType.ROTARY: cls(
                can_rotate=True, can_move_z=True, can_move_xy=False,
                has_power_control=True, has_speed_control=True, has_pulse_control=False,
                uses_coolant=True, uses_assist_gas=False, uses_water=False,
                can_turn_on_off=True, has_probing=False, has_auto_focus=False
            ),
            SpindleType.LASER: cls(
                can_rotate=False, can_move_z=True, can_move_xy=False,
                has_power_control=True, has_speed_control=False, has_pulse_control=True,
                uses_coolant=False, uses_assist_gas=True, uses_water=False,
                can_turn_on_off=True, has_probing=False, has_auto_focus=True
            ),
            SpindleType.WATERJET: cls(
                can_rotate=False, can_move_z=True, can_move_xy=False,
                has_power_control=True, has_speed_control=False, has_pulse_control=False,
                uses_coolant=False, uses_assist_gas=False, uses_water=True,
                can_turn_on_off=True, has_probing=False, has_auto_focus=False
            ),
            SpindleType.PLASMA: cls(
                can_rotate=False, can_move_z=True, can_move_xy=False,
                has_power_control=True, has_speed_control=False, has_pulse_control=False,
                uses_coolant=False, uses_assist_gas=True, uses_water=False,
                can_turn_on_off=True, has_probing=False, has_auto_focus=False
            ),
        }
        return capabilities.get(spindle_type, capabilities[SpindleType.ROTARY])


@dataclass
class Spindle:
    """Represents a single spindle/tool in a machine configuration"""

    name: str
    spindle_type: SpindleType = SpindleType.ROTARY
    id: Optional[str] = None
    
    # Power and performance specifications
    max_power_kw: float = 0
    max_rpm: float = 0  # Only relevant for rotary spindles
    min_rpm: float = 0  # Only relevant for rotary spindles
    
    # Tool change and handling
    tool_change: str = "manual"
    tool_axis: Optional[FreeCAD.Vector] = None
    
    # Coolant and support systems
    coolant_flood: bool = False
    coolant_mist: bool = False
    coolant_delay: float = 0.0
    
    # Timing and control
    spindle_wait: float = 0.0  # seconds to wait after spindle start
    power_on_delay: float = 0.0  # seconds to wait for power stabilization
    
    # Type-specific parameters
    laser_wavelength: Optional[float] = None  # nm, for lasers
    laser_focus_range: Optional[Tuple[float, float]] = None  # min/max focus distance
    waterjet_pressure: Optional[float] = None  # bar, for waterjets
    plasma_amperage: Optional[float] = None  # amps, for plasma
    
    # Capabilities (auto-generated based on type)
    capabilities: Optional[SpindleCapabilities] = None

    def __post_init__(self):
        """Set default values and capabilities"""
        if self.tool_axis is None:
            self.tool_axis = FreeCAD.Vector(0, 0, -1)
        
        if self.capabilities is None:
            self.capabilities = SpindleCapabilities.for_type(self.spindle_type)
        
        # Set type-specific defaults
        if self.spindle_type == SpindleType.LASER:
            if self.laser_wavelength is None:
                self.laser_wavelength = 1064.0  # Default fiber laser wavelength
        elif self.spindle_type == SpindleType.WATERJET:
            if self.waterjet_pressure is None:
                self.waterjet_pressure = 4000.0  # Default 4000 bar
        elif self.spindle_type == SpindleType.PLASMA:
            if self.plasma_amperage is None:
                self.plasma_amperage = 45.0  # Default 45 amps

    def is_rotary(self) -> bool:
        """Check if this is a rotary spindle."""
        return self.spindle_type == SpindleType.ROTARY

    def is_laser(self) -> bool:
        """Check if this is a laser spindle."""
        return self.spindle_type == SpindleType.LASER

    def is_waterjet(self) -> bool:
        """Check if this is a waterjet spindle."""
        return self.spindle_type == SpindleType.WATERJET

    def is_plasma(self) -> bool:
        """Check if this is a plasma spindle."""
        return self.spindle_type == SpindleType.PLASMA

    def can_use_coolant(self) -> bool:
        """Check if this spindle can use coolant."""
        return self.capabilities.uses_coolant if self.capabilities else False

    def can_control_speed(self) -> bool:
        """Check if this spindle can control speed."""
        return self.capabilities.has_speed_control if self.capabilities else False

    def can_control_power(self) -> bool:
        """Check if this spindle can control power."""
        return self.capabilities.has_power_control if self.capabilities else False

    def to_dict(self):
        """Serialize to dictionary for JSON persistence"""
        data = {
            "name": self.name,
            "spindle_type": self.spindle_type.value,
            "max_power_kw": self.max_power_kw,
            "max_rpm": self.max_rpm,
            "min_rpm": self.min_rpm,
            "tool_change": self.tool_change,
            "tool_axis": [self.tool_axis.x, self.tool_axis.y, self.tool_axis.z],
            "coolant_flood": self.coolant_flood,
            "coolant_mist": self.coolant_mist,
            "coolant_delay": self.coolant_delay,
            "spindle_wait": self.spindle_wait,
            "power_on_delay": self.power_on_delay,
        }
        
        # Add type-specific parameters
        if self.laser_wavelength is not None:
            data["laser_wavelength"] = self.laser_wavelength
        if self.laser_focus_range is not None:
            data["laser_focus_range"] = list(self.laser_focus_range)
        if self.waterjet_pressure is not None:
            data["waterjet_pressure"] = self.waterjet_pressure
        if self.plasma_amperage is not None:
            data["plasma_amperage"] = self.plasma_amperage
        
        if self.id is not None:
            data["id"] = self.id
            
        return data

    @classmethod
    def from_dict(cls, data):
        """Deserialize from dictionary"""
        tool_axis_data = data.get("tool_axis", [0, 0, -1])
        tool_axis = FreeCAD.Vector(tool_axis_data[0], tool_axis_data[1], tool_axis_data[2])
        
        # Parse spindle type
        spindle_type_str = data.get("spindle_type", "rotary")
        spindle_type = SpindleType(spindle_type_str)
        
        # Parse laser focus range
        laser_focus_range = None
        if "laser_focus_range" in data:
            focus_data = data["laser_focus_range"]
            laser_focus_range = (focus_data[0], focus_data[1])
        
        return cls(
            data["name"],
            spindle_type,
            data.get("id"),
            data.get("max_power_kw", 0),
            data.get("max_rpm", 0),
            data.get("min_rpm", 0),
            data.get("tool_change", "manual"),
            tool_axis,
            data.get("coolant_flood", False),
            data.get("coolant_mist", False),
            data.get("coolant_delay", 0.0),
            data.get("spindle_wait", 0.0),
            data.get("power_on_delay", 0.0),
            data.get("laser_wavelength"),
            laser_focus_range,
            data.get("waterjet_pressure"),
            data.get("plasma_amperage"),
        )


@dataclass
class Machine:
    """Represents a CNC machine configuration with axes, spindles, and output settings.

    This class encapsulates all machine parameters including linear and rotary axes,
    spindles, post-processor settings, and G-code generation options. It provides
    methods for serialization to/from JSON and various factory methods for common
    machine configurations (3-axis, 4-axis, 5-axis).
    """

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

    # Machine components
    linear_axes: Dict[str, LinearAxis] = field(default_factory=dict)
    rotary_axes: Dict[str, RotaryAxis] = field(default_factory=dict)
    spindles: List[Spindle] = field(default_factory=list)

    # Coordinate system
    reference_system: Dict[str, FreeCAD.Vector] = field(
        default_factory=lambda: {
            "X": FreeCAD.Vector(1, 0, 0),
            "Y": FreeCAD.Vector(0, 1, 0),
            "Z": FreeCAD.Vector(0, 0, 1),
        }
    )
    tool_axis: FreeCAD.Vector = field(default_factory=lambda: FreeCAD.Vector(0, 0, -1))

    # Rotary axis configuration
    primary_rotary_axis: Optional[str] = None
    secondary_rotary_axis: Optional[str] = None
    compound_moves: bool = True
    prefer_positive_rotation: bool = True

    # Units and versioning
    configuration_units: str = "metric"  # Internal storage for configuration_units
    version: int = 1
    freecad_version: str = field(init=False)

    # ========================================================================
    # POST-PROCESSOR CONFIGURATION
    # ========================================================================

    # Output options
    output: OutputOptions = field(default_factory=OutputOptions)
    processing: ProcessingOptions = field(default_factory=ProcessingOptions)

    # Post-processor selection and configuration
    postprocessor_file_name: str = ""
    postprocessor_properties: Dict[str, Any] = field(default_factory=dict)

    # Dynamic state (for runtime)
    parameter_functions: Dict[str, Callable] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize computed fields and handle backward compatibility"""
        # Initialize computed fields
        self.freecad_version = ".".join(FreeCAD.Version()[0:3])

        # Validate configuration_units
        if self.configuration_units not in ["metric", "imperial"]:
            raise ValueError(
                f"configuration_units must be 'metric' or 'imperial', got '{self.configuration_units}'"
            )

    # ========================================================================
    # PROPERTIES - Bridge between physical machine and post-processor
    # ========================================================================

    @property
    def machine_units(self) -> MachineUnits:
        """Get machine configuration units as enum"""
        return (
            MachineUnits.METRIC if self.configuration_units == "metric" else MachineUnits.IMPERIAL
        )

    @property
    def output_machine_units(self) -> MachineUnits:
        """Get output units as enum for G-code generation"""
        return (
            MachineUnits.METRIC
            if self.output.output_units == OutputUnits.METRIC
            else MachineUnits.IMPERIAL
        )

    @property
    def gcode_units(self) -> MachineUnits:
        """Get G-code output units as enum for post-processor"""
        return (
            MachineUnits.METRIC
            if self.output.output_units == OutputUnits.METRIC
            else MachineUnits.IMPERIAL
        )

    @property
    def unit_format(self) -> str:
        """Get machine configuration unit format string (mm or in)"""
        return "mm" if self.configuration_units == "metric" else "in"

    @property
    def output_unit_format(self) -> str:
        """Get G-code output unit format string (mm or in)"""
        return "mm" if self.output.output_units == OutputUnits.METRIC else "in"

    @property
    def unit_speed_format(self) -> str:
        """Get machine configuration unit speed format string (mm/min or in/min)"""
        return "mm/min" if self.configuration_units == "metric" else "in/min"

    @property
    def output_unit_speed_format(self) -> str:
        """Get G-code output unit speed format string (mm/min or in/min)"""
        return "mm/min" if self.output.output_units == OutputUnits.METRIC else "in/min"

    @property
    def machine_type(self) -> str:
        """
        Determine machine type based on available axes.
        Returns one of: 'xyz', 'xyza', 'xyzb', 'xyzac', 'xyzbc', or 'custom'
        """
        if not all(axis in self.linear_axes for axis in ["X", "Y", "Z"]):
            return "custom"

        rot_axes = set(self.rotary_axes.keys())

        # Check for 5-axis configurations
        if {"A", "C"}.issubset(rot_axes):
            return "xyzac"
        if {"B", "C"}.issubset(rot_axes):
            return "xyzbc"

        # Check for 4-axis configurations
        if "A" in rot_axes:
            return "xyza"
        if "B" in rot_axes:
            return "xyzb"

        # 3-axis configuration
        return "xyz"

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
        # AB configuration will be detected as 'custom' by the machine_type property
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
                "units": self.configuration_units,
                "axes": axes,
                "spindles": [spindle.to_dict() for spindle in self.spindles],
            },
            "version": self.version,
        }

        # Add post-processor configuration
        data["postprocessor"] = {
            "file_name": self.postprocessor_file_name,
            "properties": self.postprocessor_properties,
        }

        # Output options
        data["output"] = {
            "units": self.output.units.value,
            "output_tool_length_offset": self.output.output_tool_length_offset,
            "remote_post": self.output.remote_post,
            "header": {
                "output_header": self.output.output_header,
                "include_date": self.output.header.include_date,
                "include_description": self.output.header.include_description,
                "include_document_name": self.output.header.include_document_name,
                "include_machine_name": self.output.header.include_machine_name,
                "include_project_file": self.output.header.include_project_file,
                "include_units": self.output.header.include_units,
                "include_tool_list": self.output.header.include_tool_list,
                "include_fixture_list": self.output.header.include_fixture_list,
            },
            "comments": {
                "enabled": self.output.comments.enabled,
                "symbol": self.output.comments.symbol,
                "include_operation_labels": self.output.comments.include_operation_labels,
                "include_blank_lines": self.output.comments.include_blank_lines,
                "output_bcnc_comments": self.output.comments.output_bcnc_comments,
            },
            "formatting": {
                "line_numbers": self.output.formatting.line_numbers,
                "line_number_start": self.output.formatting.line_number_start,
                "line_number_prefix": self.output.formatting.line_number_prefix,
                "line_increment": self.output.formatting.line_increment,
                "command_space": self.output.formatting.command_space,
                "end_of_line_chars": self.output.formatting.end_of_line_chars,
            },
            "precision": {
                "axis": self.output.precision.axis,
                "feed": self.output.precision.feed,
                "spindle": self.output.precision.spindle,
            },
            "duplicates": {
                "commands": self.output.duplicates.commands,
                "parameters": self.output.duplicates.parameters,
            },
        }

        # Processing options
        data["processing"] = {
            "early_tool_prep": self.processing.early_tool_prep,
            "filter_inefficient_moves": self.processing.filter_inefficient_moves,
            "split_arcs": self.processing.split_arcs,
            "tool_change": self.processing.tool_change,
            "translate_rapid_moves": self.processing.translate_rapid_moves,
            "xy_before_z_after_tool_change": self.processing.xy_before_z_after_tool_change,
        }
        if self.processing.return_to:
            data["processing"]["return_to"] = list(self.processing.return_to)

        return data

    def _initialize_3axis_config(self) -> None:
        """Initialize as a standard 3-axis XYZ configuration (no rotary axes)"""
        self.linear_axes = {
            "X": LinearAxis("X", FreeCAD.Vector(1, 0, 0)),
            "Y": LinearAxis("Y", FreeCAD.Vector(0, 1, 0)),
            "Z": LinearAxis("Z", FreeCAD.Vector(0, 0, 1)),
        }
        self.rotary_axes = {}
        self.primary_rotary_axis = None
        self.secondary_rotary_axis = None
        self.compound_moves = True

    @classmethod
    def create_3axis_config(cls) -> "Machine":
        """Create standard 3-axis XYZ configuration (no rotary axes)"""
        config = cls("3-Axis XYZ Configuration")
        config._initialize_3axis_config()
        return config

    def _initialize_4axis_A_config(self, a_limits=(-120, 120)) -> None:
        """Initialize as a 4-axis XYZA configuration (rotary table around X)"""
        self._initialize_3axis_config()
        self.rotary_axes["A"] = RotaryAxis(
            "A", FreeCAD.Vector(1, 0, 0), min_limit=a_limits[0], max_limit=a_limits[1]
        )
        self.primary_rotary_axis = "A"

    def _initialize_4axis_B_config(self, b_limits=(-120, 120)) -> None:
        """Initialize as a 4-axis XYZB configuration (rotary table around Y)"""
        self._initialize_3axis_config()
        self.rotary_axes["B"] = RotaryAxis(
            "B", FreeCAD.Vector(0, 1, 0), min_limit=b_limits[0], max_limit=b_limits[1]
        )
        self.primary_rotary_axis = "B"

    def _initialize_AC_table_config(self, a_limits=(-120, 120), c_limits=(-360, 360)) -> None:
        """Initialize as a 5-axis AC table configuration"""
        self._initialize_4axis_A_config(a_limits)
        self.rotary_axes["C"] = RotaryAxis(
            "C", FreeCAD.Vector(0, 0, 1), min_limit=c_limits[0], max_limit=c_limits[1]
        )
        self.secondary_rotary_axis = "C"

    def _initialize_BC_head_config(self, b_limits=(-120, 120), c_limits=(-360, 360)) -> None:
        """Initialize as a 5-axis BC head configuration"""
        self._initialize_4axis_B_config(b_limits)
        self.rotary_axes["C"] = RotaryAxis(
            "C", FreeCAD.Vector(0, 0, 1), min_limit=c_limits[0], max_limit=c_limits[1]
        )
        self.secondary_rotary_axis = "C"

    def _initialize_from_machine_type(self, machine_type: str) -> None:
        """Initialize machine configuration based on machine type"""
        if machine_type == "xyz":
            self._initialize_3axis_config()
        elif machine_type == "xyza":
            self._initialize_4axis_A_config()
        elif machine_type == "xyzb":
            self._initialize_4axis_B_config()
        elif machine_type == "xyzac":
            self._initialize_AC_table_config()
        elif machine_type == "xyzbc":
            self._initialize_BC_head_config()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Machine":
        """Deserialize configuration from dictionary (supports both old and new formats)"""
        machine_data = data.get("machine", data)  # Support both old and new formats

        # Extract basic configuration
        config = cls(
            name=machine_data.get("name", "Loaded Machine"),
            configuration_units=machine_data.get("units", "metric"),
            manufacturer=machine_data.get("manufacturer", ""),
            description=machine_data.get("description", ""),
        )

        # Parse axes from new flattened structure
        axes = machine_data.get("axes", {})
        config.linear_axes = {}
        config.rotary_axes = {}

        # Determine primary/secondary rotary axes
        rotary_axis_names = [
            name for name, axis_data in axes.items() if axis_data.get("type") == "angular"
        ]
        rotary_axis_names.sort()  # Sort to get consistent ordering

        if len(rotary_axis_names) > 0:
            config.primary_rotary_axis = rotary_axis_names[0]
        if len(rotary_axis_names) > 1:
            config.secondary_rotary_axis = rotary_axis_names[1]

        # Parse linear and rotary axes
        for axis_name, axis_data in axes.items():
            axis_type = axis_data.get("type", "linear")

            if axis_type == "linear":
                # Extract direction vector from joint
                joint = axis_data.get("joint", [[1, 0, 0], [0, 0, 0]])
                direction_vec = FreeCAD.Vector(joint[0][0], joint[0][1], joint[0][2])

                min_limit = axis_data.get("min", 0)
                max_limit = axis_data.get("max", 1000)
                max_velocity = axis_data.get("max_velocity", 10000)

                config.linear_axes[axis_name] = LinearAxis(
                    name=axis_name,
                    direction_vector=direction_vec,
                    min_limit=min_limit,
                    max_limit=max_limit,
                    max_velocity=max_velocity,
                )
            elif axis_type == "angular":
                joint = axis_data.get("joint", [[0, 0, 0], [0, 0, 1]])
                rotation_vec = FreeCAD.Vector(joint[1][0], joint[1][1], joint[1][2])

                min_limit = axis_data.get("min", -360)
                max_limit = axis_data.get("max", 360)
                max_velocity = axis_data.get("max_velocity", 36000)
                prefer_positive = axis_data.get("prefer_positive", True)

                config.rotary_axes[axis_name] = RotaryAxis(
                    name=axis_name,
                    rotation_vector=rotation_vec,
                    min_limit=min_limit,
                    max_limit=max_limit,
                    max_velocity=max_velocity,
                    prefer_positive=prefer_positive,
                )

        # Parse spindles if present
        spindles = machine_data.get("spindles", [])
        config.spindles = [Spindle.from_dict(s) for s in spindles]

        # Parse post-processor settings if present
        post_data = data.get("postprocessor", {})
        if post_data:
            config.postprocessor_file_name = post_data.get("file_name", "")
            config.postprocessor_args = post_data.get("args", "")
            config.postprocessor_properties = post_data.get("properties", {})

        # Load output options
        output_data = data.get("output", {})
        if output_data:
            # Main output options
            output_units_str = output_data.get("units", "metric")
            config.output.units = (
                OutputUnits.METRIC if output_units_str == "metric" else OutputUnits.IMPERIAL
            )
            config.output.output_tool_length_offset = output_data.get("output_tool_length_offset", True)
            config.output.remote_post = output_data.get("remote_post", False)

            # Header options
            header_data = output_data.get("header", {})
            # Handle backward compatibility - if header is a bool, use it for include_date
            if isinstance(header_data, bool):
                # Old structure: header was a boolean controlling all header output
                config.output.output_header = header_data
                config.output.header.include_date = header_data
                config.output.header.include_description = header_data
                config.output.header.include_document_name = header_data
                config.output.header.include_machine_name = header_data
                config.output.header.include_project_file = header_data
                config.output.header.include_units = header_data
                config.output.header.include_tool_list = header_data
                config.output.header.include_fixture_list = header_data
            else:
                # New nested structure - output_header can be in header subsection or main output
                config.output.output_header = header_data.get("output_header", output_data.get("output_header", True))
                config.output.header.include_date = header_data.get("include_date", True)
                config.output.header.include_description = header_data.get("include_description", True)
                config.output.header.include_document_name = header_data.get("include_document_name", True)
                config.output.header.include_machine_name = header_data.get("include_machine_name", True)
                config.output.header.include_project_file = header_data.get("include_project_file", True)
                config.output.header.include_units = header_data.get("include_units", True)
                config.output.header.include_tool_list = header_data.get("include_tool_list", True)
                config.output.header.include_fixture_list = header_data.get("include_fixture_list", True)

            # Comment options
            comments_data = output_data.get("comments", {})
            # Handle backward compatibility - if comments is a bool, use it for enabled
            if isinstance(comments_data, bool):
                # Old structure: comments was a boolean controlling all comment output
                config.output.comments.enabled = comments_data
                config.output.comments.symbol = "("  # Default symbol
                config.output.comments.include_operation_labels = False
                config.output.comments.include_blank_lines = True
                config.output.comments.output_bcnc_comments = False
            else:
                # New nested structure
                config.output.comments.enabled = comments_data.get("enabled", True)
                config.output.comments.symbol = comments_data.get("symbol", "(")
                config.output.comments.include_operation_labels = comments_data.get("include_operation_labels", False)
                config.output.comments.include_blank_lines = comments_data.get("include_blank_lines", True)
                config.output.comments.output_bcnc_comments = comments_data.get("output_bcnc_comments", False)

            # Formatting options
            formatting_data = output_data.get("formatting", {})
            # Handle backward compatibility for old flat structure
            if "line_numbers" in output_data and not formatting_data:
                # Old structure: line_numbers was at top level
                config.output.formatting.line_numbers = output_data.get("line_numbers", False)
                config.output.formatting.line_number_start = output_data.get("line_number_start", 100)
                config.output.formatting.line_number_prefix = output_data.get("line_number_prefix", "N")
                config.output.formatting.line_increment = output_data.get("line_increment", 10)
                config.output.formatting.command_space = output_data.get("command_space", " ")
                config.output.formatting.end_of_line_chars = output_data.get("end_of_line_chars", "\n")
            else:
                # New nested structure
                config.output.formatting.line_numbers = formatting_data.get("line_numbers", False)
                config.output.formatting.line_number_start = formatting_data.get("line_number_start", 100)
                config.output.formatting.line_number_prefix = formatting_data.get("line_number_prefix", "N")
                config.output.formatting.line_increment = formatting_data.get("line_increment", 10)
                config.output.formatting.command_space = formatting_data.get("command_space", " ")
                config.output.formatting.end_of_line_chars = formatting_data.get("end_of_line_chars", "\n")

            # Precision options
            precision_data = output_data.get("precision", {})
            # Handle backward compatibility for old flat structure
            if "axis_precision" in output_data and not precision_data:
                # Old structure: axis_precision was at top level
                config.output.precision.axis = output_data.get("axis_precision", 3)
                config.output.precision.feed = output_data.get("feed_precision", 3)
                config.output.precision.spindle = output_data.get("spindle_precision", 0)
            else:
                # New nested structure
                config.output.precision.axis = precision_data.get("axis", 3)
                config.output.precision.feed = precision_data.get("feed", 3)
                config.output.precision.spindle = precision_data.get("spindle", 0)

            # Duplicate options
            duplicates_data = output_data.get("duplicates", {})
            # Handle backward compatibility for old flat structure
            if "output_duplicate_parameters" in output_data and not duplicates_data:
                # Old structure: output_duplicate_parameters was at top level
                config.output.duplicates.commands = output_data.get("output_duplicate_commands", True)
                config.output.duplicates.parameters = output_data.get("output_duplicate_parameters", True)
            else:
                # New nested structure
                config.output.duplicates.commands = duplicates_data.get("commands", True)
                config.output.duplicates.parameters = duplicates_data.get("parameters", True)

            # Handle legacy output_comments field (for backward compatibility)
            if "output_comments" in output_data and "comments" not in output_data:
                # Old structure: output_comments was a boolean
                config.output.comments.enabled = output_data.get("output_comments", True)

        # Load processing options
        processing_data = data.get("processing", {})
        if processing_data:
            config.processing.early_tool_prep = processing_data.get("early_tool_prep", False)
            config.processing.filter_inefficient_moves = processing_data.get(
                "filter_inefficient_moves", False
            )
            config.processing.split_arcs = processing_data.get("split_arcs", False)
            config.processing.tool_change = processing_data.get("tool_change", True)
            config.processing.translate_rapid_moves = processing_data.get(
                "translate_rapid_moves", False
            )
            config.processing.xy_before_z_after_tool_change = processing_data.get(
                "xy_before_z_after_tool_change", False
            )
            return_to = processing_data.get("return_to", None)
            config.processing.return_to = tuple(return_to) if return_to is not None else None

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
            raise ValueError(f"Invalid JSON in machine file {filepath}: {e}")
        except Exception as e:
            raise Exception(f"Failed to load machine file {filepath}: {e}")

    @classmethod
    def create_default_machine_data(cls):
        """
        Create a default machine configuration dictionary for the editor.

        Returns:
            Dictionary with default machine configuration structure
        """
        machine = Machine(name="New Machine")
        return machine.to_dict()

    @classmethod
    def list_builtin_templates(cls) -> list[tuple[str, str]]:
        """Get list of built-in machine templates.

        Scans the Machine/machines subdirectory for .fcm template files
        and returns tuples of (display_name, full_file_path).

        Returns:
            list: List of (name, path) tuples for built-in template files
        """
        templates = []
        try:
            # Get the built-in machines directory from FreeCAD installation
            machines_dir = (
                pathlib.Path(FreeCAD.getHomePath()) / "Mod" / "CAM" / "Machine" / "machines"
            )

            if machines_dir.exists():
                for machine_file in sorted(machines_dir.glob("*.fcm")):
                    display_name = machine_file.stem.replace("_", " ")
                    templates.append((display_name, str(machine_file)))
        except Exception as e:
            Path.Log.warning(f"Could not load built-in machine templates: {e}")

        return templates

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
            # Failed to access machine directory or read files, return default list only
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
