# Cloud gui init module
# (c) 2001 Juergen Riegel LGPL
# (c) 2019 Jean-Marie Verdun LGPL


class CloudWorkbench (Workbench):
    "Cloud workbench object"

    def __init__(self):
        self.__class__.Icon = FreeCAD.getResourceDir() + "Mod/Cloud/Resources/icons/CloudWorkbench.svg"
        self.__class__.MenuText = "Cloud"
        self.__class__.ToolTip = "Cloud workbench"

    def Initialize(self):
        global CloudCommandGroup

        # Add preferences page
        from cloudScripts import preferencesGui
        FreeCADGui.addPreferencePage(preferencesGui.PreferencesPage, "Cloud")

        # load the module
        import CloudGui
        #import cloudScripts
        from cloudScripts import sender
        from cloudScripts import cloudCommands
        from PySide import QtCore, QtGui

        FreeCADGui.addLanguagePath(":/translations")
        FreeCADGui.addIconPath(":/icons")

        # build commands list
        cmdlist = ["Cloud_Send", "Cloud_Get", "Cloud_Dock"]
        self.appendToolbar(QtCore.QT_TRANSLATE_NOOP("Cloud", "Communicate"), cmdlist)
        self.appendMenu(QtCore.QT_TRANSLATE_NOOP("Cloud", "&Cloud"), cmdlist)

    def GetClassName(self):
        #return "CloudGui::Workbench"
        return "Gui::PythonWorkbench"

    def Activated(self):
        return FreeCAD.ActiveDocument is not None

    def Deactivated(self):
        pass

Gui.addWorkbench(CloudWorkbench())
