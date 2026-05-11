# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 sliptonic <shopinthewoods@gmail.com>
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

Values = Dict[str, Any]
Visible = Dict[str, bool]

POST_TYPE = "machine"


def _as_bool(value, default: bool) -> bool:
    """Coerce a property value to bool, handling strings stored in .fcm files."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return bool(value)


class Fanuc(PostProcessor):
    """Fanuc controller post processor.

    Outputs G-code targeted at Fanuc 0i/30i/31i-class controllers (also
    compatible with most Haas/Doosan/Mazak/Okuma controllers running in
    Fanuc mode).

    Fanuc-specific behavior beyond the base PostProcessor:
      * Rigid tapping (``M29 S<rpm>``) before ``G84``/``G74`` with
        feed computed as ``pitch * RPM``.
      * Optional parametric tool-length-offset using the ``#4120``
        ("active T-code") system variable.
      * Optional ``%`` tape wrap.
      * Optional end-of-job spindle-empty park (``M5`` + retract +
        ``M6 T0``) before the postamble.
      * Native canned cycles (G73/G81/G82/G83/G85) - cycles are not
        expanded into G0/G1 moves by default.
    """

    @classmethod
    def get_common_property_schema(cls):
        """Override common properties with Fanuc-specific defaults."""
        common_props = super().get_common_property_schema()

        for prop in common_props:
            if prop["name"] == "preamble":
                prop["default"] = "G17 G54 G40 G49 G80 G90 G94"
            elif prop["name"] == "postamble":
                prop["default"] = "M05\nG17 G54 G90 G80 G40\nM30"
            elif prop["name"] == "safetyblock":
                # Preamble already establishes a safe state on Fanuc; keep
                # the safety block empty by default to avoid duplication.
                prop["default"] = ""
            elif prop["name"] == "drill_cycles_to_translate":
                # Fanuc supports canned cycles natively. Emit, do not expand.
                prop["default"] = ""
            elif prop["name"] == "supports_tool_radius_compensation":
                prop["default"] = True
            elif prop["name"] == "pre_tool_change":
                prop["default"] = "M05\nG28 G91 Z0\nG90"

        return common_props

    @classmethod
    def get_property_schema(cls):
        """Return schema for Fanuc-specific configurable properties."""
        return [
            {
                "name": "wrap_in_percent",
                "type": "bool",
                "runtime": True,
                "label": translate("CAM", "Wrap output in '%' lines"),
                "default": True,
                "help": translate(
                    "CAM",
                    "Wrap the gcode in leading and trailing '%' lines, as "
                    "expected by Fanuc tape-format DNC.",
                ),
            },
            {
                "name": "rigid_tap",
                "type": "bool",
                "runtime": True,
                "label": translate("CAM", "Rigid tapping (M29)"),
                "default": True,
                "help": translate(
                    "CAM",
                    "Emit 'M29 S<rpm>' before G84/G74 cycles to enable rigid "
                    "tapping. The cycle feed is computed as pitch x RPM. "
                    "Individual cycle commands can override this via the "
                    "'rigid' annotation.",
                ),
            },
            {
                "name": "tlo_macro_form",
                "type": "bool",
                "runtime": True,
                "label": translate("CAM", "Parametric tool-length offset"),
                "default": False,
                "help": translate(
                    "CAM",
                    "Emit 'G91 G0 G43 G54 Z-[#[2000+#4120]] H#4120 ; G90' "
                    "instead of 'G43 H<n>'. Requires the machine to follow "
                    "the #2000+H register convention for negated Z offsets.",
                ),
            },
            {
                "name": "end_spindle_empty",
                "type": "bool",
                "runtime": True,
                "label": translate("CAM", "Park empty spindle at job end"),
                "default": False,
                "help": translate(
                    "CAM",
                    "Stop the spindle, perform a tool-change retract, and "
                    "emit 'M6 T0' before the postamble so the last tool is "
                    "returned to the carousel.",
                ),
            },
            {
                "name": "tool_change_retract",
                "type": "text",
                "runtime": True,
                "label": translate("CAM", "Tool-change retract block"),
                "default": "G28 G91 Z0\nG90",
                "help": translate(
                    "CAM",
                    "Block emitted before the end-of-job M6 T0 when the "
                    "empty-spindle park is enabled.",
                ),
            },
        ]

    def __init__(
        self,
        job,
        tooltip=translate("CAM", "Fanuc post processor"),
        tooltipargs=[""],
        units="Metric",
    ) -> None:
        super().__init__(
            job=job,
            tooltip=tooltip,
            tooltipargs=tooltipargs,
            units=units,
        )
        # Remembered for rigid-tap fallback when the cycle command has no S.
        self._last_spindle_speed = 0
        Path.Log.debug("Fanuc post processor initialized.")

    def reinitialize(self) -> None:
        """Reset per-export state in addition to the base reinitialize."""
        super().reinitialize()
        self._last_spindle_speed = 0

    def init_values(self, values: Values) -> None:
        """Initialize values that are used throughout the postprocessor."""
        super().init_values(values)

        values["ENABLE_COOLANT"] = True
        values["MACHINE_NAME"] = "fanuc"
        values["OUTPUT_ADAPTIVE"] = True
        values["POSTPROCESSOR_FILE_NAME"] = __name__

        # Standard Fanuc parameter order. K is omitted for the XY plane;
        # arcs in other planes need rework when 5-axis support lands.
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

    def init_arguments_visible(self, arguments_visible: Visible) -> None:
        """Initialize which argument pairs are visible in TOOLTIP_ARGS."""
        super().init_arguments_visible(arguments_visible)
        arguments_visible["axis-modal"] = True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _bool_prop(self, name: str, default: bool) -> bool:
        """Return a boolean property, preferring the applied bundle."""
        # apply_configuration_bundle() uppercases keys into self.values.
        if name.upper() in self.values:
            return _as_bool(self.values[name.upper()], default)
        if self._machine and hasattr(self._machine, "postprocessor_properties"):
            return _as_bool(
                self._machine.postprocessor_properties.get(name, default),
                default,
            )
        return default

    def _is_imperial(self) -> bool:
        if self._machine and hasattr(self._machine, "output"):
            try:
                from Machine.models.machine import OutputUnits

                return self._machine.output.units == OutputUnits.IMPERIAL
            except ImportError:
                pass
        return self.values.get("UNITS", "G21") == "G20"

    # ------------------------------------------------------------------
    # Command conversion overrides
    # ------------------------------------------------------------------

    def _convert_spindle_command(self, command):
        """Track the last commanded spindle speed for rigid-tap fallback."""
        if "S" in command.Parameters:
            try:
                self._last_spindle_speed = int(command.Parameters["S"])
            except (TypeError, ValueError):
                pass
        return super()._convert_spindle_command(command)

    def _convert_drill_cycle(self, command):
        """Emit M29 + computed feed for rigid G84/G74; standard cycle otherwise."""
        if command.Name in ("G84", "G74"):
            rigid = self._bool_prop("rigid_tap", True)
            anno = command.Annotations.get("rigid")
            if anno == "True":
                rigid = True
            elif anno == "False":
                rigid = False
            if rigid:
                return self._emit_rigid_tap(command)
        return super()._convert_drill_cycle(command)

    def _convert_modal_command(self, command):
        """Optionally render TLO G43 in Fanuc parametric form."""
        if command.Name == "G43" and command.Annotations.get("tool_length_offset"):
            if self._bool_prop("tlo_macro_form", False):
                return "G91 G0 G43 G54 Z-[#[2000+#4120]] H#4120\nG90"
        return super()._convert_modal_command(command)

    def _emit_rigid_tap(self, command):
        """Format a G84/G74 cycle as a Fanuc rigid tap.

        The tapping generator stores pitch in F, spindle speed in S, the start
        XY in X/Y, the depth in Z, the retract plane in R, the dwell in P,
        the peck depth in Q, and the repeat count in L. The cycle feed for
        a rigid tap is ``pitch * RPM``.
        """
        params = command.Parameters
        annotations = command.Annotations
        block_delete = "/" if annotations.get("blockdelete") else ""

        pitch_raw = params.get("F")
        if pitch_raw is None:
            Path.Log.warning(
                f"Rigid tap {command.Name} missing pitch (F parameter); "
                f"falling back to standard cycle."
            )
            return super()._convert_drill_cycle(command)

        precision = int(self.values.get("AXIS_PRECISION") or 3)
        is_imperial = self._is_imperial()

        def fmt(value):
            v = value / 25.4 if is_imperial else value
            return f"{v:.{precision}f}"

        pitch = pitch_raw / 25.4 if is_imperial else pitch_raw

        rpm = 0
        if "S" in params:
            try:
                rpm = int(params["S"])
            except (TypeError, ValueError):
                rpm = 0
        if rpm == 0:
            rpm = self._last_spindle_speed
        feed = pitch * rpm if rpm > 0 else pitch

        lines = []
        if rpm > 0:
            lines.append(f"{block_delete}M29 S{rpm}")

        cycle_parts = [f"{block_delete}{command.Name}"]
        for axis in ("X", "Y", "Z", "R"):
            if axis in params:
                cycle_parts.append(f"{axis}{fmt(params[axis])}")
        cycle_parts.append(f"F{feed:.{precision}f}")
        for axis in ("P", "Q"):
            if axis in params:
                cycle_parts.append(f"{axis}{fmt(params[axis])}")
        if "L" in params:
            try:
                cycle_parts.append(f"L{int(params['L'])}")
            except (TypeError, ValueError):
                pass
        lines.append(" ".join(cycle_parts))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Output assembly overrides
    # ------------------------------------------------------------------

    def _append_trailing_lines(self, gcode_string) -> str:
        """Inject end-spindle-empty block before the postamble when enabled."""
        if self._bool_prop("end_spindle_empty", False):
            retract_text = ""
            if self._machine and hasattr(self._machine, "postprocessor_properties"):
                retract_text = (
                    self._machine.postprocessor_properties.get("tool_change_retract", "") or ""
                )
            retract_lines = [line for line in retract_text.split("\n") if line.strip()]
            if not retract_lines:
                retract_lines = ["G28 G91 Z0", "G90"]

            block = ["M05"] + retract_lines + ["M6 T0"]
            line_ending = self.values.get("END_OF_LINE_CHARS", "\n")
            block_str = line_ending.join(block)
            gcode_string = gcode_string + line_ending + block_str

        return super()._append_trailing_lines(gcode_string)

    def export2(self):
        """Wrap each output section in '%' lines when enabled."""
        sections = super().export2()
        if not sections:
            return sections

        if not self._bool_prop("wrap_in_percent", True):
            return sections

        line_ending = self.values.get("END_OF_LINE_CHARS", "\n")
        wrapped = []
        for name, gcode in sections:
            if gcode is None:
                wrapped.append((name, gcode))
                continue
            body = gcode
            if not body.endswith(line_ending):
                body = body + line_ending
            wrapped.append((name, "%" + line_ending + body + "%" + line_ending))
        return wrapped

    # ------------------------------------------------------------------
    # Tooltips
    # ------------------------------------------------------------------

    @property
    def tooltip(self):
        return """
        This is the Fanuc post processor for the CAM workbench.

        Outputs G-code targeted at Fanuc 0i/30i/31i-class controllers
        (also compatible with most Haas/Doosan/Mazak controllers in
        Fanuc mode).

        Fanuc-specific behavior:
        - Rigid tapping (M29 S<rpm>) for G84/G74, feed = pitch x RPM.
        - Optional parametric TLO using the #4120 system variable.
        - Optional '%' tape wrap.
        - Optional end-of-job spindle-empty park (M6 T0).
        - Native canned cycles (G73/G81/G82/G83/G85).
        """
