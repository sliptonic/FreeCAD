# ***************************************************************************
# *   Copyright (c) 2020 sliptonic <shopinghewoods@gmail.com>               *
# *                                                                         *
# *   This file is part of the FreeCAD CAx development system.              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful,            *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Lesser General Public License for more details.                   *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with FreeCAD; if not, write to the Free Software        *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************/
# Dxf post implementes the base post:
# writes a dxf file rather than gcode
# 2021/1/25 Porting to new post framework

from __future__ import print_function
import argparse
import FreeCAD
import importDXF
import Part
import Path
import PathScripts.PathGeom as PathGeom
import PathScripts.PathLog as PathLog
import postprocessor as postprocessor


TOOLTIP = '''
DXF_post.py Used to take a pseudo-gcode fragment outputted by a Path object,
and output a dxf file.
Operations are output to layers.
vertical moves are ignore
All path moves are flattened to z=0

Does NOT remove redundant lines.  If you have multiple step-downs in your
operation, you'll get multiple redundant lines in your dxf.

import dxf_post
dxf_post.export(object,"/path/to/file.dxf","")
'''

PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())

class DefaultPost(postprocessor.ObjectPost):

    def getArgs(self):
        parser = argparse.ArgumentParser(prog=self._name, add_help=False)
        self.TOOLTIP_ARGS = parser.format_help()
        self._parser = parser
        return parser

    def processArguments(self, argstring):
        return True

    def export(self, objectslist, filename, argstring):
        doc = FreeCAD.ActiveDocument
        print("postprocessing...")
        layers = []
        self.processArguments(argstring)
        for i in objectslist:
            result = self.parse(i)
            if len(result) > 0:
                layername = i.Name
                grp = doc.addObject("App::DocumentObjectGroup", layername)
                for o in result:
                    o.adjustRelativeLinks(grp)
                    grp.addObject(o)
                layers.append(grp)

        self.dxfWrite(layers, filename)


    def dxfWrite(self, objlist, filename):
        importDXF.export(objlist, filename)


    def parse(self, pathobj):
        ''' accepts a Path object.  Returns a list of wires'''

        feedcommands = ['G01', 'G1', 'G2', 'G3', 'G02', 'G03']
        rapidcommands = ['G0', 'G00']

        edges = []
        objlist = []

        # Gotta start somewhere.  Assume 0,0,0
        curPoint = FreeCAD.Vector(0, 0, 0)
        for c in pathobj.Path.Commands:
            PathLog.debug('{} -> {}'.format(curPoint, c))
            if 'Z' in c.Parameters:
                newparams = c.Parameters
                newparams.pop('Z', None)
                flatcommand = Path.Command(c.Name, newparams)
                c.Parameters = newparams
            else:
                flatcommand = c

            # ignore gcode that isn't moving
            if flatcommand.Name not in feedcommands + rapidcommands:
                PathLog.debug('non move')
                continue

            # ignore pure vertical feed and rapid
            if (flatcommand.Parameters.get('X', curPoint.x) == curPoint.x
                    and flatcommand.Parameters.get('Y', curPoint.y) == curPoint.y):
                PathLog.debug('vertical')
                continue

            # feeding move.  Build an edge
            if flatcommand.Name in feedcommands:
                edges.append(PathGeom.edgeForCmd(flatcommand, curPoint))
                PathLog.debug('feeding move')

            # update the curpoint
            curPoint.x = flatcommand.Parameters['X']
            curPoint.y = flatcommand.Parameters['Y']

        if len(edges) > 0:
            candidates = Part.sortEdges(edges)
            for c in candidates:
                obj = FreeCAD.ActiveDocument.addObject("Part::Feature", "Wire")
                obj.Shape = Part.Wire(c)
                objlist.append(obj)

        return objlist

def export(objectslist, filename, argstring=""):
    # pylint: disable=global-statement
    if not post.processArguments(argstring):
        return None
    post.export(objectslist, filename, argstring)


post = DefaultPost('Default')
parser = post.getArgs()
TOOLTIP_ARGS = '''Arguments for dxf:'''

print(__name__ + " gcode postprocessor loaded.")
