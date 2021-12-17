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

import Path
import FreeCAD
import Generators.helix_generator as generator
import PathScripts.PathLog as PathLog
import PathTests.PathTestUtils as PathTestUtils
import Part


import PathScripts.PathJob as PathJob
import PathScripts.PathCustom as PathCustom

if FreeCAD.GuiUp:
    import PathScripts.PathCustomGui as PathCustomGui
    import PathScripts.PathJobGui as PathJobGui


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
PathLog.trackModule(PathLog.thisModule())


def _addViewProvider(op):
    if FreeCAD.GuiUp:
        PathOpGui = PathCustomGui.PathOpGui
        cmdRes = PathCustomGui.Command.res
        op.ViewObject.Proxy = PathOpGui.ViewProvider(op.ViewObject, cmdRes)
        op.ViewObject.Proxy.deleteOnReject = False
        op.ViewObject.Visibility = False


class TestPathHelixGenerator(PathTestUtils.PathTestBase):
    @classmethod
    def setUpClass(cls):
        """setUpClass()...
        This method is called upon instantiation of this test class.  Add code and objects here
        that are needed for the duration of the test() methods in this class.  In other words,
        set up the 'global' test environment here; use the `setUp()` method to set up a 'local'
        test environment.
        This method does not have access to the class `self` reference, but it
        is able to call static methods within this same class.
        """

        # Open existing FreeCAD document with test geometry
        # doc = FreeCAD.open(
        #     FreeCAD.getHomePath() + "Mod/Path/PathTests/test_adaptive.fcstd"
        # )

        doc = FreeCAD.ActiveDocument
        box = doc.addObject("Part::Box", "Box")
        box.Shape = Part.makeBox(30, 20, 10)

        # Create Job object, adding geometry objects from file opened above
        job = PathJob.Create("Job", [doc.Box], None)
        job.GeometryTolerance.Value = 0.001
        if FreeCAD.GuiUp:
            job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)
            job.ViewObject.Proxy.showOriginAxis(True)
            job.ViewObject.Proxy.deleteOnReject = False

        # Instantiate an Adaptive operation for querying available properties
        prototype = PathCustom.Create("Custom")
        prototype.Label = "Prototype"
        _addViewProvider(prototype)

        doc.recompute()

    @classmethod
    def tearDownClass(cls):
        """tearDownClass()...
        This method is called prior to destruction of this test class.  Add code and objects here
        that cleanup the test environment after the test() methods in this class have been executed.
        This method does not have access to the class `self` reference.  This method
        is able to call static methods within this same class.
        """
        # FreeCAD.Console.PrintMessage("TestPathAdaptive.tearDownClass()\n")

        # Close geometry document without saving
        # FreeCAD.closeDocument(FreeCAD.ActiveDocument.Name)
        pass

    # Setup and tear down methods called before and after each unit test
    def setUp(self):
        """setUp()...
        This method is called prior to each `test()` method.  Add code and objects here
        that are needed for multiple `test()` methods.
        """
        self.doc = FreeCAD.ActiveDocument
        self.con = FreeCAD.Console

    def tearDown(self):
        """tearDown()...
        This method is called after each test() method. Add cleanup instructions here.
        Such cleanup instructions will likely undo those in the setUp() method.
        """
        pass

    def test00(self):
        """Test Basic Helix Generator Return"""
        v1 = FreeCAD.Vector(5, 5, 20)
        v2 = FreeCAD.Vector(5, 5, 10)

        edg = Part.makeLine(v1, v2)

        args = {
            "edge": edg,
            "hole_radius": 10.0,
            "step_down": 1.0,
            "step_over": 5.0,
            "tool_diameter": 5.0,
            "inner_radius": 0.0,
            "direction": "CW",
            "startAt": "Inside",
        }

        result = generator.generate(**args)

        self.assertTrue(type(result) is list)
        self.assertTrue(type(result[0]) is Path.Command)

        # for c in result:
        #    print("cmd: {}".format(c))

        # Instantiate an Adaptive operation for querying available properties
        op = PathCustom.Create("Custom")
        op.Label = "Custom_test00"
        op.Gcode = [r.toGCode() + "\n" for r in result]
        _addViewProvider(op)

    def test01(self):
        """Test Basic Helix Generator argument types and requirements"""

        args = resetArgs()

        # require hole radius > 0
        args["hole_radius"] = -10.0
        self.assertRaises(ValueError, generator.generate, **args)

        # require hole radius is float
        args["hole_radius"] = 10
        self.assertRaises(ValueError, generator.generate, **args)

        # require inner radius is float
        args = resetArgs()
        args["inner_radius"] = 2
        self.assertRaises(ValueError, generator.generate, **args)

        # require tool diameter is float
        args = resetArgs()
        args["tool_diameter"] = 5
        self.assertRaises(ValueError, generator.generate, **args)

        # require tool fit 1: radius diff less than tool diam
        args["hole_radius"] = 10.0
        args["inner_radius"] = 6.0
        args["tool_diameter"] = 5.0
        self.assertRaises(ValueError, generator.generate, **args)

        # require tool fit 2: hole radius less than tool diam with zero inner radius
        args["hole_radius"] = 4.5
        args["inner_radius"] = 0.0
        args["tool_diameter"] = 5.0
        self.assertRaises(ValueError, generator.generate, **args)

        # validate "startAt" value
        args = resetArgs()
        args["startAt"] = "Other"
        self.assertRaises(ValueError, generator.generate, **args)

        # validate "direction" value
        args = resetArgs()
        args["direction"] = "clock"
        self.assertRaises(ValueError, generator.generate, **args)

        # verify linear edge is vertical: X
        args = resetArgs()
        v1 = FreeCAD.Vector(5, 5, 20)
        v2 = FreeCAD.Vector(5.0001, 5, 10)
        edg = Part.makeLine(v1, v2)
        args["edge"] = edg
        self.assertRaises(ValueError, generator.generate, **args)

        # verify linear edge is vertical: Y
        args = resetArgs()
        v1 = FreeCAD.Vector(5, 5.0001, 20)
        v2 = FreeCAD.Vector(5, 5, 10)
        edg = Part.makeLine(v1, v2)
        args["edge"] = edg
        self.assertRaises(ValueError, generator.generate, **args)


def resetArgs():
    v1 = FreeCAD.Vector(5, 5, 20)
    v2 = FreeCAD.Vector(5, 5, 10)

    edg = Part.makeLine(v1, v2)

    return {
        "edge": edg,
        "hole_radius": 10.0,
        "step_down": 1.0,
        "step_over": 5.0,
        "tool_diameter": 5.0,
        "inner_radius": 0.0,
        "direction": "CW",
        "startAt": "Inside",
    }
