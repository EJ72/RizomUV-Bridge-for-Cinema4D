# coding=utf-8
# Copyright (C) 2018 Resonic.ru
# Compatibility and functionality restoration for Cinema 4D R19 to R2024.1.0 by Eric Jeffery

import os, re, json, subprocess, time, platform
from threading import Thread

import c4d
from c4d import plugins, bitmaps, storage, gui, utils

demo = """ZomSelect({PrimType="Edge", ResetBefore=true, Select=true, XYZSpace=true, IDs={0}, List=true})
ZomSelect({PrimType="Edge", Select=true, All=true, FilterIslandVisible=true})
ZomCut({PrimType="Edge"})
ZomIslandGroups({Mode="DistributeInTilesByBBox", MergingPolicy=8322})
ZomIslandGroups({Mode="DistributeInTilesEvenly", MergingPolicy=8322, UseTileLocks=true, UseIslandLocks=true})
ZomPack({ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", Scaling={Mode=2}, Rotate={}, Translate=true, LayoutScalingMode=2})"""

edge_selection = """for i, edge in pairs(edges) do
	ZomSelect({PrimType="Edge", Select=true, IDs={ edge}, List=true})
end"""


class BCommandData(c4d.plugins.CommandData):
    def __init__(self, plugin):
        self.dlg = None
        self.plugin = plugin

    def Execute(self, doc):

        bc = c4d.BaseContainer()
        c4d.gui.GetInputState(c4d.BFM_INPUT_KEYBOARD, c4d.BFM_INPUT_CHANNEL, bc)

        if self.plugin == "export":
            # SHIFT == 1, CTRL == 2
            if bc[c4d.BFM_INPUT_QUALIFIER] == 1:
                dlg = Options()
                dlg.Open(
                    c4d.DLG_TYPE_MODAL, xpos=-1, ypos=-1, defaultw=200, defaulth=100
                )
            else:
                self.dlg = Starter()

        elif self.plugin == "options":
            dlg = Options()
            dlg.Open(c4d.DLG_TYPE_MODAL, xpos=-1, ypos=-1, defaultw=200, defaulth=100)

        elif self.plugin == "scripts":
            dlg = ScriptsManager()
            dlg.Open(
                c4d.DLG_TYPE_MODAL_RESIZEABLE,
                xpos=-1,
                ypos=-1,
                defaultw=500,
                defaulth=250,
            )

        return True


class Exporter:
    def __init__(self, *args):

        self.ui = {
            "TXT_U3D_PATH": [1999, ""],
            "CHK_NEW_UV": [2000, False],
            "RADIO_GROUP": [2001, 0],
            "CHK_AUTO_CLOSE": [2002, True],
            "CHK_UDIM": [2003, False],
            "CHK_NOMAT": [2004, True],
            "CHK_KEEP": [2005, False],
            "CHK_SINGLE": [2006, False],
            "LST_SCRIPTS": [2007, 0],
        }

        self.ui_ = {
            "TXT_MONO": 1990,
            "BTN_UPD": 1991,
            "BTN_NEW": 1992,
            "BTN_DEL": 1993,
            "BTN_FIND": 1994,
            "BTN_SAVE": 1995,
            "BTN_RUN": 1996,
            "BTN_CANCEL": 1997,
        }

        self.doc = None
        self.selected_objs = None
        self.plugin_folder = None
        self.scripts_folder = None
        self.settings_path = None
        self.object_path = None
        self.time = None
        self.p = None

        self.settings_load()

    def dispatch(self, mode):

        if mode == "roaming":
            self.plugin_folder = os.path.join(
                storage.GeGetC4DPath(c4d.C4D_PATH_PREFS), "rizomUV"
            )

        # if mode == 'temp':
        # self.plugin_folder = os.path.join(os.environ['Temp'], 'rizomUV')

        self.settings_path = os.path.join(self.plugin_folder, "settings.json")
        self.object_path = os.path.join(self.plugin_folder, "temp.fbx")
        self.scripts_folder = os.path.join(self.plugin_folder, "scripts")

    def settings_load(self):
        self.dispatch("roaming")
        settings = json_load(self.settings_path)

        if settings is None:
            self.dispatch("temp")
            settings = json_load(self.settings_path)

        if settings:
            self.ui = settings
        else:
            self.settings_save()
            self.demo_scripts()
            print("Loading Default Settings")

    def settings_save(self):
        try:
            self.dispatch("roaming")
            if json_save(self.settings_path, self.ui):
                return
            else:
                self.dispatch("temp")
                json_save(self.settings_path, self.ui)
        except WindowsError:
            c4d.gui.MessageDialog("Write Settings Failed")
            return False

    def demo_scripts(self):

        scripts = [demo]

        for index, script in enumerate(scripts):
            file_path = os.path.join(
                self.scripts_folder, "demo_script_" + str(index) + ".lua"
            )
            with open(file_path, "w") as file_:
                file_.write(script)

    def script_save(self, name, script, dialog=True, mode="w"):

        if name is None:
            dialog = True

        if dialog:
            script_name = storage.SaveDialog(
                0, "Save *.lua File", "lua", def_path=self.scripts_folder, def_file=name
            )
        else:
            script_name = os.path.join(self.scripts_folder, name)

        if script_name is None:
            return

        if os.path.exists(self.scripts_folder):
            if mode == "w":
                with open(script_name, "w") as file_:
                    file_.write(script)
                    file_.close()
            if mode == "r+":
                with open(script_name, "r+") as file_:
                    lines = file_.readlines()
                    lines.insert(0, script)
                    file_.writelines(lines)

            split_name = script_name.split("\\")[-1]
            return split_name

    def script_formation(self, selection, script):
        path = self.object_path.replace("\\", "/")

        load_string = (
            'ZomLoad({File={Path="'
            + path
            + '", ImportGroups=true, XYZUVW=true, UVWProps='
            + str(self.ui["CHK_NEW_UV"][1])
            + "}, NormalizeUVW=true})"
        )

        save_string = ""
        if self.ui["CHK_SINGLE"][1] and len(script) > 0:
            save_string = (
                'ZomSave({File={Path="'
                + path
                + '", UVWProps=true}, __UpdateUIObjFileName=true})'
            )

        code = "{}\n{}\n{}\n{}".format(load_string, selection, script, save_string)
        self.script_save("temp.lua", code, dialog=False)


class Starter(Exporter):
    def __init__(self, script="", cmd=False):
        Exporter.__init__(self)
        self.rizomuv_run(script, cmd)

    def rizomuv_run(self, script, cmd):
        c4d.CallCommand(12236)  # Make Editable

        self.doc = c4d.documents.GetActiveDocument()
        self.selected_objs = self.doc.GetActiveObjects(
            c4d.GETACTIVEOBJECTFLAGS_CHILDREN
        )

        if not fbx_exchange(self.doc, self.selected_objs, self.object_path, self.ui):
            return

        # [ SELECTION ] - - - - - - - - - - - - - - - - - - - - - - - [/]
        lua_selection = ""
        if self.ui["RADIO_GROUP"][1] > 1:

            index = -1
            to_select = []

            for obj in self.selected_objs:

                if obj is None or obj.GetType() != c4d.Opolygon:
                    gui.MessageDialog("Only polygon objects are allowed.")
                    return

                rizomuv_edges = rizomuv_indexes(obj, index)  # edge : rizom

                # if self.ui['RADIO_GROUP'][1] == 2
                bs_e = obj.GetEdgeS()
                p_count = obj.GetPolygonCount()

                edges = [idx for idx, sel in enumerate(bs_e.GetAll(p_count * 4)) if sel]

                # if state == 3
                # TAG

                for k, v in rizomuv_edges.items():  # edge : rizom
                    if k in edges:
                        to_select.append(str(v))

                index = sorted(rizomuv_edges.values())[-1]

            lua_selection = "edges = {" + ", ".join(to_select) + "}\n" + edge_selection
            cmd = True

        self.script_formation(lua_selection, script)

        # [ RUN COMMAND LINE ] - - - - - - - - - - - - - - - - - - - [/]
        if cmd:
            temp_script = os.path.join(self.scripts_folder, "temp.lua")
            param = [self.ui["TXT_U3D_PATH"][1], "-cfi", temp_script]
        else:
            param = [self.ui["TXT_U3D_PATH"][1], self.object_path]

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

        try:
            self.p = subprocess.Popen(param)
        except OSError:
            c4d.gui.MessageDialog(
                "RizomUV not found! Please configure path to the RizomUV executable in Option window first!"
            )
            print("RizomUV not found!")
            return

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

        self.time = os.path.getmtime(self.object_path)

        wt = WatchThread(
            "ht",
            self.doc,
            self.selected_objs,
            self.object_path,
            self.time,
            self.p,
            self.ui,
        )
        wt.start()


class WatchThread(Thread):
    def __init__(self, name, doc, selected_objs, swap_path, t, p, UI):
        Thread.__init__(self, name=name)
        self.doc = doc
        self.selected_objs = selected_objs
        self.swap_path = swap_path
        self.time = t
        self.p = p

        self.UI = UI

    def run(self):
        doc = c4d.documents.GetActiveDocument()
        selected = doc.GetActiveObjects(0)
        printed = 0

        dirt_flag = False

        while True:
            printed += 1
            if printed == 1:
                print("Waiting...")

            # Modified begin
            if file_checker(self.swap_path, self.time):
                self.time = os.path.getmtime(self.swap_path)
                dirt_flag = True

            time.sleep(1)

            # Double check and loading
            if not file_checker(self.swap_path, self.time) and dirt_flag:

                # Loading
                fbx_exchange(self.doc, self.selected_objs, self.swap_path, self.UI, 1)

                if self.UI["CHK_AUTO_CLOSE"][1]:
                    self.p.kill()

                if len(selected) != 0:
                    for ob in selected:
                        print("Updating " + ob.GetName() + " UVs...")
                        print(ob.GetName() + " UVs Updated!")

                break

            # RizomUV is closed
            if self.p.poll() is not None:
                print("Update UVs Canceled")
                break

            time.sleep(1)


class Options(Exporter, gui.GeDialog):
    def __init__(self, *args):
        Exporter.__init__(self, *args)

    def InitValues(self):
        self.parser(0)
        return True

    def CreateLayout(self):
        self.SetTitle("RizomUV Exporter Options")

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 1, 10)
        self.GroupBorderSpace(10, 10, 10, 0)

        # [ OPTIONS ] - - - - - - - - - - - - - - - - - - - - - - - [/]

        self.GroupBegin(1, c4d.BFH_SCALEFIT, 2, 1)
        self.GroupBorderSpace(0, 10, 0, 10)

        self.GroupBegin(2, c4d.BFH_SCALEFIT, 1, 2)
        self.AddCheckbox(self.ui["CHK_NEW_UV"][0], c4d.BFH_SCALEFIT, 150, 10, "New UVW")
        self.AddCheckbox(
            self.ui["CHK_AUTO_CLOSE"][0], c4d.BFH_SCALEFIT, 150, 10, "Auto Close"
        )
        self.GroupEnd()

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

        self.GroupBegin(4, c4d.BFH_SCALEFIT, 1, 2)
        self.AddCheckbox(
            self.ui["CHK_NOMAT"][0], c4d.BFH_SCALEFIT, 150, 10, "No Materials"
        )
        self.AddCheckbox(
            self.ui["CHK_KEEP"][0], c4d.BFH_SCALEFIT, 150, 10, "Keep History"
        )
        self.GroupEnd()

        self.GroupEnd()

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

        self.AddSeparatorH(6, c4d.BFH_SCALEFIT)

        # [ SELECTION ] - - - - - - - - - - - - - - - - - - - - - - [/]

        self.GroupBegin(5, c4d.BFH_SCALEFIT, 2, 1)
        self.GroupBorderSpace(0, 5, 0, 5)

        self.AddRadioGroup(self.ui["RADIO_GROUP"][0], c4d.BFH_SCALEFIT, 1, 2)
        self.AddChild(self.ui["RADIO_GROUP"][0], 1, "Ignore edge selection")
        self.AddChild(self.ui["RADIO_GROUP"][0], 2, "Export edge selection")
        # self.AddChild(self.ui['RADIO_GROUP'][0], 3, "Use first selection tag")
        self.GroupEnd()

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

        self.AddSeparatorH(6, c4d.BFH_SCALEFIT)

        # [ EXE PATH ] - - - - - - - - - - - - - - - - - - - - - - - [/]

        self.GroupBegin(7, c4d.BFH_SCALEFIT, 1, 2)
        self.GroupBorderSpace(0, 10, 0, 10)
        self.AddStaticText(1500, c4d.BFH_SCALEFIT, 200, 10, "RizomUV Path: ", 0)

        self.GroupBegin(8, c4d.BFH_SCALEFIT, 2, 1)
        self.AddEditText(self.ui["TXT_U3D_PATH"][0], c4d.BFH_SCALEFIT, 200, 10)
        self.AddButton(self.ui_["BTN_FIND"], c4d.BFH_RIGHT, name="...")
        self.GroupEnd()

        self.GroupEnd()

        # [ BUTTONS ] - - - - - - - - - - - - - - - - - - - - - - - [/]

        self.GroupBegin(9, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 2, 1)
        self.AddButton(self.ui_["BTN_SAVE"], c4d.BFH_SCALEFIT, inith=15, name="Save")
        self.AddButton(
            self.ui_["BTN_CANCEL"], c4d.BFH_SCALEFIT, inith=15, name="Cancel"
        )
        self.GroupEnd()

        # [ COPYRIGHTS ] - - - - - - - - - - - - - - - - - - - - - [/]

        self.GroupBegin(8, c4d.BFH_RIGHT, 1, 1)
        self.AddStaticText(10, c4d.BFH_RIGHT, name="(C) www.zen.team")
        self.GroupEnd()

        self.GroupEnd()
        return True

    def Command(self, id, msg):
        if id == self.ui_["BTN_FIND"]:
            # Open a file dialog for selecting "RizomUV executable"
            selected_file = c4d.storage.LoadDialog(
                type=c4d.FILESELECTTYPE_ANYTHING,
                title="RizomUV Executable",
                flags=c4d.FILESELECT_LOAD,
            )

            if selected_file:
                os_name = platform.system()
                abs_file_path = None

                if os_name == "Windows":
                    print(os_name)
                    abs_file_path = os.path.abspath(selected_file)
                elif os_name == "Darwin":
                    print(os_name)
                    # Convert the relative path to an absolute path
                    name = selected_file.replace("/Applications/", "").replace(
                        ".app", ""
                    )
                    abs_file_path = os.path.abspath(
                        selected_file + "/Contents/MacOS/" + name
                    )

                if abs_file_path:
                    # Update the 'TXT_U3D_PATH' value with the absolute path
                    self.ui["TXT_U3D_PATH"][1] = abs_file_path
                    # Also, update the text field in the dialog
                    self.SetString(self.ui["TXT_U3D_PATH"][0], abs_file_path)

        if id == self.ui_["BTN_SAVE"]:
            self.parser(1)
            self.settings_save()
            self.Close()

        if id == self.ui_["BTN_CANCEL"]:
            self.Close()

        return True

    def parser(self, save_mode=0):

        # TODO: global parser
        exclude_list = {"options": ["LST_SCRIPTS", "CHK_SINGLE"]}

        for k, v in self.ui.items():

            if k in exclude_list["options"]:
                continue

            if isinstance(v[1], str) or isinstance(v[1], str):  # TEXT
                if save_mode == 0:
                    self.SetString(v[0], v[1])
                else:
                    v[1] = self.GetString(v[0])

            if isinstance(v[1], bool):  # CHK
                if save_mode == 0:
                    self.SetBool(v[0], v[1])
                else:
                    v[1] = self.GetBool(v[0])

            if isinstance(v[1], int):  # RADIO
                if save_mode == 0:
                    self.SetInt32(v[0], v[1])
                else:
                    v[1] = self.GetInt32(v[0])


class ScriptsManager(Exporter, gui.GeDialog):
    def __init__(self, *args):
        Exporter.__init__(self, *args)
        self.grid = {}
        self.combo_box = self.ui["LST_SCRIPTS"][0]

    def InitValues(self):
        self.scan_folder()
        self.ui_set(self.ui["LST_SCRIPTS"][1])

        self.SetBool(self.ui["CHK_SINGLE"][0], self.ui["CHK_SINGLE"][1])
        return True

    def CreateLayout(self):

        if not os.path.exists(self.scripts_folder):
            c4d.gui.MessageDialog("Write Settings Failed")
            self.Close()
            return True

        self.SetTitle("RizomUV Scripts")

        self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 1, 3)
        self.GroupBorderSpace(10, 10, 10, 10)

        # [ COMBOTEXT ] - - - - - - - - - - - - - - - - - - - - - [/]
        self.GroupBegin(1, c4d.BFH_SCALEFIT, 6, 1)
        self.GroupBorderSpace(0, 10, 0, 5)
        self.AddComboBox(self.combo_box, c4d.BFH_SCALEFIT, 250, 15, specialalign=False)
        self.AddButton(self.ui_["BTN_UPD"], c4d.BFH_LEFT, inith=15, name="Reload")

        self.GroupBegin(4, c4d.BFV_SCALEFIT, 1, 1)
        self.GroupBorderSpace(5, 0, 5, 0)
        self.AddSeparatorH(1, c4d.BFV_SCALEFIT)
        self.GroupEnd()

        self.AddButton(self.ui_["BTN_NEW"], c4d.BFH_LEFT, inith=15, name="New")
        self.AddButton(self.ui_["BTN_SAVE"], c4d.BFH_LEFT, inith=15, name="Save As")
        self.AddButton(self.ui_["BTN_DEL"], c4d.BFH_LEFT, inith=15, name="Delete")

        self.GroupEnd()

        # [ MONOTEXT ] - - - - - - - - - - - - - - - - - - - - - [/]
        self.GroupBegin(2, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 1, 1)
        self.GroupBorderSpace(0, 0, 0, 10)
        self.AddMultiLineEditText(
            self.ui_["TXT_MONO"],
            c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
            400,
            200,
            c4d.DR_MULTILINE_MONOSPACED
            | c4d.DR_MULTILINE_STATUSBAR
            | c4d.DR_MULTILINE_HIGHLIGHTLINE,
        )
        self.GroupEnd()

        # [ BUTTONS ] - - - - - - - - - - - - - - - - - - - - - [/]
        self.GroupBegin(3, c4d.BFH_RIGHT, 4, 1)

        self.AddCheckbox(
            self.ui["CHK_SINGLE"][0], c4d.BFH_LEFT, 150, 12, "Run and Close"
        )

        self.GroupBegin(4, c4d.BFV_SCALEFIT, 1, 1)
        self.GroupBorderSpace(5, 0, 5, 0)
        self.AddSeparatorH(1, c4d.BFV_SCALEFIT)
        self.GroupEnd()

        self.AddButton(
            self.ui_["BTN_RUN"], c4d.BFH_SCALEFIT, inith=15, initw=100, name="Run"
        )
        self.AddButton(
            self.ui_["BTN_CANCEL"], c4d.BFH_SCALEFIT, inith=15, initw=100, name="Close"
        )
        self.GroupEnd()

        self.GroupEnd()
        return True

    def Command(self, id, msg):

        if id == self.combo_box:
            index = self.ui_get("index")
            self.ui_set(index)

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

        if id == self.ui_["BTN_UPD"]:
            index = self.ui_get("index")
            self.scan_folder()
            self.ui_set(index)

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

        if id == self.ui_["BTN_NEW"]:

            script_name = self.script_new()
            if script_name is None:
                return True

            ids = self.search_id(script_name)
            if ids:
                c4d.gui.MessageDialog(
                    "The requested file could not be created because"
                    " a file with the same name already exists."
                )
                return True

            self.script_save(script_name, "", dialog=False)
            self.scan_folder()

            ids = self.search_id(script_name)
            if ids:
                self.ui_set(ids)

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

        if id == self.ui_["BTN_SAVE"]:
            ids, name, text = self.ui_get()

            script_name = self.script_save(name, text)
            if script_name is None:
                return True

            self.scan_folder()

            ids = self.search_id(script_name)
            if ids:
                self.ui_set(ids)

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

        if id == self.ui_["BTN_DEL"]:

            if len(self.grid) == 0:
                c4d.gui.MessageDialog("There are no scripts in folder!")
                return True

            name = self.ui_get("name")
            self.script_delete(name)
            self.scan_folder()
            self.ui_set(500)

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

        if id == self.ui_["BTN_RUN"]:
            self.parser()
            self.settings_save()

            Starter(self.ui_get("text"), cmd=True)

            self.Close()

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

        if id == self.ui_["BTN_CANCEL"]:
            self.parser()
            self.settings_save()
            self.Close()

        return True

    def parser(self):
        # TODO: Replace to parser
        self.ui["LST_SCRIPTS"][1] = self.GetInt32(self.combo_box)
        self.ui["CHK_SINGLE"][1] = self.GetBool(self.ui["CHK_SINGLE"][0])

    def scan_folder(self):

        # self.grid = {}

        scripts = [
            file_ for file_ in os.listdir(self.scripts_folder) if file_.endswith(".lua")
        ]

        for index, name in enumerate(scripts):
            file_path = os.path.join(self.scripts_folder, name)
            with open(file_path, "r") as file_:
                text = file_.read()
                file_.close()

            self.grid.update({index + 500: {"name": name, "text": text}})

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

        self.FreeChildren(self.combo_box)
        for index, value in self.grid.items():
            self.AddChild(self.combo_box, index, value["name"])

        return True

    def search_id(self, name):
        for key, value in self.grid.items():
            if value["name"] == name:
                return key

    def ui_get(self, params=None):
        # TODO: Replace to parser
        index = self.GetInt32(self.combo_box)
        text = self.GetString(self.ui_["TXT_MONO"])
        name = None
        if self.grid.get(index):
            name = self.grid[index]["name"]

        ui = {"index": index, "name": name, "text": text}

        if params:
            return ui[params]

        return ui.values()

    def ui_set(self, index):
        self.SetInt32(self.combo_box, index)

        if self.grid.get(index):
            self.SetString(self.ui_["TXT_MONO"], self.grid[index]["text"])
        else:
            self.SetString(self.ui_["TXT_MONO"], "")

    @staticmethod
    def script_new():
        sub_dialog = SubScriptName()
        sub_dialog.Open(c4d.DLG_TYPE_MODAL, 1041417, subid=1)
        name = sub_dialog.name

        if name is None:
            return None

        script_name = name + ".lua"
        return script_name

    def script_load(self, name):
        file_path = os.path.join(self.scripts_folder, name)
        if os.path.exists(file_path):
            with open(file_path, "r") as file_:
                return file_.read()

    def script_delete(self, name):
        sub_dialog = SubScriptDelete()
        sub_dialog.Open(c4d.DLG_TYPE_MODAL, 1041417, subid=2)

        if sub_dialog.answer:
            file_path = os.path.join(self.scripts_folder, name)
            if os.path.exists(file_path):
                os.remove(file_path)


class SubScriptName(c4d.gui.GeDialog):
    def __init__(self):
        self.name = None

    def CreateLayout(self):
        self.SetTitle("New file`s name")

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 1, 2)
        self.GroupBorderSpace(10, 10, 10, 10)

        self.GroupBegin(1, c4d.BFH_SCALEFIT, 2, 1)
        self.AddStaticText(1000, c4d.BFH_LEFT, initw=60, name="Name:")
        self.AddEditText(1001, c4d.BFH_SCALEFIT, initw=40)
        self.GroupEnd()

        self.AddDlgGroup(c4d.DLG_OK | c4d.DLG_CANCEL)

        self.GroupEnd()

        return True

    def Command(self, id, msg):

        if id == 1:
            temp_name = self.GetString(1001)
            if temp_name is None or re.search("[^ a-zA-Z0-9_]", temp_name):
                gui.MessageDialog("Incorrect name!")
            else:
                self.name = temp_name

            self.Close()

        if id == 2:
            self.Close()

        return True


class SubScriptDelete(c4d.gui.GeDialog):
    def __init__(self):
        self.answer = False

    def CreateLayout(self):
        self.SetTitle("Delete Confirmation Dialog")

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 1, 2)

        self.GroupBegin(1, c4d.BFH_SCALEFIT, 1, 1)
        self.GroupBorderSpace(40, 10, 0, 10)
        self.AddStaticText(
            1000, c4d.BFH_RIGHT, name="Are you sure want delete this script?"
        )
        self.GroupEnd()

        self.AddDlgGroup(c4d.DLG_OK | c4d.DLG_CANCEL)

        self.GroupEnd()

        return True

    def Command(self, id, msg):

        if id == 1:
            self.answer = True
            self.Close()

        if id == 2:
            self.Close()

        return True


def rizomuv_indexes(op, rizom_index=-1):
    # ->  [(a:0, b:3, c:4, d:1), (a:1, b:4, c:5, d:2)]
    p = op.GetAllPolygons()
    tag = op.GetTag(c4d.Tuvw)

    # tag test

    nbr = utils.Neighbor()
    nbr.Init(op)

    open_edges = []
    pass_edges = []
    pass_uvws = []

    x, y = 0, 0
    rizomuv_edges = {}

    for i in range(op.GetPolygonCount()):

        uv = tag.GetSlow(i)

        # -> [0, 3, 4, 1]
        points = [p[i].a, p[i].b, p[i].c, p[i].d]

        sides = [0, 1, 2, 3]
        uvws = [uv["a"], uv["b"], uv["c"], uv["d"]]
        quad = True

        if p[i].IsTriangle():
            sides = [0, 2, 3]
            uvws = [uv["a"], uv["b"], uv["c"]]
            quad = False

        for side in sides:
            if side == 0:
                x, y = 0, -1  # a / d | a / c
            if side == 1:
                x, y = -1, 2  # d / c | -----
            if side == 2:
                x, y = 2, 1  # -c / b | c / b
                if quad:
                    rizom_index += 1
            if side == 3:
                x, y = 1, 0  # -b / a | b / a

            a, b = points[x], points[y]
            u, v = uvws[x], uvws[y]

            # -> 12, 13, ... indexes
            pt = sorted([a, b])

            # -> [Vector(0.251, 0.749, 0), Vector(0.251, 0.998, 0)]
            uv = sorted((u.x, u.y) + (v.x, v.y))

            unique_edge = pt not in pass_edges
            unique_uv = uv not in pass_uvws

            if unique_edge or unique_uv:
                edge_index = i * 4 + p[i].FindEdge(a, b)

                # print edge_index, 'index --> ', unique_edge, '====', unique_uv

                if unique_edge is False and unique_uv:
                    open_edges.append(edge_index)
                    continue

                pass_edges.append(pt)
                pass_uvws.append(uv)

                rizom_index += 1

                rizomuv_edges.update({edge_index: rizom_index})

    index = sorted(rizomuv_edges.values())[-1]
    for i, edge in enumerate(open_edges):
        rizomuv_edges.update({edge: index + 1})

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # print 'index ', index
    # print 'open edges ', open_edges
    # print rizomuv_edges
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    return rizomuv_edges


def make_dirs(path):
    folder = os.path.dirname(path)
    script_folder = os.path.join(folder, "scripts")
    if not os.path.exists(script_folder):
        os.makedirs(script_folder)
        return True


def json_save(path, data):
    make_dirs(path)
    with open(path, "w") as file_:
        json.dump(data, file_, ensure_ascii=False, indent=4)
        # print "Settings saved to: " + path
        return True


def json_load(path):
    if not os.path.exists(path):
        return

    with open(path, "r") as file_:
        # print "Settings load from: " + path
        return json.load(file_)


def file_checker(obj_path, t):
    if obj_path is None:
        return
    nwt = os.path.getmtime(obj_path)
    if nwt != t:
        return True


def get_next_object(op):
    if op is None:
        return None
    if op.GetDown():
        return op.GetDown()
    while not op.GetNext() and op.GetUp():
        op = op.GetUp()
    return op.GetNext()


def tag_search(tag_type, op):
    tag_list = []
    tags = op.GetTags()
    for tag in tags:
        if tag and tag.GetType() == tag_type:
            tag_list.append(tag)
    return tag_list


def tag_cleaner(doc):
    obj = doc.GetFirstObject()
    while obj:
        tags_list = tag_search(5671, obj)
        for tag in tags_list:
            tag.Remove()
        obj = get_next_object(obj)


def fbx_config(fbx):
    optionsUI = Exporter()

    fbx[c4d.FBXEXPORT_FBX_VERSION] = 0
    fbx[c4d.FBXEXPORT_ASCII] = 0
    fbx[c4d.FBXEXPORT_SELECTION_ONLY] = 0
    fbx[c4d.FBXEXPORT_CAMERAS] = 0
    fbx[c4d.FBXEXPORT_SPLINES] = 0
    fbx[c4d.FBXEXPORT_GLOBAL_MATRIX] = 0

    if c4d.GetC4DVersion() > 26000:
        fbx[c4d.FBXEXPORT_SDS_CAGE] = 0
    if c4d.GetC4DVersion() < 26000:
        fbx[c4d.FBXEXPORT_SDS] = True

    fbx[c4d.FBXEXPORT_LIGHTS] = 0
    fbx[c4d.FBXEXPORT_TRACKS] = 0
    fbx[c4d.FBXEXPORT_BAKE_ALL_FRAMES] = 0
    fbx[c4d.FBXEXPORT_PLA_TO_VERTEXCACHE] = 0
    fbx[c4d.FBXEXPORT_SAVE_NORMALS] = 1
    fbx[c4d.FBXEXPORT_SAVE_VERTEX_MAPS_AS_COLORS] = 0
    fbx[c4d.FBXEXPORT_SAVE_VERTEX_COLORS] = 0
    fbx[c4d.FBXEXPORT_TRIANGULATE] = 0
    fbx[c4d.FBXEXPORT_SDS_SUBDIVISION] = 0
    fbx[c4d.FBXEXPORT_LOD_SUFFIX] = 0

    if optionsUI.ui["CHK_NOMAT"][0]:
        if c4d.GetC4DVersion() < 22000:
            fbx[c4d.FBXEXPORT_TEXTURES] = 1
        if c4d.GetC4DVersion() > 21999 < 25999:
            fbx[c4d.FBXEXPORT_MATERIALS] = c4d.FBXEXPORT_MATERIALS_PHONGLAMBERT
        if c4d.GetC4DVersion() > 25999:
            fbx[c4d.FBXEXPORT_MATERIALS] = 1

    if optionsUI.ui["CHK_NOMAT"][1]:
        if c4d.GetC4DVersion() < 22000:
            fbx[c4d.FBXEXPORT_TEXTURES] = 0
        if c4d.GetC4DVersion() > 21999 < 25999:
            fbx[c4d.FBXEXPORT_MATERIALS] = c4d.FBXEXPORT_MATERIALS_OFF
        if c4d.GetC4DVersion() > 25999:
            fbx[c4d.FBXEXPORT_MATERIALS] = 0

    fbx[c4d.FBXEXPORT_EMBED_TEXTURES] = 0
    fbx[c4d.FBXEXPORT_SUBSTANCES] = 0

    return fbx


def fbx_exchange(doc, objects, obj_path, ui, mode=0):
    plug = plugins.FindPlugin(1026370, c4d.PLUGINTYPE_SCENESAVER)
    if plug is None:
        gui.MessageDialog("C4D version incorrect!")
        return

    op = {}
    if plug.Message(c4d.MSG_RETRIEVEPRIVATEDATA, op):

        if "imexporter" not in op:
            return

        fbx = op["imexporter"]
        if fbx is None:
            return

        if c4d.GetC4DVersion() > 2023999:
            temp_fbx = fbx.GetDataInstance()
        else:
            temp_fbx = fbx.GetData()
        fbx_config(fbx)

        # [ EXPORT ] - - - - - - - - - - - - - - - - - - - - -[/]
        if mode == 0:

            if not objects:
                gui.MessageDialog("Select the object!")
                return

            # - - - - - - - - - - - - - - - - - - - - - - - -

            c4d.CallCommand(c4d.ID_NGON_REMOVE_MENU)  # Remove ngons

            # - - - - - - - - - - - - - - - - - - - - - - - -

            doc_temp = c4d.documents.IsolateObjects(doc, objects)
            if doc_temp is None:
                return

            if ui["CHK_NEW_UV"][1]:
                tag_cleaner(doc_temp)

            # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

            if c4d.documents.SaveDocument(
                doc_temp, obj_path, c4d.SAVEDOCUMENTFLAGS_DONTADDTORECENTLIST, 1026370
            ):
                print("Exported to: " + obj_path)
            else:
                gui.MessageDialog("Export failed!")

        # [ IMPORT ] - - - - - - - - - - - - - - - - - - - - -[/]
        if mode == 1:

            if obj_path is None:
                return

            if ui["CHK_KEEP"][1]:
                for obj in objects:
                    obj[c4d.ID_BASEOBJECT_VISIBILITY_EDITOR] = True
                    obj[c4d.ID_BASEOBJECT_VISIBILITY_RENDER] = True
            else:
                for obj in objects:
                    obj.Remove()

            # - - - - - - - - - - - - - - - - - - - - - - - - - -

            c4d.documents.MergeDocument(
                doc,
                obj_path,
                c4d.SCENEFILTER_OBJECTS
                | c4d.SCENEFILTER_MATERIALS
                | c4d.SCENEFILTER_MERGESCENE,
                None,
            )

        # [ RESTORE ] - - - - - - - - - - - - - - - - - - - - [/]
        for data_id, data in temp_fbx:
            fbx[data_id] = data

        if c4d.GetC4DVersion() > 2024999:
            c4d.gui.StatusClear()
        else:
            c4d.StatusClear()

        c4d.EventAdd()
        return True

if __name__ == "__main__":
    dir, file_name = os.path.split(__file__)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    bmp_export = bitmaps.BaseBitmap()
    ico_export = os.path.join(dir, "res", "export.tif")
    bmp_export.InitWith(ico_export)

    c4d.plugins.RegisterCommandPlugin(
        id=1041414,
        str="Export to RizomUV",
        help="Exchange to RizomUV, [Shift]: Open Options",
        info=0,
        dat=BCommandData("export"),
        icon=bmp_export,
    )

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    bmp_opt = bitmaps.BaseBitmap()
    ico_opt = os.path.join(dir, "res", "opt.tif")
    bmp_opt.InitWith(ico_opt)

    c4d.plugins.RegisterCommandPlugin(
        id=1041415,
        str="Options",
        help="Export Options",
        info=0,
        dat=BCommandData("options"),
        icon=bmp_opt,
    )

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Extend!
    bmp_script = bitmaps.BaseBitmap()
    ico_script = os.path.join(dir, "res", "scripts.tif")
    bmp_script.InitWith(ico_opt)

    c4d.plugins.RegisterCommandPlugin(
        id=1041417,
        str="Scripts Manager",
        help="",
        info=0,
        dat=BCommandData("scripts"),
        icon=bmp_script,
    )
