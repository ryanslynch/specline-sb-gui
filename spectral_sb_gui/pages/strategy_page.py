from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QTextEdit,
    QVBoxLayout,
    QWizardPage,
)

from spectral_sb_gui.models.observation import (
    ObservationModel,
    SwitchingMode,
)

# Receivers where AutoOOF is available (high-frequency receivers)
AUTO_OOF_RECEIVERS = {"Rcvr26_40", "RcvrArray18_26", "Rcvr40_52", "Rcvr68_92", "RcvrArray75_115"}


class StrategyPage(QWizardPage):
    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Observing Strategy")
        self.setSubTitle(
            "Review the auto-generated observing strategy. "
            "Adjust initial calibration steps and scan types as needed."
        )

        layout = QVBoxLayout()

        # Initial calibration group
        cal_group = QGroupBox("Initial Calibration")
        cal_layout = QVBoxLayout()

        self._pointing_cb = QCheckBox("Initial pointing correction (AutoPeakFocus)")
        self._pointing_cb.setChecked(True)
        self._pointing_cb.setToolTip(
            "Perform an initial pointing and focus correction on a nearby "
            "calibrator before starting science observations"
        )
        cal_layout.addWidget(self._pointing_cb)

        self._focus_cb = QCheckBox("Initial focus correction")
        self._focus_cb.setChecked(True)
        self._focus_cb.setToolTip("Include a focus correction in the initial calibration sequence")
        cal_layout.addWidget(self._focus_cb)

        self._oof_cb = QCheckBox("AutoOOF (out-of-focus holography)")
        self._oof_cb.setChecked(False)
        self._oof_cb.setToolTip(
            "Perform out-of-focus holography to correct the dish surface. "
            "Only available for high-frequency receivers (Ka, KFPA, Q, W, Argus)."
        )
        cal_layout.addWidget(self._oof_cb)

        cal_group.setLayout(cal_layout)
        layout.addWidget(cal_group)

        # Strategy preview
        preview_group = QGroupBox("Strategy Preview")
        preview_layout = QVBoxLayout()
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setToolTip(
            "Read-only preview of the observing strategy that will be used "
            "to generate scheduling blocks"
        )
        preview_layout.addWidget(self._preview)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # Connect checkboxes to update preview
        self._pointing_cb.toggled.connect(self._update_preview)
        self._focus_cb.toggled.connect(self._update_preview)
        self._oof_cb.toggled.connect(self._update_preview)

        self.setLayout(layout)

    def _update_preview(self):
        lines = []
        lines.append("=== Observing Strategy ===")
        lines.append("")

        if self._pointing_cb.isChecked() or self._focus_cb.isChecked():
            lines.append("1. Initial Calibration:")
            if self._pointing_cb.isChecked():
                lines.append("   - AutoPeakFocus on first source")
            if self._oof_cb.isChecked() and self._oof_cb.isEnabled():
                lines.append("   - AutoOOF procedure")
            lines.append("")

        step = 2
        for setup in self.observation.source_setups:
            for config in setup.receiver_configs:
                scan_type = "Track" if config.switching_mode == SwitchingMode.FREQUENCY else "OnOff"
                lines.append(f"{step}. Source: {setup.source_name}")
                lines.append(f"   Receiver: {config.display_name}")
                lines.append(f"   Switching: {config.switching_mode.value}")
                lines.append(f"   Scan type: {scan_type}")
                lines.append(
                    f"   Rest freqs: {', '.join(f'{f:.2f} MHz' for f in config.rest_freqs_mhz)}"
                )
                lines.append(f"   swper={config.swper}s, tint={config.tint}s")
                lines.append("")
                step += 1

        self._preview.setText("\n".join(lines))

    def _check_oof_availability(self):
        """Enable AutoOOF checkbox only if high-freq receivers are in use."""
        available = False
        for setup in self.observation.source_setups:
            for config in setup.receiver_configs:
                if config.receiver_name in AUTO_OOF_RECEIVERS:
                    available = True
                    break
            if available:
                break
        self._oof_cb.setEnabled(available)
        if not available:
            self._oof_cb.setChecked(False)
        self.observation.strategy.auto_oof_available = available

    # ------------------------------------------------------------------
    # Page lifecycle
    # ------------------------------------------------------------------

    def initializePage(self):
        self._pointing_cb.setChecked(self.observation.strategy.do_initial_pointing)
        self._focus_cb.setChecked(self.observation.strategy.do_initial_focus)
        self._oof_cb.setChecked(self.observation.strategy.do_auto_oof)
        self._check_oof_availability()
        self._update_preview()

    def validatePage(self):
        self.observation.strategy.do_initial_pointing = self._pointing_cb.isChecked()
        self.observation.strategy.do_initial_focus = self._focus_cb.isChecked()
        self.observation.strategy.do_auto_oof = self._oof_cb.isChecked()
        return True
