# -*- coding: utf-8 -*-

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2014 sliptonic <shopinthewoods@gmail.com>               *
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

from __future__ import print_function

import FreeCAD
import FreeCADGui
import Path
import PathScripts
import PathScripts.PathLog as PathLog
import PathScripts.PathToolEdit as PathToolEdit
import PathScripts.PathUtil as PathUtil
import PathScripts.PathUtils as PathUtils
import PathScripts.PathPreferences as PathPreferences
import json
import os
import xml.sax
import glob

from PySide import QtCore, QtGui

PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
PathLog.trackModule(PathLog.thisModule())

def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)

# Tooltable XML readers
class FreeCADTooltableHandler(xml.sax.ContentHandler):
    # http://www.tutorialspoint.com/python/python_xml_processing.htm

    def __init__(self):
        PathLog.track()
        self.tooltable = None
        self.tool = None
        self.number = None

    # Call when an element is found
    def startElement(self, tag, attributes):
        if tag == "Tooltable":
            self.tooltable = Path.Tooltable()
        elif tag == "Toolslot":
            self.number = int(attributes["number"])
        elif tag == "Tool":
            self.tool = Path.Tool()
            self.tool.Name = str(attributes["name"])
            self.tool.ToolType = str(attributes["type"])
            self.tool.Material = str(attributes["mat"])
            # for some reason without the following line I get an error
            #print attributes["diameter"]
            self.tool.Diameter = float(attributes["diameter"])
            self.tool.LengthOffset = float(attributes["length"])
            self.tool.FlatRadius = float(attributes["flat"])
            self.tool.CornerRadius = float(attributes["corner"])
            self.tool.CuttingEdgeAngle = float(attributes["angle"])
            self.tool.CuttingEdgeHeight = float(attributes["height"])
            self.tool.ChipLoad = float(attributes["chipload"])
            self.tool.FluteCount = int(attributes["flutecount"])

    # Call when an elements ends
    def endElement(self, tag):
        if tag == "Toolslot":
            if self.tooltable and self.tool and self.number:
                self.tooltable.setTool(self.number, self.tool)
                self.number = None
                self.tool = None


class HeeksTooltableHandler(xml.sax.ContentHandler):

    def __init__(self):
        self.tooltable = Path.Tooltable()
        self.tool = None
        self.number = None

    # Call when an element is found
    def startElement(self, tag, attributes):
        if tag == "Tool":
            self.tool = Path.Tool()
            self.number = int(attributes["tool_number"])
            self.tool.Name = str(attributes["title"])
        elif tag == "params":
            t = str(attributes["type"])
            if t == "drill":
                self.tool.ToolType = "Drill"
            elif t == "center_drill_bit":
                self.tool.ToolType = "CenterDrill"
            elif t == "end_mill":
                self.tool.ToolType = "EndMill"
            elif t == "slot_cutter":
                self.tool.ToolType = "SlotCutter"
            elif t == "ball_end_mill":
                self.tool.ToolType = "BallEndMill"
            elif t == "chamfer":
                self.tool.ToolType = "Chamfer"
            elif t == "engraving_bit":
                self.tool.ToolType = "Engraver"
            m = str(attributes["material"])
            if m == "0":
                self.tool.Material = "HighSpeedSteel"
            elif m == "1":
                self.tool.Material = "Carbide"
            # for some reason without the following line I get an error
            #print attributes["diameter"]
            self.tool.Diameter = float(attributes["diameter"])
            self.tool.LengthOffset = float(attributes["tool_length_offset"])
            self.tool.FlatRadius = float(attributes["flat_radius"])
            self.tool.CornerRadius = float(attributes["corner_radius"])
            self.tool.CuttingEdgeAngle = float(
                attributes["cutting_edge_angle"])
            self.tool.CuttingEdgeHeight = float(
                attributes["cutting_edge_height"])

    # Call when an elements ends
    def endElement(self, tag):
        if tag == "Tool":
            if self.tooltable and self.tool and self.number:
                self.tooltable.setTool(self.number, self.tool)
                self.number = None
                self.tool = None


class ToolLibraryManager():
    '''
    A Tool Library is a list of individual tools. The user can have any number of tool libraries.
    The Tool Library Manager will allow creation of new tool libraries, as well as add/delete/modif of tools in
    a library.
    '''

    # TooltableTypeJSON     = translate("TooltableEditor", "Tooltable JSON (*.json)")
    # TooltableTypeXML      = translate("TooltableEditor", "Tooltable XML (*.xml)")
    # TooltableTypeHeekscad = translate("TooltableEditor", "HeeksCAD tooltable (*.tooltable)")
    # TooltableTypeLinuxCNC = translate("TooltableEditor", "LinuxCNC tooltable (*.tbl)")

    # PreferenceMainLibraryXML = "ToolLibrary"
    # PreferenceMainLibraryJSON = "ToolLibrary-Main"


    def __init__(self):
        PathLog.track()
        self.prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Path")
        return

    def templateAttrs(self, tooltable):
        attrs = {}
        attrs['Version'] = 1
        attrs['Tools'] = tooltable.templateAttrs()
        return attrs

    def tooltableFromAttrs(self, stringattrs):
        PathLog.track()
        if stringattrs.get('Version') and 1 == int(stringattrs['Version']):
            attrs = {}
            for key, val in PathUtil.keyValueIter(stringattrs['Tools']):
                attrs[int(key)] = val
            return Path.Tooltable(attrs)
        else:
            PathLog.error(translate('PathToolLibraryManager', "Unsupported Path tooltable template version %s") % stringattrs.get('Version'))
        return None

    # def saveMainLibrary(self, tooltable):
    #     '''Persists the permanent library to FreeCAD user preferences'''
    #     PathLog.track()
    #     tmpstring = json.dumps(self.templateAttrs(tooltable))
    #     self.prefs.SetString(self.PreferenceMainLibraryJSON, tmpstring)
    #     return True

    # def getLists(self):
    #     '''Builds the list of all Tool Table lists'''
    #     PathLog.track()
    #     tablelist = []
    #     toollist = "<Main>"
    #     tablelist.append(toollist)

    #     # Get ToolTables from any open CNC jobs
    #     for o in FreeCAD.ActiveDocument.Objects:
    #         if hasattr(o, "Proxy"):
    #             if isinstance(o.Proxy, PathScripts.PathJob.ObjectJob):
    #                 tablelist.append(o.Label)
    #     return tablelist

    # def _findList(self, listname):
    #     PathLog.track()
    #     tt = None
    #     if listname == "<Main>":
    #         tmpstring = self.prefs.GetString(self.PreferenceMainLibraryJSON, "")
    #         if not tmpstring:
    #             tmpstring = self.prefs.GetString(self.PreferenceMainLibraryXML, "")
    #         if tmpstring:
    #             if tmpstring[0] == '{':
    #                 tt = self.tooltableFromAttrs(json.loads(tmpstring))
    #             elif tmpstring[0] == '<':
    #                 # legacy XML table
    #                 Handler = FreeCADTooltableHandler()
    #                 xml.sax.parseString(tmpstring, Handler)
    #                 tt = Handler.tooltable
    #                 # store new format
    #                 self.saveMainLibrary(tt)
    #         else:
    #             tt = Path.Tooltable()
    #     else:
    #         for o in FreeCAD.ActiveDocument.Objects:
    #             if o.Label == listname:
    #                 tt = o.Tooltable
    #     return tt

    # def getTool(self, listname, toolnum):
    #     PathLog.track()
    #     tt = self._findList(listname)
    #     return tt.getTool(toolnum)

    def getTool(self, toolattrs):
        PathLog.track()
        #tt = self._findList(listname)
        print (toolattrs)
        return Path.Tool(json.dumps(toolattrs))

    def getTools(self):
        PathLog.track()

        def unitconv(ivalue):
            val = FreeCAD.Units.Quantity(ivalue, FreeCAD.Units.Length)
            displayed_val = val.UserString      #just the displayed value-not the internal one
            return displayed_val

        libraryFiles = []

        for path in PathPreferences.searchPaths():
            libraryFiles.extend(self.libraryFilesIn(path))

        #tt = self._findList(tablename)

        headers = ["Name","Tool Num.","Tool Type"]
        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(headers)
        
        for lib in libraryFiles:

            with open(PathUtil.toUnicode(lib), "rb") as fp:
                ht = self.tooltableFromAttrs(json.load(fp))

            libitem = QtGui.QStandardItem(os.path.splitext(os.path.basename(lib))[0][6:])
            #for t in ht.Tools:
            for number, t in PathUtil.keyValueIter(ht.Tools):

                itemcheck = QtGui.QStandardItem()
                itemcheck.setCheckable(True)
                #itemNumber =  QtGui.QStandardItem(str(number))
                itemName =  QtGui.QStandardItem(t.Name)
                itemToolType =  QtGui.QStandardItem(t.ToolType)
                itemMaterial =  QtGui.QStandardItem(t.Material)
                itemDiameter =  QtGui.QStandardItem(unitconv(t.Diameter))
                itemLengthOffset =  QtGui.QStandardItem(unitconv(t.LengthOffset))
                itemFlatRadius =  QtGui.QStandardItem(unitconv(t.FlatRadius))
                itmCornerRadius =  QtGui.QStandardItem(unitconv(t.CornerRadius))
                itemCuttingEdgeAngle =  QtGui.QStandardItem(str(t.CuttingEdgeAngle))
                itemCuttingEdgeHeight =  QtGui.QStandardItem(unitconv(t.CuttingEdgeHeight))
                itemChipLoad = QtGui.QStandardItem(unitconv(t.ChipLoad))
                itemFluteCount = QtGui.QStandardItem(int(t.FluteCount))
                itemToolNumber = QtGui.QStandardItem(int(t.ToolNumber))
                itemPocketNumber = QtGui.QStandardItem(int(t.PocketNumber))
                itemattrs = QtGui.QStandardItem(json.dumps(t.templateAttrs()))

                toolrow = [itemcheck, itemName, itemToolType,
                        itemMaterial, itemDiameter, itemLengthOffset,
                        itemFlatRadius, itmCornerRadius, itemCuttingEdgeAngle,
                        itemCuttingEdgeHeight, itemChipLoad, itemFluteCount, 
                        itemToolNumber, itemPocketNumber, itemattrs]
                libitem.appendRow(toolrow)

            model.appendRow(libitem)

        return model





    # def getTools(self, tablename):
    #     '''returns the tool data for a given table'''
    #     PathLog.track()
    #     tooldata = []
    #     tt = self._findList(tablename)
    #     headers = ["Name","Tool Num.","Tool Type"]
    #     model = QtGui.QStandardItemModel()
    #     model.setHorizontalHeaderLabels(headers)

    #     def unitconv(ivalue):
    #         val = FreeCAD.Units.Quantity(ivalue, FreeCAD.Units.Length)
    #         displayed_val = val.UserString      #just the displayed value-not the internal one
    #         return displayed_val

    #     if tt:
    #         if len(tt.Tools) == 0:
    #             tooldata.append([])
    #         for number, t in PathUtil.keyValueIter(tt.Tools):

    #             itemcheck = QtGui.QStandardItem()
    #             itemcheck.setCheckable(True)
    #             itemNumber =  QtGui.QStandardItem(str(number))
    #             itemName =  QtGui.QStandardItem(t.Name)
    #             itemToolType =  QtGui.QStandardItem(t.ToolType)
    #             itemMaterial =  QtGui.QStandardItem(t.Material)
    #             itemDiameter =  QtGui.QStandardItem(unitconv(t.Diameter))
    #             itemLengthOffset =  QtGui.QStandardItem(unitconv(t.LengthOffset))
    #             itemFlatRadius =  QtGui.QStandardItem(unitconv(t.FlatRadius))
    #             itmCornerRadius =  QtGui.QStandardItem(unitconv(t.CornerRadius))
    #             itemCuttingEdgeAngle =  QtGui.QStandardItem(str(t.CuttingEdgeAngle))
    #             itemCuttingEdgeHeight =  QtGui.QStandardItem(unitconv(t.CuttingEdgeHeight))
    #             itemChipLoad = QtGui.QStandardItem(unitconv(t.ChipLoad))
    #             itemFluteCount = QtGui.QStandardItem(int(t.FluteCount))

    #             row = [itemcheck, itemNumber, itemName, itemToolType,
    #                     itemMaterial, itemDiameter, itemLengthOffset,
    #                     itemFlatRadius, itmCornerRadius, itemCuttingEdgeAngle,
    #                     itemCuttingEdgeHeight, itemChipLoad, itemFluteCount]
    #             model.appendRow(row)

    #     return model

    # # methods for importing and exporting
    # def read(self, filename, listname):
    #     "imports a tooltable from a file"

    #     try:
    #         fileExtension = os.path.splitext(filename[0])[1].lower()
    #         xmlHandler = None
    #         if fileExtension == '.tooltable':
    #             xmlHandler = HeeksTooltableHandler()
    #         if fileExtension == '.xml':
    #             xmlHandler = FreeCADTooltableHandler()

    #         if xmlHandler:
    #             parser = xml.sax.make_parser()
    #             parser.setFeature(xml.sax.handler.feature_namespaces, 0)
    #             parser.setContentHandler(xmlHandler)
    #             parser.parse(PathUtil.toUnicode(filename[0]))
    #             if not xmlHandler.tooltable:
    #                 return None

    #             ht = xmlHandler.tooltable
    #         else:
    #             with open(PathUtil.toUnicode(filename[0]), "rb") as fp:
    #                 ht = self.tooltableFromAttrs(json.load(fp))

    #         tt = self._findList(listname)
    #         for t in ht.Tools:
    #             newt = ht.getTool(t).copy()
    #             tt.addTools(newt)
    #         if listname == "<Main>":
    #             self.saveMainLibrary(tt)
    #         return True
    #     except Exception as e:
    #         print("could not parse file", e)


    # def write(self, filename, listname):
    #     "exports the tooltable to a file"
    #     tt = self._findList(listname)
    #     if tt:
    #         try:
    #             def openFileWithExtension(name, ext):
    #                 fext = os.path.splitext(name)[1].lower()
    #                 if fext != ext:
    #                     name = "{}{}".format(name, ext)
    #                 return (open(PathUtil.toUnicode(name), 'wb'), name)

    #             if filename[1] == self.TooltableTypeXML:
    #                 fp,fname = openFileWithExtension(filename[0], '.xml')
    #                 fp.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    #                 fp.write(tt.Content)
    #             elif filename[1] == self.TooltableTypeLinuxCNC:
    #                 fp,fname = openFileWithExtension(filename[0], '.tbl')
    #                 for key in tt.Tools:
    #                     t = tt.Tools[key]
    #                     fp.write("T{} P{} Y{} Z{} A{} B{} C{} U{} V{} W{} D{} I{} J{} Q{} ;{}\n".format(
    #                         key,key,0,t.LengthOffset,0,0,0,0,0,0,t.Diameter,0,0,0,t.Name))
    #             else:
    #                 fp,fname = openFileWithExtension(filename[0], '.json')
    #                 json.dump(self.templateAttrs(tt), fp, sort_keys=True, indent=2)

    #             fp.close()
    #             print("Written ", PathUtil.toUnicode(fname))

    #         except Exception as e:
    #             print("Could not write file:", e)

    # def addnew(self, listname, tool, position = None):
    #     "adds a new tool at the end of the table"
    #     PathLog.track()
    #     print(listname, tool, position)
    #     tt = self._findList(listname)
    #     if not tt:
    #         tt = Path.Tooltable()
    #     if position is None:
    #         tt.addTools(tool)
    #         newID = tt.Tools.keys()[-1]
    #     else:
    #         tt.setTool(position, tool)
    #         newID = position

    #     if listname == "<Main>":
    #         return self.saveMainLibrary(tt)
    #     return newID

    # def updateTool(self, listname, toolnum, tool):
    #     '''updates tool data'''
    #     PathLog.track()
    #     tt = self._findList(listname)
    #     tt.deleteTool(toolnum)
    #     tt.setTool(toolnum, tool)
    #     if listname == "<Main>":
    #         return self.saveMainLibrary(tt)
    #     return True

    # def moveup(self, number, listname):
    #     "moves a tool to a lower number, if possible"
    #     PathLog.track()
    #     if number < 2:
    #         return False
    #     target = number - 1
    #     tt = self._findList(listname)

    #     t1 = tt.getTool(number).copy()
    #     tt.deleteTool(number)
    #     if target in tt.Tools.keys():
    #         t2 = tt.getTool(target).copy()
    #         tt.deleteTool(target)
    #         tt.setTool(number, t2)
    #     tt.setTool(target, t1)
    #     if listname == "<Main>":
    #         self.saveMainLibrary(tt)
    #     return True

    # def movedown(self, number, listname):
    #     "moves a tool to a higher number, if possible"
    #     PathLog.track()
    #     tt = self._findList(listname)
    #     target = number + 1
    #     t1 = tt.getTool(number).copy()
    #     tt.deleteTool(number)
    #     if target in tt.Tools.keys():
    #         t2 = tt.getTool(target).copy()
    #         tt.deleteTool(target)
    #         tt.setTool(number, t2)
    #     tt.setTool(target, t1)
    #     if listname == "<Main>":
    #         self.saveMainLibrary(tt)
    #     return True

    # def delete(self, number, listname):
    #     '''deletes a tool from the current list'''
    #     PathLog.track()
    #     tt = self._findList(listname)
    #     tt.deleteTool(number)
    #     if listname == "<Main>":
    #         self.saveMainLibrary(tt)
    #     return True




    def libraryFilesIn(self, path):
        '''libraryFilesIn(path) ... answer all file in the given directory which fit the tool library naming convention.
        Tool libarary files are name tools_*.json'''
        PathLog.track(path)
        return glob.glob(path + '/tools_*.json')


class EditorPanel():

    def __init__(self, job, cb):
        PathLog.track()
        self.form = FreeCADGui.PySideUic.loadUi(":/panels/ToolLibraryEditor.ui")
        self.TLM = ToolLibraryManager()

        self.loadTable()
        #self.form.ToolsList.resizeColumnsToContents()
        self.job = job
        self.cb = cb

    def toolEditor(self, tool):
        dialog = FreeCADGui.PySideUic.loadUi(":/panels/DlgToolEdit.ui")
        editor = PathToolEdit.ToolEditor(tool, dialog.toolEditor, dialog)
        editor.setupUI()
        return editor

    def accept(self):
        pass

    def reject(self):
        FreeCADGui.Control.closeDialog()
        FreeCAD.ActiveDocument.recompute()

    def getFields(self):
        pass

    def getType(self, tooltype):
        "gets a combobox index number for a given type or viceversa"
        toolslist = Path.Tool.getToolTypes(Path.Tool())
        if isinstance(tooltype, str):
            if tooltype in toolslist:
                return toolslist.index(tooltype)
            else:
                return 0
        else:
            return toolslist[tooltype]

    def getMaterial(self, material):
        "gets a combobox index number for a given material or viceversa"
        matslist = Path.Tool.getToolMaterials(Path.Tool())
        if isinstance(material, str):
            if material in matslist:
                return matslist.index(material)
            else:
                return 0
        else:
            return matslist[material]

    def addTool(self):
        PathLog.track()
        tool = Path.Tool()
        editor = self.toolEditor(tool)

        r = editor.Parent.exec_()
        if r:
            editor.accept()
            listname = "<Main>"
            if self.TLM.addnew(listname, editor.Tool) is True:
                self.loadTable()

    def setFields(self):
        pass

    def open(self):
        pass

    def loadTable(self):
        PathLog.track()
        #tooldata = self.TLM.getTools(curr.data())
        tooldata = self.TLM.getTools()
        self.form.ToolsList.setModel(tooldata)

    def moveUp(self):
        "moves a tool to a lower number, if possible"
        item = self.form.ToolsList.selectedIndexes()[1].data()
        if item:
            number = int(item)
            listname = "<Main>"
            #listname = self.form.listView.selectedIndexes()[0].data()
            if self.TLM.moveup(number, listname) is True:
                self.loadTable()

    def moveDown(self):
        "moves a tool to a higher number, if possible"
        item = self.form.ToolsList.selectedIndexes()[1].data()
        if item:
            number = int(item)
            listname = "<Main>"
            #listname = self.form.listView.selectedIndexes()[0].data()
            if self.TLM.movedown(number, listname) is True:
                self.loadTable()

    def delete(self):
        '''deletes a tool'''
        #listname  =  self.form.listView.selectedIndexes()[0].data()
        listname = "<Main>"
        model = self.form.ToolsList.model()
        for i in range(model.rowCount()):
            item = model.item(i, 0)
            if item.checkState():
                t = model.index(i, 1)
                self.TLM.delete(int(t.data()) ,listname)
        self.loadTable()

    def editTool(self, currItem):

        row = currItem.row()
        value = currItem.sibling(row, 14).data()
        #print(value)
        #listname = self.form.listView.selectedIndexes()[0].data()
        #listname = "<Main>"
        #toolnum = int(value)
        #tool = self.TLM.getTool(listname, toolnum)
        tool = self.TLM.getTool(value)
        editor = self.toolEditor(tool)

        r = editor.Parent.exec_()
        if r:
            editor.accept()
            if self.TLM.updateTool(listname, toolnum, editor.Tool) is True:
                self.loadTable()

    def importFile(self):
        "imports a tooltable from a file"
        filename = QtGui.QFileDialog.getOpenFileName(self.form, translate( "TooltableEditor", "Open tooltable", None), None, "{};;{};;{}".format(ToolLibraryManager.TooltableTypeJSON, ToolLibraryManager.TooltableTypeXML, ToolLibraryManager.TooltableTypeHeekscad))
        if filename[0]:
            listname = '<Main>'
            if self.TLM.read(filename, listname):
                self.loadTable()


    def exportFile(self):
        "export a tooltable to a file"
        filename = QtGui.QFileDialog.getSaveFileName(self.form, translate("TooltableEditor", "Save tooltable", None), None, "{};;{};;{}".format(ToolLibraryManager.TooltableTypeJSON, ToolLibraryManager.TooltableTypeXML, ToolLibraryManager.TooltableTypeLinuxCNC))

        if filename[0]:
            #listname = self.form.listView.selectedIndexes()[0].data()
            listname = '<Main>'
            self.TLM.write(filename, listname)

    def checkCopy(self):
        self.form.btnCopyTools.setEnabled(False)
        model = self.form.ToolsList.model()
        for i in range(model.rowCount()):
            item = model.item(i, 0)
            if item.checkState():
                self.form.btnCopyTools.setEnabled(True)

        if len(PathUtils.GetJobs()) == 0:
            self.form.btnCopyTools.setEnabled(False)

    def copyTools(self):
        tools = []
        model = self.form.ToolsList.model()
        for i in range(model.rowCount()):
            item = model.item(i, 0)
            if item.checkState():
                item = model.index(i, 1)
                tools.append(item.data())
        if len(tools) == 0:
            return

        targets = self.TLM.getLists()
        currList = "<Main>"

        for target in targets:
            if target == currList:
                targets.remove(target)

        if len(targets) == 0:
            FreeCAD.Console.PrintWarning("no place to go")
            return
        elif len(targets) == 1:
            targetlist = targets[0]
        else:
            form = FreeCADGui.PySideUic.loadUi(":/panels/DlgToolCopy.ui")
            form.cboTarget.addItems(targets)
            r = form.exec_()
            if r is False:
                return None
            else:
                targetlist = form.cboTarget.currentText()

        for toolnum in tools:
            tool = self.TLM.getTool(currList, int(toolnum))
            PathLog.debug('tool: {}, toolnum: {}'.format(tool, toolnum))
            if self.job:
                label = "T{}: {}".format(toolnum, tool.Name)
                tc = PathScripts.PathToolController.Create(label, tool=tool, toolNumber=int(toolnum))
                self.job.Proxy.addToolController(tc)
            else:
                for job in FreeCAD.ActiveDocument.findObjects("Path::Feature"):
                    if isinstance(job.Proxy, PathScripts.PathJob.ObjectJob) and job.Label == targetlist:
                        label = "T{}: {}".format(toolnum, tool.Name)
                        tc = PathScripts.PathToolController.Create(label, tool=tool, toolNumber=int(toolnum))
                        job.Proxy.addToolController(tc)
        if self.cb:
            self.cb()
        FreeCAD.ActiveDocument.recompute()

    def getStandardButtons(self):
        return int(QtGui.QDialogButtonBox.Ok)

    def setupUi(self):
        # Connect Signals and Slots
        self.form.ButtonNewTool.clicked.connect(self.addTool)
        self.form.ButtonImport.clicked.connect(self.importFile)
        self.form.ButtonExport.clicked.connect(self.exportFile)
        # self.form.ButtonDown.clicked.connect(self.moveDown)
        # self.form.ButtonUp.clicked.connect(self.moveUp)
        self.form.ButtonDelete.clicked.connect(self.delete)
        self.form.ToolsList.doubleClicked.connect(self.editTool)
        self.form.ToolsList.clicked.connect(self.checkCopy)
        self.form.btnCopyTools.clicked.connect(self.copyTools)

        self.form.btnCopyTools.setEnabled(False)

        self.setFields()

class CommandToolLibraryEdit():
    def edit(self, job=None, cb=None):
        editor = EditorPanel(job, cb)
        editor.setupUi()

        r = editor.form.exec_()
        if r:
            pass

    def GetResources(self):
        return {'Pixmap'  : 'Path-ToolTable',
                'MenuText': QtCore.QT_TRANSLATE_NOOP("Path_ToolTable","Tool Manager"),
                'Accel': "P, T",
                'ToolTip': QtCore.QT_TRANSLATE_NOOP("Path_ToolTable","Tool Manager")}

    def IsActive(self):
        return not FreeCAD.ActiveDocument is None

    def Activated(self):

        self.edit()

if FreeCAD.GuiUp:
    # register the FreeCAD command
    FreeCADGui.addCommand('Path_ToolLibraryEdit',CommandToolLibraryEdit())
