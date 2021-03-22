# -*- coding: utf-8 -*-
# ***************************************************************************
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
import PathScripts.PathLog as PathLog
# from pivy import coin
# from itertools import cycle
# import FreeCADGui as Gui
# import json
# import tempfile
import os
import Mesh
# import string
# import random
import camotics
import PathScripts.PathPost  as PathPost
import io
# import time
import PathScripts
import queue
from threading import Thread, Lock
import subprocess

from PySide import QtCore #, QtGui

__title__ = "Camotics Simulator"
__author__ = "sliptonic (Brad Collette)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Task panel for Camotics Simulation"

PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
PathLog.trackModule(PathLog.thisModule())

# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class CAMoticsUI:
    def __init__(self, simulation):
        # this will create a Qt widget from our ui file
        self.form = FreeCADGui.PySideUic.loadUi(":/panels/TaskPathCamoticsSim.ui")
        self.simulation = simulation
        self.initializeUI()
        self.lock = False

    def initializeUI(self):
        self.form.timeSlider.sliderReleased.connect(lambda : self.simulation.XXX(self.form.timeSlider.value()))
        self.form.progressBar.reset() #setValue(0)
        self.form.timeSlider.setEnabled=False
        self.form.btnLaunchCamotics.clicked.connect(self.launchCamotics)
        # self.form.btnMakeFile.clicked.connect(self.f2)
        self.simulation.progressUpdate.connect(self.calculating)

    def launchCamotics(self):
        subprocess.Popen(["camotics", ""])

    def accept(self):
        self.simulation.accept()
        FreeCADGui.Control.closeDialog()

    def reject(self):
        self.simulation.cancel()
        FreeCADGui.Control.closeDialog()

    def setRunTime(self, duration):
        self.form.timeSlider.setMinimum(0)
        self.form.timeSlider.setMaximum(duration)

    def calculating(self, progress=0.0):
        self.form.timeSlider.setEnabled = (progress == 1.0)
        self.form.progressBar.setValue(int(progress*100))


class CamoticsSimulation(QtCore.QObject):

    SIM = camotics.Simulation()
    q = queue.Queue()
    progressUpdate      = QtCore.Signal(object)

    SHAPEMAP = {'ballend': 'Ballnose',
                'endmill': 'Cylindrical',
                'v-bit'  : 'Conical',
                'chamfer': 'Snubnose'}

    def worker(self, lock):
        while True:
            item = self.q.get()
            print('worker processing: {}'.format(item))
            with lock:
                if item['TYPE'] == 'STATUS':
                    if item['VALUE'] == 'DONE':
                        self.SIM.wait()
                        surface = self.SIM.get_surface('binary')
                        self.SIM.wait()
                        self.addMesh(surface)
                elif item['TYPE'] == 'PROGRESS':
                    #self.taskForm.calculating(item['VALUE'])
                    msg = item['VALUE']
                    self.progressUpdate.emit(msg)
            print('lockoff')
            self.q.task_done()



    def __init__(self):
        super().__init__()  # needed for QT signals
        lock = Lock()
        Thread(target=self.worker, daemon=True, args=(lock,)).start()

    def callback(self, status, progress):
        self.q.put({'TYPE': 'PROGRESS', 'VALUE': progress})
        self.q.put({'TYPE': 'STATUS'  , 'VALUE': status  })

    def isDone(self, success):
        self.q.put({'TYPE': 'STATUS'  , 'VALUE': 'DONE'})


    def addMesh(self, surface):
        '''takes a binary stl and adds a Mesh to the current docuemnt'''

        buffer=io.BytesIO()
        buffer.write(surface)
        buffer.seek(0)
        mesh=Mesh.Mesh()
        mesh.read(buffer, "STL")
        Mesh.show(mesh)

    def Activate(self):
        self.taskForm = CAMoticsUI(self)
        FreeCADGui.Control.showDialog(self.taskForm)
        self.job = FreeCADGui.Selection.getSelectionEx()[0].Object
        self.SIM.set_metric()
        self.SIM.set_resolution('high')

        bb = self.job.Stock.Shape.BoundBox
        self.SIM.set_workpiece(min = (bb.XMin, bb.YMin, bb.ZMin), max = (bb.XMax, bb.YMax, bb.ZMax))

        for t in self.job.Tools.Group:
            self.SIM.set_tool(t.ToolNumber,
                    metric = True,
                    shape = self.SHAPEMAP.get(t.Tool.ShapeName, 'Cylindrical'),
                    length = t.Tool.Length.Value,
                    diameter = t.Tool.Diameter.Value)

        postlist = PathPost.buildPostList(self.job)
        filename = PathPost.resolveFileName(self.job)

        #gcode = PathPost.CommandPathPost().exportObjectsWith(objlist, self.job, needFilename=False)

        success = True

        gcode = ""
        if self.job.SplitOutput:
            for index, slist in enumerate(postlist):
                split = os.path.splitext(filename)
                partname = split[0] + "_{}".format(index) + split[1]
                result = PathPost.CommandPathPost().exportObjectsWith(slist, self.job, partname)
                if result is None:
                    success = False
                else:
                    gcode += result

        else:
            finalpostlist = [item for slist in postlist for item in slist]
            gcode = PathPost.CommandPathPost().exportObjectsWith(finalpostlist, self.job, False)
            success = gcode is not None

        if not success:
            return
        # gcode = self.job.Path.toGCode()  #temporary solution!!!!!
        self.SIM.compute_path(gcode)
        self.SIM.wait()


        tot = sum([step['time'] for step in self.SIM.get_path()])
        print("sim time: {}".format(tot))
        self.taskForm.setRunTime(tot)
        # print(self.SIM.get_path())

        #self.taskForm.calculating()
        #self.SIM.start(self.callback, done=self.isDone)

    def XXX(self, timeIndex):
        #self.taskForm.calculating()
        self.SIM.start(self.callback, time=timeIndex, done=self.isDone)
        # while self.SIM.is_running():
        #     time.sleep(0.1)

        # self.SIM.wait()

        # surface = self.SIM.get_surface('binary')
        # self.addMesh(surface)

    #def makeCoinMesh(self, surface):
    #    # this doesn't work yet
    #    sg = Gui.ActiveDocument.ActiveView.getSceneGraph();
    #    color = coin.SoBaseColor()
    #    color.rgb = (1, 0, 1)
    #    coords = coin.SoTransform()
    #    node = coin.SoSeparator()
    #    node.addChild(color)
    #    node.addChild(coords)

    #    end = [-1]
    #    vertices = list(zip(*[iter(surface['vertices'])] * 3))
    #    #polygons = list(zip(*[iter(vertices)] * 3, cycle(end)))
    #    polygons = list(zip(*[iter(range(len(vertices)))] * 3, cycle(end)))

    #    print(vertices)
    #    print(polygons)

    #    data=coin.SoCoordinate3()
    #    face=coin.SoIndexedFaceSet()
    #    node.addChild(data)
    #    node.addChild(face)

    #    i = 0
    #    for v in vertices:
    #        data.point.set1Value(i, v[0], v[1], v[2])
    #        i += 1
    #    i = 0
    #    for p in polygons:
    #        try:
    #            face.coordIndex.set1Value(i, p)
    #            i += 1
    #        except Exception as e:
    #            print(e)
    #            print(i)
    #            print(p)

    #    sg.addChild(node)


    # def Activated(self):

    #     s = self.SIM
    #     print('activated')
    #     print (s.is_running())

    #     if s.is_running():
    #         print('interrupted')
    #         s.interrupt()
    #         s.wait()
    #     else:
    #         try:
    #             surface = s.get_surface('python')
    #         except Exception as e:
    #             print(e)
    #             pp = CommandPathPost()
    #             job = FreeCADGui.Selection.getSelectionEx()[0].Object


    #             s = camotics.Simulation()
    #             s.set_metric()
    #             s.set_resolution('high')

    #             bb = job.Stock.Shape.BoundBox
    #             s.set_workpiece(min = (bb.XMin, bb.YMin, bb.ZMin), max = (bb.XMax, bb.YMax, bb.ZMax))

    #             shapemap = {'ballend': 'Ballnose',
    #                         'endmill': 'Cylindrical',
    #                         'v-bit'  : 'Conical',
    #                         'chamfer': 'Snubnose'}

    #             for t in job.Tools.Group:
    #                 s.set_tool(t.ToolNumber,
    #                         metric = True,
    #                         shape = shapemap.get(t.Tool.ShapeName, 'Cylindrical'),
    #                         length = t.Tool.Length.Value,
    #                         diameter = t.Tool.Diameter.Value)

    #             gcode = job.Path.toGCode()  #temporary solution!!!!!
    #             s.compute_path(gcode)
    #             s.wait()

    #             print(s.get_path())

    #             tot = sum([step['time'] for step in s.get_path()])

    #             print(tot)

    #             for t in range(1, int(tot), int(tot/10)):
    #                 print(t)
    #                 s.start(callback, time=t)
    #                 while s.is_running():
    #                     time.sleep(0.1)

    #                 s.wait()

    #                 surface = s.get_surface('binary')
    #                 self.addMesh(surface)

    def RemoveMaterial(self):
        pass
        # if self.cutMaterial is not None:
        #     FreeCAD.ActiveDocument.removeObject(self.cutMaterial.Name)
        #     self.cutMaterial = None
        # self.RemoveInnerMaterial()

    def accept(self):
        pass
        # self.EndSimulation()
        # self.RemoveInnerMaterial()
        # self.RemoveTool()

    def cancel(self):
        # self.EndSimulation()
        # self.RemoveTool()
        self.RemoveMaterial()


    def buildproject(self, files=[]):

        job = self.job

        tooltemplate = {
            "units": "metric",
            "shape": "cylindrical",
            "length": 10,
            "diameter": 3.125,
            "description": ""
        }

        workpiecetemplate = {
            "automatic": "false",
            "margin": 0,
            "bounds": {
                "min": [0, 0, 0],
                "max": [0, 0, 0]}
        }

        camoticstemplate = {
            "units": "metric",
            "resolution-mode": "medium",
            "resolution": 1,
            "tools": {},
            "workpiece": {},
            "files": []
        }

        unitstring = "imperial" if FreeCAD.Units.getSchema() in [2,3,5,7] else "metric"

        camoticstemplate["units"] = unitstring
        camoticstemplate["resolution-mode"] = "medium"
        camoticstemplate["resolution"] = 1

        toollist = {}
        for t in job.Tools.Group:
            tooltemplate["units"] = unitstring
            if hasattr(t.Tool, 'Camotics'):
                tooltemplate["shape"] = t.Tool.Camotics
            else:
                tooltemplate["shape"] = self.shapemap.get(t.Tool.ShapeName, 'Cylindrical')

            tooltemplate["length"] = t.Tool.Length.Value
            tooltemplate["diameter"] = t.Tool.Diameter.Value
            tooltemplate["description"] = t.Label
            toollist[t.ToolNumber] = tooltemplate

        camoticstemplate['tools'] = toollist

        bb = job.Stock.Shape.BoundBox

        workpiecetemplate['bounds']['min'] = [bb.XMin, bb.YMin, bb.ZMin]
        workpiecetemplate['bounds']['max'] = [bb.XMax, bb.YMax, bb.ZMax]
        camoticstemplate['workpiece'] = workpiecetmpl

        camoticstemplate['files'] = files

        return json.dumps(camoticstemplate, indent=2)


class CommandCamoticsSimulate:
    def GetResources(self):
        return {'Pixmap': 'Path_Camotics',
                'MenuText': QtCore.QT_TRANSLATE_NOOP("Path_Camotics", "Camotics"),
                'Accel': "P, C",
                'ToolTip': QtCore.QT_TRANSLATE_NOOP("Path_Camotics", "Simulate using Camotics"),
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
        pathSimulation.Activate()


pathSimulation = CamoticsSimulation()

if FreeCAD.GuiUp:
    FreeCADGui.addCommand('Path_Camotics', CommandCamoticsSimulate())


FreeCAD.Console.PrintLog("Loading PathCamoticsSimulateGui ... done\n")
