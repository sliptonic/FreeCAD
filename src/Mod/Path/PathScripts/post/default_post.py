# ***************************************************************************
# *   Copyright (c) 2014 sliptonic <shopinthewoods@gmail.com>               *
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
# ***************************************************************************

# Default post implementes the base post:
# 2021/1/25  Initial Implementation.

from __future__ import print_function
import postprocessor as postprocessor

TOOLTIP = '''
Generate g-code from one or more path objects.
Should also work will with most machine controllers.
import default_post
default_post.export(object,"/path/to/file.ncc","")
'''


class DefaultPost(postprocessor.ObjectPost):
    MACHINE_NAME = "Default"
    CORNER_MIN = {'x': 0, 'y': 0, 'z': 0}
    CORNER_MAX = {'x': 500, 'y': 300, 'z': 300}
    PRECISION = 3

    def getArgs(self):
        parser = super().getArgs()
        return parser

    def processArguments(self, argstring):
        super().processArguments(argstring)

    def machineConfiguration(self):
        '''returns the machine configuration as json'''

        config = {'Machine_Name': self.MACHINE_NAME,
                  'WorkSpace':
                    {
                        'Corner_Min': self.CORNER_MIN,
                        'Corner_Max': self.CORNER_MAX
                    },
                    'Job_Type': '3D',
                 }

        return config


def export(objectslist, filename, argstring):
    if not post.processArguments(argstring):
        return None
    finalGcode = post.export(objectslist)
    post.writeFile(finalGcode, filename)


print(__name__ + " gcode postprocessor loaded.")
post = DefaultPost('Default')
parser = post.getArgs()
TOOLTIP_ARGS = parser.format_help()
