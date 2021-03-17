# -*- coding: utf-8 -*-

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2020 sliptonic <shopinthewoods@gmail.com>               *
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
import PathScripts.Strategy as Strategy
# import PathScripts.PathJob as PathJob
import PathScripts.PathOpDlg as PathOpDlg
import PathScripts.PathLog as PathLog
# import PathScripts.PathPreferences as PathPreferences
# import PathScripts.PathStock as PathStock
# import PathScripts.PathUtil as PathUtil
# import json
# import os
import PathScripts.PathUtils as PathUtils
import inspect
from PySide import QtCore, QtGui
import PathScripts.PathOperationGui as PathOperationGui

# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())


class CommandOpCreate:
    '''
    Command used to create an operation.
    When activated the command parses the current selection,
    opens a dialog allowing the user to select an operation strategy.
    It then creates an operation using that strategy.
    '''

    def __init__(self):
        pass

    def GetResources(self):
        return {'Pixmap': 'Path-New-Operation',
                'MenuText': QtCore.QT_TRANSLATE_NOOP("Path_New_Operation", "New Operation"),
                'Accel': "P, O",
                'ToolTip': QtCore.QT_TRANSLATE_NOOP("Path_New_Operation", "Creates an operation object")}

    def IsActive(self):
        if FreeCAD.ActiveDocument is not None:
            for o in FreeCAD.ActiveDocument.Objects:
                if o.Name[:3] == "Job":
                    return True
        return False


    def Activated(self):
        # jobs = PathUtils.GetJobs()

        # if len(jobs) > 1:
        #     form = FreeCADGui.PySideUic.loadUi(":/panels/DlgJobChooser.ui")
        #     form.cboProject.addItems([job.Label for job in jobs])
        #     r = form.exec_()
        #     if r is False:
        #         return
        #     else:
        #         job = PathUtils.GetJobs(form.cboProject.currentText())
        # else:
        #     job = jobs[0]

        # stratlist = []
        dialog = PathOpDlg.OpCreate()
        dialog.setupModel()

        result = dialog.exec_()

        if result is not None:
            obj = PathOperationGui.Command.Activated()
            obj.Label = result
            obj.Strategy = result
            print('in cmd strategy:{}'.format(obj.Strategy))


    @classmethod
    def Execute(cls, base, template):
        FreeCADGui.addModule('PathScripts.PathOpGui')
        FreeCADGui.doCommand('PathScripts.PathOpGui.Create()')


if FreeCAD.GuiUp:
    # register the FreeCAD command
    FreeCADGui.addCommand('Path_Op', CommandOpCreate())

FreeCAD.Console.PrintLog("Loading PathOpCmd... done\n")
