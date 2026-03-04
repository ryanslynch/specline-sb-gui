import re
from collections import OrderedDict

from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QWizardPage,
)

from spectral_sb_gui.models.observation import (
    CoordSystem,
    ObservationModel,
    SwitchingMode,
    VelocityDefinition,
    VelocityFrame,
)


def _safe_name(name: str) -> str:
    """Convert a source name to a valid Python identifier fragment."""
    return re.sub(r"[^A-Za-z0-9]", "_", name)


# ------------------------------------------------------------------
# Velocity frame / definition mapping to Astrid keywords
# ------------------------------------------------------------------

_VFRAME_MAP = {
    VelocityFrame.TOPOCENTRIC: "Topocentric",
    VelocityFrame.BARYCENTRIC: "Barycentric",
    VelocityFrame.LSRK: "LSRK",
    VelocityFrame.GALACTIC: "Galactic",
    VelocityFrame.CMB: "CMB",
}

_VDEF_MAP = {
    VelocityDefinition.RADIO: "Radio",
    VelocityDefinition.OPTICAL: "Optical",
    VelocityDefinition.RELATIVISTIC: "Relativistic",
}


# ------------------------------------------------------------------
# Python syntax highlighter (adapted from pulsar GUI)
# ------------------------------------------------------------------


class _PythonHighlighter(QSyntaxHighlighter):
    """Simple Python syntax highlighter for scheduling block scripts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        # Keywords
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#0000FF"))
        kw_fmt.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "and",
            "as",
            "assert",
            "break",
            "class",
            "continue",
            "def",
            "del",
            "elif",
            "else",
            "except",
            "False",
            "finally",
            "for",
            "from",
            "global",
            "if",
            "import",
            "in",
            "is",
            "lambda",
            "None",
            "nonlocal",
            "not",
            "or",
            "pass",
            "raise",
            "return",
            "True",
            "try",
            "while",
            "with",
            "yield",
        ]
        for kw in keywords:
            pattern = QRegularExpression(rf"\b{kw}\b")
            self._rules.append((pattern, kw_fmt))

        # Astrid commands
        builtin_fmt = QTextCharFormat()
        builtin_fmt.setForeground(QColor("#008080"))
        builtins = [
            "Catalog",
            "Configure",
            "Slew",
            "Track",
            "OnOff",
            "Balance",
            "ResetConfig",
            "AutoPeakFocus",
            "AutoOOF",
            "Offset",
        ]
        for b in builtins:
            pattern = QRegularExpression(rf"\b{b}\b")
            self._rules.append((pattern, builtin_fmt))

        # Numbers
        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#FF6600"))
        self._rules.append(
            (
                QRegularExpression(r"\b[0-9]+\.?[0-9]*([eE][+-]?[0-9]+)?\b"),
                num_fmt,
            )
        )

        # Strings
        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#008000"))
        self._rules.append(
            (
                QRegularExpression(r'""".*?"""|\'\'\'.*?\'\'\''),
                str_fmt,
            )
        )
        self._rules.append(
            (
                QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"|\'[^\'\\]*(\\.[^\'\\]*)*\''),
                str_fmt,
            )
        )

        # Comments
        self._comment_fmt = QTextCharFormat()
        self._comment_fmt.setForeground(QColor("#808080"))
        self._comment_fmt.setFontItalic(True)

        self._triple_dq = QRegularExpression(r'"""')
        self._triple_sq = QRegularExpression(r"'''")

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

        comment_match = QRegularExpression(r"#[^\n]*").match(text)
        if comment_match.hasMatch():
            start = comment_match.capturedStart()
            length = comment_match.capturedLength()
            self.setFormat(start, length, self._comment_fmt)

        self._handle_multiline_strings(text)

    def _handle_multiline_strings(self, text: str):
        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#008000"))

        prev_state = self.previousBlockState()
        if prev_state < 0:
            prev_state = 0

        offset = 0
        if prev_state in (1, 2):
            delim = self._triple_dq if prev_state == 1 else self._triple_sq
            match = delim.match(text, offset)
            if match.hasMatch():
                end = match.capturedStart() + 3
                self.setFormat(0, end, str_fmt)
                offset = end
                prev_state = 0
            else:
                self.setFormat(0, len(text), str_fmt)
                self.setCurrentBlockState(prev_state)
                return

        while offset < len(text):
            dq_match = self._triple_dq.match(text, offset)
            sq_match = self._triple_sq.match(text, offset)
            dq_start = dq_match.capturedStart() if dq_match.hasMatch() else len(text)
            sq_start = sq_match.capturedStart() if sq_match.hasMatch() else len(text)
            if dq_start >= len(text) and sq_start >= len(text):
                break
            if dq_start <= sq_start:
                close_match = self._triple_dq.match(text, dq_start + 3)
                if close_match.hasMatch():
                    end = close_match.capturedStart() + 3
                    self.setFormat(dq_start, end - dq_start, str_fmt)
                    offset = end
                else:
                    self.setFormat(dq_start, len(text) - dq_start, str_fmt)
                    self.setCurrentBlockState(1)
                    return
            else:
                close_match = self._triple_sq.match(text, sq_start + 3)
                if close_match.hasMatch():
                    end = close_match.capturedStart() + 3
                    self.setFormat(sq_start, end - sq_start, str_fmt)
                    offset = end
                else:
                    self.setFormat(sq_start, len(text) - sq_start, str_fmt)
                    self.setCurrentBlockState(2)
                    return

        self.setCurrentBlockState(0)


# ------------------------------------------------------------------
# Preview Page
# ------------------------------------------------------------------


class PreviewPage(QWizardPage):
    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Scheduling Block Preview")
        self.setSubTitle(
            "Review the generated Astrid scheduling blocks. "
            "Select a block on the left to view and edit."
        )

        self._current_label: str = ""

        layout = QVBoxLayout()
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Left: SB list
        self._sb_list = QListWidget()
        self._sb_list.setToolTip("Select a scheduling block to view or edit")
        self._splitter.addWidget(self._sb_list)

        # Right: editor + restore button
        right_widget = QWidget()
        right_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._restore_btn = QPushButton("Restore Defaults")
        self._restore_btn.setToolTip(
            "Discard manual edits and restore the auto-generated scheduling block"
        )
        self._restore_btn.clicked.connect(self._restore_current)
        btn_row.addWidget(self._restore_btn)
        right_layout.addLayout(btn_row)

        self._editor = QPlainTextEdit()
        self._editor.setToolTip("Astrid scheduling block Python script — edit directly if needed")
        self._editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        mono_font = QFont("Monospace")
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self._editor.setFont(mono_font)
        self._highlighter = _PythonHighlighter(self._editor.document())
        right_layout.addWidget(self._editor)

        self._splitter.addWidget(right_widget)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 3)

        layout.addWidget(self._splitter)
        self.setLayout(layout)

        self._sb_list.currentTextChanged.connect(self._on_sb_selected)

    # ------------------------------------------------------------------
    # Page lifecycle
    # ------------------------------------------------------------------

    def initializePage(self):
        self._generate_all_sbs()
        self._sb_list.blockSignals(True)
        self._sb_list.clear()
        for label in self.observation.generated_sbs:
            self._sb_list.addItem(label)
        self._sb_list.blockSignals(False)
        self._current_label = ""
        if self.observation.generated_sbs:
            self._sb_list.setCurrentRow(0)

    def validatePage(self):
        self._save_current_sb()
        return True

    # ------------------------------------------------------------------
    # SB switching
    # ------------------------------------------------------------------

    def _on_sb_selected(self, label: str):
        if not label:
            return
        self._save_current_sb()
        self._current_label = label
        self._load_sb(label)

    def _save_current_sb(self):
        if self._current_label and self._current_label in self.observation.generated_sbs:
            self.observation.generated_sbs[self._current_label] = self._editor.toPlainText()

    def _load_sb(self, label: str):
        text = self.observation.generated_sbs.get(label, "")
        self._editor.setPlainText(text)

    def _restore_current(self):
        if not self._current_label:
            return
        self._generate_all_sbs()
        self._load_sb(self._current_label)

    # ------------------------------------------------------------------
    # SB generation
    # ------------------------------------------------------------------

    def _generate_all_sbs(self):
        sbs: OrderedDict[str, str] = OrderedDict()

        for setup in self.observation.source_setups:
            src = self._find_source(setup.source_name)
            if src is None:
                continue
            for config in setup.receiver_configs:
                label = f"{setup.source_name} — {config.display_name}"
                sbs[label] = self._generate_sb(src, setup, config)

        self.observation.generated_sbs = sbs

    def _find_source(self, name):
        for src in self.observation.sources:
            if src.name == name:
                return src
        return None

    def _generate_sb(self, src, setup, config):
        lines = []
        strategy = self.observation.strategy

        # Header
        lines.append(f"# GBT Spectral Line Observation — {src.name} — {config.display_name}")
        lines.append("# Generated by Spectral-SB-GUI")
        lines.append("")

        # Catalog
        lines.extend(self._generate_catalog(src))

        # Configuration
        safe = _safe_name(src.name)
        config_name = f"config_{safe}_{_safe_name(config.receiver_name)}"
        lines.extend(self._generate_config_block(config_name, src, config))

        # Observation sequence
        lines.append("# === Observation Sequence ===")
        lines.append("")
        lines.append("ResetConfig()")

        if strategy.do_initial_pointing or strategy.do_initial_focus:
            lines.append(f"AutoPeakFocus(location='{src.name}')")
            lines.append("")

        if strategy.do_auto_oof and strategy.auto_oof_available:
            lines.append(f"AutoOOF(location='{src.name}')")
            lines.append("")

        lines.append(f"Slew('{src.name}')")
        lines.append(f"Configure({config_name})")
        lines.append("Balance()")

        if config.switching_mode == SwitchingMode.FREQUENCY:
            lines.append(f"Track('{src.name}', None, 300)")
        else:
            lines.append(f"OnOff('{src.name}', Offset('J2000', 0.0, 30.0/60.0), 300)")

        lines.append("")
        return "\n".join(lines)

    def _generate_catalog(self, src):
        lines = []

        if src.coord_system == CoordSystem.J2000:
            lines.append('Catalog("""')
            lines.append("format=spherical")
            lines.append("coordmode=J2000")
            head = "HEAD = NAME                              RA              DEC"
            if src.velocity_kms != 0:
                head += "             VELOCITY"
            lines.append(head)
            entry = f"{src.name:40s} {src.coord1:16s} {src.coord2:16s}"
            if src.velocity_kms != 0:
                entry += f" {src.velocity_kms}"
            lines.append(entry)
            lines.append('""")')
        elif src.coord_system == CoordSystem.B1950:
            lines.append('Catalog("""')
            lines.append("format=spherical")
            lines.append("coordmode=B1950")
            head = "HEAD = NAME                              RA              DEC"
            if src.velocity_kms != 0:
                head += "             VELOCITY"
            lines.append(head)
            entry = f"{src.name:40s} {src.coord1:16s} {src.coord2:16s}"
            if src.velocity_kms != 0:
                entry += f" {src.velocity_kms}"
            lines.append(entry)
            lines.append('""")')
        else:
            lines.append('Catalog("""')
            lines.append("format=spherical")
            lines.append("coordmode=Galactic")
            head = "HEAD = NAME                              GLON            GLAT"
            if src.velocity_kms != 0:
                head += "            VELOCITY"
            lines.append(head)
            entry = f"{src.name:40s} {src.coord1:16s} {src.coord2:16s}"
            if src.velocity_kms != 0:
                entry += f" {src.velocity_kms}"
            lines.append(entry)
            lines.append('""")')

        lines.append("")
        return lines

    def _generate_config_block(self, config_name, src, config):
        lines = []

        # Determine swmode keyword
        if config.switching_mode == SwitchingMode.FREQUENCY:
            swmode = "sp"
        else:
            swmode = "tp"

        rest_freq_str = ", ".join(f"{f:.4f}" for f in config.rest_freqs_mhz)
        doppler_freq = config.obs_freqs_mhz[0] if config.obs_freqs_mhz else config.rest_freqs_mhz[0]

        vframe = _VFRAME_MAP.get(src.velocity_frame, "Topocentric")
        vdef = _VDEF_MAP.get(src.velocity_definition, "Radio")

        lines.append(f'{config_name} = """')
        lines.append("    obstype = 'Spectroscopy'")
        lines.append("    backend = 'VEGAS'")
        lines.append(f"    receiver = '{config.receiver_name}'")
        lines.append(f"    restfreq = {rest_freq_str}")
        lines.append(f"    bandwidth = {config.bandwidth_mhz}")
        lines.append(f"    dopplertrackfreq = {doppler_freq:.4f}")
        lines.append(f"    swmode = '{swmode}'")
        lines.append(f"    swper = {config.swper}")
        lines.append(f"    tint = {config.tint}")
        lines.append(f"    vframe = '{vframe}'")
        lines.append(f"    vdef = '{vdef}'")

        if config.switching_mode == SwitchingMode.FREQUENCY:
            lines.append(f"    swfreq = {config.swfreq_mhz}, 0")
            lines.append("    noisecal = 'lo'")
        else:
            lines.append("    swmode = 'tp'")
            lines.append("    noisecal = 'lo'")

        lines.append(f"    vegas.nchan = {config.channels}")
        lines.append("    vegas.subband = 1")
        lines.append('"""')
        lines.append("")

        return lines
