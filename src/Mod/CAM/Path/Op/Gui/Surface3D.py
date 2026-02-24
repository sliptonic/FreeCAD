# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *   Copyright (c) 2025 sliptonic <shopinthewoods@gmail.com>               *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

from PySide import QtCore
from PySide.QtCore import QT_TRANSLATE_NOOP
import FreeCAD
import FreeCADGui
import Path
import Path.Base.Gui.Util as PathGuiUtil
import Path.Op.Gui.Base as PathOpGui
import Path.Op.Surface3D as PathSurface3D

__title__ = "CAM Surface 3D Operation UI"
__author__ = "sliptonic (Brad Collette)"
__url__ = "https://www.freecad.org"
__doc__ = "Surface 3D operation page controller and command implementation."

translate = FreeCAD.Qt.translate

if False:
    Path.Log.setLevel(Path.Log.Level.DEBUG, Path.Log.thisModule())
    Path.Log.trackModule(Path.Log.thisModule())
else:
    Path.Log.setLevel(Path.Log.Level.INFO, Path.Log.thisModule())


class TaskPanelOpPage(PathOpGui.TaskPanelPage):
    """Page controller class for the Surface3D operation."""

    def initPage(self, obj):
        """initPage(obj) ... initialize the task panel page"""
        self.setTitle("3D Surface - " + obj.Label)
        self.updateVisibility()
        self.form.accuracySlider.setPageStep(1)

    def getForm(self):
        """getForm() ... returns UI"""
        form = FreeCADGui.PySideUic.loadUi(":/panels/PageOpSurface3DEdit.ui")
        comboToPropertyMap = [
            ("strategySelect", "Strategy"),
            ("boundBoxSelect", "BoundBox"),
            ("layerMode", "LayerMode"),
            ("cutPattern", "CutPattern"),
            ("clearLastLayer", "ClearLastLayer"),
        ]
        enumTups = PathSurface3D.ObjectSurface3D.propertyEnumerations(dataType="raw")
        PathGuiUtil.populateCombobox(form, enumTups, comboToPropertyMap)
        return form

    def getFields(self, obj):
        """getFields(obj) ... transfers values from UI to obj's properties"""
        self.updateToolController(obj, self.form.toolController)
        self.updateCoolant(obj, self.form.coolantController)

        if obj.Strategy != str(self.form.strategySelect.currentData()):
            obj.Strategy = str(self.form.strategySelect.currentData())

        if obj.BoundBox != str(self.form.boundBoxSelect.currentData()):
            obj.BoundBox = str(self.form.boundBoxSelect.currentData())

        if obj.LayerMode != str(self.form.layerMode.currentData()):
            obj.LayerMode = str(self.form.layerMode.currentData())

        obj.CutPattern = self.form.cutPattern.currentData()
        obj.ClearLastLayer = self.form.clearLastLayer.currentData()

        if obj.AvoidLastX_Faces != self.form.avoidLastX_Faces.value():
            obj.AvoidLastX_Faces = self.form.avoidLastX_Faces.value()

        PathGuiUtil.updateInputField(obj, "DepthOffset", self.form.depthOffset)
        PathGuiUtil.updateInputField(obj, "IgnoreOuterAbove", self.form.ignoreOuterAbove)
        PathGuiUtil.updateInputField(obj, "BoundaryAdjustment", self.form.boundaryAdjustment)
        PathGuiUtil.updateInputField(obj, "SampleInterval", self.form.sampleInterval)

        if obj.StepOver != self.form.stepOver.value():
            obj.StepOver = self.form.stepOver.value()

        if obj.UseStartPoint != self.form.useStartPoint.isChecked():
            obj.UseStartPoint = self.form.useStartPoint.isChecked()

        if obj.OptimizeLinearPaths != self.form.optimizeEnabled.isChecked():
            obj.OptimizeLinearPaths = self.form.optimizeEnabled.isChecked()

        if obj.KeepToolDown != self.form.keepToolDown.isChecked():
            obj.KeepToolDown = self.form.keepToolDown.isChecked()

    def setFields(self, obj):
        """setFields(obj) ... transfers obj's property values to UI"""
        self.setupToolController(obj, self.form.toolController)
        self.setupCoolant(obj, self.form.coolantController)
        self.selectInComboBox(obj.Strategy, self.form.strategySelect)
        self.selectInComboBox(obj.BoundBox, self.form.boundBoxSelect)
        self.selectInComboBox(obj.LayerMode, self.form.layerMode)
        self.selectInComboBox(obj.CutPattern, self.form.cutPattern)
        self.selectInComboBox(obj.ClearLastLayer, self.form.clearLastLayer)

        self.form.avoidLastX_Faces.setValue(obj.AvoidLastX_Faces)
        self.form.depthOffset.setText(
            FreeCAD.Units.Quantity(obj.DepthOffset.Value, FreeCAD.Units.Length).UserString
        )
        self.form.ignoreOuterAbove.setText(
            FreeCAD.Units.Quantity(obj.IgnoreOuterAbove.Value, FreeCAD.Units.Length).UserString
        )
        self.form.boundaryAdjustment.setText(
            FreeCAD.Units.Quantity(obj.BoundaryAdjustment.Value, FreeCAD.Units.Length).UserString
        )
        self.form.stepOver.setValue(obj.StepOver)
        self.form.sampleInterval.setText(
            FreeCAD.Units.Quantity(obj.SampleInterval.Value, FreeCAD.Units.Length).UserString
        )

        if obj.UseStartPoint:
            self.form.useStartPoint.setCheckState(QtCore.Qt.Checked)
        else:
            self.form.useStartPoint.setCheckState(QtCore.Qt.Unchecked)

        if obj.OptimizeLinearPaths:
            self.form.optimizeEnabled.setCheckState(QtCore.Qt.Checked)
        else:
            self.form.optimizeEnabled.setCheckState(QtCore.Qt.Unchecked)

        if obj.KeepToolDown:
            self.form.keepToolDown.setCheckState(QtCore.Qt.Checked)
        else:
            self.form.keepToolDown.setCheckState(QtCore.Qt.Unchecked)

        self._syncAccuracyLabel()

        self.updateVisibility()

    def getSignalsForUpdate(self, obj):
        """getSignalsForUpdate(obj) ... return list of signals for updating obj"""
        signals = []
        signals.append(self.form.toolController.currentIndexChanged)
        signals.append(self.form.coolantController.currentIndexChanged)
        signals.append(self.form.strategySelect.currentIndexChanged)
        signals.append(self.form.boundBoxSelect.currentIndexChanged)
        signals.append(self.form.layerMode.currentIndexChanged)
        signals.append(self.form.cutPattern.currentIndexChanged)
        signals.append(self.form.clearLastLayer.currentIndexChanged)
        signals.append(self.form.avoidLastX_Faces.editingFinished)
        signals.append(self.form.depthOffset.editingFinished)
        signals.append(self.form.ignoreOuterAbove.editingFinished)
        signals.append(self.form.boundaryAdjustment.editingFinished)
        signals.append(self.form.stepOver.editingFinished)
        signals.append(self.form.sampleInterval.editingFinished)
        signals.append(self.form.accuracySlider.valueChanged)

        if hasattr(self.form.useStartPoint, "checkStateChanged"):  # Qt version >= 6.7.0
            signals.append(self.form.useStartPoint.checkStateChanged)
            signals.append(self.form.optimizeEnabled.checkStateChanged)
            signals.append(self.form.keepToolDown.checkStateChanged)
        else:  # Qt version < 6.7.0
            signals.append(self.form.useStartPoint.stateChanged)
            signals.append(self.form.optimizeEnabled.stateChanged)
            signals.append(self.form.keepToolDown.stateChanged)

        return signals

    def _onAccuracySliderChanged(self, level):
        """Populate UI fields and non-UI properties from the selected accuracy preset."""
        presets = PathSurface3D.ObjectSurface3D.ACCURACY_PRESETS
        preset = presets.get(level, presets[4])
        self.form.sampleInterval.setText(
            FreeCAD.Units.Quantity(preset["sample_interval"], FreeCAD.Units.Length).UserString
        )
        self.form.accuracyDescription.setText(
            "{} - {}".format(preset["name"], preset["description"])
        )
        obj = self.obj
        if hasattr(obj, "AngularDeflection"):
            obj.AngularDeflection = preset["angular_deflection"]
        if hasattr(obj, "LinearDeflection"):
            obj.LinearDeflection = preset["linear_deflection"]
        if hasattr(obj, "MeshSimplification"):
            obj.MeshSimplification = preset["mesh_simplification"]

    def _syncAccuracyLabel(self):
        """Check if current UI values match a preset; update slider and label accordingly."""
        presets = PathSurface3D.ObjectSurface3D.ACCURACY_PRESETS
        try:
            current_si = FreeCAD.Units.Quantity(self.form.sampleInterval.text()).Value
        except Exception:
            current_si = None

        for lvl, preset in presets.items():
            if current_si is not None and abs(current_si - preset["sample_interval"]) < 0.001:
                self.form.accuracySlider.blockSignals(True)
                self.form.accuracySlider.setValue(lvl)
                self.form.accuracySlider.blockSignals(False)
                self.form.accuracyDescription.setText(
                    "{} - {}".format(preset["name"], preset["description"])
                )
                return

        self.form.accuracyDescription.setText("Custom")

    def updateVisibility(self, sentObj=None):
        """updateVisibility(sentObj=None)... Updates visibility of Tasks panel objects."""
        strategy = self.form.strategySelect.currentData()
        is_dropcutter = strategy == "DropCutter"
        is_waterline = strategy in ("Waterline", "AdaptiveWaterline", "SliceWaterline")

        # DropCutter-specific widgets
        if is_dropcutter:
            self.form.cutPattern.show()
            self.form.cutPattern_label.show()
            self.form.avoidLastX_Faces.show()
            self.form.avoidLastX_Faces_label.show()
            self.form.keepToolDown.show()
        else:
            self.form.cutPattern.hide()
            self.form.cutPattern_label.hide()
            self.form.avoidLastX_Faces.hide()
            self.form.avoidLastX_Faces_label.hide()
            self.form.keepToolDown.hide()

        # Waterline-specific widgets
        if is_waterline:
            self.form.clearLastLayer.show()
            self.form.clearLastLayer_label.show()
            self.form.ignoreOuterAbove.show()
            self.form.ignoreOuterAbove_label.show()
        else:
            self.form.clearLastLayer.hide()
            self.form.clearLastLayer_label.hide()
            self.form.ignoreOuterAbove.hide()
            self.form.ignoreOuterAbove_label.hide()

    def registerSignalHandlers(self, obj):
        self.form.strategySelect.currentIndexChanged.connect(self.updateVisibility)
        self.form.accuracySlider.valueChanged.connect(self._onAccuracySliderChanged)
        self.form.sampleInterval.editingFinished.connect(self._syncAccuracyLabel)


Command = PathOpGui.SetupOperation(
    "Surface3D",
    PathSurface3D.Create,
    TaskPanelOpPage,
    "CAM_3DSurface",
    QT_TRANSLATE_NOOP("CAM_Surface3D", "3D Surface"),
    QT_TRANSLATE_NOOP("CAM_Surface3D", "Create a 3D Surface Operation from a model"),
    PathSurface3D.SetupProperties,
)

FreeCAD.Console.PrintLog("Loading PathSurface3DGui... done\n")
