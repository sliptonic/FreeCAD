
# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2021 sliptonic <shopinthewoods@gmail.com>               *
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
import PathScripts.PathLog as PathLog
#from pivy import coin
import FreeCADGui
#import Mesh
import Part
import PathScripts
import PathScripts.PathUtils as PathUtils
from PathScripts.PathUtils import depth_params as depth_params
from pivy import coin

from PySide import QtCore #, QtGui

__title__ = "Selection Toy"
__author__ = "sliptonic (Brad Collette)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Task Panel to explore selection management and intent"

PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
PathLog.trackModule(PathLog.thisModule())


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class SelectionToyUI:
    def __init__(self, parent):
        self.strategyList = {
            "MillFacing":0,
            "Roughing":1,
            "Finishing":2,
            "Profiling":3,
            "Facing":4}


        self.pickStyles = {
            "SHAPE": coin.SoPickStyle.SHAPE,
            "BOUNDING_BOX": coin.SoPickStyle.BOUNDING_BOX,
            "UNPICKABLE": coin.SoPickStyle.UNPICKABLE,
            "SHAPE_ON_TOP": coin.SoPickStyle.SHAPE_ON_TOP,
            "BOUNDING_BOX_ON_TOP": coin.SoPickStyle.BOUNDING_BOX_ON_TOP,
            "SHAPE_FRONTFACES": coin.SoPickStyle.SHAPE_FRONTFACES}

        self.form = FreeCADGui.PySideUic.loadUi(":/panels/TaskSelectionToy.ui")
        self.parent = parent

        self.form.cboStrategies.addItems(list(self.strategyList.keys()))
        self.form.cboPick.addItems(list(self.pickStyles.keys()))

        self.form.cboStrategies.currentIndexChanged.connect(self.lucky)
        self.form.cboPick.currentIndexChanged.connect(self.lucky)

        self.job = FreeCADGui.Selection.getSelectionEx()[0].Object
        self.ghost = None

        self.s = SelMonitor(self)
        FreeCADGui.Selection.addObserver(self.s)


    def lucky(self):
        print(FreeCADGui.Selection.getSelectionEx())
        strat = self.form.cboStrategies.currentText()

        if strat == 'MillFacing':
            stock = self.job.Stock

            modeltopZ = self.job.Stock.Shape.BoundBox.ZMin
            for i in self.job.Model.Group:
                if i.Shape.BoundBox.ZMax > modeltopZ:
                    modeltopZ = i.Shape.BoundBox.ZMax

            stocktop = self.job.Stock.Shape.BoundBox.ZMax
            depthparams = depth_params(clearance_height=stocktop,
                                       safe_height=stocktop,
                                       start_depth=stocktop,
                                       step_down=1,
                                       z_finish_step=1,
                                       final_depth=modeltopZ,
                                       user_depths=None,
                                       equalstep=False)

            bb = stock.Shape.BoundBox
            bbperim = Part.makeBox(bb.XLength, bb.YLength,
                                   1,
                                   FreeCAD.Vector(bb.XMin, bb.YMin, bb.ZMin),
                                   FreeCAD.Vector(0, 0, 1))

            self.envelope = PathUtils.getEnvelope(partshape=bbperim,
                                                  depthparams=depthparams)

            self.ghost = self.makeGhost(self.envelope)

    def accept(self):
        # self.parent.accept()
        self.killGhost()

        if self.form.chkMakeSolid.isChecked() and self.envelope is not None:
            Part.show(self.envelope)
        FreeCADGui.Selection.removeObserver(self.s)
        FreeCADGui.Control.closeDialog()

    def reject(self):
        self.killGhost()
        FreeCADGui.Selection.removeObserver(self.s)
        FreeCADGui.Control.closeDialog()

    def killGhost(self):
        if self.ghost is not None:
            graph = FreeCADGui.ActiveDocument.ActiveView.getSceneGraph()
            graph.removeChild(self.ghost)
            self.ghost = None

    def makeGhost(self, shape):
        self.killGhost()

        ghostNode = coin.SoSeparator()

        mat = coin.SoMaterial()
        mat.diffuseColor.setValue(coin.SbColor(0.921, 0.7, 0.930))
        mat.specularColor.setValue(coin.SbColor(1, 1, 1))
        mat.shininess.setValue(1.0)
        mat.transparency.setValue(0.5)

        ghostNode.addChild(mat)

        pick_style = coin.SoPickStyle()
        style = self.pickStyles[self.form.cboPick.currentText()]
        pick_style.style.setValue(style)
        ghostNode.addChild(pick_style)

        mode=2
        deviation=0.3
        angle=0.4
        buf = shape.writeInventor(mode, deviation, angle)

        inp = coin.SoInput()
        inp.setBuffer(buf)

        shapeNode = coin.SoDB.readAll(inp)
        ghostNode.addChild(shapeNode)

        graph = FreeCADGui.ActiveDocument.ActiveView.getSceneGraph()
        graph.addChild(ghostNode)

        return ghostNode


class SelectionTool:

    def Activate(self):
        self.taskForm = SelectionToyUI(self)
        FreeCADGui.Control.showDialog(self.taskForm)


class CommandSelectionToy:
    def GetResources(self):
        return {'Pixmap': 'Path_SelectionToy',
                'MenuText': QtCore.QT_TRANSLATE_NOOP("Path_SelectionToy", "Selection"),
                'Accel': "P, S",
                'ToolTip': QtCore.QT_TRANSLATE_NOOP("Path_SelectionToy", "Selection"),
                'CmdType': "ForEdit"}

    def IsActive(self):
        if bool(FreeCADGui.Selection.getSelection()) is False:
            return False
        try:
            job = FreeCADGui.Selection.getSelectionEx()[0].Object
            return isinstance(job.Proxy, PathScripts.PathJob.ObjectJob)
        except:
            return False

    def Activated(self):
        pathSelectionTool = SelectionTool()
        pathSelectionTool.Activate()


class SelMonitor():
    def __init__(self, parent):
        self.parent = parent

    def addSelection(self, document, object, element, position):
        print('addSelection')
        self.parent.lucky()

    def removeSelection(self, document, object, element):
        print('removeSelection')
        self.parent.lucky()

    def setSelection(self, document):
        print('setSelection')
        self.parent.lucky()

    def clearSelection(self, document):
        print('clearSelection')
        self.parent.lucky()


if FreeCAD.GuiUp:
    FreeCADGui.addCommand('Path_SelectionToy', CommandSelectionToy())

FreeCAD.Console.PrintLog("Loading SelectionToy Gui ... done\n")
