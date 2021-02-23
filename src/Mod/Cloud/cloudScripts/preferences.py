# -*- coding: utf-8 -*-
# ***************************************************************************
# *                                                                         *
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
import os
import json


# Linear tolerance to use when generating Paths, eg when tessellating geometry
ServerList               = "ServerList"
DefaultServerName        = "DefaultServerName"


def preferences():
    return FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Cloud")


def cloudScriptsSourcePath():
    return os.path.join(FreeCAD.getHomePath(), "Mod/Path/cloudScripts/")


def defaultServer():
    pref = preferences()
    servername = pref.GetString(DefaultServerName, "")
    return getServer(servername)


def getServer(name):
    servers = getServers()
    if servers is None:
        return None
    if name == "":
        return servers[0]

    return next((item for item in servers if item["name"] == name), None)

def getServers():
    pref = preferences()
    servers = pref.GetString(ServerList, "")
    if servers == "":
        return []
    return json.loads(servers)


def removeServer(name):
    pref = preferences()
    serverList = getServers()
    newlist = []
    for server in serverList:
        if server['name'] != name:
            newlist.append(server)
    pref.SetString(ServerList, json.dumps(newlist))


def addServer(name, authToken, secretToken, url, port):
    pref = preferences()
    serverList = getServers()

    #check if the server already exists
    server = getServer(name)

    if server is None:
        server = {"name": name,
                  "authToken": authToken,
                  "secretToken": secretToken,
                  "url": url,
                  "port": port}
    else:
        itemindex = next((index for (index, d) in enumerate(serverList) if d["name"] == name), None)
        serverList.pop(itemindex)

        server['authToken'] = authToken
        server['secretToken'] = authToken
        server['url'] = url
        server['port'] = port

    serverList.append(server)
    pref.SetString(ServerList, json.dumps(serverList))

    return server


def setDefaultServer(name):
    server = getServer(name)
    if server is None:
        raise LookupError('server with that name not found')

    return preferences().SetString(DefaultServerName, name)


