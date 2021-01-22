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

# LinuxCNC post differs from the base post:
# 2021/1/25  Tolerance argument and value added by sliptonic

from __future__ import print_function
import shlex
import postprocessor as postprocessor

TOOLTIP = '''
Generate g-code from one or more path objects that is compatible with LinuxCNC.
Should also work will with Machinekit controllers.
import linuxcnc_post
linuxcnc_post.export(object,"/path/to/file.ncc","")
'''

class LinuxCNCPost(postprocessor.ObjectPost):

    def getArgs(self):
        parser = super().getArgs()
        parser.add_argument('--tolerance', help='Path blending tolerance')
        return parser

    def processArguments(self, argstring):
        super().processArguments(argstring)

        try:
            args = parser.parse_args(shlex.split(argstring))
            if args.tolerance is not None:
                tolvalue = args.tolerance
            else:
                if args.inches:
                    tolvalue = 0.001
                else:
                    tolvalue = 0.025

            self._preamble += " G64 P{}".format(tolvalue)

        except Exception as e: # pylint: disable=broad-except
            print(e)
            return False

        return True

def export(objectslist, filename, argstring):
    # pylint: disable=global-statement
    if not post.processArguments(argstring):
        return None
    finalGcode = post.export(objectslist)
    post.writeFile(finalGcode, filename)


post = LinuxCNCPost('LinuxCNC')
parser = post.getArgs()
TOOLTIP_ARGS = parser.format_help()
