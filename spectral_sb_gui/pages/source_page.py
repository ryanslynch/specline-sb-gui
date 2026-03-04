import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWizardPage,
)

from spectral_sb_gui.models.observation import (
    CoordSystem,
    ObservationModel,
    Source,
    VelocityDefinition,
    VelocityFrame,
)


class _CoordSystemDelegate(QStyledItemDelegate):
    """Combobox editor for the Coord System column."""

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        for cs in CoordSystem:
            combo.addItem(cs.value)
        return combo

    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.DisplayRole)
        idx = editor.findText(value)
        if idx >= 0:
            editor.setCurrentIndex(idx)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class _VelFrameDelegate(QStyledItemDelegate):
    """Combobox editor for the Velocity Frame column."""

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        for vf in VelocityFrame:
            combo.addItem(vf.value)
        return combo

    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.DisplayRole)
        idx = editor.findText(value)
        if idx >= 0:
            editor.setCurrentIndex(idx)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class _VelDefDelegate(QStyledItemDelegate):
    """Combobox editor for the Velocity Definition column."""

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        for vd in VelocityDefinition:
            combo.addItem(vd.value)
        return combo

    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.DisplayRole)
        idx = editor.findText(value)
        if idx >= 0:
            editor.setCurrentIndex(idx)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class _LookupResultsDialog(QDialog):
    """Dialog to display SIMBAD/NED lookup results and let the user pick one."""

    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Source Lookup Results")
        self.setMinimumSize(600, 400)
        self.selected = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select a source from the results below:"))

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Name", "RA", "Dec", "Velocity (km/s)", "Source"])
        self._tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._tree.setToolTip("Double-click a row to select it")

        for r in results:
            item = QTreeWidgetItem(
                [
                    r.get("name", ""),
                    r.get("ra", ""),
                    r.get("dec", ""),
                    str(r.get("velocity", "")),
                    r.get("service", ""),
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, r)
            self._tree.addTopLevelItem(item)

        self._tree.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._tree)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_double_click(self, item, col):
        self.selected = item.data(0, Qt.ItemDataRole.UserRole)
        self.accept()

    def _accept(self):
        current = self._tree.currentItem()
        if current:
            self.selected = current.data(0, Qt.ItemDataRole.UserRole)
        self.accept()


class SourcePage(QWizardPage):
    COL_CHECK = 0
    COL_NAME = 1
    COL_COORDSYS = 2
    COL_COORD1 = 3
    COL_COORD2 = 4
    COL_VELOCITY = 5
    COL_VELFRAME = 6
    COL_VELDEF = 7
    NUM_COLS = 8

    _INVALID_NAME_CHARS = set(" #/\\\0'\"!$&()*;<>?[]`{|}~^")

    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Sources")
        self.setSubTitle("Specify the sources you want to observe.")

        layout = QVBoxLayout()

        # --- Source table ---
        self.table = QTableWidget(0, self.NUM_COLS)
        self.table.setHorizontalHeaderLabels(
            [
                "",
                "Name",
                "Coord System",
                "Coord 1 (RA/l)",
                "Coord 2 (Dec/b)",
                "Velocity (km/s)",
                "Vel Frame",
                "Vel Def",
            ]
        )
        self.table.setToolTip("Sources to observe — double-click cells to edit inline")
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.table.setItemDelegateForColumn(self.COL_COORDSYS, _CoordSystemDelegate(self.table))
        self.table.setItemDelegateForColumn(self.COL_VELFRAME, _VelFrameDelegate(self.table))
        self.table.setItemDelegateForColumn(self.COL_VELDEF, _VelDefDelegate(self.table))

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_CHECK, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(self.COL_CHECK, 30)
        for col in range(self.COL_NAME, self.NUM_COLS):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)

        self._header_checked = False
        header.sectionClicked.connect(self._on_header_clicked)
        self.table.currentCellChanged.connect(lambda row, *_: self._on_row_selected(row))
        self._editing_blocked = False
        self._pre_edit_value = ""
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.cellChanged.connect(self._on_cell_edited)
        layout.addWidget(self.table)

        # --- Entry form ---
        form_layout = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(32)
        self.name_edit.setPlaceholderText("Source name (e.g. NGC253)")
        self.name_edit.setToolTip("Name of the astronomical source")
        row1.addWidget(self.name_edit)

        row1.addWidget(QLabel("Coord System:"))
        self.coord_system_combo = QComboBox()
        self.coord_system_combo.setToolTip("Coordinate system for source position")
        for cs in CoordSystem:
            self.coord_system_combo.addItem(cs.value, cs)
        self.coord_system_combo.currentIndexChanged.connect(self._update_coord_placeholders)
        row1.addWidget(self.coord_system_combo)
        form_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Coord 1:"))
        self.coord1_edit = QLineEdit()
        self.coord1_edit.setToolTip("Right Ascension (HH:MM:SS.SS) or Galactic longitude (degrees)")
        row2.addWidget(self.coord1_edit)
        row2.addWidget(QLabel("Coord 2:"))
        self.coord2_edit = QLineEdit()
        self.coord2_edit.setToolTip("Declination (DD:MM:SS.SS) or Galactic latitude (degrees)")
        row2.addWidget(self.coord2_edit)
        form_layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Velocity (km/s):"))
        self.velocity_edit = QLineEdit()
        self.velocity_edit.setPlaceholderText("0")
        self.velocity_edit.setToolTip("Source radial velocity in km/s")
        row3.addWidget(self.velocity_edit)
        row3.addWidget(QLabel("Frame:"))
        self.vel_frame_combo = QComboBox()
        self.vel_frame_combo.setToolTip("Velocity reference frame")
        for vf in VelocityFrame:
            self.vel_frame_combo.addItem(vf.value, vf)
        row3.addWidget(self.vel_frame_combo)
        row3.addWidget(QLabel("Definition:"))
        self.vel_def_combo = QComboBox()
        self.vel_def_combo.setToolTip("Velocity definition convention")
        for vd in VelocityDefinition:
            self.vel_def_combo.addItem(vd.value, vd)
        row3.addWidget(self.vel_def_combo)
        form_layout.addLayout(row3)

        layout.addLayout(form_layout)
        self._update_coord_placeholders()

        # --- Action buttons ---
        button_row1 = QHBoxLayout()
        self.add_btn = QPushButton("Add Source")
        self.add_btn.setToolTip("Add a new source or update the selected source")
        self.add_btn.clicked.connect(self._add_or_update_source)
        button_row1.addWidget(self.add_btn)

        self.lookup_btn = QPushButton("Lookup (SIMBAD/NED)")
        self.lookup_btn.setToolTip(
            "Search SIMBAD and NED databases by source name to retrieve coordinates and velocity"
        )
        self.lookup_btn.clicked.connect(self._lookup_source)
        button_row1.addWidget(self.lookup_btn)

        self.import_btn = QPushButton("Import Catalog...")
        self.import_btn.setToolTip("Import sources from a GBT/Astrid catalog file")
        self.import_btn.clicked.connect(self._import_catalog)
        button_row1.addWidget(self.import_btn)
        layout.addLayout(button_row1)

        button_row2 = QHBoxLayout()
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.setToolTip("Remove all checked sources from the table")
        self.remove_btn.clicked.connect(self._remove_checked)
        button_row2.addWidget(self.remove_btn)

        self.clear_form_btn = QPushButton("Clear Form")
        self.clear_form_btn.setToolTip("Clear all form fields")
        self.clear_form_btn.clicked.connect(self._clear_form)
        button_row2.addWidget(self.clear_form_btn)
        layout.addLayout(button_row2)

        self.setLayout(layout)

    # ------------------------------------------------------------------
    # Coord placeholders
    # ------------------------------------------------------------------

    def _update_coord_placeholders(self):
        cs = self.coord_system_combo.currentData()
        if cs == CoordSystem.GALACTIC:
            self.coord1_edit.setPlaceholderText("l (degrees)")
            self.coord2_edit.setPlaceholderText("b (degrees)")
        else:
            self.coord1_edit.setPlaceholderText("HH:MM:SS.SS")
            self.coord2_edit.setPlaceholderText("\u00b1DD:MM:SS.SS")

    def _clear_form(self):
        self.name_edit.clear()
        self.coord_system_combo.setCurrentIndex(0)
        self.coord1_edit.clear()
        self.coord2_edit.clear()
        self.velocity_edit.clear()
        self.vel_frame_combo.setCurrentIndex(0)
        self.vel_def_combo.setCurrentIndex(0)
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)

    # ------------------------------------------------------------------
    # Table helpers
    # ------------------------------------------------------------------

    def _on_header_clicked(self, section):
        if section != self.COL_CHECK:
            return
        self._header_checked = not self._header_checked
        for row in range(self.table.rowCount()):
            item = self.table.item(row, self.COL_CHECK)
            if item:
                item.setCheckState(
                    Qt.CheckState.Checked if self._header_checked else Qt.CheckState.Unchecked
                )

    def _checked_rows(self):
        rows = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, self.COL_CHECK)
            if item and item.checkState() == Qt.CheckState.Checked:
                rows.append(row)
        return rows

    def _on_row_selected(self, row):
        if row < 0:
            return
        self.name_edit.setText(self.table.item(row, self.COL_NAME).text())
        cs_text = self.table.item(row, self.COL_COORDSYS).text()
        for i in range(self.coord_system_combo.count()):
            if self.coord_system_combo.itemText(i) == cs_text:
                self.coord_system_combo.setCurrentIndex(i)
                break
        self.coord1_edit.setText(self.table.item(row, self.COL_COORD1).text())
        self.coord2_edit.setText(self.table.item(row, self.COL_COORD2).text())
        self.velocity_edit.setText(self.table.item(row, self.COL_VELOCITY).text())
        vf_text = self.table.item(row, self.COL_VELFRAME).text()
        for i in range(self.vel_frame_combo.count()):
            if self.vel_frame_combo.itemText(i) == vf_text:
                self.vel_frame_combo.setCurrentIndex(i)
                break
        vd_text = self.table.item(row, self.COL_VELDEF).text()
        for i in range(self.vel_def_combo.count()):
            if self.vel_def_combo.itemText(i) == vd_text:
                self.vel_def_combo.setCurrentIndex(i)
                break

    def _on_cell_double_clicked(self, row, col):
        if col == self.COL_CHECK:
            return
        item = self.table.item(row, col)
        self._pre_edit_value = item.text() if item else ""

    def _on_cell_edited(self, row, col):
        if self._editing_blocked or col == self.COL_CHECK:
            return
        item = self.table.item(row, col)
        if item is None:
            return
        new_value = item.text().strip()
        error = self._validate_cell(row, col, new_value)
        if error:
            QMessageBox.warning(self, "Validation Error", error)
            self._editing_blocked = True
            item.setText(self._pre_edit_value)
            self._editing_blocked = False
        self.completeChanged.emit()

    def _set_table_row(self, row, name, cs_text, coord1, coord2, vel, vf, vd):
        self._editing_blocked = True
        check_item = self.table.item(row, self.COL_CHECK)
        if check_item is None:
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, self.COL_CHECK, check_item)
        self.table.setItem(row, self.COL_NAME, QTableWidgetItem(name))
        self.table.setItem(row, self.COL_COORDSYS, QTableWidgetItem(cs_text))
        self.table.setItem(row, self.COL_COORD1, QTableWidgetItem(coord1))
        self.table.setItem(row, self.COL_COORD2, QTableWidgetItem(coord2))
        self.table.setItem(row, self.COL_VELOCITY, QTableWidgetItem(vel))
        self.table.setItem(row, self.COL_VELFRAME, QTableWidgetItem(vf))
        self.table.setItem(row, self.COL_VELDEF, QTableWidgetItem(vd))
        self._editing_blocked = False

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_sexagesimal(text):
        parts = text.lstrip("+-").split(":")
        if len(parts) < 2 or len(parts) > 3:
            return None
        try:
            vals = [float(p) for p in parts]
        except ValueError:
            return None
        if vals[0] != int(vals[0]) or vals[0] < 0:
            return None
        if vals[1] != int(vals[1]) or not (0 <= vals[1] < 60):
            return None
        if len(vals) == 3 and not (0 <= vals[2] < 60):
            return None
        total = vals[0] + vals[1] / 60.0
        if len(vals) == 3:
            total += vals[2] / 3600.0
        if text.startswith("-"):
            total = -total
        return total

    def _get_coord_system_for_row(self, row):
        cs_text = self.table.item(row, self.COL_COORDSYS).text()
        for member in CoordSystem:
            if member.value == cs_text:
                return member
        return CoordSystem.J2000

    def _validate_cell(self, row, col, value):
        if col == self.COL_NAME:
            if not value:
                return "Source name is required."
            if len(value) > 32:
                return "Source name must be 32 characters or fewer."
            bad_chars = self._INVALID_NAME_CHARS.intersection(value)
            if bad_chars:
                return f"Source name contains invalid characters: {' '.join(sorted(bad_chars))}"

        elif col == self.COL_COORDSYS:
            valid = [cs.value for cs in CoordSystem]
            if value not in valid:
                return f"Coordinate system must be one of: {', '.join(valid)}"

        elif col == self.COL_COORD1:
            if not value:
                return "Coordinate 1 is required."
            cs = self._get_coord_system_for_row(row)
            if cs == CoordSystem.GALACTIC:
                try:
                    l_val = float(value)
                except ValueError:
                    return "Galactic longitude (l) must be a number in degrees."
                if not (0 <= l_val <= 360):
                    return "Galactic longitude (l) must be between 0 and 360 degrees."
            else:
                # Accept sexagesimal or decimal hours for RA
                if re.match(r"^\d{1,2}(\.\d+)?$", value):
                    try:
                        hours = float(value)
                        if not (0 <= hours < 24):
                            return "RA in decimal hours must be between 0 and 24."
                    except ValueError:
                        return "Invalid RA format."
                elif not re.match(r"^\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?$", value):
                    return (
                        "RA must be in HH:MM:SS.SS format (e.g. 00:47:33.12) "
                        "or decimal hours (e.g. 0.7925)."
                    )
                else:
                    ra_hours = self._parse_sexagesimal(value)
                    if ra_hours is None or not (0 <= ra_hours < 24):
                        return "RA must be between 00:00:00 and 23:59:59.99."

        elif col == self.COL_COORD2:
            if not value:
                return "Coordinate 2 is required."
            cs = self._get_coord_system_for_row(row)
            if cs == CoordSystem.GALACTIC:
                try:
                    b_val = float(value)
                except ValueError:
                    return "Galactic latitude (b) must be a number in degrees."
                if not (-90 <= b_val <= 90):
                    return "Galactic latitude (b) must be between -90 and +90 degrees."
            else:
                if re.match(r"^[+-]?\d{1,3}(\.\d+)?$", value):
                    try:
                        deg = float(value)
                        if not (-90 <= deg <= 90):
                            return "Dec in decimal degrees must be between -90 and +90."
                    except ValueError:
                        return "Invalid Dec format."
                elif not re.match(r"^[+-]?\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?$", value):
                    return "Dec must be in \u00b1DD:MM:SS.SS format (e.g. -25:17:17.7) or decimal degrees."
                else:
                    dec_deg = self._parse_sexagesimal(value)
                    if dec_deg is None or not (-90 <= dec_deg <= 90):
                        return "Dec must be between -90:00:00 and +90:00:00."

        elif col == self.COL_VELOCITY:
            if value:
                try:
                    float(value)
                except ValueError:
                    return "Velocity must be a number in km/s."

        return None

    def _validate_form(self):
        name = self.name_edit.text().strip()
        if not name:
            return "Source name is required."
        if len(name) > 32:
            return "Source name must be 32 characters or fewer."
        bad_chars = self._INVALID_NAME_CHARS.intersection(name)
        if bad_chars:
            return f"Source name contains invalid characters: {' '.join(sorted(bad_chars))}"

        coord1 = self.coord1_edit.text().strip()
        coord2 = self.coord2_edit.text().strip()
        if not coord1:
            return "Coordinate 1 is required."
        if not coord2:
            return "Coordinate 2 is required."

        cs = self.coord_system_combo.currentData()
        if cs == CoordSystem.GALACTIC:
            try:
                l_val = float(coord1)
            except ValueError:
                return "Galactic longitude (l) must be a number in degrees."
            if not (0 <= l_val <= 360):
                return "Galactic longitude (l) must be between 0 and 360 degrees."
            try:
                b_val = float(coord2)
            except ValueError:
                return "Galactic latitude (b) must be a number in degrees."
            if not (-90 <= b_val <= 90):
                return "Galactic latitude (b) must be between -90 and +90 degrees."
        else:
            # Allow sexagesimal or decimal hours for RA
            if re.match(r"^\d{1,2}(\.\d+)?$", coord1):
                try:
                    hours = float(coord1)
                    if not (0 <= hours < 24):
                        return "RA in decimal hours must be between 0 and 24."
                except ValueError:
                    return "Invalid RA format."
            elif not re.match(r"^\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?$", coord1):
                return "RA must be in HH:MM:SS.SS format or decimal hours."
            else:
                ra_hours = self._parse_sexagesimal(coord1)
                if ra_hours is None or not (0 <= ra_hours < 24):
                    return "RA must be between 00:00:00 and 23:59:59.99."

            if re.match(r"^[+-]?\d{1,3}(\.\d+)?$", coord2):
                try:
                    deg = float(coord2)
                    if not (-90 <= deg <= 90):
                        return "Dec in decimal degrees must be between -90 and +90."
                except ValueError:
                    return "Invalid Dec format."
            elif not re.match(r"^[+-]?\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?$", coord2):
                return "Dec must be in \u00b1DD:MM:SS.SS format or decimal degrees."
            else:
                dec_deg = self._parse_sexagesimal(coord2)
                if dec_deg is None or not (-90 <= dec_deg <= 90):
                    return "Dec must be between -90:00:00 and +90:00:00."

        vel_text = self.velocity_edit.text().strip()
        if vel_text:
            try:
                float(vel_text)
            except ValueError:
                return "Velocity must be a number in km/s."

        return None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add_or_update_source(self):
        error = self._validate_form()
        if error:
            QMessageBox.warning(self, "Validation Error", error)
            return

        name = self.name_edit.text().strip()
        cs = self.coord_system_combo.currentData()
        coord1 = self.coord1_edit.text().strip()
        coord2 = self.coord2_edit.text().strip()
        vel = self.velocity_edit.text().strip() or "0"
        vf = self.vel_frame_combo.currentData().value
        vd = self.vel_def_combo.currentData().value

        selected_row = self.table.currentRow()
        if selected_row >= 0:
            self._set_table_row(selected_row, name, cs.value, coord1, coord2, vel, vf, vd)
        else:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._set_table_row(row, name, cs.value, coord1, coord2, vel, vf, vd)

        self._clear_form()
        self.completeChanged.emit()

    def _remove_checked(self):
        checked = self._checked_rows()
        if not checked:
            QMessageBox.information(self, "Remove Selected", "No sources are checked.")
            return
        reply = QMessageBox.question(
            self,
            "Remove Selected",
            f"Remove {len(checked)} checked source(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for row in reversed(checked):
            self.table.removeRow(row)
        self._clear_form()
        self.completeChanged.emit()

    # ------------------------------------------------------------------
    # SIMBAD / NED lookup
    # ------------------------------------------------------------------

    def _lookup_source(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Lookup", "Enter a source name first.")
            return

        results = []
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            results.extend(self._query_simbad(name))
            results.extend(self._query_ned(name))
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Lookup Error", f"Error during lookup:\n{e}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        if not results:
            QMessageBox.information(
                self, "Lookup", f"No results found for '{name}' in SIMBAD or NED."
            )
            return

        if len(results) == 1:
            self._apply_lookup_result(results[0])
        else:
            dialog = _LookupResultsDialog(results, self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected:
                self._apply_lookup_result(dialog.selected)

    def _query_simbad(self, name):
        results = []
        try:
            from astroquery.simbad import Simbad

            simbad = Simbad()
            simbad.add_votable_fields("velocity")
            table = simbad.query_object(name)
            if table is not None and len(table) > 0:
                for row in table:
                    ra = str(row["RA"]) if "RA" in row.colnames else ""
                    dec = str(row["DEC"]) if "DEC" in row.colnames else ""
                    vel = ""
                    if "RVZ_RADVEL" in row.colnames:
                        v = row["RVZ_RADVEL"]
                        if v is not None and str(v) != "--":
                            vel = str(float(v))
                    main_id = str(row["MAIN_ID"]) if "MAIN_ID" in row.colnames else name
                    results.append(
                        {
                            "name": main_id,
                            "ra": ra,
                            "dec": dec,
                            "velocity": vel,
                            "service": "SIMBAD",
                        }
                    )
        except Exception:
            pass
        return results

    @staticmethod
    def _deg_to_sexagesimal_hours(deg):
        """Convert RA from decimal degrees to sexagesimal hours (HH:MM:SS.SS)."""
        hours_total = deg / 15.0
        h = int(hours_total)
        remainder = (hours_total - h) * 60.0
        m = int(remainder)
        s = (remainder - m) * 60.0
        return f"{h:02d}:{m:02d}:{s:05.2f}"

    @staticmethod
    def _deg_to_sexagesimal_dec(deg):
        """Convert Dec from decimal degrees to sexagesimal (DD:MM:SS.SS)."""
        sign = "+" if deg >= 0 else "-"
        deg = abs(deg)
        d = int(deg)
        remainder = (deg - d) * 60.0
        m = int(remainder)
        s = (remainder - m) * 60.0
        return f"{sign}{d:02d}:{m:02d}:{s:05.2f}"

    def _query_ned(self, name):
        results = []
        try:
            from astroquery.ipac.ned import Ned

            table = Ned.query_object(name)
            if table is not None and len(table) > 0:
                for row in table:
                    # NED returns RA/Dec in decimal degrees — convert to sexagesimal
                    ra = ""
                    dec = ""
                    if "RA" in row.colnames:
                        try:
                            ra_deg = float(row["RA"])
                            ra = self._deg_to_sexagesimal_hours(ra_deg)
                        except (ValueError, TypeError):
                            ra = str(row["RA"])
                    if "DEC" in row.colnames:
                        try:
                            dec_deg = float(row["DEC"])
                            dec = self._deg_to_sexagesimal_dec(dec_deg)
                        except (ValueError, TypeError):
                            dec = str(row["DEC"])
                    vel = ""
                    if "Velocity" in row.colnames:
                        v = row["Velocity"]
                        if v is not None and str(v) != "--":
                            vel = str(float(v))
                    obj_name = str(row["Object Name"]) if "Object Name" in row.colnames else name
                    results.append(
                        {
                            "name": obj_name,
                            "ra": ra,
                            "dec": dec,
                            "velocity": vel,
                            "service": "NED",
                        }
                    )
        except Exception:
            pass
        return results

    def _apply_lookup_result(self, result):
        ra = result.get("ra", "")
        dec = result.get("dec", "")
        vel = result.get("velocity", "")

        # SIMBAD returns RA as "HH MM SS.SS", convert to colon-separated
        if ra and " " in ra:
            ra = ra.replace(" ", ":")
        if dec and " " in dec:
            dec = dec.replace(" ", ":")

        self.coord_system_combo.setCurrentIndex(0)  # J2000
        self.coord1_edit.setText(ra)
        self.coord2_edit.setText(dec)
        if vel:
            self.velocity_edit.setText(vel)

    # ------------------------------------------------------------------
    # Catalog import
    # ------------------------------------------------------------------

    def _import_catalog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Catalog File",
            "",
            "Catalog Files (*.cat *.txt);;All Files (*)",
        )
        if not file_path:
            return
        try:
            sources = self._parse_catalog(file_path)
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to parse catalog:\n{e}")
            return
        if not sources:
            QMessageBox.information(self, "Import", "No sources found in catalog file.")
            return
        for src in sources:
            row = self.table.rowCount()
            self.table.insertRow(row)
            vel = str(src.velocity_kms) if src.velocity_kms != 0 else "0"
            self._set_table_row(
                row,
                src.name,
                src.coord_system.value,
                src.coord1,
                src.coord2,
                vel,
                src.velocity_frame.value,
                src.velocity_definition.value,
            )
        self.completeChanged.emit()
        QMessageBox.information(self, "Import Complete", f"Imported {len(sources)} source(s).")

    def _parse_catalog(self, file_path):
        sources = []
        coord_system = CoordSystem.J2000
        in_data = False
        col_names = []

        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line and not in_data:
                    key, _, value = line.partition("=")
                    key = key.strip().lower()
                    value = value.strip()
                    if key == "coordmode":
                        value_upper = value.upper()
                        if value_upper == "GALACTIC":
                            coord_system = CoordSystem.GALACTIC
                        elif value_upper == "B1950":
                            coord_system = CoordSystem.B1950
                        else:
                            coord_system = CoordSystem.J2000
                    if key == "head":
                        col_names = [c.upper() for c in value.split()]
                        in_data = True
                    continue
                if in_data:
                    parts = line.split()
                    if len(parts) < len(col_names):
                        continue
                    name_idx = self._find_col(col_names, ("NAME",))
                    glon_idx = self._find_col(col_names, ("GLON",))
                    glat_idx = self._find_col(col_names, ("GLAT",))
                    ra_idx = self._find_col(col_names, ("RA",))
                    dec_idx = self._find_col(col_names, ("DEC",))
                    vel_idx = self._find_col(col_names, ("VELOCITY", "VEL", "VELO"))

                    if glon_idx is not None and glat_idx is not None:
                        c1_idx, c2_idx = glon_idx, glat_idx
                        coord_system = CoordSystem.GALACTIC
                    elif ra_idx is not None and dec_idx is not None:
                        c1_idx, c2_idx = ra_idx, dec_idx
                    else:
                        raise ValueError(
                            "Catalog HEAD line must contain coordinate columns (RA/DEC or GLON/GLAT)."
                        )
                    if name_idx is None:
                        raise ValueError("Catalog HEAD line must contain a NAME column.")

                    vel_kms = 0.0
                    if vel_idx is not None and vel_idx < len(parts):
                        try:
                            vel_kms = float(parts[vel_idx])
                        except ValueError:
                            pass

                    sources.append(
                        Source(
                            name=parts[name_idx],
                            coord_system=coord_system,
                            coord1=parts[c1_idx],
                            coord2=parts[c2_idx],
                            velocity_kms=vel_kms,
                        )
                    )
        return sources

    @staticmethod
    def _find_col(col_names, candidates):
        for name in candidates:
            try:
                return col_names.index(name)
            except ValueError:
                continue
        return None

    # ------------------------------------------------------------------
    # Page lifecycle
    # ------------------------------------------------------------------

    def _sources_from_table(self):
        sources = []
        for row in range(self.table.rowCount()):
            name = self.table.item(row, self.COL_NAME).text()
            cs_text = self.table.item(row, self.COL_COORDSYS).text()
            coord1 = self.table.item(row, self.COL_COORD1).text()
            coord2 = self.table.item(row, self.COL_COORD2).text()
            vel_text = self.table.item(row, self.COL_VELOCITY).text()
            vf_text = self.table.item(row, self.COL_VELFRAME).text()
            vd_text = self.table.item(row, self.COL_VELDEF).text()

            cs = CoordSystem.J2000
            for member in CoordSystem:
                if member.value == cs_text:
                    cs = member
                    break
            vel = 0.0
            if vel_text:
                try:
                    vel = float(vel_text)
                except ValueError:
                    pass
            vf = VelocityFrame.TOPOCENTRIC
            for member in VelocityFrame:
                if member.value == vf_text:
                    vf = member
                    break
            vd = VelocityDefinition.RADIO
            for member in VelocityDefinition:
                if member.value == vd_text:
                    vd = member
                    break

            sources.append(
                Source(
                    name=name,
                    coord_system=cs,
                    coord1=coord1,
                    coord2=coord2,
                    velocity_kms=vel,
                    velocity_frame=vf,
                    velocity_definition=vd,
                )
            )
        return sources

    def initializePage(self):
        self.table.setRowCount(0)
        for src in self.observation.sources:
            row = self.table.rowCount()
            self.table.insertRow(row)
            vel = str(src.velocity_kms) if src.velocity_kms != 0 else "0"
            self._set_table_row(
                row,
                src.name,
                src.coord_system.value,
                src.coord1,
                src.coord2,
                vel,
                src.velocity_frame.value,
                src.velocity_definition.value,
            )
        self._clear_form()

    def validatePage(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Validation Error", "At least one source is required.")
            return False

        # Check for duplicate names
        names = set()
        for row in range(self.table.rowCount()):
            name = self.table.item(row, self.COL_NAME).text().strip()
            if name in names:
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    f"Duplicate source name: '{name}'. All source names must be unique.",
                )
                return False
            names.add(name)

        self.observation.sources = self._sources_from_table()
        return True

    def isComplete(self):
        return self.table.rowCount() > 0
