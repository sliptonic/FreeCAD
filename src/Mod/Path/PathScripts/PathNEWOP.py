# -*- coding: utf-8 -*-

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2018 sliptonic <shopinthewoods@gmail.com>               *
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
import Path
import PathScripts.PathLog as PathLog
import PathScripts.PathOp as PathOp
import PathScripts.PathUtils as PathUtils

#from PathScripts.PathUtils import waiting_effects
from PySide import QtCore

__title__ = "Sample New Operation"
__author__ = "sliptonic (Brad Collette)"
__url__ = "http://www.freecadweb.org"
__doc__ = "New Operation Template.  Does nothing."

if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())


# Qt tanslation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class ObjectNEWOP(PathOp.ObjectOp):
    '''Proxy object for Probing operation.'''

    def opFeatures(self, obj):
        '''opFeatures(obj) ... Probing works on the stock object.'''
        return PathOp.FeatureDepths | PathOp.FeatureHeights | PathOp.FeatureTool

    def initOperation(self, obj):
        # Add Properties here
        pass
        obj.addProperty("App::PropertyLength", "Example", "NEWOP", QtCore.QT_TRANSLATE_NOOP("App::Property", "An Example Property"))


    def opExecute(self, obj):
        '''opExecute(obj) ... generate the tool path.'''
        PathLog.track()
        self.commandlist.append(Path.Command("(Begin New Operation)"))

        stock = PathUtils.findParentJob(obj).Stock
        bb = stock.Shape.BoundBox

        openstring = '(NEWOP OPEN)'

        # Bulk of the work is done here

        self.commandlist.append(Path.Command("(NEWOP CLOSE)"))


    def opSetDefaultValues(self, obj, job):
        '''opSetDefaultValues(obj, job) ... set default value for RetractHeight'''
        pass

def SetupProperties():
    setup = ['Example']
    return setup

def Create(name, obj = None):
    '''Create(name) ... Creates and returns a NEWOP operation.'''
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    proxy = ObjectNEWOP(obj, name)
    return obj
