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
import FreeCADGui
import PathGui as PGui # ensure Path/Gui/Resources are loaded
import PathScripts.PathOperation as PathOperation
import PathScripts.PathOpGui as PathOpGui
import PathScripts.PathGui as PathGui
import PathScripts.PathOpDlg as PathOpDlg

from PySide import QtCore, QtGui

__title__ = "Path Generic Operation UI"
__author__ = "sliptonic (Brad Collette)"
__url__ = "http://www.freecadweb.org"
__doc__ = "Generic operation page controller and command implementation."


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class TaskPanelOpPage(PathOpGui.TaskPanelPage):
    '''Page controller class for the Probing operation.'''

    def getForm(self):
        '''getForm() ... returns UI'''
        return FreeCADGui.PySideUic.loadUi(":/panels/PageOpGenericEdit.ui")

    def getFields(self, obj):
        '''getFields(obj) ... transfers values from UI to obj's proprties'''
        #self.updateToolController(obj, self.form.toolController)
        pass

    def setFields(self, obj):
        '''setFields(obj) ... transfers obj's property values to UI'''
        #self.setupToolController(obj, self.form.toolController)
        self.form.strategy.setText(obj.Strategy)

    def getSignalsForUpdate(self, obj):
        '''getSignalsForUpdate(obj) ... return list of signals for updating obj'''
        signals = []
        self.form.btnStrategy.clicked.connect(self.setStrategy)
        return signals

    def setStrategy(self):
        dialog = PathOpDlg.OpCreate()
        dialog.setupModel()

        strategy = dialog.exec_()

        if strategy is not None:
            print('strategy:{}'.format(strategy))
            self.form.strategy.setText(strategy)


Command = PathOpGui.SetupOperation('Generic', PathOperation.Create, TaskPanelOpPage,
                'Path_Generic',
                QtCore.QT_TRANSLATE_NOOP("Generic", "Generic"),
                QtCore.QT_TRANSLATE_NOOP("Generic", "Create a generic op"),
                PathOperation.SetupProperties)

FreeCAD.Console.PrintLog("Loading PathGenericOperationGui... done\n")
