# -*- coding: utf-8 -*-

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2019 sliptonic <shopinthewoods@gmail.com>               *
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

import FreeCAD
import FreeCADGui
import Part
import PathScripts
import PathScripts.PathGui as PathGui
import PathScripts.PathLog as PathLog
import PathScripts.PathToolController as PathToolController
import PathScripts.PathToolEdit as PathToolEdit
import PathScripts.PathUtil as PathUtil
import math
from FreeCAD import Units

from PySide import QtCore, QtGui

# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)

class ViewProvider:

    def __init__(self, vobj):
        vobj.Proxy = self
        self.vobj = vobj

    def attach(self, vobj):
        mode = 2
        vobj.setEditorMode('LineWidth', mode)
        vobj.setEditorMode('MarkerColor', mode)
        vobj.setEditorMode('NormalColor', mode)
        vobj.setEditorMode('DisplayMode', mode)
        vobj.setEditorMode('BoundingBox', mode)
        vobj.setEditorMode('Selectable', mode)
        vobj.setEditorMode('ShapeColor', mode)
        vobj.setEditorMode('Transparency', mode)
        vobj.setEditorMode('Visibility', mode)
        self.vobj = vobj

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None

    def getIcon(self):
        return ":/icons/Path-ToolController.svg"

    def onChanged(self, vobj, prop):
        # pylint: disable=unused-argument
        mode = 2
        vobj.setEditorMode('LineWidth', mode)
        vobj.setEditorMode('MarkerColor', mode)
        vobj.setEditorMode('NormalColor', mode)
        vobj.setEditorMode('DisplayMode', mode)
        vobj.setEditorMode('BoundingBox', mode)
        vobj.setEditorMode('Selectable', mode)

    def onDelete(self, vobj, args=None):
        # pylint: disable=unused-argument
        PathUtil.clearExpressionEngine(vobj.Object)
        return True

    def updateData(self, vobj, prop):
        # this is executed when a property of the APP OBJECT changes
        # pylint: disable=unused-argument
        pass

    def setEdit(self, vobj=None, mode=0):
        if 0 == mode:
            if vobj is None:
                vobj = self.vobj
            FreeCADGui.Control.closeDialog()
            taskd = TaskPanel(vobj.Object)
            FreeCADGui.Control.showDialog(taskd)
            taskd.setupUi()

            FreeCAD.ActiveDocument.recompute()

            return True
        return False

    def unsetEdit(self, vobj, mode):
        # this is executed when the user cancels or terminates edit mode
        # pylint: disable=unused-argument
        return False

    def setupContextMenu(self, vobj, menu):
        # pylint: disable=unused-argument
        PathLog.track()
        for action in menu.actions():
            menu.removeAction(action)
        action = QtGui.QAction(translate('Path', 'Edit'), menu)
        action.triggered.connect(self.setEdit)
        menu.addAction(action)

def Create(name = 'Default Tool', tool=None, toolNumber=1):
    PathLog.track(tool, toolNumber)

    obj = PathScripts.PathToolController.Create(name, tool, toolNumber)
    ViewProvider(obj.ViewObject)
    return obj


class CommandPathToolController(object):
    # pylint: disable=no-init

    def GetResources(self):
        return {'Pixmap': 'Path-LengthOffset',
                'MenuText': QtCore.QT_TRANSLATE_NOOP("Path_ToolController", "Add Tool Controller to the Job"),
                'ToolTip': QtCore.QT_TRANSLATE_NOOP("Path_ToolController", "Add Tool Controller")}

    def IsActive(self):
        if FreeCAD.ActiveDocument is not None:
            for o in FreeCAD.ActiveDocument.Objects:
                if o.Name[:3] == "Job":
                        return True
        return False

    def Activated(self):
        PathLog.track()
        Create()

class ToolControllerEditor(object):

    def __init__(self, obj, asDialog):
        self.form = FreeCADGui.PySideUic.loadUi(":/panels/DlgToolControllerEdit.ui")
        if not asDialog:
            self.form.buttonBox.hide()
        self.obj = obj

        self.vertFeed = PathGui.QuantitySpinBox(self.form.vertFeed, obj, 'VertFeed')
        self.horizFeed = PathGui.QuantitySpinBox(self.form.horizFeed, obj, 'HorizFeed')
        self.vertRapid = PathGui.QuantitySpinBox(self.form.vertRapid, obj, 'VertRapid')
        self.horizRapid = PathGui.QuantitySpinBox(self.form.horizRapid, obj, 'HorizRapid')

        self.editor = PathToolEdit.ToolEditor(obj.Tool, self.form.toolEditor)

    def updateUi(self):
        tc = self.obj
        self.form.tcName.setText(tc.Label)
        self.form.tcNumber.setValue(tc.ToolNumber)
        self.horizFeed.updateSpinBox()
        self.horizRapid.updateSpinBox()
        self.vertFeed.updateSpinBox()
        self.vertRapid.updateSpinBox()
        self.form.spindleSpeed.setValue(tc.SpindleSpeed)
        index = self.form.spindleDirection.findText(tc.SpindleDir, QtCore.Qt.MatchFixedString)
        if index >= 0:
            self.form.spindleDirection.setCurrentIndex(index)

        self.editor.updateUI()

    def updateToolController(self):
        tc = self.obj
        try:
            tc.Label = self.form.tcName.text()
            tc.ToolNumber = self.form.tcNumber.value()
            self.horizFeed.updateProperty()
            self.vertFeed.updateProperty()
            self.horizRapid.updateProperty()
            self.vertRapid.updateProperty()
            tc.SpindleSpeed = self.form.spindleSpeed.value()
            tc.SpindleDir = self.form.spindleDirection.currentText()

            self.editor.updateTool()
            tc.Tool = self.editor.tool

        except Exception as e: # pylint: disable=broad-except
            PathLog.error(translate("PathToolController", "Error updating TC: %s") % e)


    def refresh(self):
        self.form.blockSignals(True)
        self.updateToolController()
        self.updateUi()
        self.form.blockSignals(False)

    def feedspeed(self):
        calculator = FeedSpeed(self.obj)
        result = calculator.form.exec_()

        if result:
            # use the values from the form
            self.obj.VertFeed = calculator.vertfeed
            self.obj.HorizFeed = calculator.horizfeed
            self.form.spindleSpeed.setValue(calculator.spindlespeed)
            self.horizFeed.updateSpinBox()
            self.vertFeed.updateSpinBox()
            self.refresh()
        else:
            pass
            # do nothing

    def setupUi(self):
        self.editor.setupUI()

        self.form.tcName.editingFinished.connect(self.refresh)
        self.form.horizFeed.editingFinished.connect(self.refresh)
        self.form.vertFeed.editingFinished.connect(self.refresh)
        self.form.horizRapid.editingFinished.connect(self.refresh)
        self.form.vertRapid.editingFinished.connect(self.refresh)
        self.form.btnFeedSpeed.clicked.connect(self.feedspeed)


class FeedSpeed:
    flutecount = 0  # number of cutting edges
    tooldiameter = 0  # tool diameter from active tool
    srps = 0  # spindle rotation in RPS
    chipload = 0  # chip load / feed per tooth
    fpr = 0  # feed per rotation
    ssm = 0  # surface speed
    hfr = 0  # horizontal feed rate
    vfr = 0  # vertical feed rate
    rdoc = 0

    def __init__(self, obj):
        self.form = FreeCADGui.PySideUic.loadUi(":/panels/DlgFeedSpeed.ui")
        self.flutecount = int(obj.Tool.FluteCount)
        self.tooldiameter = obj.Tool.Diameter
        self.srps = obj.SpindleSpeed / 60  # Unit calculations are always in seconds.
        self.chipload = obj.Tool.ChipLoad
        self.rdoc = self.tooldiameter / 2

        self.setupUi()
        self.calculate()

    @property
    def spindlespeed(self):
        return self.srps * 60

    @property
    def vertfeed(self):
        return self.vfr

    @property
    def horizfeed(self):
        return self.hfr

    def calculate(self):
        self.fpr = self.flutecount * self.chipload
        self.ssm = (self.tooldiameter * math.pi) * self.srps

        self.form.RDOC.setEnabled(self.form.chkRCTEnable.isChecked())
        if self.form.chkRCTEnable.isChecked():
            usechipload = (self.chipload * self.tooldiameter) / (2 * (math.sqrt((self.tooldiameter * self.rdoc) - self.rdoc**2)))
        else:
            usechipload = self.chipload

        # Tool engagement angle:  a = COS-1( 1 - WOC / Dia/2 )

        self.hfr = self.srps * self.flutecount * usechipload
        self.vfr = self.hfr / 2
        self.updateUI()

    def updateUI(self):
        if self.form.radioMetric.isChecked():
            Schema = 6
        else:
            Schema = 3

        self.form.toolDiameter.setText(Units.schemaTranslate(Units.Quantity(self.tooldiameter, Units.Length), Schema)[0])
        self.form.RDOC.setText(Units.schemaTranslate(Units.Quantity(self.rdoc, Units.Length), Schema)[0])
        self.form.feedPerTooth.setText(Units.schemaTranslate(Units.Quantity(self.chipload, Units.Length), Schema)[0])
        self.form.fluteCount.setText(str(self.flutecount))
        self.form.spindleRPM.setText(str(self.srps * 60))
        self.form.vertFeed.setText(Units.schemaTranslate(Units.Quantity(self.vfr, Units.Velocity), Schema)[0])
        self.form.horizFeed.setText(Units.schemaTranslate(Units.Quantity(self.hfr, Units.Velocity), Schema)[0])

        surfspeed = str(Units.Quantity(self.ssm, Units.Velocity).getValueAs('ft/min')) + 'ft/min'
        self.form.surfaceSpeed.setText(surfspeed)
        self.form.update()

    def updateSpindleRPM(self):
        self.srps = FreeCAD.Units.Quantity(self.form.spindleRPM.text()).Value / 60
        self.calculate()

    def updateRDOC(self):
        self.rdoc = FreeCAD.Units.Quantity(self.form.RDOC.text()).Value
        self.calculate()

    def updateChipLoad(self):
        self.chipload = FreeCAD.Units.Quantity(self.form.feedPerTooth.text()).Value
        self.calculate()

    def accept(self):
        pass

    def reject(self):
        pass

    def setupUi(self):
        self.form.radioMetric.toggled.connect(self.calculate)
        self.form.chkRCTEnable.toggled.connect(self.calculate)
        self.form.spindleRPM.editingFinished.connect(self.updateSpindleRPM)
        self.form.RDOC.editingFinished.connect(self.updateRDOC)
        self.form.feedPerTooth.editingFinished.connect(self.updateChipLoad)


class TaskPanel:

    def __init__(self, obj):
        self.editor = ToolControllerEditor(obj, False)
        self.form = self.editor.form
        self.updating = False
        self.toolrep = None
        self.obj = obj

    def accept(self):
        self.getFields()

        FreeCADGui.ActiveDocument.resetEdit()
        FreeCADGui.Control.closeDialog()
        if self.toolrep is not None:
            FreeCAD.ActiveDocument.removeObject(self.toolrep.Name)
        FreeCAD.ActiveDocument.recompute()

    def reject(self):
        FreeCADGui.Control.closeDialog()
        if self.toolrep is not None:
            FreeCAD.ActiveDocument.removeObject(self.toolrep.Name)
        FreeCAD.ActiveDocument.recompute()

    def getFields(self):
        self.editor.updateToolController()
        self.obj.Proxy.execute(self.obj)

    def setFields(self):
        self.editor.updateUi()

        tool = self.obj.Tool
        radius = tool.Diameter / 2
        length = tool.CuttingEdgeHeight
        t = Part.makeCylinder(radius, length)
        self.toolrep.Shape = t

    def edit(self, item, column):
        # pylint: disable=unused-argument
        if not self.updating:
            self.resetObject()

    def resetObject(self, remove=None):
        # pylint: disable=unused-argument
        "transfers the values from the widget to the object"
        FreeCAD.ActiveDocument.recompute()

    def setupUi(self):
        t = Part.makeCylinder(1, 1)
        self.toolrep = FreeCAD.ActiveDocument.addObject("Part::Feature", "tool")
        self.toolrep.Shape = t

        self.setFields()
        self.editor.setupUi()


class DlgToolControllerEdit:
    def __init__(self, obj):
        self.editor = ToolControllerEditor(obj, True)
        self.editor.updateUi()
        self.editor.setupUi()
        self.obj = obj

    def exec_(self):
        restoreTC   = self.obj.Proxy.templateAttrs(self.obj)

        rc = False
        if not self.editor.form.exec_():
            PathLog.info("revert")
            self.obj.Proxy.setFromTemplate(self.obj, restoreTC)
            rc = True
        return rc


if FreeCAD.GuiUp:
    # register the FreeCAD command
    FreeCADGui.addCommand('Path_ToolController', CommandPathToolController())
    # and set view provider for creation from template
    PathToolController.ViewProviderClass = ViewProvider

FreeCAD.Console.PrintLog("Loading PathToolControllerGui... done\n")
