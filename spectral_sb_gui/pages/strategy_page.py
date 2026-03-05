import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QWizardPage,
)

from spectral_sb_gui.models.observation import (
    ObservationModel,
    ObservingStrategy,
    SwitchingMode,
)

# Receivers for which AutoOOF is available
_AUTO_OOF_RECEIVERS = {"Rcvr26_40", "Rcvr40_52", "Rcvr68_92", "RcvrArray75_115"}

# UWBR receiver name (prime focus but supports AutoPeakFocus)
_UWBR_NAME = "Rcvr_2500"

# Pointing/focus cadence options: most-frequent first
_CADENCE_CHOICES = [
    ("every_45min", "Every 45 minutes"),  # ≥67 GHz (Argus, W-Band)
    ("hourly", "Every 60 minutes"),  # 40–67 GHz (Q-Band, Ka-Band)
    ("every_90min", "Every 90 minutes"),  # 12–40 GHz (Ka, K, Ku, KFPA)
    ("every_3hr", "Every 3 hours"),  # 4–12 GHz (C, X)
    ("initial_only", "Initial only"),  # <4 GHz
]


class StrategyPage(QWizardPage):
    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Observing Strategy")
        self.setSubTitle(
            "Configure pointing/focus calibration, AutoOOF, and scan parameters "
            "for each source/receiver group."
        )

        self._current_group_label: str = ""
        self._current_config = None  # ReceiverConfig for currently displayed group
        self._group_labels: list[str] = []

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: group list
        self._group_list = QListWidget()
        self._group_list.setToolTip(
            "Select a source/receiver group to configure its observing strategy"
        )
        self._group_list.currentRowChanged.connect(self._on_group_selected)
        splitter.addWidget(self._group_list)

        # Right: scroll area with strategy form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)

        # Receiver note
        self._receiver_note = QLabel("")
        self._receiver_note.setWordWrap(True)
        self._receiver_note.setStyleSheet("color: #1a5276; font-style: italic;")
        form_layout.addWidget(self._receiver_note)

        # ----- Sub-Scan parameters group (hidden entirely for frequency switching) -----
        # Placed first so it is immediately visible without scrolling.
        self._scan_group = QGroupBox("Sub-Scan Parameters")
        scan_layout = QVBoxLayout()

        scan_dur_row = QHBoxLayout()
        scan_dur_row.addWidget(QLabel("Sub-scan duration (s):"))
        self._scan_dur_spin = QDoubleSpinBox()
        self._scan_dur_spin.setToolTip(
            "Duration of each individual on-source scan in seconds.\n"
            "Each position-switched on+off pair takes 2× this duration.\n"
            "Typical values: 120–300 s."
        )
        self._scan_dur_spin.setRange(10.0, 3600.0)
        self._scan_dur_spin.setDecimals(0)
        self._scan_dur_spin.setValue(300.0)
        self._scan_dur_spin.setSingleStep(60.0)
        scan_dur_row.addWidget(self._scan_dur_spin)
        scan_dur_row.addStretch()
        scan_layout.addLayout(scan_dur_row)

        n_scans_row = QHBoxLayout()
        n_scans_row.addWidget(QLabel("Number of sub-scans:"))
        self._n_scans_label = QLabel("—")
        self._n_scans_label.setStyleSheet("font-weight: bold;")
        self._n_scans_label.setToolTip(
            "Number of on/off scan pairs needed to reach the total observation duration.\n"
            "Computed automatically as ceil(total duration / sub-scan duration)."
        )
        n_scans_row.addWidget(self._n_scans_label)
        n_scans_row.addStretch()
        scan_layout.addLayout(n_scans_row)

        self._setup_dur_label = QLabel("")
        self._setup_dur_label.setWordWrap(True)
        scan_layout.addWidget(self._setup_dur_label)

        self._scan_group.setLayout(scan_layout)
        form_layout.addWidget(self._scan_group)

        # ----- Pointing & Focus group -----
        pf_group = QGroupBox("Pointing & Focus Corrections")
        pf_layout = QVBoxLayout()

        self._pointing_cb = QCheckBox("Perform pointing corrections")
        self._pointing_cb.setChecked(True)
        self._pointing_cb.setToolTip(
            "Run a pointing scan on a nearby calibrator before science observations."
        )
        pf_layout.addWidget(self._pointing_cb)

        self._focus_cb = QCheckBox("Perform focus corrections")
        self._focus_cb.setChecked(True)
        self._focus_cb.setToolTip(
            "Run a focus scan on a nearby calibrator. "
            "Not supported for prime focus receivers (except UWBR)."
        )
        pf_layout.addWidget(self._focus_cb)

        self._focus_note = QLabel(
            "Focus corrections are not available for prime focus receivers. "
            "Only AutoPeak (pointing) will be used."
        )
        self._focus_note.setWordWrap(True)
        self._focus_note.setStyleSheet("color: gray; font-style: italic;")
        self._focus_note.setVisible(False)
        pf_layout.addWidget(self._focus_note)

        cadence_row = QHBoxLayout()
        cadence_row.addWidget(QLabel("Correction cadence:"))
        self._cadence_combo = QComboBox()
        self._cadence_combo.setToolTip(
            "How often to perform pointing/focus corrections during the observation.\n"
            "Suggested automatically based on the observing frequency."
        )
        for key, label in _CADENCE_CHOICES:
            self._cadence_combo.addItem(label, key)
        cadence_row.addWidget(self._cadence_combo)
        cadence_row.addStretch()
        pf_layout.addLayout(cadence_row)

        self._pf_function_label = QLabel("")
        self._pf_function_label.setWordWrap(True)
        self._pf_function_label.setStyleSheet("color: #555555;")
        pf_layout.addWidget(self._pf_function_label)

        pf_group.setLayout(pf_layout)
        form_layout.addWidget(pf_group)

        # ----- AutoOOF group -----
        oof_group = QGroupBox("AutoOOF (Active Surface Correction)")
        oof_layout = QVBoxLayout()

        self._oof_cb = QCheckBox("Run AutoOOF before science observations")
        self._oof_cb.setToolTip(
            "Run out-of-focus holography to correct the dish surface.\n"
            "Recommended at 40 GHz and above. Takes ~25 minutes."
        )
        oof_layout.addWidget(self._oof_cb)

        oof_rcvr_row = QHBoxLayout()
        oof_rcvr_row.addWidget(QLabel("OOF receiver:"))
        self._oof_rcvr_combo = QComboBox()
        self._oof_rcvr_combo.setToolTip(
            "Receiver to use for AutoOOF. Ka-Band (via CCB) provides the most accurate\n"
            "surface corrections and is recommended for W-Band and Argus observations."
        )
        oof_rcvr_row.addWidget(self._oof_rcvr_combo)
        oof_rcvr_row.addStretch()
        oof_layout.addLayout(oof_rcvr_row)

        oof_src_row = QHBoxLayout()
        oof_src_row.addWidget(QLabel("OOF calibrator source (optional):"))
        self._oof_source_edit = QLineEdit()
        self._oof_source_edit.setPlaceholderText("Leave blank for automatic selection")
        self._oof_source_edit.setToolTip(
            "Name of the bright calibrator to use for AutoOOF (≥ 3.5 Jy, el 30–75°).\n"
            "Leave blank to let Astrid auto-select."
        )
        oof_src_row.addWidget(self._oof_source_edit)
        oof_layout.addLayout(oof_src_row)

        self._oof_note = QLabel("")
        self._oof_note.setWordWrap(True)
        self._oof_note.setStyleSheet("color: #555555; font-style: italic;")
        oof_layout.addWidget(self._oof_note)

        oof_group.setLayout(oof_layout)
        form_layout.addWidget(oof_group)

        form_layout.addStretch()
        scroll.setWidget(form_widget)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        main_layout = QVBoxLayout()
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

        # Connect signals
        self._pointing_cb.toggled.connect(self._update_pf_label)
        self._focus_cb.toggled.connect(self._update_pf_label)
        self._oof_cb.toggled.connect(self._update_oof_state)
        self._scan_dur_spin.valueChanged.connect(self._update_n_scans_label)

    # ------------------------------------------------------------------
    # Per-group helpers
    # ------------------------------------------------------------------

    def _find_config_for_label(self, label):
        for setup in self.observation.source_setups:
            for config in setup.receiver_configs:
                if f"{setup.source_name} — {config.display_name}" == label:
                    return setup, config
        return None, None

    def _is_prime_focus(self, config):
        return config.receiver_type == "prime_focus" and config.receiver_name != _UWBR_NAME

    def _oof_available(self, config):
        return config.receiver_name in _AUTO_OOF_RECEIVERS

    def _suggest_cadence(self, max_freq_ghz):
        if max_freq_ghz >= 67.0:
            return "every_45min"
        elif max_freq_ghz >= 40.0:
            return "hourly"
        elif max_freq_ghz >= 12.0:
            return "every_90min"
        elif max_freq_ghz >= 4.0:
            return "every_3hr"
        else:
            return "initial_only"

    def _make_default_strategy(self, config):
        is_pf = self._is_prime_focus(config)
        oof_avail = self._oof_available(config)
        max_freq_ghz = max(config.obs_freqs_mhz) / 1000.0 if config.obs_freqs_mhz else 0.0
        cadence = self._suggest_cadence(max_freq_ghz)

        rname = config.receiver_name
        if rname in ("Rcvr68_92", "RcvrArray75_115"):
            oof_rcvr = "ka"
        elif rname == "Rcvr40_52":
            oof_rcvr = "ka"
        elif rname == "Rcvr26_40":
            oof_rcvr = "primary"
        else:
            oof_rcvr = "auto"

        oof_on = oof_avail and max_freq_ghz >= 40.0

        is_fsw = config.switching_mode == SwitchingMode.FREQUENCY
        if is_fsw:
            # For frequency switching the single Track scan spans the full duration.
            scan_dur = config.total_duration_s if config.total_duration_s > 0 else 300.0
            n_scans = 1
        else:
            scan_dur = 300.0
            if config.total_duration_s > 0:
                n_scans = math.ceil(config.total_duration_s / scan_dur)
            else:
                n_scans = 1

        return ObservingStrategy(
            do_pointing=True,
            do_focus=not is_pf,
            pf_cadence=cadence,
            do_auto_oof=oof_on,
            oof_receiver=oof_rcvr,
            oof_source="",
            scan_duration_s=scan_dur,
            n_scans=n_scans,
        )

    def _rebuild_oof_rcvr_combo(self, config, saved_oof_rcvr):
        rname = config.receiver_name
        self._oof_rcvr_combo.blockSignals(True)
        self._oof_rcvr_combo.clear()

        if rname in ("Rcvr68_92", "RcvrArray75_115"):
            self._oof_rcvr_combo.addItem("Ka-Band (recommended)", "ka")
            self._oof_rcvr_combo.addItem("Q-Band", "q")
            if rname == "Rcvr68_92":
                self._oof_rcvr_combo.addItem("W-Band (primary)", "primary")
            else:
                self._oof_rcvr_combo.addItem("Argus (primary)", "primary")
        elif rname == "Rcvr40_52":
            self._oof_rcvr_combo.addItem("Ka-Band (recommended)", "ka")
            self._oof_rcvr_combo.addItem("Q-Band (primary)", "primary")
        elif rname == "Rcvr26_40":
            self._oof_rcvr_combo.addItem("Ka-Band (primary)", "primary")
        else:
            self._oof_rcvr_combo.addItem("Automatic", "auto")

        for i in range(self._oof_rcvr_combo.count()):
            if self._oof_rcvr_combo.itemData(i) == saved_oof_rcvr:
                self._oof_rcvr_combo.setCurrentIndex(i)
                break

        self._oof_rcvr_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # UI update
    # ------------------------------------------------------------------

    def _update_pf_label(self):
        if self._current_config is None:
            return
        is_pf = self._is_prime_focus(self._current_config)
        do_pointing = self._pointing_cb.isChecked()
        do_focus = self._focus_cb.isChecked() and not is_pf

        if is_pf:
            if do_pointing:
                func_text = "<b>AutoPeak()</b> will be used — pointing only (prime focus receiver)."
            else:
                func_text = "No pointing or focus corrections will be performed."
        elif do_pointing and do_focus:
            func_text = "<b>AutoPeakFocus()</b> will be used — both pointing and focus corrections."
        elif not do_pointing and do_focus:
            func_text = "<b>AutoFocus()</b> will be used — focus corrections only."
        elif do_pointing and not do_focus:
            func_text = "<b>AutoPeak()</b> will be used — pointing corrections only."
        else:
            func_text = "No pointing or focus corrections will be performed."

        self._pf_function_label.setText(func_text)

    def _update_oof_state(self):
        oof_on = self._oof_cb.isChecked() and self._oof_cb.isEnabled()
        self._oof_rcvr_combo.setEnabled(oof_on)
        self._oof_source_edit.setEnabled(oof_on)

    def _update_n_scans_label(self):
        """Recompute and display n_scans = ceil(total_duration / scan_duration)."""
        if self._current_config is None:
            return
        scan_dur = self._scan_dur_spin.value()
        total_s = self._current_config.total_duration_s
        if total_s > 0 and scan_dur > 0:
            n = math.ceil(total_s / scan_dur)
            self._n_scans_label.setText(str(n))
        else:
            self._n_scans_label.setText("—")

    # ------------------------------------------------------------------
    # Group selection
    # ------------------------------------------------------------------

    def _on_group_selected(self, row):
        if row < 0 or row >= len(self._group_labels):
            return
        # Save current group before switching
        if self._current_group_label:
            self._save_current_group()

        label = self._group_labels[row]
        self._current_group_label = label

        _, config = self._find_config_for_label(label)
        if config is None:
            return
        self._current_config = config

        is_pf = self._is_prime_focus(config)
        oof_avail = self._oof_available(config)
        max_freq_ghz = max(config.obs_freqs_mhz) / 1000.0 if config.obs_freqs_mhz else 0.0

        # Receiver note
        if is_pf:
            note = "Prime focus receiver — only AutoPeak (pointing) is available."
        elif max_freq_ghz >= 40.0:
            note = (
                f"Observing at up to {max_freq_ghz:.0f} GHz. "
                "AutoPeakFocus and AutoOOF are recommended."
            )
        else:
            note = f"Observing at up to {max_freq_ghz:.0f} GHz. AutoPeakFocus is recommended."
        self._receiver_note.setText(note)

        # Load or create strategy
        strategy = self.observation.strategies.get(label)
        if strategy is None:
            strategy = self._make_default_strategy(config)
            self.observation.strategies[label] = strategy

        # Block signals while populating
        for w in (
            self._pointing_cb,
            self._focus_cb,
            self._cadence_combo,
            self._oof_cb,
        ):
            w.blockSignals(True)

        self._pointing_cb.setChecked(strategy.do_pointing)
        self._focus_cb.setChecked(strategy.do_focus if not is_pf else False)
        self._focus_cb.setEnabled(not is_pf)
        self._focus_note.setVisible(is_pf)

        for i in range(self._cadence_combo.count()):
            if self._cadence_combo.itemData(i) == strategy.pf_cadence:
                self._cadence_combo.setCurrentIndex(i)
                break

        self._oof_cb.setEnabled(oof_avail)
        self._oof_cb.setChecked(strategy.do_auto_oof and oof_avail)

        if oof_avail and max_freq_ghz >= 40.0:
            self._oof_note.setText(
                "AutoOOF is recommended at 40 GHz and above. "
                "Allow ~25 minutes. Ka-Band (CCB) provides the most accurate surface corrections."
            )
        elif oof_avail:
            self._oof_note.setText("AutoOOF is available but is typically not needed below 40 GHz.")
        else:
            self._oof_note.setText(
                "AutoOOF is not available for this receiver (requires Ka, Q, W, or Argus)."
            )

        self._rebuild_oof_rcvr_combo(config, strategy.oof_receiver)
        self._oof_source_edit.setText(strategy.oof_source)

        is_fsw = config.switching_mode == SwitchingMode.FREQUENCY
        self._scan_group.setVisible(not is_fsw)

        if not is_fsw:
            # Populate scan duration spinbox (block signal to avoid premature recalc)
            self._scan_dur_spin.blockSignals(True)
            self._scan_dur_spin.setValue(strategy.scan_duration_s)
            self._scan_dur_spin.blockSignals(False)
            # Set total-duration reminder and compute n_scans directly here
            total_s = config.total_duration_s
            scan_dur_val = strategy.scan_duration_s
            if total_s > 0 and scan_dur_val > 0:
                n = math.ceil(total_s / scan_dur_val)
                self._n_scans_label.setText(str(n))
                self._setup_dur_label.setText(
                    f"Total observation time (from Setup): {total_s / 60.0:.1f} min"
                )
            else:
                self._n_scans_label.setText("—")
                self._setup_dur_label.setText("Total observation time not set on Setup page.")

        for w in (
            self._pointing_cb,
            self._focus_cb,
            self._cadence_combo,
            self._oof_cb,
        ):
            w.blockSignals(False)

        self._update_pf_label()
        self._update_oof_state()

    def _save_current_group(self):
        if not self._current_group_label or self._current_config is None:
            return
        is_pf = self._is_prime_focus(self._current_config)
        is_fsw = self._current_config.switching_mode == SwitchingMode.FREQUENCY
        total_s = self._current_config.total_duration_s
        if is_fsw:
            # Scan group is hidden for FSW — derive duration from total, not spinbox
            scan_dur = total_s if total_s > 0 else 300.0
            n_scans = 1
        else:
            scan_dur = self._scan_dur_spin.value()
            n_scans = math.ceil(total_s / scan_dur) if total_s > 0 and scan_dur > 0 else 1
        strategy = ObservingStrategy(
            do_pointing=self._pointing_cb.isChecked(),
            do_focus=self._focus_cb.isChecked() and not is_pf,
            pf_cadence=self._cadence_combo.currentData() or "initial_only",
            do_auto_oof=self._oof_cb.isChecked() and self._oof_cb.isEnabled(),
            oof_receiver=self._oof_rcvr_combo.currentData() or "auto",
            oof_source=self._oof_source_edit.text().strip(),
            scan_duration_s=scan_dur,
            n_scans=n_scans,
        )
        self.observation.strategies[self._current_group_label] = strategy

    # ------------------------------------------------------------------
    # Page lifecycle
    # ------------------------------------------------------------------

    def initializePage(self):
        # Clear stale strategies so defaults are recomputed from the current config
        # (e.g. if the user went back and changed total duration on the Setup page).
        self.observation.strategies = {}

        self._group_labels = []
        self._group_list.blockSignals(True)
        self._group_list.clear()

        for setup in self.observation.source_setups:
            for config in setup.receiver_configs:
                label = f"{setup.source_name} — {config.display_name}"
                self._group_labels.append(label)
                self._group_list.addItem(label)

        self._group_list.blockSignals(False)
        self._current_group_label = ""
        self._current_config = None

        if self._group_labels:
            self._group_list.setCurrentRow(0)

    def validatePage(self):
        self._save_current_group()
        return True
