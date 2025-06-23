# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2025 phaseloop <phaseloop@protonmail.com>               *
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
import Path
from Path.Dressup.Gui.Dragknife import ObjectDressup
import Path.Main.Job as PathJob
import Path.Op.Profile as PathProfile

from CAMTests.PathTestUtils import PathTestBase


class TestDressupDragknife(PathTestBase):

    def test00(self):
        """ first unit test

            This is a dummy test to show how to construct one.
            This calls the shortcut method on the dragknife dressup
            and passes a queue of commands.

            The dragknife dressup needs to be refactored to split the GUI out.
            This would make it easier to reuse the logic and to test it without
            loading the FreeCAD Gui.

            Ideally we would have some tests that test
            - shortcut
            - segmentAngleXY
            - arcExtension
            - arcTwist
            - lineExtension
            - lineTwist

            With those, we could refactor this dressup to split the core logic away from the GUI
            and add a task panel.

        """

        c1 = Path.Command("G1 X10 Y10 Z10")
        c2 = Path.Command("G1 X10 Y20 Z10")
        c3 = Path.Command("G1 X15 Y20 Z10")
        queue = [c1, c2, c3]
        result = ObjectDressup.shortcut(None, queue)
        self.assertTrue(result == "CCW")


