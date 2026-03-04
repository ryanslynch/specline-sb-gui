import sys

from PySide6.QtWidgets import QApplication

from spectral_sb_gui.wizard import SpectralLineWizard


def main():
    app = QApplication(sys.argv)
    wizard = SpectralLineWizard()
    wizard.show()
    sys.exit(app.exec())
