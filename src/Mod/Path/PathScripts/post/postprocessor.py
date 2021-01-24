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

from __future__ import print_function
import argparse
import datetime
import FreeCAD
from FreeCAD import Units
import os
import Path
import PathLog
import PathScripts
from PathScripts import PostUtils
import shlex


PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
PathLog.trackModule(PathLog.thisModule())


class ObjectPost(object):
    '''
    Base class for postprocessor objects.

    use this class as the base class for new postprocessors.  It provides
    properties and functionality for the standard posts.
    '''
    def __init__(self, name):
        self._name = name

        # # Output options
        # self._output_comments = True
        # self._output_header = True
        # self._output_line_numbers = False
        self._linenr = 0  # line number starting value
        # self._show_editor = True
        # self._precision = 3
        self._command_space = " "

        # Options to reduce gcode size
        # self._modal = False  # if true commands are suppressed if the same as previous line.
        # self._output_doubles = True  # if false duplicate axis values are suppressed if the same as previous line.

        # Tool Change options
        # self._use_tlo = True  # if true G43 will be output following tool changes
        self._tool_change = ''''''

        # Units
        # self._units = "G21"  # G21 for metric, G20 for us standard
        # self._unit_speed_format = 'mm/min'
        # self._unit_format = 'mm'

        # These globals will be reflected in the Machine configuration of the project
        # Pre operation text will be inserted before every operation
        self._pre_operation = ''''''

        # Post operation text will be inserted after every operation
        self._post_operation = ''''''

        # Tool Change commands will be inserted before a tool change

        # Job Preamble text will appear at the beginning of the GCODE output file.
        self._preamble = '''G17 G54 G40 G49 G80 G90'''

        # Job Postamble text will appear following the last operation.
        self._postamble = '''M05
G17 G54 G90 G80 G40
M2'''

    def getArgs(self):
        '''
        creates an arparser and adds supported arguments.
        Can be extended
        '''
        parser = argparse.ArgumentParser(prog=self._name, add_help=False)

        parser.add_argument('--no-header', action='store_true', help='suppress header output')
        parser.add_argument('--no-comments', action='store_true', help='suppress comment output')
        parser.add_argument('--line-numbers', action='store_true', help='prefix with line numbers')
        parser.add_argument('--no-show-editor', action='store_true', help='don\'t pop up editor before writing output')
        parser.add_argument('--precision', default=3, help='number of digits of precision, default=3')
        parser.add_argument('--preamble', help='set commands to be issued before the first command, default="G17\nG90"')
        parser.add_argument('--postamble', help='set commands to be issued after the last command, default="M05\nG17 G90\nM2"')
        parser.add_argument('--inches', action='store_true', help='Convert output for US imperial mode (G20)')
        parser.add_argument('--modal', action='store_true', help='Output the Same G-command Name USE NonModal Mode')
        parser.add_argument('--axis-modal', action='store_true', help='Output the Same Axis Value Mode')
        parser.add_argument('--no-tlo', action='store_true', help='suppress tool length offset (G43) following tool changes')
        self.TOOLTIP_ARGS = parser.format_help()

        self._parser = parser

        return self._parser

    def processArguments(self, argstring):
        PathLog.debug(argstring)
        try:
            args = self._parser.parse_args(shlex.split(argstring))
            print(args)
            self._output_header = not(args.no_header)
            self._output_comments = not(args.no_comments)
            self._output_line_numbers = args.line_numbers
            self._show_editor = not(args.no_show_editor)
            self._precision = args.precision
            if args.preamble is not None:
                self._preamble = args.preamble
            if args.postamble is not None:
                self._postamble = args.postamble
            self._modal = args.modal
            self._output_doubles = not(args.axis_modal)
            self._use_tlo = not(args.no_tlo)
            self._precision = args.precision
            if args.inches:
                self._units = 'G20'
                self._unit_speed_format = 'in/min'
                self._unit_format = 'in'
            else:
                self._units = 'G21'
                self._unit_speed_format = 'mm/min'
                self._unit_format = 'mm'
        except Exception as e:
            print(e)
            return False

        return True

    def linenumber(self):
        '''
        calculates the line number

        Can be safely overriden
        '''
        if self._output_line_numbers:
            self._linenr += 10
            return "N {} ".format(self._linenr)
        else:
            return ""

    def parse(self, pathobj):
        '''
        Parses a single path object to output gcode.

        Can be safely overriden
        '''
        PathLog.track(pathobj.Label)

        if hasattr(pathobj, "ToolNumber"):
            return self.buildToolChange(pathobj)

        out = ""
        lastcommand = None
        precision_string = '.' + str(self._precision) + 'f'
        currLocation = {}  # keep track for no doubles

        # the order of parameters
        # linuxcnc doesn't want K properties on XY plane  Arcs need work.
        params = ['X', 'Y', 'Z', 'A', 'B', 'C', 'I', 'J', 'F', 'S', 'T', 'Q', 'R', 'L', 'H', 'D', 'P']
        firstmove = Path.Command("G0", {"X": -1, "Y": -1, "Z": -1, "F": 0.0})
        currLocation.update(firstmove.Parameters)  # set First location Parameters

        if hasattr(pathobj, "Group"):  # We have a compound or project.
            # if OUTPUT_COMMENTS:
            #     out += linenumber() + "(compound: " + pathobj.Label + ")\n"
            for p in pathobj.Group:
                out += self.parse(p)
            return out
        else:  # parsing simple path

            # groups might contain non-path things like stock.
            if not hasattr(pathobj, "Path"):
                return out

            for c in pathobj.Path.Commands:

                outstring = []
                command = c.Name
                outstring.append(command)

                # if modal: suppress the command if it is the same as the last one
                if self._modal is True:
                    if command == lastcommand:
                        outstring.pop(0)

                if c.Name[0] == '(' and not self._output_comments:  # command is a comment
                    continue

                # Now add the remaining parameters in order
                for param in params:
                    if param in c.Parameters:
                        if param == 'F' and (currLocation[param] != c.Parameters[param] or self._output_doubles):
                            if c.Name not in ["G0", "G00"]:  # linuxcnc doesn't use rapid speeds
                                speed = Units.Quantity(c.Parameters['F'], FreeCAD.Units.Velocity)
                                if speed.getValueAs(self._unit_speed_format) > 0.0:
                                    outstring.append(param + format(float(speed.getValueAs(self._unit_speed_format)), precision_string))
                            else:
                                continue
                        elif param == 'T':
                            outstring.append(param + str(int(c.Parameters['T'])))
                        elif param == 'H':
                            outstring.append(param + str(int(c.Parameters['H'])))
                        elif param == 'D':
                            outstring.append(param + str(int(c.Parameters['D'])))
                        elif param == 'S':
                            outstring.append(param + str(int(c.Parameters['S'])))
                        else:
                            if (not self._output_doubles) and (param in currLocation) and (currLocation[param] == c.Parameters[param]):
                                continue
                            else:
                                pos = Units.Quantity(c.Parameters[param], FreeCAD.Units.Length)
                                outstring.append(
                                    param + format(float(pos.getValueAs(self._unit_format)), precision_string))

                # store the latest command
                lastcommand = command
                currLocation.update(c.Parameters)

                if command == "message":
                    if self._output_comments is False:
                        out = []
                    else:
                        outstring.pop(0)  # remove the command

                # prepend a line number and append a newline
                if len(outstring) >= 1:
                    if self._output_line_numbers:
                        outstring.insert(0, (self.linenumber()))

                    # append the line to the final output
                    for w in outstring:
                        out += w + self._command_space
                    # Note: Do *not* strip `out`, since that forces the allocation
                    # of a contiguous string & thus quadratic complexity.
                    out += "\n"

            return out

    def buildHeader(self):
        '''
        calculate header gcode
        Can be safely overriden
        '''
        gcode = ""
        if self._output_header:
            now = datetime.datetime.now()
            gcode += self.linenumber() + "(Exported by FreeCAD)\n"
            gcode += self.linenumber() + "(Post Processor: {})\n".format(self._name)
            gcode += self.linenumber() + "(Output Time: {})\n".format(now)

        return gcode

    def buildPreamble(self):
        '''
        Generate the preamble
        Can be safely overriden
        '''
        gcode = ""

        if self._output_comments:
            gcode += self.linenumber() + "(begin preamble)\n"
        for line in self._preamble.splitlines(False):
            gcode += self.linenumber() + line + "\n"
        gcode += self.linenumber() + self._units + "\n"
        return gcode

    def buildPostamble(self):
        '''
        Generate the post_amble
        Can be safely overriden
        '''
        gcode = ""

        if self._output_comments:
            gcode += "(begin postamble)\n"
        for line in self._postamble.splitlines(True):
            gcode += self.linenumber() + line
        return gcode

    def buildToolChange(self, ToolController):
        '''
        Generate the tool change gcode
        Can be safely overriden
        '''
        gcode = ""

        # stop the spindle
        gcode += self.linenumber() + "M5\n"

        for line in self._tool_change.splitlines(True):
            gcode += self.linenumber() + line

        for c in ToolController.Path.Commands:
            if c.Name == 'M6':
                toolnumber = str(int(c.Parameters['T']))
                gcode += "{} T{}\n".format(c.Name, toolnumber)

                # add height offset
                if self._use_tlo:
                    gcode += self.linenumber() + 'G43 H{}\n'.format(toolnumber)

            elif c.Name in ['M3', 'M4']:
                spindlespeed = str(int(c.Parameters['S']))
                gcode += "{} S{}\n".format(c.Name, spindlespeed)

        return gcode

    def buildCoolantGcode(self, coolantMode):
        '''
        Generate coolant code
        Can be safely overriden
        '''

        gcode = ""
        if coolantMode == 'None':
            return gcode

        if self._output_comments:
            gcode += self.linenumber() + '(Coolant mode: {})\n'.format(coolantMode)

        if coolantMode == 'Flood':
            gcode += self.linenumber() + 'M8' + '\n'
        elif coolantMode == 'Mist':
            gcode += self.linenumber() + 'M7' + '\n'
        elif coolantMode == 'Cancel':
            gcode += self.linenumber() + 'M9' + '\n'

        return gcode

    def buildpreOperatonGcode(self, opLabel):
        '''
        generate gcode to be inserted before each operation
        Can be safely overriden
        '''
        gcode = ""

        if self._output_comments:
            gcode += self.linenumber() + "(begin operation: {})\n".format(opLabel)
            gcode += self.linenumber() + "(speed format: {})\n".format(self._unit_speed_format)
        for line in self._pre_operation.splitlines(True):
            gcode += self.linenumber() + line
        return gcode

    def buildpostOperatonGcode(self, opLabel):
        '''
        generate gcode to be inserted after each operation
        Can be safely overriden
        '''
        gcode = ""
        if self._output_comments:
            gcode += self.linenumber() + "(finish operation: {})\n".format(opLabel)
        for line in self._post_operation.splitlines(True):
            gcode += self.linenumber() + line

        return gcode

    def export(self, objectslist):
        '''
        Processes an entire job and generate gcode.

        Can be safely overriden
        '''

        # reset line number to 0
        self._linenr = 0

        for obj in objectslist:
            if not hasattr(obj, "Path"):
                print("the object {} is not a post-processable.".format(obj.Name))
                return None

        print("postprocessing...")
        gcode = ""

        gcode += self.buildHeader()
        gcode += self.buildPreamble()

        for obj in objectslist:

            # Skip inactive operations
            if hasattr(obj, 'Active'):
                if not obj.Active:
                    continue
            if hasattr(obj, 'Base') and hasattr(obj.Base, 'Active'):
                if not obj.Base.Active:
                    continue

            gcode += self.buildpreOperatonGcode(obj.Label)

            coolantMode = 'None'
            if hasattr(obj, "CoolantMode") or hasattr(obj, 'Base') and hasattr(obj.Base, "CoolantMode"):
                if hasattr(obj, "CoolantMode"):
                    coolantMode = obj.CoolantMode
                else:
                    coolantMode = obj.Base.CoolantMode

            # Generate the pre-operation gcode
            gcode += self.buildCoolantGcode(coolantMode)

            # Generate the operation gcode
            gcode += self.parse(obj)

            # Generate the post-operation gcode
            gcode += self.buildpostOperatonGcode(obj.Label)

            # turn coolant off if required
            if not coolantMode == 'None':
                gcode += self.buildCoolantGcode('Cancel')

        gcode += self.buildPostamble()

        print("Gcode Generated")
        return gcode

    def writeFile(self, finalgcode, filename):
        '''
        Writes gcode to target file.

        Can be safely overriden
        '''

        # Give the user a chance to edit the result before writing to file
        # requires to UI to be up and the show_editor flag set.
        # If the output is too large, skip this step (> 10000 lines)

        if FreeCAD.GuiUp and self._show_editor:
            if len(finalgcode) > 100000:
                print("Skipping editor since output is greater than 100kb")
                result = True
            else:
                dia = PostUtils.GCodeEditorDialog()
                dia.editor.setText(finalgcode)
                result = dia.exec_()
                if result:
                    finalgcode = dia.editor.toPlainText()
        else:
            result = True

        if result and os.access(os.path.dirname(filename), os.W_OK):
            with open(filename, 'w') as gfile:
                gfile.write(finalgcode)

            print("File Written to {}".format(filename))
