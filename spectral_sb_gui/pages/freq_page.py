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
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
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
                species = str(row_data.get("Species", "") or row_data.get("Chemical Name", ""))
                transition = str(row_data.get("Resolved QNs", row_data.get("QNs", "")))
                # Try known MHz key first, then search for any freq key
                freq_mhz = None
                if "Freq-MHz(rest)" in row_data:
                    try:
                        freq_mhz = float(row_data["Freq-MHz(rest)"])
                    except (ValueError, TypeError):
                        pass
                if freq_mhz is None:
                    for k, v in row_data.items():
                        kl = k.lower()
                        if "freq" not in kl:
                            continue
                        try:
                            val = float(v)
                        except (ValueError, TypeError):
                            continue
                        if "ghz" in kl:
                            freq_mhz = val * 1000.0
                        else:
                            freq_mhz = val
                        break
                if freq_mhz is None:
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
    COL_CHECK = 0
    COL_FREQ = 1
    COL_SPECIES = 2
    COL_TRANSITION = 3
    COL_WIDTH = 4
    COL_RES_VALUE = 5
    COL_RES_UNIT = 6
    NUM_COLS = 7

    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Rest Frequencies")
        self.setSubTitle(
            "Specify the rest frequencies to observe and the desired spectral resolution."
        )

        main_layout = QVBoxLayout()
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- Left panel: source list ----
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Sources"))

        self._source_list = QListWidget()
        self._source_list.setToolTip(
            "Select a source to configure its rest frequencies.\n"
            "Check 'Apply to all sources' to share one setup."
        )
        self._source_list.currentRowChanged.connect(self._on_source_changed)
        left_layout.addWidget(self._source_list)

        self._apply_all_cb = QCheckBox("Apply to all sources")
        self._apply_all_cb.setChecked(True)
        self._apply_all_cb.setToolTip(
            "When checked, all sources share the same rest frequency setup. "
            "Uncheck to configure each source independently."
        )
        self._apply_all_cb.toggled.connect(self._on_apply_all_toggled)
        left_layout.addWidget(self._apply_all_cb)

        splitter.addWidget(left_widget)

        # ---- Right panel: freq table + form + buttons ----
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Frequency table
        self._table = QTableWidget(0, self.NUM_COLS)
        self._table.setHorizontalHeaderLabels(
            [
                "",
                "Frequency (MHz)",
                "Species",
                "Transition",
                "Line Width (km/s)",
                "Resolution",
                "Unit",
            ]
        )
        self._table.setToolTip("Rest frequencies to observe — one row per spectral line")
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(self.COL_CHECK, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_CHECK, 30)
        for col in range(self.COL_FREQ, self.NUM_COLS):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        self._header_checked = False
        header.sectionClicked.connect(self._on_header_clicked)
        right_layout.addWidget(self._table)

        # Entry form row 1: freq, species, transition
        form1 = QHBoxLayout()
        form1.addWidget(QLabel("Freq (MHz):"))
        self._freq_edit = QLineEdit()
        self._freq_edit.setPlaceholderText("e.g. 1420.405")
        self._freq_edit.setToolTip("Rest frequency in MHz")
        form1.addWidget(self._freq_edit)

        form1.addWidget(QLabel("Species:"))
        self._species_edit = QLineEdit()
        self._species_edit.setPlaceholderText("e.g. HI")
        self._species_edit.setToolTip("Chemical species or molecular formula (optional)")
        form1.addWidget(self._species_edit)

        form1.addWidget(QLabel("Transition:"))
        self._transition_edit = QLineEdit()
        self._transition_edit.setPlaceholderText("e.g. 1-0")
        self._transition_edit.setToolTip("Transition label (optional)")
        form1.addWidget(self._transition_edit)
        right_layout.addLayout(form1)

        # Entry form row 2: line width, resolution
        form2 = QHBoxLayout()
        form2.addWidget(QLabel("Line Width (km/s):"))
        self._width_edit = QLineEdit()
        self._width_edit.setPlaceholderText("optional")
        self._width_edit.setToolTip(
            "Expected line width in km/s (optional). "
            "Used to auto-select frequency vs. position switching."
        )
        form2.addWidget(self._width_edit)

        form2.addWidget(QLabel("Resolution:"))
        self._res_edit = QLineEdit()
        self._res_edit.setPlaceholderText("e.g. 1.0")
        self._res_edit.setToolTip("Desired spectral resolution")
        form2.addWidget(self._res_edit)

        self._res_unit_combo = QComboBox()
        self._res_unit_combo.setToolTip("Resolution unit: kHz or km/s")
        for ru in ResolutionUnit:
            self._res_unit_combo.addItem(ru.value, ru)
        form2.addWidget(self._res_unit_combo)
        right_layout.addLayout(form2)

        # Buttons
        btn_row = QHBoxLayout()

        self._add_btn = QPushButton("Add Frequency")
        self._add_btn.setToolTip("Add the specified rest frequency to the table")
        self._add_btn.clicked.connect(self._add_frequency)
        btn_row.addWidget(self._add_btn)

        self._remove_btn = QPushButton("Remove Checked")
        self._remove_btn.setToolTip("Remove all checked frequencies from the table")
        self._remove_btn.clicked.connect(self._remove_checked)
        btn_row.addWidget(self._remove_btn)

        self._apply_btn = QPushButton("Apply to Selected")
        self._apply_btn.setToolTip(
            "Apply non-empty form fields to all checked frequencies in the table "
            "(Species, Transition, Line Width, Resolution — not Frequency)"
        )
        self._apply_btn.clicked.connect(self._apply_to_checked)
        btn_row.addWidget(self._apply_btn)

        self._splatalogue_btn = QPushButton("Search Splatalogue...")
        self._splatalogue_btn.setToolTip(
            "Search Splatalogue by species name. Enter a species name above first."
        )
        self._splatalogue_btn.clicked.connect(self._search_splatalogue)
        btn_row.addWidget(self._splatalogue_btn)

        self._import_btn = QPushButton("Import from File...")
        self._import_btn.setToolTip(
            "Import rest frequencies from a text file (one frequency per line)"
        )
        self._import_btn.clicked.connect(self._import_file)
        btn_row.addWidget(self._import_btn)

        right_layout.addLayout(btn_row)
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

        # Per-source freq storage: source_name -> list[RestFrequency]
        self._per_source_freqs: dict[str, list[RestFrequency]] = {}
        self._current_source_idx = -1

    # ------------------------------------------------------------------
    # Unit combo helper
    # ------------------------------------------------------------------

    def _make_unit_combo(self, value: ResolutionUnit) -> QComboBox:
        combo = QComboBox()
        for ru in ResolutionUnit:
            combo.addItem(ru.value, ru)
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                break
        combo.currentIndexChanged.connect(self.completeChanged)
        return combo

    # ------------------------------------------------------------------
    # Checkbox helpers
    # ------------------------------------------------------------------

    def _on_header_clicked(self, section):
        if section != self.COL_CHECK:
            return
        self._header_checked = not self._header_checked
        for row in range(self._table.rowCount()):
            item = self._table.item(row, self.COL_CHECK)
            if item:
                item.setCheckState(
                    Qt.CheckState.Checked if self._header_checked else Qt.CheckState.Unchecked
                )

    def _checked_rows(self):
        rows = []
        for row in range(self._table.rowCount()):
            item = self._table.item(row, self.COL_CHECK)
            if item and item.checkState() == Qt.CheckState.Checked:
                rows.append(row)
        return rows

    def _add_check_item(self, row):
        check_item = QTableWidgetItem()
        check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        check_item.setCheckState(Qt.CheckState.Unchecked)
        self._table.setItem(row, self.COL_CHECK, check_item)

    # ------------------------------------------------------------------
    # Source switching
    # ------------------------------------------------------------------

    def _on_apply_all_toggled(self, checked):
        self._source_list.setEnabled(not checked)
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
            self._add_check_item(row)
            self._table.setItem(row, self.COL_FREQ, QTableWidgetItem(f"{rf.freq_mhz:.4f}"))
            self._table.setItem(row, self.COL_SPECIES, QTableWidgetItem(rf.species))
            self._table.setItem(row, self.COL_TRANSITION, QTableWidgetItem(rf.transition))
            width_text = f"{rf.line_width_kms:.3f}" if rf.line_width_kms is not None else ""
            self._table.setItem(row, self.COL_WIDTH, QTableWidgetItem(width_text))
            self._table.setItem(
                row,
                self.COL_RES_VALUE,
                QTableWidgetItem(f"{rf.resolution_value:.4f}" if rf.resolution_value else ""),
            )
            self._table.setCellWidget(
                row, self.COL_RES_UNIT, self._make_unit_combo(rf.resolution_unit)
            )

    def _freqs_from_table(self):
        freqs = []
        for row in range(self._table.rowCount()):
            freq_text = self._table.item(row, self.COL_FREQ).text()
            species = self._table.item(row, self.COL_SPECIES).text()
            transition = self._table.item(row, self.COL_TRANSITION).text()
            width_text = self._table.item(row, self.COL_WIDTH).text()
            res_text = self._table.item(row, self.COL_RES_VALUE).text()
            unit_widget = self._table.cellWidget(row, self.COL_RES_UNIT)

            try:
                freq_mhz = float(freq_text)
            except ValueError:
                continue

            line_width = None
            if width_text:
                try:
                    line_width = float(width_text)
                except ValueError:
                    pass

            res_val = 0.0
            if res_text:
                try:
                    res_val = float(res_text)
                except ValueError:
                    pass

            res_unit = unit_widget.currentData() if unit_widget is not None else ResolutionUnit.KHZ

            freqs.append(
                RestFrequency(
                    freq_mhz=freq_mhz,
                    species=species,
                    transition=transition,
                    line_width_kms=line_width,
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

        width_text = self._width_edit.text().strip()
        line_width = None
        if width_text:
            try:
                line_width = float(width_text)
                if line_width <= 0:
                    QMessageBox.warning(self, "Validation", "Line width must be positive.")
                    return
            except ValueError:
                QMessageBox.warning(self, "Validation", "Line width must be a number in km/s.")
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
        transition = self._transition_edit.text().strip()
        res_unit = self._res_unit_combo.currentData()

        row = self._table.rowCount()
        self._table.insertRow(row)
        self._add_check_item(row)
        self._table.setItem(row, self.COL_FREQ, QTableWidgetItem(f"{freq_mhz:.4f}"))
        self._table.setItem(row, self.COL_SPECIES, QTableWidgetItem(species))
        self._table.setItem(row, self.COL_TRANSITION, QTableWidgetItem(transition))
        width_item_text = f"{line_width:.3f}" if line_width is not None else ""
        self._table.setItem(row, self.COL_WIDTH, QTableWidgetItem(width_item_text))
        self._table.setItem(
            row,
            self.COL_RES_VALUE,
            QTableWidgetItem(f"{res_val:.4f}" if res_val else ""),
        )
        self._table.setCellWidget(row, self.COL_RES_UNIT, self._make_unit_combo(res_unit))

        self._freq_edit.clear()
        self._species_edit.clear()
        self._transition_edit.clear()
        self._width_edit.clear()
        self._res_edit.clear()
        self.completeChanged.emit()

    def _remove_checked(self):
        checked = self._checked_rows()
        if not checked:
            QMessageBox.information(self, "Remove Checked", "No frequencies are checked.")
            return
        for row in reversed(checked):
            self._table.removeRow(row)
        self.completeChanged.emit()

    def _apply_to_checked(self):
        checked = self._checked_rows()
        if not checked:
            QMessageBox.information(self, "Apply to Selected", "No frequencies are checked.")
            return

        species = self._species_edit.text().strip()
        transition = self._transition_edit.text().strip()
        width_text = self._width_edit.text().strip()
        res_text = self._res_edit.text().strip()
        res_unit = self._res_unit_combo.currentData()

        apply_species = bool(species)
        apply_transition = bool(transition)
        apply_width = bool(width_text)
        apply_res = bool(res_text)

        if not any([apply_species, apply_transition, apply_width, apply_res]):
            QMessageBox.information(
                self,
                "Apply to Selected",
                "No fields to apply. Fill in at least one of: Species, Transition, "
                "Line Width, or Resolution.",
            )
            return

        if apply_width:
            try:
                w = float(width_text)
                if w <= 0:
                    QMessageBox.warning(self, "Validation Error", "Line width must be positive.")
                    return
            except ValueError:
                QMessageBox.warning(
                    self, "Validation Error", "Line width must be a number in km/s."
                )
                return

        if apply_res:
            try:
                r = float(res_text)
                if r <= 0:
                    QMessageBox.warning(self, "Validation Error", "Resolution must be positive.")
                    return
            except ValueError:
                QMessageBox.warning(self, "Validation Error", "Resolution must be a number.")
                return

        for row in checked:
            if apply_species:
                self._table.item(row, self.COL_SPECIES).setText(species)
            if apply_transition:
                self._table.item(row, self.COL_TRANSITION).setText(transition)
            if apply_width:
                self._table.item(row, self.COL_WIDTH).setText(f"{float(width_text):.3f}")
            if apply_res:
                self._table.item(row, self.COL_RES_VALUE).setText(f"{float(res_text):.4f}")
                unit_widget = self._table.cellWidget(row, self.COL_RES_UNIT)
                if unit_widget is not None:
                    for i in range(unit_widget.count()):
                        if unit_widget.itemData(i) == res_unit:
                            unit_widget.setCurrentIndex(i)
                            break
        self.completeChanged.emit()

    def _search_splatalogue(self):
        species = self._species_edit.text().strip()
        if not species:
            QMessageBox.warning(
                self,
                "Splatalogue Search",
                "Enter a species name in the 'Species' field to search Splatalogue.",
            )
            return

        # Optional: narrow by frequency if entered
        freq_text = self._freq_edit.text().strip()
        if freq_text:
            try:
                center_freq = float(freq_text)
                lo = max(GBT_FREQ_MIN_MHZ, center_freq - 10)
                hi = min(GBT_FREQ_MAX_MHZ, center_freq + 10)
            except ValueError:
                QMessageBox.warning(self, "Splatalogue Search", "Frequency must be a number.")
                return
        else:
            lo = GBT_FREQ_MIN_MHZ
            hi = GBT_FREQ_MAX_MHZ

        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            from astroquery.splatalogue import Splatalogue
            from astropy import units as u

            results = Splatalogue.query_lines(lo * u.MHz, hi * u.MHz, chemical_name=species)
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
                self,
                "Splatalogue Search",
                f"No results found for species '{species}' in Splatalogue.",
            )
            return

        # Find the rest-frequency column; prefer MHz, fall back to GHz
        import sys

        print(f"[Splatalogue] columns: {results.colnames}", file=sys.stderr)
        freq_col = None
        freq_col_is_ghz = False
        for col_name in results.colnames:
            cl = col_name.lower()
            if "freq" in cl and "mhz" in cl:
                freq_col = col_name
                break
        if freq_col is None:
            for col_name in results.colnames:
                cl = col_name.lower()
                if "freq" in cl and "ghz" in cl:
                    freq_col = col_name
                    freq_col_is_ghz = True
                    break
        if freq_col is None:
            for col_name in results.colnames:
                if "freq" in col_name.lower():
                    freq_col = col_name
                    break

        rows = []
        for table_row in results:
            row_dict = {}
            for col_name in results.colnames:
                try:
                    row_dict[col_name] = table_row[col_name]
                except Exception:
                    pass
            # Normalise to "Freq-MHz(rest)" key
            if "Freq-MHz(rest)" not in row_dict and freq_col is not None:
                raw = row_dict.get(freq_col, "")
                try:
                    val = float(raw)
                    row_dict["Freq-MHz(rest)"] = val * 1000.0 if freq_col_is_ghz else val
                except (ValueError, TypeError):
                    row_dict["Freq-MHz(rest)"] = raw
            rows.append(row_dict)

        dialog = _SplatalogueDialog(rows, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_lines:
            for line in dialog.selected_lines:
                row = self._table.rowCount()
                self._table.insertRow(row)
                self._add_check_item(row)
                self._table.setItem(row, self.COL_FREQ, QTableWidgetItem(f"{line['freq_mhz']:.4f}"))
                self._table.setItem(row, self.COL_SPECIES, QTableWidgetItem(line["species"]))
                self._table.setItem(row, self.COL_TRANSITION, QTableWidgetItem(line["transition"]))
                self._table.setItem(row, self.COL_WIDTH, QTableWidgetItem(""))
                self._table.setItem(row, self.COL_RES_VALUE, QTableWidgetItem(""))
                self._table.setCellWidget(
                    row, self.COL_RES_UNIT, self._make_unit_combo(ResolutionUnit.KHZ)
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
                self._add_check_item(row)
                self._table.setItem(row, self.COL_FREQ, QTableWidgetItem(f"{freq_mhz:.4f}"))
                self._table.setItem(row, self.COL_SPECIES, QTableWidgetItem(species))
                self._table.setItem(row, self.COL_TRANSITION, QTableWidgetItem(transition))
                self._table.setItem(row, self.COL_WIDTH, QTableWidgetItem(""))
                self._table.setItem(row, self.COL_RES_VALUE, QTableWidgetItem(""))
                self._table.setCellWidget(
                    row, self.COL_RES_UNIT, self._make_unit_combo(ResolutionUnit.KHZ)
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
        self._source_list.blockSignals(True)
        self._source_list.clear()
        for src in self.observation.sources:
            self._source_list.addItem(src.name)
        self._source_list.blockSignals(False)

        self._apply_all_cb.setChecked(self.observation.apply_freqs_to_all)
        self._source_list.setEnabled(not self.observation.apply_freqs_to_all)

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
            self._source_list.setCurrentRow(0)

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
