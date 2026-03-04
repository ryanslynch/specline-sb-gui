from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWizardPage,
)

from spectral_sb_gui.models.observation import (
    ObservationModel,
    ResolutionUnit,
    RestFrequency,
)

# GBT frequency range
GBT_FREQ_MIN_MHZ = 290.0
GBT_FREQ_MAX_MHZ = 116000.0


class _SplatalogueDialog(QDialog):
    """Dialog to select spectral lines from Splatalogue search results."""

    def __init__(self, results_table, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Splatalogue Results")
        self.setMinimumSize(700, 400)
        self.selected_lines = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select one or more spectral lines:"))

        self._table = QTableWidget()
        self._table.setToolTip("Check the lines you want to add, then click OK")
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Species", "Transition", "Frequency (MHz)", ""])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(3, 30)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        self._results = []
        if results_table is not None:
            for row_data in results_table:
                species = str(row_data.get("Species", ""))
                transition = str(row_data.get("Resolved QNs", row_data.get("QNs", "")))
                freq_str = str(row_data.get("Freq-MHz(rest)", row_data.get("Freq", "")))
                try:
                    freq_mhz = float(freq_str)
                except (ValueError, TypeError):
                    continue
                self._results.append(
                    {
                        "species": species,
                        "transition": transition,
                        "freq_mhz": freq_mhz,
                    }
                )

            self._table.setRowCount(len(self._results))
            for i, r in enumerate(self._results):
                self._table.setItem(i, 0, QTableWidgetItem(r["species"]))
                self._table.setItem(i, 1, QTableWidgetItem(r["transition"]))
                self._table.setItem(i, 2, QTableWidgetItem(f"{r['freq_mhz']:.4f}"))
                check_item = QTableWidgetItem()
                check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                check_item.setCheckState(Qt.CheckState.Unchecked)
                self._table.setItem(i, 3, check_item)

        layout.addWidget(self._table)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self):
        self.selected_lines = []
        for i in range(self._table.rowCount()):
            check = self._table.item(i, 3)
            if check and check.checkState() == Qt.CheckState.Checked:
                self.selected_lines.append(self._results[i])
        self.accept()


class FreqPage(QWizardPage):
    COL_FREQ = 0
    COL_SPECIES = 1
    COL_TRANSITION = 2
    COL_RES_VALUE = 3
    COL_RES_UNIT = 4
    NUM_COLS = 5

    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Rest Frequencies")
        self.setSubTitle(
            "Specify the rest frequencies to observe and the desired spectral resolution."
        )

        layout = QVBoxLayout()

        # Source selector + apply-to-all checkbox
        source_row = QHBoxLayout()
        self._apply_all_cb = QCheckBox("Apply to all sources")
        self._apply_all_cb.setChecked(True)
        self._apply_all_cb.setToolTip(
            "When checked, all sources share the same rest frequency setup. "
            "Uncheck to configure each source independently."
        )
        self._apply_all_cb.toggled.connect(self._on_apply_all_toggled)
        source_row.addWidget(self._apply_all_cb)

        source_row.addWidget(QLabel("Source:"))
        self._source_combo = QComboBox()
        self._source_combo.setToolTip("Select a source to configure its rest frequencies")
        self._source_combo.setEnabled(False)
        self._source_combo.currentIndexChanged.connect(self._on_source_changed)
        source_row.addWidget(self._source_combo)
        layout.addLayout(source_row)

        # Frequency table
        self._table = QTableWidget(0, self.NUM_COLS)
        self._table.setHorizontalHeaderLabels(
            [
                "Frequency (MHz)",
                "Species",
                "Transition",
                "Resolution",
                "Unit",
            ]
        )
        self._table.setToolTip("Rest frequencies to observe — one row per spectral line")
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        header = self._table.horizontalHeader()
        for col in range(self.NUM_COLS):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

        # Entry form
        form = QHBoxLayout()
        form.addWidget(QLabel("Freq (MHz):"))
        self._freq_edit = QLineEdit()
        self._freq_edit.setPlaceholderText("e.g. 1420.405")
        self._freq_edit.setToolTip("Rest frequency in MHz")
        form.addWidget(self._freq_edit)

        form.addWidget(QLabel("Species:"))
        self._species_edit = QLineEdit()
        self._species_edit.setPlaceholderText("e.g. HI")
        self._species_edit.setToolTip("Chemical species or molecular formula (optional)")
        form.addWidget(self._species_edit)

        form.addWidget(QLabel("Resolution:"))
        self._res_edit = QLineEdit()
        self._res_edit.setPlaceholderText("e.g. 1.0")
        self._res_edit.setToolTip("Desired spectral resolution")
        form.addWidget(self._res_edit)

        self._res_unit_combo = QComboBox()
        self._res_unit_combo.setToolTip("Resolution unit: kHz or km/s")
        for ru in ResolutionUnit:
            self._res_unit_combo.addItem(ru.value, ru)
        form.addWidget(self._res_unit_combo)
        layout.addLayout(form)

        # Buttons
        btn_row = QHBoxLayout()

        self._add_btn = QPushButton("Add Frequency")
        self._add_btn.setToolTip("Add the specified rest frequency to the table")
        self._add_btn.clicked.connect(self._add_frequency)
        btn_row.addWidget(self._add_btn)

        self._remove_btn = QPushButton("Remove Selected")
        self._remove_btn.setToolTip("Remove the selected frequency from the table")
        self._remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(self._remove_btn)

        self._splatalogue_btn = QPushButton("Search Splatalogue...")
        self._splatalogue_btn.setToolTip(
            "Search the Splatalogue spectral line database for known transitions"
        )
        self._splatalogue_btn.clicked.connect(self._search_splatalogue)
        btn_row.addWidget(self._splatalogue_btn)

        self._import_btn = QPushButton("Import from File...")
        self._import_btn.setToolTip(
            "Import rest frequencies from a text file (one frequency per line)"
        )
        self._import_btn.clicked.connect(self._import_file)
        btn_row.addWidget(self._import_btn)

        layout.addLayout(btn_row)
        self.setLayout(layout)

        # Per-source freq storage: source_name -> list[RestFrequency]
        self._per_source_freqs: dict[str, list[RestFrequency]] = {}
        self._current_source_idx = -1

    # ------------------------------------------------------------------
    # Source switching
    # ------------------------------------------------------------------

    def _on_apply_all_toggled(self, checked):
        self._source_combo.setEnabled(not checked)
        if checked:
            self._save_current_freqs()

    def _on_source_changed(self, idx):
        if idx < 0:
            return
        self._save_current_freqs()
        self._current_source_idx = idx
        self._load_freqs_for_source(idx)

    def _save_current_freqs(self):
        freqs = self._freqs_from_table()
        if self._apply_all_cb.isChecked():
            self.observation.global_rest_freqs = freqs
        else:
            if 0 <= self._current_source_idx < len(self.observation.sources):
                name = self.observation.sources[self._current_source_idx].name
                self._per_source_freqs[name] = freqs

    def _load_freqs_for_source(self, idx):
        if self._apply_all_cb.isChecked():
            freqs = self.observation.global_rest_freqs
        else:
            if 0 <= idx < len(self.observation.sources):
                name = self.observation.sources[idx].name
                freqs = self._per_source_freqs.get(name, [])
            else:
                freqs = []
        self._populate_table(freqs)

    # ------------------------------------------------------------------
    # Table management
    # ------------------------------------------------------------------

    def _populate_table(self, freqs):
        self._table.setRowCount(0)
        for rf in freqs:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, self.COL_FREQ, QTableWidgetItem(f"{rf.freq_mhz:.4f}"))
            self._table.setItem(row, self.COL_SPECIES, QTableWidgetItem(rf.species))
            self._table.setItem(row, self.COL_TRANSITION, QTableWidgetItem(rf.transition))
            self._table.setItem(
                row,
                self.COL_RES_VALUE,
                QTableWidgetItem(f"{rf.resolution_value:.4f}" if rf.resolution_value else ""),
            )
            self._table.setItem(row, self.COL_RES_UNIT, QTableWidgetItem(rf.resolution_unit.value))

    def _freqs_from_table(self):
        freqs = []
        for row in range(self._table.rowCount()):
            freq_text = self._table.item(row, self.COL_FREQ).text()
            species = self._table.item(row, self.COL_SPECIES).text()
            transition = self._table.item(row, self.COL_TRANSITION).text()
            res_text = self._table.item(row, self.COL_RES_VALUE).text()
            unit_text = self._table.item(row, self.COL_RES_UNIT).text()

            try:
                freq_mhz = float(freq_text)
            except ValueError:
                continue

            res_val = 0.0
            if res_text:
                try:
                    res_val = float(res_text)
                except ValueError:
                    pass

            res_unit = ResolutionUnit.KHZ
            for ru in ResolutionUnit:
                if ru.value == unit_text:
                    res_unit = ru
                    break

            freqs.append(
                RestFrequency(
                    freq_mhz=freq_mhz,
                    species=species,
                    transition=transition,
                    resolution_value=res_val,
                    resolution_unit=res_unit,
                )
            )
        return freqs

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add_frequency(self):
        freq_text = self._freq_edit.text().strip()
        if not freq_text:
            QMessageBox.warning(self, "Validation", "Frequency is required.")
            return
        try:
            freq_mhz = float(freq_text)
        except ValueError:
            QMessageBox.warning(self, "Validation", "Frequency must be a number in MHz.")
            return
        if freq_mhz <= 0:
            QMessageBox.warning(self, "Validation", "Frequency must be positive.")
            return
        if freq_mhz < GBT_FREQ_MIN_MHZ or freq_mhz > GBT_FREQ_MAX_MHZ:
            QMessageBox.warning(
                self,
                "Validation",
                f"Frequency must be within the GBT range "
                f"({GBT_FREQ_MIN_MHZ:.0f} - {GBT_FREQ_MAX_MHZ:.0f} MHz).",
            )
            return

        res_text = self._res_edit.text().strip()
        res_val = 0.0
        if res_text:
            try:
                res_val = float(res_text)
            except ValueError:
                QMessageBox.warning(self, "Validation", "Resolution must be a number.")
                return
            if res_val <= 0:
                QMessageBox.warning(self, "Validation", "Resolution must be positive.")
                return

        species = self._species_edit.text().strip()
        res_unit = self._res_unit_combo.currentData()

        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, self.COL_FREQ, QTableWidgetItem(f"{freq_mhz:.4f}"))
        self._table.setItem(row, self.COL_SPECIES, QTableWidgetItem(species))
        self._table.setItem(row, self.COL_TRANSITION, QTableWidgetItem(""))
        self._table.setItem(
            row,
            self.COL_RES_VALUE,
            QTableWidgetItem(f"{res_val:.4f}" if res_val else ""),
        )
        self._table.setItem(row, self.COL_RES_UNIT, QTableWidgetItem(res_unit.value))

        self._freq_edit.clear()
        self._species_edit.clear()
        self._res_edit.clear()
        self.completeChanged.emit()

    def _remove_selected(self):
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)
            self.completeChanged.emit()

    def _search_splatalogue(self):
        freq_text = self._freq_edit.text().strip()
        if not freq_text:
            QMessageBox.warning(
                self,
                "Splatalogue Search",
                "Enter a frequency (MHz) in the frequency field to search around.",
            )
            return

        try:
            center_freq = float(freq_text)
        except ValueError:
            QMessageBox.warning(self, "Splatalogue Search", "Frequency must be a number.")
            return

        # Search +/- 10 MHz around the entered frequency
        lo = center_freq - 10
        hi = center_freq + 10

        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            from astroquery.splatalogue import Splatalogue
            from astropy import units as u

            results = Splatalogue.query_lines(lo * u.MHz, hi * u.MHz)
        except ImportError:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(
                self,
                "Splatalogue Search",
                "astroquery is required for Splatalogue lookups.\n"
                "Install it with: pip install astroquery",
            )
            return
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Splatalogue Search Error", str(e))
            return
        finally:
            QApplication.restoreOverrideCursor()

        if results is None or len(results) == 0:
            QMessageBox.information(
                self, "Splatalogue Search", f"No results found near {center_freq:.2f} MHz."
            )
            return

        # Convert astropy Table rows to dicts
        rows = []
        freq_col = None
        for col_name in results.colnames:
            if "freq" in col_name.lower() and "mhz" in col_name.lower():
                freq_col = col_name
                break
        if freq_col is None:
            freq_col = "Freq"

        for table_row in results:
            row_dict = {}
            for col_name in results.colnames:
                row_dict[col_name] = table_row[col_name]
            if freq_col != "Freq-MHz(rest)":
                row_dict["Freq-MHz(rest)"] = table_row[freq_col]
            rows.append(row_dict)

        dialog = _SplatalogueDialog(rows, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_lines:
            for line in dialog.selected_lines:
                row = self._table.rowCount()
                self._table.insertRow(row)
                self._table.setItem(row, self.COL_FREQ, QTableWidgetItem(f"{line['freq_mhz']:.4f}"))
                self._table.setItem(row, self.COL_SPECIES, QTableWidgetItem(line["species"]))
                self._table.setItem(row, self.COL_TRANSITION, QTableWidgetItem(line["transition"]))
                self._table.setItem(row, self.COL_RES_VALUE, QTableWidgetItem(""))
                self._table.setItem(
                    row, self.COL_RES_UNIT, QTableWidgetItem(ResolutionUnit.KHZ.value)
                )
            self.completeChanged.emit()

    def _import_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Frequencies",
            "",
            "Text Files (*.txt *.csv);;All Files (*)",
        )
        if not file_path:
            return
        count = 0
        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(",") if "," in line else line.split()
                if not parts:
                    continue
                try:
                    freq_mhz = float(parts[0])
                except ValueError:
                    continue
                if freq_mhz <= 0:
                    continue

                species = parts[1].strip() if len(parts) > 1 else ""
                transition = parts[2].strip() if len(parts) > 2 else ""

                row = self._table.rowCount()
                self._table.insertRow(row)
                self._table.setItem(row, self.COL_FREQ, QTableWidgetItem(f"{freq_mhz:.4f}"))
                self._table.setItem(row, self.COL_SPECIES, QTableWidgetItem(species))
                self._table.setItem(row, self.COL_TRANSITION, QTableWidgetItem(transition))
                self._table.setItem(row, self.COL_RES_VALUE, QTableWidgetItem(""))
                self._table.setItem(
                    row, self.COL_RES_UNIT, QTableWidgetItem(ResolutionUnit.KHZ.value)
                )
                count += 1
        if count:
            self.completeChanged.emit()
            QMessageBox.information(self, "Import", f"Imported {count} frequency/frequencies.")
        else:
            QMessageBox.information(self, "Import", "No valid frequencies found in file.")

    # ------------------------------------------------------------------
    # Page lifecycle
    # ------------------------------------------------------------------

    def initializePage(self):
        self._source_combo.blockSignals(True)
        self._source_combo.clear()
        for src in self.observation.sources:
            self._source_combo.addItem(src.name)
        self._source_combo.blockSignals(False)

        self._apply_all_cb.setChecked(self.observation.apply_freqs_to_all)
        self._source_combo.setEnabled(not self.observation.apply_freqs_to_all)

        # Populate per-source storage from model
        self._per_source_freqs.clear()
        for src in self.observation.sources:
            if src.rest_freqs:
                self._per_source_freqs[src.name] = list(src.rest_freqs)

        self._current_source_idx = 0
        if self._apply_all_cb.isChecked():
            self._populate_table(self.observation.global_rest_freqs)
        elif self.observation.sources:
            name = self.observation.sources[0].name
            self._populate_table(self._per_source_freqs.get(name, []))

    def validatePage(self):
        self._save_current_freqs()
        self.observation.apply_freqs_to_all = self._apply_all_cb.isChecked()

        if self._apply_all_cb.isChecked():
            freqs = self._freqs_from_table()
            if not freqs:
                QMessageBox.warning(
                    self, "Validation Error", "At least one rest frequency is required."
                )
                return False
            self.observation.global_rest_freqs = freqs
            for src in self.observation.sources:
                src.rest_freqs = list(freqs)
        else:
            missing = []
            for src in self.observation.sources:
                src_freqs = self._per_source_freqs.get(src.name, [])
                if not src_freqs:
                    missing.append(src.name)
                src.rest_freqs = list(src_freqs)
            if missing:
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    f"The following sources have no rest frequencies:\n{', '.join(missing)}",
                )
                return False

        return True

    def isComplete(self):
        return self._table.rowCount() > 0
