import json
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QWizardPage,
)

from spectral_sb_gui.models.observation import (
    ObservationModel,
    ReceiverConfig,
    ResolutionUnit,
    SourceSetup,
    SwitchingMode,
)

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data"
)


def _load_receivers():
    path = os.path.join(_DATA_DIR, "receivers.json")
    with open(path) as f:
        data = json.load(f)
    return data["receivers"]


def _load_vegas_modes():
    path = os.path.join(_DATA_DIR, "vegas_modes.json")
    with open(path) as f:
        data = json.load(f)
    return data


# ------------------------------------------------------------------
# Doppler shift calculation
# ------------------------------------------------------------------


def doppler_shift_freq(rest_freq_mhz, velocity_kms, vel_def="Radio"):
    """Compute the observed frequency given a rest frequency and velocity.

    Uses the radio convention by default: f_obs = f_rest * (1 - v/c)
    """
    c_kms = 299792.458  # speed of light in km/s
    if vel_def == "Radio":
        return rest_freq_mhz * (1.0 - velocity_kms / c_kms)
    elif vel_def == "Optical":
        # f_obs = f_rest / (1 + v/c)
        return rest_freq_mhz / (1.0 + velocity_kms / c_kms)
    else:
        # Relativistic: f_obs = f_rest * sqrt((1 - v/c) / (1 + v/c))
        beta = velocity_kms / c_kms
        return rest_freq_mhz * ((1.0 - beta) / (1.0 + beta)) ** 0.5


# ------------------------------------------------------------------
# Receiver selection
# ------------------------------------------------------------------


def find_receivers_for_freq(freq_mhz, receivers):
    """Return list of receivers that cover the given frequency."""
    matches = []
    for rcvr in receivers:
        if rcvr["freq_min_mhz"] <= freq_mhz <= rcvr["freq_max_mhz"]:
            matches.append(rcvr)
    return matches


def select_receivers_for_source(source, receivers):
    """Select minimum set of receivers to cover all of a source's Doppler-shifted freqs.

    Returns list of (receiver_dict, list_of_rest_freqs_covered).
    Uses a greedy set cover approach.
    """
    # Compute Doppler-shifted frequency for each rest freq
    freq_pairs = []  # (rest_freq_obj, obs_freq_mhz)
    for rf in source.rest_freqs:
        obs_freq = doppler_shift_freq(
            rf.freq_mhz, source.velocity_kms, source.velocity_definition.value
        )
        freq_pairs.append((rf, obs_freq))

    uncovered = set(range(len(freq_pairs)))
    selected = []

    while uncovered:
        best_rcvr = None
        best_covered = set()
        for rcvr in receivers:
            covered = set()
            for i in uncovered:
                _, obs_freq = freq_pairs[i]
                if rcvr["freq_min_mhz"] <= obs_freq <= rcvr["freq_max_mhz"]:
                    covered.add(i)
            if len(covered) > len(best_covered):
                best_covered = covered
                best_rcvr = rcvr
        if best_rcvr is None:
            break
        uncovered -= best_covered
        rest_freqs_covered = [freq_pairs[i][0] for i in best_covered]
        obs_freqs_covered = [freq_pairs[i][1] for i in best_covered]
        selected.append((best_rcvr, rest_freqs_covered, obs_freqs_covered))

    return selected


# ------------------------------------------------------------------
# VEGAS mode selection
# ------------------------------------------------------------------


def select_vegas_mode(resolution_khz, vegas_data):
    """Select the best VEGAS mode for a given resolution requirement.

    Picks the mode whose resolution is closest to (but finer than) the requested
    resolution. If no mode is finer, picks the finest available.
    """
    modes = vegas_data["modes"]
    # Prefer modes that meet the resolution requirement
    candidates = [m for m in modes if m["resolution_khz"] <= resolution_khz]
    if candidates:
        # Pick the coarsest mode that still meets the requirement (least data)
        return max(candidates, key=lambda m: m["resolution_khz"])
    # No mode meets the requirement — pick the finest available
    return min(modes, key=lambda m: m["resolution_khz"])


def resolution_to_khz(rest_freq_mhz, res_value, res_unit):
    """Convert resolution to kHz."""
    if res_unit == ResolutionUnit.KHZ:
        return res_value
    else:
        # km/s to kHz: delta_f = f * delta_v / c
        c_kms = 299792.458
        return rest_freq_mhz * res_value / c_kms * 1000.0  # MHz->kHz


# ------------------------------------------------------------------
# Switching mode selection
# ------------------------------------------------------------------


def suggest_switching_mode(rest_freqs):
    """Suggest a switching mode based on expected line widths.

    Without explicit line width info, default to position switching.
    """
    return SwitchingMode.POSITION


# ------------------------------------------------------------------
# Minimum switching period validation
# ------------------------------------------------------------------


def get_min_swper(vegas_mode, switching_mode, obs_freq_ghz, doppler_tracking, vegas_data):
    """Get minimum recommended switching period for given parameters."""
    mode_data = None
    for m in vegas_data["modes"]:
        if m["mode"] == vegas_mode:
            mode_data = m
            break
    if mode_data is None:
        return 0.25

    # Determine minimum switching period
    if switching_mode == SwitchingMode.FREQUENCY:
        min_val = max(0.25, mode_data["min_swper"].get("sp_nocal_s", 0.32))
    else:
        # Position switching uses tp keys
        min_val = mode_data["min_swper"].get("tp_s", 0.01)

    # Check Doppler tracking limits
    if doppler_tracking and "min_swper_doppler_pointed" in mode_data:
        doppler_data = mode_data["min_swper_doppler_pointed"]
        if switching_mode == SwitchingMode.FREQUENCY:
            dp = doppler_data.get("sp_nocal", {})
        else:
            dp = doppler_data.get("tp", {})
        nu_min = dp.get("nu_min_ghz", 999)
        if obs_freq_ghz >= nu_min:
            doppler_min = dp.get("swper_s", min_val)
            min_val = max(min_val, doppler_min)

    # Frequency switching minimum is always >= 0.25s
    if switching_mode == SwitchingMode.FREQUENCY:
        min_val = max(min_val, 0.25)

    return min_val


# ------------------------------------------------------------------
# Setup Page
# ------------------------------------------------------------------


class SetupPage(QWizardPage):
    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Observing Setup")
        self.setSubTitle(
            "Review the auto-selected observing setup. "
            "The GUI has chosen receivers, VEGAS modes, and switching parameters "
            "based on your sources and frequencies."
        )

        self._receivers = _load_receivers()
        self._vegas_data = _load_vegas_modes()

        layout = QVBoxLayout()

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: summary table
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._summary_table = QTableWidget()
        self._summary_table.setToolTip(
            "Summary of auto-selected observing configurations — "
            "select a row to view and modify details on the right"
        )
        self._summary_table.setColumnCount(5)
        self._summary_table.setHorizontalHeaderLabels(
            [
                "Source",
                "Receiver",
                "VEGAS Mode",
                "Bandwidth",
                "Switching",
            ]
        )
        self._summary_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._summary_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._summary_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self._summary_table.horizontalHeader()
        for col in range(5):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        self._summary_table.currentCellChanged.connect(lambda row, *_: self._on_setup_selected(row))
        left_layout.addWidget(self._summary_table)
        splitter.addWidget(left_widget)

        # Right: detail panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Switching config
        sw_group = QGroupBox("Switching Configuration")
        sw_group.setToolTip("Configure the switching mode and parameters for this setup")
        sw_layout = QVBoxLayout()

        sw_row1 = QHBoxLayout()
        sw_row1.addWidget(QLabel("Switching Mode:"))
        self._sw_mode_combo = QComboBox()
        self._sw_mode_combo.setToolTip(
            "Frequency switching: for narrow lines (<10 km/s width)\n"
            "Position switching: for broad lines (>100 km/s), crowded spectra, or high RFI"
        )
        for sm in SwitchingMode:
            self._sw_mode_combo.addItem(sm.value, sm)
        self._sw_mode_combo.currentIndexChanged.connect(self._on_switching_changed)
        sw_row1.addWidget(self._sw_mode_combo)
        sw_layout.addLayout(sw_row1)

        sw_row2 = QHBoxLayout()
        sw_row2.addWidget(QLabel("Switching Period (s):"))
        self._swper_spin = QDoubleSpinBox()
        self._swper_spin.setToolTip("Switching period in seconds (default: 1.0)")
        self._swper_spin.setRange(0.01, 60.0)
        self._swper_spin.setDecimals(4)
        self._swper_spin.setValue(1.0)
        self._swper_spin.setSingleStep(0.1)
        self._swper_spin.valueChanged.connect(self._check_swper)
        sw_row2.addWidget(self._swper_spin)
        sw_layout.addLayout(sw_row2)

        sw_row3 = QHBoxLayout()
        sw_row3.addWidget(QLabel("Integration Time (s):"))
        self._tint_spin = QDoubleSpinBox()
        self._tint_spin.setToolTip("Integration time per phase in seconds (default: 1.0)")
        self._tint_spin.setRange(0.001, 60.0)
        self._tint_spin.setDecimals(4)
        self._tint_spin.setValue(1.0)
        self._tint_spin.setSingleStep(0.1)
        sw_row3.addWidget(self._tint_spin)
        sw_layout.addLayout(sw_row3)

        self._swfreq_row = QHBoxLayout()
        self._swfreq_row_label = QLabel("Freq Throw (MHz):")
        self._swfreq_row.addWidget(self._swfreq_row_label)
        self._swfreq_spin = QDoubleSpinBox()
        self._swfreq_spin.setToolTip(
            "Frequency throw for frequency switching in MHz. "
            "Should be a few times the expected line width. "
            "If less than half the bandwidth, enables in-band frequency switching."
        )
        self._swfreq_spin.setRange(0.001, 1500.0)
        self._swfreq_spin.setDecimals(3)
        self._swfreq_spin.setValue(1.0)
        self._swfreq_row.addWidget(self._swfreq_spin)
        sw_layout.addLayout(self._swfreq_row)

        sw_group.setLayout(sw_layout)
        right_layout.addWidget(sw_group)

        # VEGAS mode info
        mode_group = QGroupBox("VEGAS Mode Details")
        mode_layout = QVBoxLayout()
        self._mode_info = QLabel("Select a setup from the table to see details.")
        self._mode_info.setWordWrap(True)
        self._mode_info.setToolTip("Details of the selected VEGAS spectral line mode")
        mode_layout.addWidget(self._mode_info)
        mode_group.setLayout(mode_layout)
        right_layout.addWidget(mode_group)

        # Rest frequencies for this setup
        freq_group = QGroupBox("Rest Frequencies")
        freq_layout = QVBoxLayout()
        self._freq_list = QTextEdit()
        self._freq_list.setReadOnly(True)
        self._freq_list.setMaximumHeight(80)
        self._freq_list.setToolTip("Rest frequencies covered by this receiver setup")
        freq_layout.addWidget(self._freq_list)
        freq_group.setLayout(freq_layout)
        right_layout.addWidget(freq_group)

        # Switching help text
        help_group = QGroupBox("Switching Mode Guide")
        help_layout = QVBoxLayout()
        help_text = QLabel(
            "<b>Frequency switching</b> is best for narrow spectral lines "
            "(&lt;10 km/s width). Choose a frequency throw a few times the "
            "line width. If the throw is less than half the bandwidth, "
            "in-band frequency switching is used (more efficient).\n\n"
            "<b>Position switching</b> is best for broad lines (&gt;100 km/s), "
            "spectrally crowded regions, or frequencies with significant RFI.\n\n"
            "When in doubt, use position switching (default)."
        )
        help_text.setWordWrap(True)
        help_text.setToolTip("Guidelines for choosing between frequency and position switching")
        help_layout.addWidget(help_text)
        help_group.setLayout(help_layout)
        right_layout.addWidget(help_group)

        right_layout.addStretch()

        self._apply_btn = QPushButton("Apply Changes")
        self._apply_btn.setToolTip("Apply the current switching and VEGAS settings to this setup")
        self._apply_btn.clicked.connect(self._apply_changes)
        right_layout.addWidget(self._apply_btn)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

        # Warning label
        self._warning_label = QLabel("")
        self._warning_label.setWordWrap(True)
        self._warning_label.setStyleSheet("color: #e65100; font-weight: bold;")
        layout.addWidget(self._warning_label)

        self.setLayout(layout)

        self._current_setup_idx = (-1, -1)  # (source_idx, config_idx)
        self._setup_index_map = []  # maps table row -> (source_idx, config_idx)

    # ------------------------------------------------------------------
    # Auto-configuration
    # ------------------------------------------------------------------

    def _auto_configure(self):
        """Auto-select receivers, VEGAS modes, and switching for all sources."""
        self.observation.source_setups = []

        for src in self.observation.sources:
            setup = SourceSetup(source_name=src.name)

            # Select receivers
            rcvr_selections = select_receivers_for_source(src, self._receivers)

            for rcvr_dict, rest_freqs, obs_freqs in rcvr_selections:
                # Pick VEGAS mode based on finest resolution requested
                target_res_khz = None
                for rf in rest_freqs:
                    if rf.resolution_value > 0:
                        res_khz = resolution_to_khz(
                            rf.freq_mhz, rf.resolution_value, rf.resolution_unit
                        )
                        if target_res_khz is None or res_khz < target_res_khz:
                            target_res_khz = res_khz

                if target_res_khz is None:
                    target_res_khz = 10.0  # default ~10 kHz

                vegas_mode = select_vegas_mode(target_res_khz, self._vegas_data)
                sw_mode = suggest_switching_mode(rest_freqs)

                config = ReceiverConfig(
                    receiver_name=rcvr_dict["name"],
                    display_name=rcvr_dict["display_name"],
                    vegas_mode=vegas_mode["mode"],
                    bandwidth_mhz=vegas_mode["bandwidth_mhz"],
                    channels=vegas_mode["channels"],
                    resolution_khz=vegas_mode["resolution_khz"],
                    switching_mode=sw_mode,
                    swper=1.0,
                    swfreq_mhz=1.0,
                    tint=1.0,
                    rest_freqs_mhz=[rf.freq_mhz for rf in rest_freqs],
                    obs_freqs_mhz=obs_freqs,
                )
                setup.receiver_configs.append(config)

            if not setup.receiver_configs and src.rest_freqs:
                # No receiver covers the frequencies — create a placeholder
                QMessageBox.warning(
                    self,
                    "Receiver Selection",
                    f"No GBT receiver covers all frequencies for source '{src.name}'. "
                    "Some frequencies may not be observable.",
                )

            self.observation.source_setups.append(setup)

    # ------------------------------------------------------------------
    # UI population
    # ------------------------------------------------------------------

    def _populate_summary(self):
        self._summary_table.setRowCount(0)
        self._setup_index_map = []

        for si, setup in enumerate(self.observation.source_setups):
            for ci, config in enumerate(setup.receiver_configs):
                row = self._summary_table.rowCount()
                self._summary_table.insertRow(row)
                self._summary_table.setItem(row, 0, QTableWidgetItem(setup.source_name))
                self._summary_table.setItem(row, 1, QTableWidgetItem(config.display_name))
                self._summary_table.setItem(row, 2, QTableWidgetItem(f"Mode {config.vegas_mode}"))
                self._summary_table.setItem(row, 3, QTableWidgetItem(f"{config.bandwidth_mhz} MHz"))
                self._summary_table.setItem(row, 4, QTableWidgetItem(config.switching_mode.value))
                self._setup_index_map.append((si, ci))

    def _on_setup_selected(self, row):
        if row < 0 or row >= len(self._setup_index_map):
            return
        si, ci = self._setup_index_map[row]
        self._current_setup_idx = (si, ci)
        config = self.observation.source_setups[si].receiver_configs[ci]

        # Populate detail panel
        for i in range(self._sw_mode_combo.count()):
            if self._sw_mode_combo.itemData(i) == config.switching_mode:
                self._sw_mode_combo.setCurrentIndex(i)
                break
        self._swper_spin.setValue(config.swper)
        self._tint_spin.setValue(config.tint)
        self._swfreq_spin.setValue(config.swfreq_mhz)

        # Show/hide freq throw
        is_freq_sw = config.switching_mode == SwitchingMode.FREQUENCY
        self._swfreq_spin.setVisible(is_freq_sw)
        self._swfreq_row_label.setVisible(is_freq_sw)

        # Mode info
        mode_info = self._get_mode_info(config.vegas_mode)
        self._mode_info.setText(mode_info)

        # Freq list
        freq_lines = []
        for freq in config.rest_freqs_mhz:
            freq_lines.append(f"{freq:.4f} MHz")
        self._freq_list.setText("\n".join(freq_lines))

        self._check_swper()

    def _get_mode_info(self, mode_num):
        for m in self._vegas_data["modes"]:
            if m["mode"] == mode_num:
                return (
                    f"Mode {m['mode']}: "
                    f"{m['subbands']} subband(s), "
                    f"{m['bandwidth_mhz']} MHz bandwidth, "
                    f"{m['channels']} channels, "
                    f"{m['resolution_khz']} kHz resolution, "
                    f"min tint = {m['min_int_time_s']} s"
                )
        return f"Mode {mode_num}"

    def _on_switching_changed(self):
        sw_mode = self._sw_mode_combo.currentData()
        is_freq_sw = sw_mode == SwitchingMode.FREQUENCY
        self._swfreq_spin.setVisible(is_freq_sw)
        self._swfreq_row_label.setVisible(is_freq_sw)
        self._check_swper()

    def _check_swper(self):
        """Check if the current switching period is below minimum."""
        si, ci = self._current_setup_idx
        if si < 0:
            self._warning_label.setText("")
            return

        config = self.observation.source_setups[si].receiver_configs[ci]
        sw_mode = self._sw_mode_combo.currentData()
        swper = self._swper_spin.value()

        # Use first obs freq to determine Doppler limits
        obs_freq_ghz = config.obs_freqs_mhz[0] / 1000.0 if config.obs_freqs_mhz else 1.0

        min_swper = get_min_swper(config.vegas_mode, sw_mode, obs_freq_ghz, True, self._vegas_data)

        if swper < min_swper:
            self._warning_label.setText(
                f"Warning: switching period {swper:.4f}s is below the "
                f"minimum recommended value of {min_swper:.4f}s for "
                f"VEGAS Mode {config.vegas_mode} with "
                f"{sw_mode.value.lower()} switching "
                f"(per GBT Memo 288)."
            )
        else:
            self._warning_label.setText("")

    def _apply_changes(self):
        si, ci = self._current_setup_idx
        if si < 0:
            return
        config = self.observation.source_setups[si].receiver_configs[ci]
        config.switching_mode = self._sw_mode_combo.currentData()
        config.swper = self._swper_spin.value()
        config.tint = self._tint_spin.value()
        config.swfreq_mhz = self._swfreq_spin.value()

        # Update summary table
        row = self._setup_index_map.index((si, ci))
        self._summary_table.item(row, 4).setText(config.switching_mode.value)

    # ------------------------------------------------------------------
    # Page lifecycle
    # ------------------------------------------------------------------

    def initializePage(self):
        self._auto_configure()
        self._populate_summary()
        self._current_setup_idx = (-1, -1)
        self._warning_label.setText("")
        if self._summary_table.rowCount() > 0:
            self._summary_table.setCurrentCell(0, 0)

    def validatePage(self):
        # Apply any pending changes
        if self._current_setup_idx[0] >= 0:
            self._apply_changes()
        return True
