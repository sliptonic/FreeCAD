# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *   Copyright (c) 2026 sliptonic <shopinthewoods@gmail.com>               *
# *                                                                         *
# *   This file is part of the FreeCAD CAx development system.              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# ***************************************************************************

"""Unified Create-Operation picker (prototype / v0).

Non-modal three-pane dialog with type-ahead filter, category navigation, and
Green/Yellow/Red tool-tier rendering. See
``src/Mod/CAM/research/unified_op_creation_plan.md`` for the design rationale
and the full-rollout backlog.

Prototype constraints reflected here:
- Widgets built programmatically (no ``.ui`` file) so the dialog can evolve
  cheaply without qrc rebuilds. Migration to a ``.ui`` lives in the
  full-rollout "UI polish and scale" section.
- "Create" on a Yellow entry falls through to the underlying per-op command;
  the inline tool-acquisition flow (Phase 2.5) is deferred.
- Non-modal: the per-op command opens its own task panel via
  ``Control.showDialog()``. A modal picker would block user access to that
  task panel, which broke Create & Add. ``Qt.Tool`` keeps the picker
  floating above the main window without blocking it.
"""

import html as _html

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui
from PySide.QtCore import QT_TRANSLATE_NOOP

import Path
import Path.Dressup.Gui.Registry as DressupRegistry
import Path.Dressup.Utils as PathDressup
import Path.Op.Gui.Registry as Registry
import PathScripts.PathUtils as PathUtils

__title__ = "CAM Create-Operation picker"
__doc__ = "Prototype unified operation picker."


SUGGESTED_CATEGORY = "Suggested"
ALL_CATEGORY = "All"

MODE_OP = "op"
MODE_DRESSUP = "dressup"


# --------------------------------------------------------------------------- #
# Tier presentation
# --------------------------------------------------------------------------- #


def _tier_color(tier):
    """Foreground tint for an entry row. None = default palette.

    Tier values are shared across op and dressup registries: both use
    string sentinels with matching values (``green``, ``yellow``, ``red``,
    ``neutral``). Dressups never produce yellow/neutral.
    """
    if tier == Registry.TIER_GREEN:
        return None
    if tier == Registry.TIER_YELLOW:
        return QtGui.QColor(180, 120, 20)
    if tier == Registry.TIER_RED:
        return QtGui.QColor(140, 140, 140)
    return None


def _tier_label(tier):
    labels = {
        Registry.TIER_GREEN: "Ready",
        Registry.TIER_YELLOW: "Needs tool",
        Registry.TIER_RED: "Unavailable",
        Registry.TIER_NEUTRAL: "",
    }
    return labels.get(tier, "")


def _row_text(result):
    entry = result.entry
    if result.tier == Registry.TIER_YELLOW and result.reason:
        return "{name}  —  {reason}".format(name=entry.name, reason=result.reason)
    return entry.name


# --------------------------------------------------------------------------- #
# Dialog
# --------------------------------------------------------------------------- #


class CreateOpDialog(QtGui.QDialog):
    """Non-modal three-pane picker."""

    def __init__(self, parent=None):
        super().__init__(parent or FreeCADGui.getMainWindow())
        self.setWindowTitle(self.tr("Create Operation"))
        # Non-modal so per-op task panels (opened via Control.showDialog from
        # the per-op command) remain reachable while the picker is open. The
        # Tool window flag keeps the picker floating above the main window.
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)
        self.resize(820, 520)

        self._mode = MODE_OP
        self._results = []  # latest filter output (op or dressup)
        self._visible_results = []  # post-filter, post-category
        self._show_all = False
        self._selection_observer = None

        self._build_ui()
        self._install_selection_observer()
        self._refresh()

    # -- UI construction --------------------------------------------------- #

    def _build_ui(self):
        root = QtGui.QVBoxLayout(self)

        splitter = QtGui.QSplitter(QtCore.Qt.Horizontal, self)

        # Category pane — populated via _populate_categories() in mode-aware fashion.
        self._category_list = QtGui.QListWidget(splitter)
        self._category_list.setMinimumWidth(140)
        self._category_list.setMaximumWidth(200)
        self._populate_categories()
        self._category_list.currentRowChanged.connect(self._on_category_changed)
        splitter.addWidget(self._category_list)

        # Op list
        self._op_list = QtGui.QListWidget(splitter)
        self._op_list.setMinimumWidth(260)
        self._op_list.itemSelectionChanged.connect(self._on_op_selection_changed)
        self._op_list.itemDoubleClicked.connect(self._on_op_double_clicked)
        splitter.addWidget(self._op_list)

        # Info pane
        self._info = QtGui.QTextBrowser(splitter)
        self._info.setMinimumWidth(280)
        self._info.setOpenExternalLinks(True)
        splitter.addWidget(self._info)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)
        root.addWidget(splitter, 1)

        # Filter row
        filter_row = QtGui.QHBoxLayout()
        filter_row.addWidget(QtGui.QLabel(self.tr("Filter:")))
        self._filter_edit = QtGui.QLineEdit(self)
        self._filter_edit.setPlaceholderText(self.tr("Type to search operations…"))
        self._filter_edit.textChanged.connect(self._populate_op_list)
        filter_row.addWidget(self._filter_edit, 1)

        self._show_all_check = QtGui.QCheckBox(self.tr("Show all"), self)
        self._show_all_check.setToolTip(
            self.tr("Include operations that the current context does not support.")
        )
        self._show_all_check.toggled.connect(self._on_show_all_toggled)
        filter_row.addWidget(self._show_all_check)
        root.addLayout(filter_row)

        # Button row
        self._buttons = QtGui.QDialogButtonBox(self)
        self._cancel_btn = self._buttons.addButton(QtGui.QDialogButtonBox.Cancel)
        self._create_btn = self._buttons.addButton(
            self.tr("Create"), QtGui.QDialogButtonBox.AcceptRole
        )
        self._create_add_btn = self._buttons.addButton(
            self.tr("Create && Add"), QtGui.QDialogButtonBox.ActionRole
        )
        self._create_btn.setDefault(True)
        self._cancel_btn.clicked.connect(self.reject)
        self._create_btn.clicked.connect(self._on_create)
        self._create_add_btn.clicked.connect(self._on_create_and_add)
        root.addWidget(self._buttons)

    def _populate_categories(self):
        """Fill the category list for the current mode. Preserves selection
        intent (Suggested) on mode change."""
        self._category_list.blockSignals(True)
        self._category_list.clear()
        if self._mode == MODE_DRESSUP:
            cats = [SUGGESTED_CATEGORY, ALL_CATEGORY] + list(DressupRegistry.CATEGORIES)
        else:
            cats = [SUGGESTED_CATEGORY, ALL_CATEGORY] + list(Registry.CATEGORIES)
        for cat in cats:
            self._category_list.addItem(QtGui.QListWidgetItem(cat))
        self._category_list.setCurrentRow(0)
        self._category_list.blockSignals(False)

    # -- Selection observer ------------------------------------------------ #

    def _install_selection_observer(self):
        """Subscribe to FreeCAD's selection observer so the picker re-scores
        when the user changes tree selection while the dialog is open.

        The picker is non-modal, so without this the user can change selection
        and the picker stays stale (e.g. won't switch to dressup mode after
        selecting a freshly-created op)."""

        dialog = self

        class _Observer:
            def addSelection(self, *_args):
                dialog._on_selection_changed()

            def removeSelection(self, *_args):
                dialog._on_selection_changed()

            def setSelection(self, *_args):
                dialog._on_selection_changed()

            def clearSelection(self, *_args):
                dialog._on_selection_changed()

        try:
            self._selection_observer = _Observer()
            FreeCADGui.Selection.addObserver(self._selection_observer)
        except Exception:
            self._selection_observer = None

    def _remove_selection_observer(self):
        if self._selection_observer is None:
            return
        try:
            FreeCADGui.Selection.removeObserver(self._selection_observer)
        except Exception:
            pass
        self._selection_observer = None

    def _on_selection_changed(self):
        # Selection observer callbacks fire synchronously from FreeCAD; defer
        # the refresh to the Qt event loop so any in-flight selection mutation
        # is fully settled before we re-read it.
        QtCore.QTimer.singleShot(0, self._refresh)

    def closeEvent(self, event):
        self._remove_selection_observer()
        super().closeEvent(event)

    # -- Mode detection ---------------------------------------------------- #

    def _detect_mode(self):
        """Return MODE_DRESSUP if exactly one Path op/dressup is selected,
        else MODE_OP. Driven by the live FreeCAD selection."""
        try:
            sel = FreeCADGui.Selection.getSelection()
        except Exception:
            return MODE_OP
        if len(sel) == 1:
            try:
                if PathDressup.isOp(sel[0]):
                    return MODE_DRESSUP
            except Exception:
                pass
        return MODE_OP

    def _selected_path(self):
        """Return the selected operation/dressup object, or None."""
        try:
            return PathDressup.selection()
        except Exception:
            return None

    # -- Context gathering ------------------------------------------------- #

    def _current_job(self):
        try:
            jobs = PathUtils.GetJobs()
        except Exception:
            return None
        if not jobs:
            return None
        if len(jobs) == 1:
            return jobs[0]
        try:
            return PathUtils.UserInput.chooseJob(jobs)
        except Exception:
            return jobs[0]

    def _current_selection(self):
        """Return ((obj, [sub, ...]), ...) matching Registry.FilterContext."""
        try:
            sel_ex = FreeCADGui.Selection.getSelectionEx()
        except Exception:
            return ()
        out = []
        for s in sel_ex:
            subs = list(s.SubElementNames) if getattr(s, "SubElementNames", None) else []
            out.append((s.Object, subs))
        return tuple(out)

    # -- Filtering & rendering --------------------------------------------- #

    def _refresh(self):
        new_mode = self._detect_mode()
        if new_mode != self._mode:
            self._mode = new_mode
            self._populate_categories()
            if new_mode == MODE_DRESSUP:
                self.setWindowTitle(self.tr("Add Dressup"))
            else:
                self.setWindowTitle(self.tr("Create Operation"))

        if self._mode == MODE_DRESSUP:
            ctx = DressupRegistry.FilterContext(path=self._selected_path())
            self._results = DressupRegistry.filter_dressups(DressupRegistry.REGISTRY, ctx)
        else:
            job = self._current_job()
            ctx = Registry.FilterContext(job=job, selection=self._current_selection())
            self._results = Registry.filter_ops(Registry.REGISTRY, ctx)
        self._populate_op_list()

    def _current_category(self):
        item = self._category_list.currentItem()
        return item.text() if item else ALL_CATEGORY

    def _visible_for_category(self, category):
        if category == SUGGESTED_CATEGORY:
            return [r for r in self._results if r.suggested]
        if category == ALL_CATEGORY:
            return list(self._results)
        return [r for r in self._results if r.entry.category == category]

    def _populate_op_list(self):
        needle = self._filter_edit.text().strip().lower() if hasattr(self, "_filter_edit") else ""
        category = self._current_category()
        candidates = self._visible_for_category(category)

        if not self._show_all:
            candidates = [r for r in candidates if r.tier != Registry.TIER_RED]

        if needle:

            def _matches(r):
                hay = " ".join(
                    [
                        r.entry.name.lower(),
                        r.entry.category.lower(),
                        r.entry.command.lower(),
                        (r.reason or "").lower(),
                    ]
                )
                return needle in hay

            candidates = [r for r in candidates if _matches(r)]

        self._visible_results = candidates
        self._op_list.clear()
        for r in candidates:
            item = QtGui.QListWidgetItem(_row_text(r))
            color = _tier_color(r.tier)
            if color is not None:
                item.setForeground(QtGui.QBrush(color))
            if r.tier == Registry.TIER_YELLOW or r.tier == Registry.TIER_RED:
                font = item.font()
                font.setItalic(True)
                item.setFont(font)
            if r.entry.pixmap:
                icon = QtGui.QIcon(":/icons/{}.svg".format(r.entry.pixmap))
                if not icon.isNull():
                    item.setIcon(icon)
            tooltip_bits = [r.entry.description]
            if r.reason:
                tooltip_bits.append(self.tr("Status: {}").format(r.reason))
            item.setToolTip("\n\n".join(tooltip_bits))
            item.setData(QtCore.Qt.UserRole, r)
            self._op_list.addItem(item)

        if self._op_list.count() > 0:
            self._op_list.setCurrentRow(0)
        else:
            self._info.setHtml(
                "<p><i>{}</i></p>".format(self.tr("No operations match the current filters."))
            )

    def _on_category_changed(self, _row):
        self._populate_op_list()

    def _on_show_all_toggled(self, checked):
        self._show_all = bool(checked)
        self._populate_op_list()

    def _on_op_selection_changed(self):
        item = self._op_list.currentItem()
        if item is None:
            self._info.clear()
            return
        result = item.data(QtCore.Qt.UserRole)
        self._render_info(result)

    def _render_info(self, result):
        entry = result.entry
        esc = _html.escape
        parts = []
        parts.append("<h2>{}</h2>".format(esc(entry.name)))
        parts.append("<p><b>{}:</b> {}</p>".format(esc(self.tr("Category")), esc(entry.category)))
        tier_label = _tier_label(result.tier)
        if tier_label:
            parts.append("<p><b>{}:</b> {}</p>".format(esc(self.tr("Status")), esc(tier_label)))
        if result.reason:
            parts.append("<p><i>{}</i></p>".format(esc(result.reason)))
        parts.append("<p>{}</p>".format(esc(entry.description)))
        # tool_shape_hint is op-registry-specific; dressups don't have it.
        tool_shape_hint = getattr(entry, "tool_shape_hint", None)
        if tool_shape_hint:
            parts.append(
                "<p><b>{}:</b> {}</p>".format(
                    esc(self.tr("Tool shape")),
                    esc(", ".join(tool_shape_hint)),
                )
            )
        if result.suggested:
            parts.append("<p><b>{}</b></p>".format(esc(self.tr("Matches the current selection."))))
        self._info.setHtml("".join(parts))

    # -- Actions ----------------------------------------------------------- #

    def _current_entry(self):
        item = self._op_list.currentItem()
        if item is None:
            return None
        result = item.data(QtCore.Qt.UserRole)
        return result.entry if result else None

    def _run_create(self, entry):
        """Dispatch to the existing per-op command."""
        try:
            FreeCADGui.runCommand(entry.command)
        except Exception as exc:
            Path.Log.error("CreateOpDialog: failed to run {}: {}\n".format(entry.command, exc))
            QtGui.QMessageBox.warning(
                self,
                self.tr("Create Operation"),
                self.tr("Could not create {name}: {err}").format(name=entry.name, err=str(exc)),
            )
            return False
        return True

    def _on_create(self):
        entry = self._current_entry()
        if entry is None:
            return
        if self._run_create(entry):
            self.accept()

    def _on_create_and_add(self):
        entry = self._current_entry()
        if entry is None:
            return
        if self._run_create(entry):
            # Selection and job state may have changed; re-score.
            self._refresh()

    def _on_op_double_clicked(self, _item):
        self._on_create()


# --------------------------------------------------------------------------- #
# Command
# --------------------------------------------------------------------------- #


class CommandCreateOperation:
    """Toolbar / menu entry. Opens the picker. Prototype-scope only."""

    # Singleton picker — re-invoking the command (toolbar / Shift+N) raises
    # the existing dialog instead of stacking a second one.
    _dialog = None

    def GetResources(self):
        return {
            "Pixmap": "CAM_CreateOperation",
            "MenuText": QT_TRANSLATE_NOOP("CAM_CreateOperation", "Create Operation…"),
            "Accel": "Shift+N",
            "ToolTip": QT_TRANSLATE_NOOP(
                "CAM_CreateOperation",
                "Open the context-aware operation picker. "
                "Filters operations by the active Job, selection, and tools.",
            ),
        }

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        for o in FreeCAD.ActiveDocument.Objects:
            if o.Name[:3] == "Job":
                return True
        return False

    def Activated(self):
        cls = type(self)
        if cls._dialog is not None:
            try:
                if cls._dialog.isVisible():
                    cls._dialog.raise_()
                    cls._dialog.activateWindow()
                    return
            except RuntimeError:
                pass  # underlying C++ object deleted; fall through to recreate
        dlg = CreateOpDialog()
        dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        cls._dialog = dlg
        dlg.show()


if FreeCAD.GuiUp:
    FreeCADGui.addCommand("CAM_CreateOperation", CommandCreateOperation())

FreeCAD.Console.PrintLog("Loading CreateOpDialog... done\n")
