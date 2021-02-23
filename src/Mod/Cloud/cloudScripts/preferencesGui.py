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
import Cloud
import cloudScripts.preferences as preferences
from PySide import QtCore, QtGui

class ServerAddDialog:
    def __init__(self, parent=None):
        import FreeCADGui
        self.dialog = FreeCADGui.PySideUic.loadUi(":preferences/ServerCreate.ui")
        #FreeCADGui.Control.showDialog(self.form)

    def exec_(self):
        if self.dialog.exec_() != 1:
            return None
        result = {'name':        self.dialog.leServerName.text(),
                  'authToken':   self.dialog.leTokenAuth.text(),
                  'secretToken': self.dialog.leTokenSecret.text(),
                  'url':         self.dialog.leServerUrl.text(),
                  'port':        self.dialog.spinPort.value()}

        return result


class ModelFactory(object):
    ''' Helper class to generate qtdata models for servers
    '''

    def __init__(self, model):
        self.model = model

    def serverLoad(self, serverList):
        for server in serverList:
            self.model.appendRow(self._serverAdd(server))


    def _serverAdd(self, server):

        serverName = QtGui.QStandardItem()
        serverName.setData(server['name'], QtCore.Qt.EditRole)
        serverName.setEditable(False)

        url = QtGui.QStandardItem()
        url.setData(server['url'], QtCore.Qt.EditRole)
        url.setEditable(False)

        authToken = QtGui.QStandardItem()
        authToken.setData(server['authToken'], QtCore.Qt.EditRole)
        authToken.setEditable(False)

        secretToken = QtGui.QStandardItem()
        secretToken.setData(server['secretToken'], QtCore.Qt.EditRole)
        secretToken.setEditable(False)

        port = QtGui.QStandardItem()
        port.setData(server['port'], QtCore.Qt.EditRole)
        port.setEditable(False)

        return [serverName, url, authToken, secretToken, port]

    def newServer(self, server):
        '''
        Adds a server item to a model
        '''

        self.model.appendRow(self._serverAdd(server))


class PreferencesPage:
    def __init__(self, parent=None):
        import FreeCADGui
        self.form = FreeCADGui.PySideUic.loadUi(":preferences/CloudPreferences.ui")
        self.form.toolBox.setCurrentIndex(0)

        self.TableHeaders = ['Server', 'URL', 'Auth Token', 'Secret Token', 'Port']
        self.model = QtGui.QStandardItemModel(0, len(self.TableHeaders))
        self.model.setHorizontalHeaderLabels(self.TableHeaders)

        self.factory = ModelFactory(self.model)

    def loadSettings(self):
        self.form.btnAddServer.clicked.connect(self.addServer)
        self.form.btnRemoveServer.clicked.connect(self.removeServer)

        servers = preferences.getServers()
        self.factory.serverLoad(servers)

        self.form.listCloudServers.setModel(self.model)

    def removeServer(self):
        index=(self.form.listCloudServers.selectionModel().currentIndex())
        value=index.sibling(index.row(), 0).data()

        preferences.removeServer(value)
        self.model.removeRow(index.row())

    def addServer(self):
        dialog = ServerAddDialog(self)
        result = dialog.exec_()

        if result is None:
            return

        print('result {}'.format(result))
        newserver = preferences.addServer(result['name'],
                                          result['authToken'],
                                          result['secretToken'],
                                          result['url'],
                                          result['port'])

        self.factory.newServer(newserver)


