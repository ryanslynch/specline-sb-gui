from PySide6.QtWidgets import QWizard

from spectral_sb_gui.models.observation import ObservationModel
from spectral_sb_gui.pages.source_page import SourcePage
from spectral_sb_gui.pages.freq_page import FreqPage
from spectral_sb_gui.pages.setup_page import SetupPage
from spectral_sb_gui.pages.strategy_page import StrategyPage
from spectral_sb_gui.pages.preview_page import PreviewPage
from spectral_sb_gui.pages.save_page import SavePage

PAGE_SOURCE = 0
PAGE_FREQ = 1
PAGE_SETUP = 2
PAGE_STRATEGY = 3
PAGE_PREVIEW = 4
PAGE_SAVE = 5


class SpectralLineWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.observation = ObservationModel()

        self.setWindowTitle("GBT Spectral Line Observation Setup")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        self.setPage(PAGE_SOURCE, SourcePage(self.observation, self))
        self.setPage(PAGE_FREQ, FreqPage(self.observation, self))
        self.setPage(PAGE_SETUP, SetupPage(self.observation, self))
        self.setPage(PAGE_STRATEGY, StrategyPage(self.observation, self))
        self.setPage(PAGE_PREVIEW, PreviewPage(self.observation, self))
        self.setPage(PAGE_SAVE, SavePage(self.observation, self))

        self.resize(1013, 731)
