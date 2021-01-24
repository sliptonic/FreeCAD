# ***************************************************************************
# *   Copyright (c) 2021 sliptonic <shopinthewoods@gmail.com>               *
# *   Copyright (c) 2021 shadowbane1000 <tyler@colberts.us>               *
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

# Fanuc post differs from the base post:
# 2021/1/23  Uppercased all output - shadowbane1000
# 2021/1/23  Default to small gcode (modal, output_doubles) - shadowbane1000
# 2021/1/23  Header modified to match what the Fanuc controller works well with - shadowbane1000
# 2021/1/23  Added --model option to specify the specific model of the controller (specified like "21i-MB") - shadowbane1000

from __future__ import print_function
import shlex
import postprocessor as postprocessor
import os
import FreeCAD

TOOLTIP = '''
Generate g-code from one or more path objects that is compatible with Fanuc controllers.
import fanuc_post
fanuc_post.export(object,"/path/to/file.ncc","")
'''

class FanucPost(postprocessor.ObjectPost):

    def __init__(self):
        super().__init__("Fanuc")
        self._output_doubles = False
        self._modal = True
        self._preamble += " G97" # turn off constant surface speed
        self._preamble += " G94" # feed rate is per minute, not per revolution
        self._preamble += " G69" # turn off coordinate system rotation
        self._preamble += " G13.1" # turn off polar coordinates
        self._model = "21i-MB";

        self._t_series = False
        self._m_series = False
        self._21i_M = False
                 
        self.filename = "O1000"

    def getArgs(self):
        parser = super().getArgs()
        
        parser.add_argument('--model', help='model of controller (default 21i-MB).  Currently searched for "T" or "M"')
        
        return parser

    def processArguments(self, argstring):
        super().processArguments(argstring)

        try:
            args = parser.parse_args(shlex.split(argstring))
            if args.model is not None:
                self._model = args.model

        except Exception as e: # pylint: disable=broad-except
            print(e)
            return False

        # break down the model number based on what we need to know
        self._t_series = 'T' in self._model
        self._m_series = 'M' in self._model

        if args.preamble is None:
            if self._t_series:
                self._preamble += " G50.2" # turn off polygon turning on T Series controllers
            if self._m_series:
                self._preamble += " G50.1" # turn off mirror image on M Series controllers
                self._preamble += " G15" # turn off polar coordinates command on M Series controllers
                self._preamble += " G40.1" # turn off normal direction control on M Series controllers
                self._preamble += " G50" # turn off scaling on M Series controllers
                self._preamble += " G64" # cutting mode (as opposed to exact stop mode, tapping mode, and auto-corner override mode)
            
        return True
        
    def buildDescriptiveName(self):
        if FreeCAD.GuiUp and FreeCAD.ActiveDocument:
            sourcefilename = FreeCAD.ActiveDocument.Name
            jobname = "Unknown Job"
        return "{},{}".format(sourcefilename or self.filename,jobname or "Unknown Job") 
        
    def buildHeader(self):
        '''
        calculate header gcode
        Can be safely overriden
        '''
        gcode = ""
        if self._output_header:
            gcode = "%\n;\n" + self.filename + " (" + self.buildDescriptiveName() + ")\n"
            gcode += super().buildHeader()

        return gcode



def export(objectslist, filename, argstring):
    # pylint: disable=global-statement
    post.filename = os.path.split(filename)[-1]
    if not post.processArguments(argstring):
        return None
    finalGcode = post.export(objectslist)
    finalGcode = finalGcode.upper()
    post.writeFile(finalGcode, filename)


post = FanucPost()
parser = post.getArgs()
TOOLTIP_ARGS = parser.format_help()
