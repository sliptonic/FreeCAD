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


def validate_machine_schema(data: Dict[str, Any]) -> bool:
    """Validate machine configuration data schema.

    Args:
        data: Dictionary containing machine configuration data

    Returns:
        True if data is valid, False otherwise
    """
    # Minimal validation of required fields
    if "machine" not in data:
        return False
    m = data["machine"]
    if "name" not in m or "type" not in m:
        return False
    return True


def load_machine_file(path: str) -> Dict[str, Any]:
    """Load machine configuration from a JSON file.

    Args:
        path: Path to the .fcm machine file to load

    Returns:
        Dictionary containing machine configuration data

    Raises:
        FileNotFoundError: If the file does not exist
        json.JSONDecodeError: If the file is not valid JSON
        Exception: For other I/O errors
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        Path.Log.info(f"Loaded machine file: {path}")
        return data
    except FileNotFoundError:
        raise FileNotFoundError(f"Machine file not found: {path}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in machine file {path}: {e}")
    except Exception as e:
        raise Exception(f"Failed to load machine file {path}: {e}")


def save_machine_file(data: Dict[str, Any], path: str):
    """Save machine configuration to a JSON file.

    Args:
        data: Dictionary containing machine configuration data
        path: Path to save the .fcm machine file

    Raises:
        Exception: For I/O errors
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, sort_keys=True, indent=4)
        Path.Log.info(f"Saved machine file: {path}")
    except Exception as e:
        raise Exception(f"Failed to save machine file {path}: {e}")


def create_default_machine_data() -> Dict[str, Any]:
    """Create default machine configuration data.

    Returns:
        Dictionary with default machine configuration
    """
    return {
        "machine": {
            "name": "New Machine",
            "manufacturer": "",
            "description": "",
            "units": "metric",
            "type": "custom",
        },
        "post": {
            "output_unit": "metric",
            "comments": True,
            "line_numbers": {"enabled": True},
            "tool_length_offset": True,
        },
        "version": 1,
    }


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


class MachineConfiguration:
    """Stores configuration data for rotation generation"""

    def __init__(self, name="Default Machine"):
        self.name = name
        self.rotary_axes = {}  # Dictionary of RotaryAxis objects
        self.linear_axes = {}  # Dictionary of LinearAxis objects
        self.reference_system = {  # Reference coordinate system vectors
            "X": FreeCAD.Vector(1, 0, 0),
            "Y": FreeCAD.Vector(0, 1, 0),
            "Z": FreeCAD.Vector(0, 0, 1),
        }
        self.tool_axis = FreeCAD.Vector(0, 0, 1)  # Default tool axis direction
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
            Path.Log.info(f"Saved machine configuration to {filepath}")
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

        return {
            "freecad_version": self.freecad_version,
            "machine": {
                "name": self.name,
                "description": self.description,
                "type": self.machine_type,
                "units": self.units,
                "axes": axes,
                "spindles": [],  # Default empty spindles
            },
            "post": {
                "output_unit": "metric",
                "comments": True,
                "line_numbers": {"enabled": True},
                "tool_length_offset": True,
            },
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data):
        """Deserialize configuration from dictionary (supports both old and new formats)"""
        # Handle new flattened format
        if "machine" in data:
            machine = data["machine"]
            config = cls(machine.get("name", "Loaded Machine"))
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
                    key=lambda x: x[1]
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

        else:
            # Handle old format (for backward compatibility)
            config = cls(data["name"])
            config.description = data.get("description", "")

            # Convert old list format to new dict format
            old_linear_axes = data.get("linear_axes", ["X", "Y", "Z"])
            config.linear_axes = {}
            for axis_name in old_linear_axes:
                dir_vec = getattr(refAxis, axis_name.lower(), refAxis.x)
                config.linear_axes[axis_name] = LinearAxis(axis_name, dir_vec, 0, 1000, 10000)

            # if "tool_axis" in data:
            #     config.tool_axis = FreeCAD.Vector(
            #         data["tool_axis"][0], data["tool_axis"][1], data["tool_axis"][2]
            #     )

            # config.primary_rotary_axis = data.get("primary_rotary_axis")
            # config.secondary_rotary_axis = data.get("secondary_rotary_axis")
            # config.compound_moves = data.get("compound_moves", True)
            # config.prefer_positive_rotation = data.get("prefer_positive_rotation", True)

            # Deserialize rotary axes from old format
            for axis_name, axis_data in data.get("rotary_axes", {}).items():
                axis = RotaryAxis.from_dict(axis_data)
                config.rotary_axes[axis_name] = axis

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
            config: MachineConfiguration object to save
            filename: Optional filename (without path). If None, uses sanitized config name

        Returns:
            Path to the saved file
        """
        if filename is None:
            # Sanitize the config name for use as filename
            filename = config.name.replace(" ", "_").replace("/", "_") + ".json"

        config_dir = cls.get_config_directory()
        filepath = config_dir / filename

        try:
            data = config.to_dict()
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, sort_keys=True, indent=4)
            Path.Log.info(f"Saved machine file: {filepath}")
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
            MachineConfiguration object if loading old format

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
            Path.Log.info(f"Loaded machine file: {filepath}")

            # Return the raw dict for new format (has "machine" key)
            # This allows the editor to work with the full structure
            if "machine" in data:
                return data
            else:
                # Old format - convert to MachineConfiguration object
                config = MachineConfiguration.from_dict(data)
                Path.Log.info(f"Loaded machine configuration from {filepath}")
                return config

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
                    name = p.stem
                    try:
                        text = p.read_text(encoding="utf-8")
                        data = json.loads(text)
                        # Try to find display name inside JSON
                        display = None
                        if isinstance(data, dict):
                            display = data.get("machine", {}).get("name") or data.get("name")
                        if display:
                            name = display
                    except Exception:
                        # fallback to filename stem
                        pass
                    machines.append((name, p))
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
    def delete_configuration(cls, filepath):
        """
        Delete a machine configuration file

        Args:
            filename: Name of the configuration file to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            if filepath.exists():
                filepath.unlink()
                Path.Log.info(f"Deleted machine: {filepath}")
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
            "XYZ": MachineConfiguration.create_3axis_config(),
            "XYZAC": MachineConfiguration.create_AC_table_config(),
            "XYZBC": MachineConfiguration.create_BC_head_config(),
            "XYZA": MachineConfiguration.create_4axis_A_config(),
            "XYZB": MachineConfiguration.create_4axis_B_config(),
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
            MachineConfiguration object
        """
        config_map = {
            "XYZ": MachineConfiguration.create_3axis_config,
            "XYZAC": MachineConfiguration.create_AC_table_config,
            "XYZBC": MachineConfiguration.create_BC_head_config,
            "XYZA": MachineConfiguration.create_4axis_A_config,
            "XYZB": MachineConfiguration.create_4axis_B_config,
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
            MachineConfiguration object

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

        # If load_configuration returned a dict (new format), convert to MachineConfiguration
        if isinstance(data, dict):
            return MachineConfiguration.from_dict(data)
        else:
            # Already a MachineConfiguration object (old format)
            return data
