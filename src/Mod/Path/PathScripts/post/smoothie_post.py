# ***************************************************************************
# *   Copyright (c) 2017 sliptonic <shopinthewoods@gmail.com>               *
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

# Smoothie post differs from the base post:
# supports writing directly to the smoothie board via eithernet

from __future__ import print_function
import shlex
import postprocessor as postprocessor
import FreeCAD

TOOLTIP = '''
Generate g-code from one or more path objects that is compatible with SmoothieBoard.
import smoothie_post
smoothie_post.export(object,"/path/to/file.ncc","")
'''

class SmoothiePost(postprocessor.ObjectPost):

    def __init__(self, name):
        super().__init__(name)
        self._precision = 4
        self._IP_ADDR = None

    def getArgs(self):
        parser = super().getArgs()
        parser.add_argument('--IP_ADDR', help='IP Address for machine target machine')
        parser.add_argument('--verbose', action='store_true', help='verbose output for debugging, default="False"')
        return parser

    def processArguments(self, argstring):
        super().processArguments(argstring)

        try:
            args = parser.parse_args(shlex.split(argstring))
            if args.IP_ADDR is not None:
                self._IP_ADDR = args.IP_ADDR

            if args.verbose is None:
                self._verbose = False
            else:
                self._verbose = args.verbose

        except Exception as e: # pylint: disable=broad-except
            print(e)
            return False

        return True

    def writeFile(self, finalgcode, filename):
        if self._IP_ADDR is not None:
            self.sendToSmoothie(finalgcode, filename)
        else:
            super().writeFile(finalgcode, filename)

    def sendToSmoothie(self, GCODE, fname):
        import sys
        import socket
        import os

        fname = os.path.basename(fname)
        FreeCAD.Console.PrintMessage('sending to smoothie: {}\n'.format(fname))

        f = GCODE.rstrip()
        filesize = len(f)
        # make connection to sftp server
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(4.0)
        s.connect((self._IP_ADDR, 115))
        tn = s.makefile(mode='rw')

        # read startup prompt
        ln = tn.readline()
        if not ln.startswith("+"):
            FreeCAD.Console.PrintMessage("Failed to connect with sftp: {}\n".format(ln))
            sys.exit()

        if self._verbose:
            print("RSP: " + ln.strip())

        # Issue initial store command
        tn.write("STOR OLD /sd/" + fname + "\n")
        tn.flush()

        ln = tn.readline()
        if not ln.startswith("+"):
            FreeCAD.Console.PrintError("Failed to create file: {}\n".format(ln))
            sys.exit()

        if self._verbose:
            print("RSP: " + ln.strip())

        # send size of file
        tn.write("SIZE " + str(filesize) + "\n")
        tn.flush()

        ln = tn.readline()
        if not ln.startswith("+"):
            FreeCAD.Console.PrintError("Failed: {}\n".format(ln))
            sys.exit()

        if self._verbose:
            print("RSP: " + ln.strip())

        cnt = 0

        # now send file
        for line in f.splitlines(1):
            tn.write(line)
            if self._verbose:
                cnt += len(line)
                print("SND: " + line.strip())
                print(str(cnt) + "/" + str(filesize) + "\r", end='')

        tn.flush()

        ln = tn.readline()
        if not ln.startswith("+"):
            FreeCAD.Console.PrintError("Failed to save file: {}\n".format(ln))
            sys.exit()

        if self._verbose:
            print("RSP: " + ln.strip())

# exit
        tn.write("DONE\n")
        tn.flush()
        tn.close()

        FreeCAD.Console.PrintMessage("Upload complete\n")

def export(objectslist, filename, argstring):
    # pylint: disable=global-statement
    if not post.processArguments(argstring):
        return None
    finalGcode = post.export(objectslist)
    post.writeFile(finalGcode, filename)


post = SmoothiePost('Smoothieboard')
parser = post.getArgs()
TOOLTIP_ARGS = parser.format_help()
