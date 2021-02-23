import FreeCADGui
import FreeCAD
import Cloud
import cloudScripts.preferences as preferences

class Sender():
    """Command to send a model to a CADcloud server"""

    def GetResources(self):
        return {'Pixmap'  : 'cloud-up', # the name of a svg file available in the resources
                'Accel' : "Shift+S", # a default shortcut (optional)
                'MenuText': "Send to Cloud",
                'ToolTip' : "Upload Model to CADCloud server"}

    def Activated(self):
        print('sending...')
        # Cloud.URL(u"https://YOUR SERVER URI") \
        # Cloud.TCPPort(u"443") \
        # Cloud.TokenAuth(u"YOUR ACCESS KEY") \
        # Cloud.TokenSecret(u"YOUR PRIVATE KEY") \
        # Cloud.Save(u"YOUR MODEL NAME (lowercase only)") \

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

class Getter():
    """Command to retrieve a Model from a CADCloud server"""

    def GetResources(self):
        return {'Pixmap'  : 'cloud-down', # the name of a svg file available in the resources
                'Accel' : "Shift+G", # a default shortcut (optional)
                'MenuText': "Get from Cloud..",
                'ToolTip' : "Gets a model from a CADcloud server"}

    def Activated(self):
        server = preferences.defaultServer()
        print(server)
        print('getting...')

        Cloud.URL(u"{}".format(server['url']))
        Cloud.TCPPort(u"{}".format(server['port']))
        Cloud.TokenAuth(u"{}".format(server['authToken']))
        Cloud.TokenSecret(u"{}".format(server['secretToken']))

        #Cloud.Restore(u"{}".format("idlerwheel"))

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

FreeCADGui.addCommand('Cloud_Send', Sender())
FreeCADGui.addCommand('Cloud_Get', Getter())
