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
import PySide.QtCore as QtCore
#import cloudScripts.CloudPreferences as CloudPreferences


class CommandCloudDockOpen:
    '''
    Command to toggle the cloud Dock
    '''

    def __init__(self):
        pass

    def GetResources(self):
        return {'Pixmap'  : 'clouds',
                'MenuText': QtCore.QT_TRANSLATE_NOOP("Cloud","Cloud Dock"),
                'Accel': "C, D",
                'ToolTip': QtCore.QT_TRANSLATE_NOOP("Cloud","Cloud Dock")}

    def IsActive(self):
        return not FreeCAD.ActiveDocument is None

    def Activated(self):
        import cloudScripts.cloudDockGui as cloudDockGui
        dock = cloudDockGui.CloudDock()
        dock.open()


if FreeCAD.GuiUp:
    FreeCADGui.addCommand('Cloud_Dock',CommandCloudDockOpen())
