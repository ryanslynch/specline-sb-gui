**THIS TOOL IS IN DEVELOPMENT AND SHOULD NOT YET BE USED BY OBSERVERS TO CREATE ASTRID SCHEDULING BLOCKS**

# Spectral Line Scheduling Block GUI

A wizard-style GUI for astronomers using the [Green Bank Telescope
(GBT)](https://greenbankobservatory.org/science/gbt/) to observe
spectroscopic sources.  The GUI guides you through entering your
sources, rest frequencies, and science goals, then auto-generates
[Astrid](https://gbtdocs.readthedocs.io/en/latest/references/observing/configure.html)
scheduling blocks with the correct GBT-specific technical setup.

## Features

- **Source entry** — Enter sources manually, upload an existing Astrid catalog,
  or look up coordinates automatically via SIMBAD or NED
- **Rest frequency entry** — Enter frequencies manually, upload from file, or
  search [Splatalogue](https://splatalogue.online/) by molecular species name
- **Automatic receiver selection** — Picks the minimum set of GBT receivers
  needed to cover all requested frequencies (with Doppler correction)
- **Automatic VEGAS mode selection** — Chooses the coarsest backend mode that
  meets your spectral resolution requirement
- **Automatic switching mode selection** — Recommends frequency switching for
  narrow lines and position switching for broad or RFI-affected lines, with
  validation against GBT Memo 288 minimum switching periods
- **Pointing/focus strategy** — Configures AutoPeakFocus/AutoPeak/AutoFocus
  cadences and AutoOOF for high-frequency observations (≥40 GHz)
- **Scheduling block preview** — Python syntax-highlighted preview before saving
- **Save to file** — Writes ready-to-load Astrid scheduling blocks

## Requirements

- Python ≥ 3.10
- PySide6 ≥ 6.5
- astropy ≥ 5.0
- astroquery ≥ 0.4

## Installation

### From source (pip)

```bash
git clone https://github.com/ryanslynch/specline-sb-gui.git
cd specline-sb-gui
pip install .
```

For development (adds pytest and ruff):

```bash
pip install -e ".[dev]"
```

### From source (conda)

```bash
git clone https://github.com/ryanslynch/specline-sb-gui.git
cd specline-sb-gui
conda env create -f environment.yaml
conda activate specline-sb-gui
pip install --no-deps -e .
```

## Running

```bash
spectral-sb-gui
```

## Development

```bash
# Run tests
pytest

# Lint and format
ruff check .
ruff format .
```

## Wizard Pages

1. **Sources** — Source names, coordinates, velocities
2. **Rest Frequencies** — Species/transitions and spectral resolution per source
3. **Observing Setup** — Auto-selected receivers, VEGAS modes, switching
   parameters, and integration time per source group
4. **Observation Strategy** — Pointing/focus calibration cadence and AutoOOF
   setup per source group
5. **Preview** — Syntax-highlighted scheduling block preview
6. **Save** — Save scheduling blocks to disk

## Reference Documentation

- [GBT Observers' Guide](https://gbtdocs.readthedocs.io/)
- [GBT Proposer's Guide](https://www.gb.nrao.edu/scienceDocs/GBTpg.pdf)
- [GBT Memo 288](https://library.nrao.edu/public/memos/gbt/GBT_288.pdf) — Minimum switching periods for VEGAS

## License

See [LICENSE](LICENSE).
