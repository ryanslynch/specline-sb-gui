# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

We are building a wizard-style GUI for astronomers using the Green
Bank Telescope (GBT) to observe spectroscopic sources.  The GUI
collects information about the user's sources and science goals, then
auto-generates Astrid scheduling blocks with the correct GBT-specific
technical setup.  See `docs/SPEC.md` for the full requirements.

## Tech Stack

- **Language:** Python >= 3.10
- **GUI framework:** PySide6 (Qt for Python)
- **Key libraries:** astropy, astroquery (for SIMBAD, NED, Splatalogue lookups)
- **Build:** setuptools with pyproject.toml
- **Testing:** pytest
- **Linting/formatting:** ruff

## Quick Reference

```bash
# Install in development mode
pip install -e ".[dev]"

# Run the application
spectral-sb-gui

# Run tests
pytest

# Run a single test file or specific test
pytest tests/test_source_page.py
pytest tests/test_source_page.py::test_function_name -v

# Lint and format
ruff check .
ruff format .
```

## Project Structure

```
spectral_sb_gui/
    app.py              # Entry point (main function)
    wizard.py           # QWizard subclass, page registration
    models/
        observation.py  # Dataclasses and enums for observation state
    pages/
        source_page.py
        freq_page.py
        setup_page.py
        strategy_page.py
        preview_page.py
        save_page.py
    data/
        receivers.json  # GBT receiver specs
        vegas_modes.json # VEGAS spectral line mode specs
```

## Coding Conventions

Follow the patterns established in the [pulsar scheduling block
GUI](https://github.com/ryanslynch/psr-sb-gui):

- **Architecture:** QWizard with one QWizardPage per step.  A shared
  `ObservationModel` dataclass is passed to every page.
- **Page pattern:** Each page lives in its own file under `pages/`.
  Pages accept the `ObservationModel` in `__init__`, populate the UI
  in `initializePage()`, and save state back to the model in
  `validatePage()`.
- **Data models:** Use dataclasses and enums in `models/observation.py`.
- **Naming:** snake_case for files, functions, and variables; PascalCase
  for classes.  Page files named after their function (e.g.,
  `source_page.py`).
- **Validation:** Validate user input in the page where it's entered.
  Show `QMessageBox` warnings for errors.
- **Reuse from pulsar GUI:** The scheduling block preview page
  (Python syntax-highlighted editor with SB list) and the save page
  can be adapted directly.  Match the overall look, feel, and layout.

## Reference Data

Structured reference data for GBT receivers and VEGAS modes is in
`data/receivers.json` and `data/vegas_modes.json`.  Use these files
for programmatic lookups (receiver selection, mode optimization)
rather than hardcoding values.

**Important:** When determining which receiver covers a given
frequency, you must Doppler-shift the rest frequency using each
source's velocity before comparing against receiver frequency ranges.

## Switching Parameters and Integration Time

The Observing Setup page must auto-select appropriate switching
parameters.  The rules below should be implemented in the GUI logic
and also summarized as user-facing help text so observers have context
for the defaults.

### Choosing a Switching Mode

- **Frequency switching** is appropriate for narrow spectral lines
  with widths less than ~10 km/s.  The frequency shift should be a
  few times the expected line width.  When possible, choose a
  frequency shift less than half the observing bandwidth — this
  enables in-band frequency switching, which is more efficient.
  (See Section 5.3 of the [GBT Proposer's
  Guide](https://www.gb.nrao.edu/scienceDocs/GBTpg.pdf).)
- **Position switching** should be used for broad lines (widths
  greater than ~100 km/s), narrow lines in spectrally crowded
  regions, or frequencies with significant radio frequency
  interference (RFI).
- **Default:** If the best choice is ambiguous, default to position
  switching.

### Defaults

- Default switching period (`swper`): **1 second**
- Default integration time (`tint`): **1 second**

### Minimum Switching Period Validation

If the user changes the switching period, the GUI should warn if the
value falls below the minimum recommended switching period from [GBT
Memo 288](https://library.nrao.edu/public/memos/gbt/GBT_288.pdf)
(Kepley, Maddalena, & Prestage 2014).  This GUI is for pointed
observations only, so the relevant tables are:

- **Without Doppler tracking:** Use Table 2 of GBT Memo 288.
  The minimum switching period is the greater of the hardware minimum
  and the value required to keep blanking below 10% of the data.
  The minimum switching period for frequency switching should always
  be greater than 0.25 s due to LO hardware limitations.
- **With Doppler tracking:** Use Table 4 of GBT Memo 288.
  This table lists the frequency (`nu_min`) above which Doppler
  blanking becomes significant for each VEGAS mode and switching
  type.  Below `nu_min`, use the switching periods from Table 2.
  At or above `nu_min`, use the switching period from Table 4.

The minimum switching period data from these tables should be stored
in `data/vegas_modes.json` alongside the mode specifications.

## Reference Documentation

The following GBT documentation should be consulted when implementing
features that depend on telescope-specific behavior:

- [GBT Receivers](https://gbtdocs.readthedocs.io/en/latest/references/receivers.html)
- [VEGAS Spectral Line Backend](https://gbtdocs.readthedocs.io/en/latest/references/backends/vegas.html)
- [Configuration Keywords](https://gbtdocs.readthedocs.io/en/latest/references/observing/configure.html)
- [Astrid Catalogs](https://gbtdocs.readthedocs.io/en/latest/references/observing/catalog.html)
- [Scan Types](https://gbtdocs.readthedocs.io/en/latest/references/observing/scan_types.html)
- [SB Commands](https://gbtdocs.readthedocs.io/en/latest/references/observing/sb_commands.html)
- [Example Scheduling Blocks](https://gbtdocs.readthedocs.io/en/latest/references/observing/sb_examples.html)
- [HI Position-Switched Tutorial](https://gbtdocs.readthedocs.io/en/latest/tutorials/hi_psw_tutorial.html)
- [GBT Observing Tactics](https://gbtdocs.readthedocs.io/en/latest/how-tos/general_guides/gbt_tactics.html)
- [Argus Observing Instructions](https://gbtdocs.readthedocs.io/en/latest/how-tos/receivers/argus/argus_obs.html)
- [GBT Proposer's Guide (PDF)](https://www.gb.nrao.edu/scienceDocs/GBTpg.pdf) — Section 5.3 covers switching modes
- [GBT Memo 288 (PDF)](https://library.nrao.edu/public/memos/gbt/GBT_288.pdf) — Minimum recommended switching periods for VEGAS

It's possible that some of this reference material is out of date or
incorrect, so if anything seems inconsistent or doesn't make sense,
please ask me for clarification.
