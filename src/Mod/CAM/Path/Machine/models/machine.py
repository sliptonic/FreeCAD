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
from typing import Dict, Any
from collections import namedtuple


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


class LinearAxis:
    """Represents a single linear axis in a machine configuration"""

    def __init__(
        self, name, direction_vector, min_limit=0, max_limit=1000, max_velocity=10000, sequence=0
    ):
        self.name = name  # Axis name (X, Y, Z)
        self.direction_vector = direction_vector.normalize()  # Vector representing axis direction
        self.min_limit = min_limit  # Minimum position
        self.max_limit = max_limit  # Maximum position
        self.max_velocity = max_velocity  # Maximum velocity
        self.sequence = sequence  # Order in motion chain

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


class RotaryAxis:
    """Represents a single rotary axis in a machine configuration"""

    def __init__(
        self,
        name,
        rotation_vector,
        min_limit=-360,
        max_limit=360,
        max_velocity=36000,
        sequence=0,
        prefer_positive=True,
    ):
        self.name = name  # Axis name (A, B, C)
        self.rotation_vector = rotation_vector.normalize()  # Vector representing rotation axis
        self.min_limit = min_limit  # Minimum angle in degrees
        self.max_limit = max_limit  # Maximum angle in degrees
        self.max_velocity = max_velocity  # Maximum angular velocity
        self.sequence = sequence  # Order in motion chain
        self.prefer_positive = prefer_positive  # Prefer positive rotation direction

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


class Spindle:
    """Represents a single spindle in a machine configuration"""

    def __init__(
        self,
        name,
        id=None,
        max_power_kw=0,
        max_rpm=0,
        min_rpm=0,
        tool_change="manual",
        tool_axis=None,
    ):
        self.name = name  # Spindle name (e.g., "Main Spindle")
        self.id = id  # Optional unique spindle ID (string, e.g., "S1")
        self.max_power_kw = max_power_kw  # Max power in kW
        self.max_rpm = max_rpm  # Max speed in RPM
        self.min_rpm = min_rpm  # Min speed in RPM
        self.tool_change = tool_change  # Tool change method ("manual" or "atc")
        self.tool_axis = (
            tool_axis if tool_axis is not None else FreeCAD.Vector(0, 0, -1)
        )  # Tool axis direction

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


class Machine:
    """Stores configuration data for rotation generation"""

    def __init__(self, name="Default Machine"):
        self.name = name
        self.manufacturer = ""  # Manufacturer name
        self.rotary_axes = {}  # Dictionary of RotaryAxis objects
        self.linear_axes = {}  # Dictionary of LinearAxis objects
        self.spindles = []  # List of Spindle objects
        self.reference_system = {  # Reference coordinate system vectors
            "X": FreeCAD.Vector(1, 0, 0),
            "Y": FreeCAD.Vector(0, 1, 0),
            "Z": FreeCAD.Vector(0, 0, 1),
        }
        self.tool_axis = FreeCAD.Vector(0, 0, -1)  # Default tool axis direction
        self.primary_rotary_axis = None  # Primary axis for alignment (e.g., "C")
        self.secondary_rotary_axis = None  # Secondary axis for alignment (e.g., "A")
        self.compound_moves = (
            True  # Combine axes in single commands (changed default to match test expectations)
        )
        self.prefer_positive_rotation = (
            True  # Prefer positive rotations when multiple solutions exist
        )
        self.description = ""  # Optional description of the machine
        self.machine_type = "custom"  # Machine type (xyz, xyzac, etc.)
        self.units = "metric"  # Machine units (metric or imperial)
        self.version = 1  # Machine configuration schema version
        self.freecad_version = ".".join(FreeCAD.Version()[0:3])  # FreeCAD version

        # Check experimental flag for machine post processor
        param = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/CAM")
        self.enable_machine_postprocessor = param.GetBool("EnableMachinePostprocessor", False)

        if self.enable_machine_postprocessor:
            self.post_processor = ""  # Default post processor
            self.post_processor_args = ""  # Default post processor arguments
            self.post_output_unit = "metric"  # Post processor output unit
            self.post_comments = True  # Include comments in output
            self.post_line_numbers = False  # Include line numbers in output
            self.post_tool_length_offset = True  # Include tool length offset

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
        """Serialize configuration to dictionary for JSON persistence (new flattened format)"""
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

        if self.enable_machine_postprocessor:
            data["post"] = {
                "output_unit": self.post_output_unit,
                "comments": self.post_comments,
                "line_numbers": self.post_line_numbers,
                "tool_length_offset": self.post_tool_length_offset,
                "processor": self.post_processor,
                "processor_args": self.post_processor_args,
            }

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

            # Load post processor settings if enabled
            if config.enable_machine_postprocessor:
                post_data = data.get("post", {})
                config.post_processor = post_data.get("processor", "")
                config.post_processor_args = post_data.get("processor_args", "")
                config.post_output_unit = post_data.get("output_unit", "metric")
                config.post_comments = post_data.get("comments", True)
                config.post_line_numbers = post_data.get("line_numbers", False)
                config.post_tool_length_offset = post_data.get("tool_length_offset", True)

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
