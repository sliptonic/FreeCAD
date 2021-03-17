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

import FreeCADGui
# import PathScripts.PathJob as PathJob
import PathScripts.PathLog as PathLog
# import PathScripts.PathPreferences as PathPreferences
# import PathScripts.PathStock as PathStock
# import PathScripts.PathUtil as PathUtil
# import glob
# import os

from PySide import QtCore, QtGui
# from collections import Counter


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())

class _ItemDelegate(QtGui.QStyledItemDelegate):

    def __init__(self, controller, parent):
        self.controller = controller
        QtGui.QStyledItemDelegate.__init__(self, parent)

    # def createEditor(self, parent, option, index):
    #     # pylint: disable=unused-argument
    #     editor = QtGui.QSpinBox(parent)
    #     self.controller.setupColumnEditor(index, editor)
    #     return editor


class OpCreate:
    DataObject = QtCore.Qt.ItemDataRole.UserRole
    catalog = None

    def __init__(self):
        # pylint: disable=unused-argument
        self.dialog = FreeCADGui.PySideUic.loadUi(":/panels/StrategySelector.ui")
        self.items2D = QtGui.QStandardItem(translate('PathJob', '2D'))
        self.items2D.setEditable(False)
        self.items25D = QtGui.QStandardItem(translate('PathJob', '2.5D'))
        self.items25D.setEditable(False)
        self.items4th = QtGui.QStandardItem(translate('PathJob', '4th Axis'))
        self.items4th.setEditable(False)
        self.itemsLathe = QtGui.QStandardItem(translate('PathJob', 'Lathe'))
        self.itemsLathe.setEditable(False)
        self.itemsUtility = QtGui.QStandardItem(translate('PathJob', 'Utility'))
        self.itemsUtility.setEditable(False)
        self.candidates = None
        self.delegate = None
        self.index = None
        self.model = None

        self.dialog.strategyCatalog.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.dialog.strategyCatalog.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)


        # self.selectionModel = self.dialog.strategyCatalog.selectionModel() # pylint: disable=attribute-defined-outside-init
        # self.selectionModel.selectionChanged.connect(self.selectionChanged)
        # self.selectionChanged()


    def selectionChanged(self):
        indexes = self.selectionModel.selectedRows()
        for index in sorted(indexes):
            item = self.model.itemFromIndex(index)
            # if item.parent() is None:
                #disable to ok button.
            okbutton = self.dialog.buttonBox.button(QtGui.QDialogButtonBox.Ok)
            okbutton.setEnabled (not(item.parent() is None))

    def setupTitle(self, title):
        self.dialog.setWindowTitle(title)

    def setupModel(self):
        testmodel = [
                (["2D","2.5D"],"Drilling","Standard Drilling Method (G81/G82)"),
                (["2D","2.5D"],"Peck Drilling","Standard Drilling Method (G83)"),
                (["2D","2.5D"],"Threading","Standard threading Method (G76)"),
                (["2D","2.5D"],"Profile","Profile Selected Geometry"),
                (["2D","2.5D"],"Contour","Profile the Outside Perimiter of the Shape"),
                (["2.5D"],"Engrave","Engrave a Shapestring"),
                (["2.5D"],"V-Carve","V-Carve Shapestring Text"),
                (["2D","2.5D"],"Helix","Helical clearing of circular region"),
                (["2D","2.5D"],"Boring","Straightline Boring Canned operation (G85/G89)"),
                (["2D","2.5D"],"Deburr","Edge Deburring"),
                (["2D","2.5D"],"Pocket","Standard Pocketing Method"),
                (["2D","2.5D"],"Pocket Shape","Standard Pocketing Method"),
                (["2D","2.5D"],"Mill Facing","Prepare the top of the stock"),
                (["2.5D"],"Slitting Saw","Slot cutting with saw tool"),
                (["2.5D"],"Slot Cut","Run cutter between two parallel surfaces"),
                (["Lathe"],"Center Drill","Center Drilling"),
                (["Lathe"],"Contour Roughing","Remove material to approximate."),
                (["Lathe"],"Contour Finishing","Contour finishing pass"),
                (["Lathe"],"Facing","End Facing"),
                (["Lathe"],"Boring","Boring operation"),
                (["Lathe"],"Threading External","Thread external"),
                (["Lathe"],"Threading Internal","Thread internal"),
                (["2.5D"],"3D Surface (waterline)","OpenCamlib Surface"),
                (["2.5D"],"3D surface (Dropcutter)","OpenCamlib surfacing"),
                (["Utility"],"Stop","Insert an optional or mandatory stop"),
                (["Utility"],"Comment","Insert a comment"),
                (["Utility"],"Custom","Insert custom gcode"),
                (["4th Axis"],"Profile","Profiling Selected geometry with 4th/5th Axis"),
                (["4th Axis"],"Pocket","Standard Pocket on 4th axis machine"),
                (["2.5D"],"Adaptive Roughing","Troichoidal clearing"),
                (["2D","2.5D"], "Holding Tags", "Dressup - Part Holding"),
                (["2D","2.5D"], "Dogbone", "Dressup - Inside corner Clearing"),
                (["2D"], "Dragknife", "Dressup - Dragknife corners"),
                (["2D","2.5D"], "LeadIn/Out", "Dressup - Controlled Entry"),
                (["2.5D"], "Ramp Entry", "Dressup - Ramp Entry"),
                (["2D","2.5D"], "Boundary", "Dressup - Limit Path area"),
                (["2.5D"], "Probe", "Generate a Probing Grid from the stock"),
                (["2.5D"], "Z Correction", "Use Probe data to correct Z Axis moves"),
                (["2D"], "Hatch Fill", "Fill an arbitrary boundary with a hatching pattern")
                ]

#         testmodel = []
#         for i in self.catalog:
#             details = i[1].getDetails()
#             testmodel.append((details['JobTypes'], details['StrategyName'], details['LongDescription']))


        for strategy in testmodel:
            for jobtype in strategy[0]:
                item0 = QtGui.QStandardItem()
                item1 = QtGui.QStandardItem()

                item0.setData(strategy[1], QtCore.Qt.EditRole)
                item0.setEnabled(True) #jobtype in ["Utility"])
                item0.setSelectable(True)#jobtype in ["Utility"])

                item1.setData(strategy[2], QtCore.Qt.EditRole)
                #item1.setEditable(False)
                item1.setEnabled(True) #jobtype in ["Utility"])
                item1.setSelectable(True) #jobtype in ["Utility"])

                if jobtype == '2D':
                    self.items2D.appendRow([item0, item1])
                elif jobtype =='2.5D':
                    self.items25D.appendRow([item0, item1])
                elif jobtype =='Lathe':
                    self.itemsLathe.appendRow([item0, item1])
                elif jobtype =='4th Axis':
                    self.items4th.appendRow([item0, item1])
                else:
                    self.itemsUtility.appendRow([item0, item1])


    #             item0.setData(base.Label, QtCore.Qt.EditRole)
    #             item0.setData(base, self.DataObject)
    #             item0.setCheckable(True)
    #             item0.setEditable(False)

    #             item1.setEnabled(True)
    #             item1.setEditable(True)

    #             if base.Label in preSelected:
    #                 itemSelected = True
    #                 item0.setCheckState(QtCore.Qt.CheckState.Checked)
    #                 item1.setData(preSelected[base.Label], QtCore.Qt.EditRole)
    #             else:
    #                 itemSelected = False
    #                 item0.setCheckState(QtCore.Qt.CheckState.Unchecked)
    #                 item1.setData(0, QtCore.Qt.EditRole)

    #             if PathUtil.isSolid(base):
    #                 self.itemsSolid.appendRow([item0, item1])
    #                 if itemSelected:
    #                     expandSolids = True
    #             else:
    #                 self.items2D.appendRow([item0, item1])
    #                 if itemSelected:
    #                     expand2Ds = True

    #     for j in sorted(PathJob.Instances(), key=lambda x: x.Label):
    #         if j != job:
    #             item0 = QtGui.QStandardItem()
    #             item1 = QtGui.QStandardItem()

    #             item0.setData(j.Label, QtCore.Qt.EditRole)
    #             item0.setData(j, self.DataObject)
    #             item0.setCheckable(True)
    #             item0.setEditable(False)

    #             item1.setEnabled(True)
    #             item1.setEditable(True)

    #             if j.Label in preSelected:
    #                 expandJobs = True
    #                 item0.setCheckState(QtCore.Qt.CheckState.Checked)
    #                 item1.setData(preSelected[j.Label], QtCore.Qt.EditRole)
    #             else:
    #                 item0.setCheckState(QtCore.Qt.CheckState.Unchecked)
    #                 item1.setData(0, QtCore.Qt.EditRole)

    #             self.itemsJob.appendRow([item0, item1])

        self.delegate = _ItemDelegate(self, self.dialog.strategyCatalog)
        self.model = QtGui.QStandardItemModel(self.dialog)
        self.model.setHorizontalHeaderLabels(['Strategy', 'Description'])

        if self.items2D.hasChildren():
            self.model.appendRow(self.items2D)
        if self.items25D.hasChildren():
            self.model.appendRow(self.items25D)
        if self.items4th.hasChildren():
            self.model.appendRow(self.items4th)
        if self.itemsLathe.hasChildren():
            self.model.appendRow(self.itemsLathe)
        if self.itemsUtility.hasChildren():
            self.model.appendRow(self.itemsUtility)

        self.dialog.strategyCatalog.setModel(self.model)
        self.dialog.strategyCatalog.setItemDelegateForColumn(1, self.delegate)
        self.dialog.strategyCatalog.expandAll()
        self.dialog.strategyCatalog.resizeColumnToContents(0)
        self.dialog.strategyCatalog.resizeColumnToContents(1)
        self.dialog.strategyCatalog.collapseAll()

        # if job.JobType == "2D":
        #     self.dialog.strategyCatalog.setExpanded(self.items2D.index(), True)
        # if job.JobType == "2.5D":
        #     self.dialog.strategyCatalog.setExpanded(self.items25D.index(), True)
        # if job.JobType == "Lathe":
        #     self.dialog.strategyCatalog.setExpanded(self.itemsLathe.index(), True)
        # if job.JobType == "4th Axis":
        #     self.dialog.strategyCatalog.setExpanded(self.items4th.index(), True)
        # self.dialog.strategyCatalog.setExpanded(self.itemsUtility.index(), True)

        self.selectionModel = self.dialog.strategyCatalog.selectionModel() # pylint: disable=attribute-defined-outside-init
        self.selectionModel.selectionChanged.connect(self.selectionChanged)

    # def updateData(self, topLeft, bottomRight):
    #     if topLeft.column() == bottomRight.column() == 0:
    #         item0 = self.model.itemFromIndex(topLeft)
    #         item1 = self.model.itemFromIndex(topLeft.sibling(topLeft.row(), 1))
    #         if item0.checkState() == QtCore.Qt.Checked:
    #             if item1.data(QtCore.Qt.EditRole) == 0:
    #                 item1.setData(1, QtCore.Qt.EditRole)
    #         else:
    #             item1.setData(0, QtCore.Qt.EditRole)

    #     if topLeft.column() == bottomRight.column() == 1:
    #         item0 = self.model.itemFromIndex(topLeft.sibling(topLeft.row(), 0))
    #         item1 = self.model.itemFromIndex(topLeft)
    #         if item1.data(QtCore.Qt.EditRole) == 0:
    #             item0.setCheckState(QtCore.Qt.CheckState.Unchecked)
    #         else:
    #             item0.setCheckState(QtCore.Qt.CheckState.Checked)

    def getModels(self):
        models = []

        # for i in range(self.itemsSolid.rowCount()):
        #     for j in range(self.itemsSolid.child(i, 1).data(QtCore.Qt.EditRole)): # pylint: disable=unused-variable
        #         models.append(self.itemsSolid.child(i).data(self.DataObject))

        # for i in range(self.items2D.rowCount()):
        #     for j in range(self.items2D.child(i, 1).data(QtCore.Qt.EditRole)):
        #         models.append(self.items2D.child(i).data(self.DataObject))

        # for i in range(self.itemsJob.rowCount()):
        #     for j in range(self.itemsJob.child(i, 1).data(QtCore.Qt.EditRole)):
        #         # Note that we do want to use the models (resource clones) of the
        #         # source job as base objects for the new job in order to get the
        #         # identical placement, and anything else that's been customized.
        #         models.extend(self.itemsJob.child(i, 0).data(self.DataObject).Model.Group)

        return models


    def exec_(self):
        # ml: For some reason the callback has to be unregistered, otherwise there is a
        # segfault when python is shutdown. To keep it symmetric I also put the callback
        # registration here
        #self.model.dataChanged.connect(self.updateData)
        #self.model.selectionChanged.connect(self.rowSelect)
        rc = self.dialog.exec_()
        self.model.dataChanged.disconnect()

        if rc == 0:
            return None
        else:
            index = self.selectionModel.selectedRows()[0]
            name = self.model.data(index)
            return name
