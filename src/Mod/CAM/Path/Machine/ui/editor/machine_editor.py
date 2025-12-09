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
from PySide import QtGui, QtCore
import FreeCAD
import json
from typing import Optional, Dict, Any
from ...models.machine import *
from ....Main.Gui.Editor import CodeEditor
import re
import os

translate = FreeCAD.Qt.translate


class MachineEditorDialog(QtGui.QDialog):
    """A dialog to edit machine JSON assets with proper form fields."""

    # Todo - Make this a json schema driven form in the future
    MACHINE_TYPES = {
        "custom": {
            "name": translate("CAM_MachineEditor", "Custom Machine"),
            "linear": [],
            "rotary": [],
        },
        "xz": {
            "name": translate("CAM_MachineEditor", "2-Axis Lathe (X, Z)"),
            "linear": ["X", "Z"],
            "rotary": [],
        },
        "xyz": {
            "name": translate("CAM_MachineEditor", "3-Axis Mill (XYZ)"),
            "linear": ["X", "Y", "Z"],
            "rotary": [],
        },
        "xyza": {
            "name": translate("CAM_MachineEditor", "4-Axis Mill (XYZ + A)"),
            "linear": ["X", "Y", "Z"],
            "rotary": ["A"],
        },
        "xyzb": {
            "name": translate("CAM_MachineEditor", "4-Axis Mill (XYZ + B)"),
            "linear": ["X", "Y", "Z"],
            "rotary": ["B"],
        },
        "xyzac": {
            "name": translate("CAM_MachineEditor", "5-Axis Mill (XYZ + A, C)"),
            "linear": ["X", "Y", "Z"],
            "rotary": ["A", "C"],
        },
        "xyzbc": {
            "name": translate("CAM_MachineEditor", "5-Axis Mill (XYZ + B, C)"),
            "linear": ["X", "Y", "Z"],
            "rotary": ["B", "C"],
        },
    }

    ROTATIONAL_AXIS_OPTIONS = [
        ("+X", [1, 0, 0]),
        ("-X", [-1, 0, 0]),
        ("+Y", [0, 1, 0]),
        ("-Y", [0, -1, 0]),
        ("+Z", [0, 0, 1]),
        ("-Z", [0, 0, -1]),
    ]

    def __init__(self, machine_filename: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(translate("CAM_MachineEditor", "Machine Editor"))
        self.setMinimumSize(700, 900)
        self.resize(700, 900)

        self.current_units = "metric"

        self.layout = QtGui.QVBoxLayout(self)

        # Tab widget for sections
        self.tabs = QtGui.QTabWidget()
        self.layout.addWidget(self.tabs)

        # Machine tab
        self.machine_tab = QtGui.QWidget()
        self.tabs.addTab(self.machine_tab, translate("CAM_MachineEditor", "Machine"))
        self.setup_machine_tab()

        # Post tab
        self.post_tab = QtGui.QWidget()
        self.tabs.addTab(self.post_tab, translate("CAM_MachineEditor", "Post Processor"))
        self.setup_post_tab()
        # Text editor (initially hidden)
        self.text_editor = CodeEditor()

        p = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Editor")
        font = QtGui.QFont()
        font.setFamily(p.GetString("Font", "Courier"))
        font.setFixedPitch(True)
        font.setPointSize(p.GetInt("FontSize", 10))

        self.text_editor.setFont(font)
        self.layout.addWidget(self.text_editor)
        self.text_editor.hide()

        button_layout = QtGui.QHBoxLayout()

        self.toggle_button = QtGui.QPushButton(translate("CAM_MachineEditor", "Edit as Text"))
        self.toggle_button.clicked.connect(self.toggle_editor_mode)
        button_layout.addWidget(self.toggle_button)

        button_layout.addStretch()

        buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Save | QtGui.QDialogButtonBox.Close,
            QtCore.Qt.Horizontal,
        )
        buttons.button(QtGui.QDialogButtonBox.Save).setText(translate("CAM_MachineEditor", "Save"))
        buttons.button(QtGui.QDialogButtonBox.Close).setText(
            translate("CAM_MachineEditor", "Close")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        button_layout.addWidget(buttons)

        self.layout.addLayout(button_layout)
        self.text_mode = False
        self.filename = machine_filename

        if machine_filename:
            data = MachineFactory.load_configuration(machine_filename)
            self.populate_from_data(data)
        else:
            self.set_defaults()
            # Set focus and select the name field for new machines
            self.name_edit.setFocus()
            self.name_edit.selectAll()

    def normalize_text(self, edit, suffix, axis=None, field=None):
        """Normalize and validate text input for numeric fields with units.

        Parses user input, converts between metric/imperial units, and ensures
        proper formatting. Updates stored data for axes configuration.

        Args:
            edit: QLineEdit widget to update
            suffix: Unit suffix (e.g., "mm", "in", "deg")
            axis: Axis identifier for data storage
            field: Field name for data storage
        """
        text = edit.text().strip()
        if not text:
            edit.setText("0 " + suffix)
            return

        # Parse input manually based on machine units
        machine_units = self.units_combo.itemData(self.units_combo.currentIndex())

        # Split number and unit
        match = re.match(r"^([+-]?\d*\.?\d+)\s*(.*)$", text)
        if not match:
            edit.setText("0 " + suffix)
            return

        num_str, unit_str = match.groups()
        try:
            value = float(num_str)
        except ValueError:
            edit.setText("0 " + suffix)
            return

        # Determine if this is a rotary axis by checking the suffix
        is_angular = suffix in ["deg", "deg/min"]

        # Convert to internal mm (or degrees for angles)
        if is_angular:
            # For rotary axes, always use degrees, no unit conversion
            if unit_str.strip():
                if unit_str.strip() in ["deg", "degree", "degrees", "°"]:
                    internal_value = value
                else:
                    # Unknown unit for angles, assume degrees
                    internal_value = value
            else:
                # No unit, assume degrees
                internal_value = value
        else:
            # Linear axes
            if unit_str.strip():
                if unit_str.strip() in ["mm", "millimeter", "millimeters"]:
                    internal_value = value
                elif unit_str.strip() in ["in", "inch", "inches", '"']:
                    internal_value = value * 25.4
                elif unit_str.strip() in ["cm", "centimeter", "centimeters"]:
                    internal_value = value * 10
                elif unit_str.strip() in ["m", "meter", "meters"]:
                    internal_value = value * 1000
                else:
                    # Unknown unit, assume machine units
                    if machine_units == "metric":
                        internal_value = value  # assume mm
                    else:
                        internal_value = value * 25.4  # assume in
            else:
                # No unit, assume machine units
                if machine_units == "metric":
                    internal_value = value  # assume mm
                else:
                    internal_value = value * 25.4  # assume in

        # Convert to display units
        if suffix == "mm":
            display_value = round(internal_value, 2)
        elif suffix == "in":
            display_value = round(internal_value / 25.4, 2)
        elif suffix == "mm/min":
            display_value = round(internal_value, 2)
        elif suffix == "in/min":
            display_value = round(internal_value / 25.4, 2)
        elif suffix == "deg":
            display_value = round(internal_value, 2)
        elif suffix == "deg/min":
            display_value = round(internal_value, 2)
        else:
            display_value = round(internal_value, 2)

        edit.setText(f"{display_value:.2f} {suffix}")

        # Update saved data (store in metric)
        if axis and field:
            if axis not in self.saved_axes_data:
                self.saved_axes_data[axis] = {}
            self.saved_axes_data[axis][field] = internal_value

    def setup_machine_tab(self):
        """Set up the machine configuration tab with form fields.

        Creates input fields for machine name, manufacturer, description,
        units, type, spindle count, axes configuration, and spindles.
        Connects change handlers for dynamic updates.
        """
        layout = QtGui.QFormLayout(self.machine_tab)

        self.name_edit = QtGui.QLineEdit()
        layout.addRow(translate("CAM_MachineEditor", "Name:"), self.name_edit)

        self.manufacturer_edit = QtGui.QLineEdit()
        layout.addRow(translate("CAM_MachineEditor", "Manufacturer:"), self.manufacturer_edit)

        self.description_edit = QtGui.QLineEdit()
        layout.addRow(translate("CAM_MachineEditor", "Description:"), self.description_edit)

        self.units_combo = QtGui.QComboBox()
        self.units_combo.addItem(translate("CAM_MachineEditor", "Metric"), "metric")
        self.units_combo.addItem(translate("CAM_MachineEditor", "Imperial"), "imperial")
        self.units_combo.currentIndexChanged.connect(self.update_axes)
        layout.addRow(translate("CAM_MachineEditor", "Units:"), self.units_combo)

        self.type_combo = QtGui.QComboBox()
        for key, value in self.MACHINE_TYPES.items():
            self.type_combo.addItem(value["name"], key)
        self.type_combo.currentIndexChanged.connect(self.update_axes)
        layout.addRow(translate("CAM_MachineEditor", "Type:"), self.type_combo)

        self.spindle_count_combo = QtGui.QComboBox()
        for i in range(1, 10):  # 1 to 9 spindles
            self.spindle_count_combo.addItem(str(i), i)
        self.spindle_count_combo.currentIndexChanged.connect(self.update_spindles)
        layout.addRow(
            translate("CAM_MachineEditor", "Number of Spindles:"), self.spindle_count_combo
        )

        # Axes group
        self.axes_group = QtGui.QGroupBox(translate("CAM_MachineEditor", "Axes"))
        self.axes_layout = QtGui.QVBoxLayout(self.axes_group)
        self.axes_group.setVisible(False)  # Initially hidden, shown when axes are configured
        self.saved_axes_data = {}  # Flattened: no linear/rotary split
        layout.addRow(self.axes_group)

        # Spindles group
        self.spindles_group = QtGui.QGroupBox(translate("CAM_MachineEditor", "Spindles"))
        spindles_layout = QtGui.QVBoxLayout(self.spindles_group)
        self.spindles_tabs = QtGui.QTabWidget()
        spindles_layout.addWidget(self.spindles_tabs)
        self.saved_spindle_data = []
        layout.addRow(self.spindles_group)

    def update_axes(self):
        """Update the axes configuration UI based on machine type and units.

        Dynamically creates input fields for all axes based on the selected
        machine type. Uses flattened structure with type property.
        """
        # Get current units for suffixes and conversion
        units = self.units_combo.itemData(self.units_combo.currentIndex())
        length_suffix = " mm" if units == "metric" else " in"
        vel_suffix = " mm/min" if units == "metric" else " in/min"
        angle_suffix = " deg"
        angle_vel_suffix = " deg/min"

        # Convert saved data if units changed
        if hasattr(self, "current_units") and self.current_units != units:
            self.current_units = units

        # Clear references before deleting widgets
        self.axis_edits = {}

        # Clear existing axes widgets
        for i in reversed(range(self.axes_layout.count())):
            widget = self.axes_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # Get current type
        type_key = self.type_combo.itemData(self.type_combo.currentIndex())
        if not type_key:
            return
        config = self.MACHINE_TYPES[type_key]

        # Create axes group
        all_axes = config.get("linear", []) + config.get("rotary", [])
        if not all_axes:
            self.axes_group.setVisible(False)
            return

        axes_form = QtGui.QFormLayout()

        # Separate linear and rotary axes
        # Use config template for new machines, or derive from saved_axes_data for loaded machines
        linear_axes = []
        rotary_axes = []

        # First, try to get from config template (for UI structure)
        template_linear = config.get("linear", [])
        template_rotary = config.get("rotary", [])

        # Build lists from template, but respect any loaded data
        for axis in template_linear:
            linear_axes.append(axis)
        for axis in template_rotary:
            rotary_axes.append(axis)

        # Linear axes
        if linear_axes:
            linear_group = QtGui.QGroupBox("Linear Axes")
            linear_layout = QtGui.QFormLayout(linear_group)

            for axis in linear_axes:
                saved_min = self.saved_axes_data.get(axis, {}).get("min", 0)
                converted_min = saved_min if units == "metric" else saved_min / 25.4
                min_edit = QtGui.QLineEdit()
                min_edit.setText(f"{converted_min:.2f}{length_suffix}")
                min_edit.editingFinished.connect(
                    lambda edit=min_edit, suffix=length_suffix.strip(), ax=axis, fld="min": self.normalize_text(
                        edit, suffix, ax, fld
                    )
                )

                saved_max = self.saved_axes_data.get(axis, {}).get("max", 1000)
                converted_max = saved_max if units == "metric" else saved_max / 25.4
                max_edit = QtGui.QLineEdit()
                max_edit.setText(f"{converted_max:.2f}{length_suffix}")
                max_edit.editingFinished.connect(
                    lambda edit=max_edit, suffix=length_suffix.strip(), ax=axis, fld="max": self.normalize_text(
                        edit, suffix, ax, fld
                    )
                )

                saved_vel = self.saved_axes_data.get(axis, {}).get("max_velocity", 10000)
                converted_vel = saved_vel if units == "metric" else saved_vel / 25.4
                vel_edit = QtGui.QLineEdit()
                vel_edit.setText(f"{converted_vel:.2f}{vel_suffix}")
                vel_edit.editingFinished.connect(
                    lambda edit=vel_edit, suffix=vel_suffix.strip(), ax=axis, fld="max_velocity": self.normalize_text(
                        edit, suffix, ax, fld
                    )
                )

                axis_layout = QtGui.QHBoxLayout()
                axis_layout.addWidget(QtGui.QLabel("Min:"))
                axis_layout.addWidget(min_edit)
                axis_layout.addWidget(QtGui.QLabel("Max:"))
                axis_layout.addWidget(max_edit)
                axis_layout.addWidget(QtGui.QLabel("Max Vel:"))
                axis_layout.addWidget(vel_edit)

                linear_layout.addRow(f"{axis}:", axis_layout)
                self.axis_edits[axis] = {
                    "min": min_edit,
                    "max": max_edit,
                    "max_velocity": vel_edit,
                    "type": "linear",
                }
            self.axes_layout.addWidget(linear_group)

        # Rotary axes
        if rotary_axes:
            rotary_group = QtGui.QGroupBox("Rotary Axes")
            rotary_layout = QtGui.QFormLayout(rotary_group)

            for axis in rotary_axes:
                min_edit = QtGui.QLineEdit()
                min_edit.setText(
                    f"{self.saved_axes_data.get(axis, {}).get('min', -180):.2f}{angle_suffix}"
                )
                min_edit.editingFinished.connect(
                    lambda edit=min_edit, suffix=angle_suffix.strip(), ax=axis, fld="min": self.normalize_text(
                        edit, suffix, ax, fld
                    )
                )

                max_edit = QtGui.QLineEdit()
                max_edit.setText(
                    f"{self.saved_axes_data.get(axis, {}).get('max', 180):.2f}{angle_suffix}"
                )
                max_edit.editingFinished.connect(
                    lambda edit=max_edit, suffix=angle_suffix.strip(), ax=axis, fld="max": self.normalize_text(
                        edit, suffix, ax, fld
                    )
                )

                vel_edit = QtGui.QLineEdit()
                vel_edit.setText(
                    f"{self.saved_axes_data.get(axis, {}).get('max_velocity', 36000):.2f}{angle_vel_suffix}"
                )
                vel_edit.editingFinished.connect(
                    lambda edit=vel_edit, suffix=angle_vel_suffix.strip(), ax=axis, fld="max_velocity": self.normalize_text(
                        edit, suffix, ax, fld
                    )
                )

                # Sequence number for rotary axes
                sequence_spin = QtGui.QSpinBox()
                sequence_spin.setRange(0, 10)
                sequence_spin.setValue(self.saved_axes_data.get(axis, {}).get("sequence", 0))

                # Joint (rotation axis) combo
                joint_combo = QtGui.QComboBox()
                for label, vector in self.ROTATIONAL_AXIS_OPTIONS:
                    joint_combo.addItem(label, vector)
                saved_joint = self.saved_axes_data.get(axis, {}).get(
                    "joint",
                    [
                        [0, 0, 0],
                        [1, 0, 0] if axis == "A" else [0, 1, 0] if axis == "B" else [0, 0, 1],
                    ],
                )
                # Use the second element of joint array (first is always [0,0,0])
                if len(saved_joint) == 2:
                    for i, (label, vector) in enumerate(self.ROTATIONAL_AXIS_OPTIONS):
                        if vector == saved_joint[1]:
                            joint_combo.setCurrentIndex(i)
                            break

                prefer_positive = QtGui.QCheckBox()
                prefer_positive.setChecked(
                    self.saved_axes_data.get(axis, {}).get("prefer_positive", True)
                )

                # Grid layout
                axis_grid = QtGui.QGridLayout()

                # Row 0: Min, Max, Vel
                axis_grid.addWidget(QtGui.QLabel("Min:"), 0, 0, QtCore.Qt.AlignRight)
                axis_grid.addWidget(min_edit, 0, 1)
                axis_grid.addWidget(QtGui.QLabel("Max:"), 0, 2, QtCore.Qt.AlignRight)
                axis_grid.addWidget(max_edit, 0, 3)
                axis_grid.addWidget(QtGui.QLabel("Max Vel:"), 0, 4, QtCore.Qt.AlignRight)
                axis_grid.addWidget(vel_edit, 0, 5)

                # Row 1: Sequence, Joint, Prefer+
                axis_grid.addWidget(QtGui.QLabel("Sequence:"), 1, 0, QtCore.Qt.AlignRight)
                axis_grid.addWidget(sequence_spin, 1, 1)
                axis_grid.addWidget(QtGui.QLabel("Joint:"), 1, 2, QtCore.Qt.AlignRight)
                axis_grid.addWidget(joint_combo, 1, 3)
                axis_grid.addWidget(QtGui.QLabel("Prefer+:"), 1, 4, QtCore.Qt.AlignRight)
                axis_grid.addWidget(prefer_positive, 1, 5)

                rotary_layout.addRow(f"{axis}:", axis_grid)
                self.axis_edits[axis] = {
                    "min": min_edit,
                    "max": max_edit,
                    "max_velocity": vel_edit,
                    "sequence": sequence_spin,
                    "joint": joint_combo,
                    "prefer_positive": prefer_positive,
                    "type": "angular",
                }
            self.axes_layout.addWidget(rotary_group)

        # Show axes group if any axes configured
        self.axes_group.setVisible(bool(linear_axes or rotary_axes))

    def update_spindles(self):
        """Update the spindle configuration UI based on spindle count.

        Dynamically creates tabbed interface for multiple spindles with
        input fields for name, ID, power, speed, and tool holder.
        Maintains spindle data across UI updates.
        """
        # Update saved data with current edits
        if hasattr(self, "spindle_edits"):
            for i, edits in enumerate(self.spindle_edits):
                if i >= len(self.saved_spindle_data):
                    self.saved_spindle_data.append({})
                self.saved_spindle_data[i] = {
                    "name": edits["name"].text(),
                    "id": edits["id"].text(),
                    "max_power_kw": edits["max_power_kw"].value(),
                    "max_rpm": edits["max_rpm"].value(),
                    "min_rpm": edits["min_rpm"].value(),
                    "tool_change": edits["tool_change"].itemData(
                        edits["tool_change"].currentIndex()
                    ),
                    "tool_axis": edits["tool_axis"].itemData(edits["tool_axis"].currentIndex()),
                }

        # Clear existing spindle tabs
        self.spindles_tabs.clear()
        self.spindle_edits = []
        count = self.spindle_count_combo.itemData(self.spindle_count_combo.currentIndex())
        for i in range(count):
            tab = QtGui.QWidget()
            layout = QtGui.QFormLayout(tab)

            name_edit = QtGui.QLineEdit()
            name_edit.setText(
                self.saved_spindle_data[i]["name"]
                if i < len(self.saved_spindle_data) and "name" in self.saved_spindle_data[i]
                else f"Spindle {i+1}"
            )
            layout.addRow("Name:", name_edit)

            id_edit = QtGui.QLineEdit()
            id_edit.setText(
                self.saved_spindle_data[i]["id"]
                if i < len(self.saved_spindle_data) and "id" in self.saved_spindle_data[i]
                else f"spindle{i+1}"
            )
            layout.addRow("ID:", id_edit)

            max_power_edit = QtGui.QDoubleSpinBox()
            max_power_edit.setRange(0, 100)
            max_power_edit.setValue(
                self.saved_spindle_data[i]["max_power_kw"]
                if i < len(self.saved_spindle_data) and "max_power_kw" in self.saved_spindle_data[i]
                else 3.0
            )
            layout.addRow("Max Power (kW):", max_power_edit)

            max_rpm_edit = QtGui.QSpinBox()
            max_rpm_edit.setRange(0, 100000)
            max_rpm_edit.setValue(
                self.saved_spindle_data[i]["max_rpm"]
                if i < len(self.saved_spindle_data) and "max_rpm" in self.saved_spindle_data[i]
                else 24000
            )
            layout.addRow("Max RPM:", max_rpm_edit)

            min_rpm_edit = QtGui.QSpinBox()
            min_rpm_edit.setRange(0, 100000)
            min_rpm_edit.setValue(
                self.saved_spindle_data[i]["min_rpm"]
                if i < len(self.saved_spindle_data) and "min_rpm" in self.saved_spindle_data[i]
                else 6000
            )
            layout.addRow("Min RPM:", min_rpm_edit)

            tool_change_combo = QtGui.QComboBox()
            tool_change_combo.addItem("Manual", "manual")
            tool_change_combo.addItem("ATC", "atc")
            if i < len(self.saved_spindle_data) and "tool_change" in self.saved_spindle_data[i]:
                index = tool_change_combo.findData(self.saved_spindle_data[i]["tool_change"])
                if index >= 0:
                    tool_change_combo.setCurrentIndex(index)
            layout.addRow("Tool Change:", tool_change_combo)

            self.spindles_tabs.addTab(tab, f"Spindle {i+1}")
            self.spindle_edits.append(
                {
                    "name": name_edit,
                    "id": id_edit,
                    "max_power_kw": max_power_edit,
                    "max_rpm": max_rpm_edit,
                    "min_rpm": min_rpm_edit,
                    "tool_change": tool_change_combo,
                }
            )

    def setup_post_tab(self):
        """Set up the post processor configuration tab.

        Creates input fields for output units, comments, line numbers,
        tool length offsets, and placeholder for additional post settings.
        """
        layout = QtGui.QFormLayout(self.post_tab)

        self.output_unit_combo = QtGui.QComboBox()
        self.output_unit_combo.addItem("Metric", "metric")
        self.output_unit_combo.addItem("Imperial", "imperial")
        layout.addRow("Output Unit:", self.output_unit_combo)

        self.comments_combo = QtGui.QComboBox()
        self.comments_combo.addItem("Yes", True)
        self.comments_combo.addItem("No", False)
        layout.addRow("Comments:", self.comments_combo)

        self.line_numbers_combo = QtGui.QComboBox()
        self.line_numbers_combo.addItem("Yes", True)
        self.line_numbers_combo.addItem("No", False)
        layout.addRow("Line Numbers:", self.line_numbers_combo)

        self.tool_length_offset_combo = QtGui.QComboBox()
        self.tool_length_offset_combo.addItem("Yes", True)
        self.tool_length_offset_combo.addItem("No", False)
        layout.addRow("Tool Length Offset:", self.tool_length_offset_combo)

        # Placeholder for other post settings
        self.other_post_group = QtGui.QGroupBox("Other Post Settings")
        other_layout = QtGui.QVBoxLayout(self.other_post_group)
        other_layout.addWidget(
            QtGui.QLabel("Additional post processor settings (to be implemented)")
        )
        layout.addRow(self.other_post_group)

    def set_defaults(self):
        """Set default values for all form fields.

        Initializes the dialog with sensible defaults for creating a new machine.
        """
        data = MachineFactory.create_default_machine_data()
        self.populate_from_data(data)

    def populate_from_data(self, data: Dict[str, Any]):
        """Populate UI fields from machine data dictionary.

        Args:
            data: Dictionary containing machine configuration data
        """
        machine = data.get("machine", {})
        self.name_edit.setText(machine.get("name", ""))
        self.manufacturer_edit.setText(machine.get("manufacturer", ""))
        self.description_edit.setText(machine.get("description", ""))
        units = machine.get("units", "metric")
        index = self.units_combo.findData(units)
        if index >= 0:
            self.units_combo.setCurrentIndex(index)
        self.current_units = units
        machine_type = machine.get("type", "custom")
        index = self.type_combo.findData(machine_type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)

        # Get units for suffixes in populate
        units = self.units_combo.itemData(self.units_combo.currentIndex())
        length_suffix = " mm" if units == "metric" else " in"
        vel_suffix = " mm/min" if units == "metric" else " in/min"
        angle_suffix = " deg"
        angle_vel_suffix = " deg/min"

        # Populate axes values - NEW FLATTENED STRUCTURE
        axes = machine.get("axes", {})

        # Store axes data in flattened structure
        self.saved_axes_data = {}
        for axis_name, axis_values in axes.items():
            axis_type = axis_values.get("type", "linear")
            self.saved_axes_data[axis_name] = {
                "min": axis_values.get("min", 0 if axis_type == "linear" else -180),
                "max": axis_values.get("max", 1000 if axis_type == "linear" else 180),
                "max_velocity": axis_values.get(
                    "max_velocity", 10000 if axis_type == "linear" else 36000
                ),
                "type": axis_type,
            }
            if axis_type == "angular":
                self.saved_axes_data[axis_name]["sequence"] = axis_values.get("sequence", 0)
                self.saved_axes_data[axis_name]["joint"] = axis_values.get(
                    "joint", [[0, 0, 0], [1, 0, 0]]
                )
                self.saved_axes_data[axis_name]["prefer_positive"] = axis_values.get(
                    "prefer_positive", True
                )

        # Update axes UI after loading data
        self.update_axes()

        # Populate UI with axis values
        if hasattr(self, "axis_edits"):
            for axis_name, edits in self.axis_edits.items():
                if axis_name in axes:
                    values = axes[axis_name]
                    axis_type = values.get("type", "linear")

                    if axis_type == "linear":
                        converted_min = (
                            values.get("min", 0)
                            if units == "metric"
                            else values.get("min", 0) / 25.4
                        )
                        edits["min"].setText(f"{converted_min:.2f}{length_suffix}")
                        converted_max = (
                            values.get("max", 1000)
                            if units == "metric"
                            else values.get("max", 1000) / 25.4
                        )
                        edits["max"].setText(f"{converted_max:.2f}{length_suffix}")
                        converted_vel = (
                            values.get("max_velocity", 10000)
                            if units == "metric"
                            else values.get("max_velocity", 10000) / 25.4
                        )
                        edits["max_velocity"].setText(f"{converted_vel:.2f}{vel_suffix}")
                    else:  # angular
                        edits["min"].setText(f"{values.get('min', -180):.2f}{angle_suffix}")
                        edits["max"].setText(f"{values.get('max', 180):.2f}{angle_suffix}")
                        edits["max_velocity"].setText(
                            f"{values.get('max_velocity', 36000):.2f}{angle_vel_suffix}"
                        )
                        edits["sequence"].setValue(values.get("sequence", 0))
                        edits["prefer_positive"].setChecked(values.get("prefer_positive", True))

                        # Set joint combo
                        joint = values.get("joint", [[0, 0, 0], [1, 0, 0]])
                        if len(joint) == 2:
                            for i, (label, vector) in enumerate(self.ROTATIONAL_AXIS_OPTIONS):
                                if vector == joint[1]:
                                    edits["joint"].setCurrentIndex(i)
                                    break

        spindles = machine.get("spindles", [])
        spindle_count = len(spindles)
        if spindle_count == 0:
            spindle_count = 1  # Default to 1 if none
        spindle_count = min(spindle_count, 9)  # Cap at 9
        self.spindle_count_combo.setCurrentText(str(spindle_count))
        self.update_spindles()  # Update spindles after setting count

        # Populate spindle values
        for i, spindle in enumerate(spindles):
            if i < len(self.spindle_edits):
                edits = self.spindle_edits[i]
                edits["name"].setText(spindle.get("name", ""))
                edits["id"].setText(spindle.get("id", ""))
                edits["max_power_kw"].setValue(spindle.get("max_power_kw", 3.0))
                edits["max_rpm"].setValue(spindle.get("max_rpm", 24000))
                edits["min_rpm"].setValue(spindle.get("min_rpm", 6000))
                tool_change = spindle.get("tool_change", {}).get("type", "manual")
                index = edits["tool_change"].findData(tool_change)
                if index >= 0:
                    edits["tool_change"].setCurrentIndex(index)

        # Save loaded spindle data to persistent storage
        self.saved_spindle_data = []
        for edits in self.spindle_edits:
            self.saved_spindle_data.append(
                {
                    "name": edits["name"].text(),
                    "id": edits["id"].text(),
                    "max_power_kw": edits["max_power_kw"].value(),
                    "max_rpm": edits["max_rpm"].value(),
                    "min_rpm": edits["min_rpm"].value(),
                    "tool_change": edits["tool_change"].itemData(
                        edits["tool_change"].currentIndex()
                    ),
                }
            )

        post = data.get("post", {})
        output_unit = post.get("output_unit", "metric")
        index = self.output_unit_combo.findData(output_unit)
        if index >= 0:
            self.output_unit_combo.setCurrentIndex(index)

        comments = post.get("comments", True)
        index = self.comments_combo.findData(comments)
        if index >= 0:
            self.comments_combo.setCurrentIndex(index)

        line_numbers = post.get("line_numbers", {}).get("enabled", True)
        index = self.line_numbers_combo.findData(line_numbers)
        if index >= 0:
            self.line_numbers_combo.setCurrentIndex(index)

        tool_length_offset = post.get("tool_length_offset", True)
        index = self.tool_length_offset_combo.findData(tool_length_offset)
        if index >= 0:
            self.tool_length_offset_combo.setCurrentIndex(index)

    def to_data(self) -> Dict[str, Any]:
        """Convert UI state to machine data dictionary.

        Returns:
            Dict containing complete machine configuration in JSON format
        """
        machine_type = self.type_combo.itemData(self.type_combo.currentIndex())
        config = self.MACHINE_TYPES.get(machine_type, {})

        # Always save in metric units - NEW FLATTENED STRUCTURE
        axes = {}

        # Save all configured axes (both linear and rotary) in flattened structure
        all_configured_axes = config.get("linear", []) + config.get("rotary", [])

        if hasattr(self, "axis_edits"):
            for axis_name in all_configured_axes:
                if axis_name in self.axis_edits:
                    edits = self.axis_edits[axis_name]
                    axis_type = edits.get("type", "linear")
                    values = self.saved_axes_data.get(axis_name, {})

                    axis_data = {
                        "min": values.get("min", 0 if axis_type == "linear" else -180),
                        "max": values.get("max", 1000 if axis_type == "linear" else 180),
                        "max_velocity": values.get(
                            "max_velocity", 10000 if axis_type == "linear" else 36000
                        ),
                        "type": axis_type,
                    }

                    # Add default joint for all axes
                    if axis_type == "linear":
                        # For linear axes, joint defines the axis direction
                        if axis_name == "X":
                            axis_data["joint"] = [[1, 0, 0], [0, 0, 0]]
                        elif axis_name == "Y":
                            axis_data["joint"] = [[0, 1, 0], [0, 0, 0]]
                        elif axis_name == "Z":
                            axis_data["joint"] = [[0, 0, 1], [0, 0, 0]]
                    else:  # angular
                        # For rotary axes: first element is origin [0,0,0], second is rotation axis
                        joint_vector = edits["joint"].itemData(edits["joint"].currentIndex())
                        axis_data["joint"] = [[0, 0, 0], joint_vector]
                        axis_data["sequence"] = edits["sequence"].value()
                        axis_data["prefer_positive"] = edits["prefer_positive"].isChecked()

                    axes[axis_name] = axis_data

        spindles = []
        if hasattr(self, "spindle_edits"):
            for edits in self.spindle_edits:
                spindles.append(
                    {
                        "name": edits["name"].text(),
                        "id": edits["id"].text(),
                        "max_power_kw": edits["max_power_kw"].value(),
                        "max_rpm": edits["max_rpm"].value(),
                        "min_rpm": edits["min_rpm"].value(),
                        "tool_change": {
                            "type": edits["tool_change"].itemData(
                                edits["tool_change"].currentIndex()
                            )
                        },
                    }
                )

        data = {
            "freecad_version": ".".join(FreeCAD.Version()[0:3]),
            "machine": {
                "name": self.name_edit.text(),
                "manufacturer": self.manufacturer_edit.text(),
                "description": self.description_edit.text(),
                "units": self.units_combo.itemData(self.units_combo.currentIndex()),
                "type": machine_type,
                "axes": axes,
                "spindles": spindles,
            },
            "post": {
                "output_unit": self.output_unit_combo.itemData(
                    self.output_unit_combo.currentIndex()
                ),
                "comments": self.comments_combo.itemData(self.comments_combo.currentIndex()),
                "line_numbers": {
                    "enabled": self.line_numbers_combo.itemData(
                        self.line_numbers_combo.currentIndex()
                    )
                },
                "tool_length_offset": self.tool_length_offset_combo.itemData(
                    self.tool_length_offset_combo.currentIndex()
                ),
            },
            "version": 1,
        }
        return data

    def toggle_editor_mode(self):
        """Toggle between form view and text editor view."""
        if self.text_mode:
            # Switching from text to form mode
            try:
                # Parse JSON from text editor
                json_text = self.text_editor.toPlainText()
                data = json.loads(json_text)
                # Validate and populate form
                self.populate_from_data(data)
                # Show form, hide editor
                self.tabs.show()
                self.text_editor.hide()
                self.toggle_button.setText(translate("CAM_MachineEditor", "Edit as Text"))
                self.text_mode = False
            except json.JSONDecodeError as e:
                QtGui.QMessageBox.critical(
                    self,
                    translate("CAM_MachineEditor", "JSON Error"),
                    translate("CAM_MachineEditor", "Invalid JSON: {}").format(str(e)),
                )
            except Exception as e:
                QtGui.QMessageBox.critical(
                    self,
                    translate("CAM_MachineEditor", "Error"),
                    translate("CAM_MachineEditor", "Failed to parse data: {}").format(str(e)),
                )
        else:
            # Switching from form to text mode
            try:
                # Get current data from form
                data = self.to_data()
                # Convert to JSON with nice formatting
                json_text = json.dumps(data, indent=4, sort_keys=True)
                self.text_editor.setPlainText(json_text)
                # Hide form, show editor
                self.tabs.hide()
                self.text_editor.show()
                self.toggle_button.setText(translate("CAM_MachineEditor", "Edit as Form"))
                self.text_mode = True
            except Exception as e:
                QtGui.QMessageBox.critical(
                    self,
                    translate("CAM_MachineEditor", "Error"),
                    translate("CAM_MachineEditor", "Failed to generate JSON: {}").format(str(e)),
                )

    def accept(self):
        """Handle save and close action."""
        # Check for duplicate machine names when creating new machines
        if self.text_mode:
            try:
                json_text = self.text_editor.toPlainText()
                data = json.loads(json_text)
                machine_name = data.get("machine", {}).get("name", "")
            except json.JSONDecodeError:
                machine_name = ""
        else:
            machine_name = self.name_edit.text().strip()

        # Check for duplicate machine names
        if machine_name:
            existing_machines = MachineFactory.list_configurations()
            # Case-insensitive check to match get_machine behavior
            machine_name_lower = machine_name.lower()
            existing_names_lower = [name.lower() for name in existing_machines]

            # For existing machines, allow keeping the same name (case-insensitive)
            current_name_allowed = False
            if self.filename:
                try:
                    current_data = MachineFactory.load_configuration(self.filename)
                    current_name = current_data.get("machine", {}).get("name", "").lower()
                    if machine_name_lower == current_name:
                        current_name_allowed = True
                except:
                    pass

            if machine_name_lower in existing_names_lower and not current_name_allowed:
                QtGui.QMessageBox.warning(
                    self,
                    translate("CAM_MachineEditor", "Duplicate Machine Name"),
                    translate(
                        "CAM_MachineEditor",
                        "A machine with the name '{}' already exists. Please choose a different name.",
                    ).format(machine_name),
                )
                return

        if self.text_mode:
            # If in text mode, parse JSON before saving
            try:
                json_text = self.text_editor.toPlainText()
                data = json.loads(json_text)
                if self.filename:
                    config = MachineConfiguration.from_dict(data)
                    saved_path = MachineFactory.save_configuration(config, self.filename)
                else:
                    # New machine, create and save
                    config = MachineConfiguration.from_dict(data)
                    saved_path = MachineFactory.save_configuration(config)
                    self.filename = saved_path.name
                self.path = str(saved_path)  # Keep for compatibility
            except json.JSONDecodeError as e:
                QtGui.QMessageBox.critical(
                    self,
                    translate("CAM_MachineEditor", "JSON Error"),
                    translate("CAM_MachineEditor", "Invalid JSON: {}").format(str(e)),
                )
                return
            except Exception as e:
                QtGui.QMessageBox.critical(
                    self,
                    translate("CAM_MachineEditor", "Error"),
                    translate("CAM_MachineEditor", "Failed to save: {}").format(str(e)),
                )
                return
        else:
            # Form mode - use existing save logic
            if self.filename:
                data = self.to_data()
                config = MachineConfiguration.from_dict(data)
                saved_path = MachineFactory.save_configuration(config, self.filename)
            else:
                # New machine, create and save
                data = self.to_data()
                config = MachineConfiguration.from_dict(data)
                saved_path = MachineFactory.save_configuration(config)
                self.filename = saved_path.name
            self.path = str(saved_path)  # Keep for compatibility
        super().accept()
