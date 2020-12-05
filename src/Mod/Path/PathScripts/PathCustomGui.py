# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2017 sliptonic <shopinthewoods@gmail.com>               *
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
import PathGui as PGui # ensure Path/Gui/Resources are loaded
import PathScripts.PathCustom as PathCustom
import PathScripts.PathOpGui as PathOpGui
import PathScripts.PathLog as PathLog

import PathScripts.PathGetPoint as PathGetPoint
#import pivy.coin as coin
#import draftutils.gui_utils as gui_utils

from PySide import QtCore

__title__ = "Path Custom Operation UI"
__author__ = "sliptonic (Brad Collette)"
__url__ = "http://www.freecadweb.org"
__doc__ = "Custom operation page controller and command implementation."


if True:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class TaskPanelOpPage(PathOpGui.TaskPanelPage):
    '''Page controller class for the Custom operation.'''

    def __del__(self):
        PathLog.track()
        self.view.removeEventCallback("SoMouseButtonEvent",self.findPoint)

    def getForm(self):
        '''getForm() ... returns UI'''
        self.getPoint = PathGetPoint.TaskPanel(self)
        return FreeCADGui.PySideUic.loadUi(":/panels/PageOpCustomEdit.ui")

    def getFields(self, obj):
        '''getFields(obj) ... transfers values from UI to obj's properties'''
        self.updateToolController(obj, self.form.toolController)
        self.updateCoolant(obj, self.form.coolantController)

    def setFields(self, obj):
        '''setFields(obj) ... transfers obj's property values to UI'''
        self.setupToolController(obj, self.form.toolController)
        self.form.txtGCode.setText("\n".join(obj.Gcode))
        self.setupCoolant(obj, self.form.coolantController)

    def getSignalsForUpdate(self, obj):
        '''getSignalsForUpdate(obj) ... return list of signals for updating obj'''
        signals = []
        signals.append(self.form.toolController.currentIndexChanged)
        signals.append(self.form.coolantController.currentIndexChanged)
        self.form.txtGCode.textChanged.connect(self.setGCode)
        self.form.btnG0Add.clicked.connect(lambda: self.insertPoint('G0'))
        self.form.btnG1Add.clicked.connect(lambda: self.insertPoint('G1'))
        self.view = FreeCADGui.activeDocument().activeView()
        self.view.addEventCallback("SoMouseButtonEvent",self.findPoint)
        return signals

    def setGCode(self):
        PathLog.track()
        self.obj.Gcode = self.form.txtGCode.toPlainText().splitlines()

    def insertPoint(self, command):
        self.form.txtGCode.insertPlainText("{} X{:.3f} Y{:.3f} Z{:.3f}\n".format(command, self.pnt.x, self.pnt.y, self.pnt.z))

    def findPoint(self, info):
        down = (info["State"] == "DOWN")
        pos = info["Position"]
        if (down):
            self.form.btnG0Add.setEnabled(True)
            self.form.btnG1Add.setEnabled(True)
            self.pnt = self.view.getPoint(pos)
            self.form.txtPoint.setText('X:{:.3f} Y:{:.3f} Z:{:.3f}'.format(self.pnt.x, self.pnt.y, self.pnt.z))


Command = PathOpGui.SetupOperation('Custom', PathCustom.Create, TaskPanelOpPage,
                'Path_Custom',
                QtCore.QT_TRANSLATE_NOOP("Path_Custom", "Custom"),
                QtCore.QT_TRANSLATE_NOOP("Path_Custom", "Create custom gcode snippet"),
                PathCustom.SetupProperties)

FreeCAD.Console.PrintLog("Loading PathCustomGui... done\n")
