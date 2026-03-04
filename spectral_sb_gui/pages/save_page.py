import os
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWizardPage,
)

from spectral_sb_gui.models.observation import ObservationModel


def _auto_filename(label: str) -> str:
    """Convert an SB label to a safe filename with .py extension."""
    name = label.replace(" ", "_")
    name = re.sub(r"[^\w\-.]", "", name)
    if not name.endswith(".py"):
        name += ".py"
    return name


class SavePage(QWizardPage):
    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Save")
        self.setSubTitle("Save scheduling blocks to files.")

        self._saved_paths: dict[str, str] = {}
        self._last_directory: str = os.getcwd()
        self._sb_labels: list[str] = []

        layout = QVBoxLayout()

        self._table = QTableWidget()
        self._table.setToolTip("Scheduling blocks and their save status")
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Scheduling Block", "File", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._save_all_btn = QPushButton("Save All")
        self._save_all_btn.setToolTip("Save all unsaved scheduling blocks to files")
        self._save_all_btn.clicked.connect(self._save_all)
        btn_layout.addWidget(self._save_all_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def initializePage(self):
        self._saved_paths.clear()
        self._sb_labels = list(self.observation.generated_sbs.keys())

        self._table.setRowCount(len(self._sb_labels))
        for row, label in enumerate(self._sb_labels):
            item = QTableWidgetItem(label)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 0, item)

            btn = QPushButton("Save...")
            btn.setToolTip("Save this scheduling block to a file")
            btn.clicked.connect(lambda checked, lbl=label: self._save_one(lbl))
            self._table.setCellWidget(row, 1, btn)

            self._set_status(row, "Unsaved")

    def validatePage(self):
        unsaved = [lbl for lbl in self._sb_labels if lbl not in self._saved_paths]
        if unsaved:
            reply = QMessageBox.question(
                self,
                "Unsaved Scheduling Blocks",
                "Some scheduling blocks have not been saved. Finish anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            return reply == QMessageBox.StandardButton.Yes
        return True

    def _set_status(self, row: int, text: str, saved: bool = False):
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if saved:
            item.setForeground(QColor("#2e7d32"))
        else:
            item.setForeground(QColor("#e65100"))
        self._table.setItem(row, 2, item)

    def _save_one(self, label: str) -> bool:
        default_path = os.path.join(self._last_directory, _auto_filename(label))
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            f"Save {label}",
            default_path,
            "Python files (*.py);;All files (*)",
        )
        if not filepath:
            return False

        sb_text = self.observation.generated_sbs[label]
        with open(filepath, "w") as f:
            f.write(sb_text)

        self._saved_paths[label] = filepath
        self._last_directory = os.path.dirname(filepath)
        self.observation.output_path = self._last_directory

        row = self._sb_labels.index(label)
        self._set_status(row, filepath, saved=True)
        return True

    def _save_all(self):
        for label in self._sb_labels:
            if label not in self._saved_paths:
                if not self._save_one(label):
                    break
