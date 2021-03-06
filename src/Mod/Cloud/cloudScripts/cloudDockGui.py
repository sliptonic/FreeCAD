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
import PySide
import cloudScripts.preferences as preferences

class ModelFactory(object):
    ''' Helper class to generate qtdata models for CADcloud instance
    '''

    def __init__(self, path=None):
        PathLog.track()
        self.path = ""
        # self.currentLib = ""

    def __libraryLoad(self, path, datamodel):
        PathLog.track(path)
        PathPreferences.setLastFileToolLibrary(path)
        # self.currenLib = path

        with open(path) as fp:
            library = json.load(fp)

        for toolBit in library['tools']:
            try:
                nr = toolBit['nr']
                bit = PathToolBit.findToolBit(toolBit['path'], path)
                if bit:
                    PathLog.track(bit)
                    tool = PathToolBit.Declaration(bit)
                    datamodel.appendRow(self._toolAdd(nr, tool, bit))
                else:
                    PathLog.error("Could not find tool #{}: {}".format(nr, toolBit['path']))
            except Exception as e:
                msg = "Error loading tool: {} : {}".format(toolBit['path'], e)
                FreeCAD.Console.PrintError(msg)

    def _toolAdd(self, nr, tool, path):

        strShape = os.path.splitext(os.path.basename(tool['shape']))[0]
        # strDiam = tool['parameter']['Diameter']
        tooltip = "{}".format(strShape)

        toolNr = PySide.QtGui.QStandardItem()
        toolNr.setData(nr, PySide.QtCore.Qt.EditRole)
        toolNr.setToolTip(tool['shape'])
        toolNr.setData(path, _PathRole)
        toolNr.setData(UUID.uuid4(), _UuidRole)
        toolNr.setToolTip(tooltip)

        toolName = PySide.QtGui.QStandardItem()
        toolName.setData(tool['name'], PySide.QtCore.Qt.EditRole)
        toolName.setEditable(False)
        toolName.setToolTip(tooltip)

        toolShape = PySide.QtGui.QStandardItem()
        toolShape.setData(strShape, PySide.QtCore.Qt.EditRole)
        toolShape.setEditable(False)

        return [toolNr, toolName, toolShape]

    def newTool(self, datamodel, path):
        '''
        Adds a toolbit item to a model
        '''
        PathLog.track()

        try:
            nr = 0
            for row in range(datamodel.rowCount()):
                itemNr = int(datamodel.item(row, 0).data(PySide.QtCore.Qt.EditRole))
                nr = max(nr, itemNr)
            nr += 1
            tool = PathToolBit.Declaration(path)
        except Exception as e:
            PathLog.error(e)

        datamodel.appendRow(self._toolAdd(nr, tool, path))

    def findLibraries(self, model):
        '''
        Finds all the fctl files in a location
        Returns a QStandardItemModel
        '''
        PathLog.track()
        path = PathPreferences.lastPathToolLibrary()

        if os.path.isdir(path):  # opening all tables in a directory
            libFiles = [f for f in glob.glob(path + os.path.sep + '*.fctl')]
            libFiles.sort()
            for libFile in libFiles:
                loc, fnlong = os.path.split(libFile)
                fn, ext = os.path.splitext(fnlong)
                libItem = PySide.QtGui.QStandardItem(fn)
                libItem.setToolTip(loc)
                libItem.setData(libFile, _PathRole)
                libItem.setIcon(PySide.QtGui.QPixmap(':/icons/Path_ToolTable.svg'))
                model.appendRow(libItem)

        PathLog.debug('model rows: {}'.format(model.rowCount()))
        return model

    def libraryOpen(self, model, lib=""):
        '''
        opens the tools in library
        Returns a QStandardItemModel
        '''
        PathLog.track(lib)

        if lib == "":
            lib = PathPreferences.lastFileToolLibrary()

        if lib == "" or lib is None:
            return model

        if os.path.isfile(lib):  # An individual library is wanted
            self.__libraryLoad(lib, model)

        PathLog.debug('model rows: {}'.format(model.rowCount()))
        return model


class CloudDock(object):
    '''Dock object for showing models on servers and downloading'''

    def __init__(self):
        self.form = FreeCADGui.PySideUic.loadUi(':/panels/CloudDock.ui')
        # self.factory = ModelFactory()
        # self.toolModel = PySide.QtGui.QStandardItemModel(0, len(self.columnNames()))
        self.setupUI()
        self.title = self.form.windowTitle()

    def columnNames(self):
        return ['', 'Model']

    # def currentLibrary(self, shortNameOnly):
    #     libfile = PathPreferences.lastFileToolLibrary()
    #     if libfile is None or libfile == "":
    #         return ""
    #     elif shortNameOnly:
    #         return os.path.splitext(os.path.basename(libfile))[0]
    #     return libfile

    def loadData(self):
    #     self.toolModel.clear()
    #     self.toolModel.setHorizontalHeaderLabels(self.columnNames())
        servers = preferences.getServers()
        print(servers)
        for server in servers:
            self.form.cboServers.addItem(server['name'])
    #     self.form.lblLibrary.setText(self.currentLibrary(True))
    #     self.form.lblLibrary.setToolTip(self.currentLibrary(False))
    #     self.factory.libraryOpen(self.toolModel)
    #     self.toolModel.takeColumn(3)
    #     self.toolModel.takeColumn(2)

    def setupUI(self):
        self.loadData()
        # self.form.tools.setModel(self.toolModel)
        # self.form.tools.selectionModel().selectionChanged.connect(self.enableButtons)
        # self.form.tools.doubleClicked.connect(partial(self.selectedOrAllToolControllers))
        # self.form.libraryEditorOpen.clicked.connect(self.libraryEditorOpen)
        # self.form.addToolController.clicked.connect(self.selectedOrAllToolControllers)

    # def enableButtons(self):
    #     selected = (len(self.form.tools.selectedIndexes()) >= 1)
    #     if selected:
    #         jobs = len([1 for j in FreeCAD.ActiveDocument.Objects if j.Name[:3] == "Job"]) >= 1
    #     self.form.addToolController.setEnabled(selected and jobs)


    def open(self):
        ''' load library stored in path and bring up ui'''
        docs = FreeCADGui.getMainWindow().findChildren(PySide.QtGui.QDockWidget)
        for doc in docs:
            if doc.objectName() == "CloudDock":
                if doc.isVisible():
                    doc.deleteLater()
                    return
                else:
                    doc.setVisible(True)
                    return

        mw = FreeCADGui.getMainWindow()
        mw.addDockWidget(PySide.QtCore.Qt.RightDockWidgetArea, self.form,
                         PySide.QtCore.Qt.Orientation.Vertical)
