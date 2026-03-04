# Spectral Line Scheduling Block GUI — Requirements Specification

## Page 1: Sources

Users add information about the sources they want to observe.  Users
can enter information manually, upload a pre-existing [Astrid
Catalog](https://gbtdocs.readthedocs.io/en/latest/references/observing/catalog.html),
or search by name using
[SIMBAD](https://simbad.u-strasbg.fr/simbad/) and
[NED](https://ned.ipac.caltech.edu/).  If a name search returns
multiple matches, the user selects one.

### Source Fields

| Field | Required | Default | Notes |
|-------|----------|---------|-------|
| Name | Yes | — | Must be unique across all sources |
| Coordinates | Yes | — | Equatorial (RA/Dec) or Galactic (l/b) |
| Coordinate System | Yes | J2000 | J2000, B1950, or Galactic |
| Velocity | No | 0 km/s | In km/s |
| Velocity Frame | No | Topocentric | Topocentric, Barycentric, LSRK, Galactic, or CMB |
| Velocity Definition | No | Radio | Radio, Optical, or Relativistic |

### Coordinate Format

- RA: sexagesimal (HH:MM:SS.SS) or decimal hours
- Dec: sexagesimal (DD:MM:SS.SS) or decimal degrees
- Galactic: decimal degrees only
- Note: RA is always in units of hours (not degrees), matching the
  Astrid catalog format

---

## Page 2: Rest Frequencies

For each source, users specify the rest frequencies to observe and
the desired resolution.

- Frequencies in MHz; must be within the GBT's frequency range
- Resolution specified as spectral resolution (kHz) or velocity
  resolution (km/s)
- Entry options: manual, upload from file, or search
  [Splatalogue](https://astroquery.readthedocs.io/en/latest/splatalogue/splatalogue.html)
- If a Splatalogue search returns multiple species, the user can
  select one or more results
- Users can apply the same frequency setup to some/all sources, or
  configure each source independently

---

## Page 3: Observing Setup

The GUI auto-selects the best observing setup based on Pages 1-2,
then the user reviews and can make changes.  This page populates the
[configuration section](https://gbtdocs.readthedocs.io/en/latest/references/observing/configure.html)
of the scheduling blocks.

### Receiver Selection

Choose the minimum number of GBT receivers needed to cover all
requested frequencies.  Use the Doppler-shifted frequency (not the
rest frequency) when checking receiver coverage.  See
`data/receivers.json` for receiver frequency ranges.

For multi-beam receivers (KFPA, Argus), users can apply the same
rest frequency setup to all beams or assign different setups per beam.

### Switching Parameters

See the "Switching Parameters and Integration Time" section in
`CLAUDE.md` for the full decision logic, defaults, and validation
rules.  Key points:

- Auto-select frequency switching or position switching based on
  expected line width
- Default `swper` and `tint` are both 1 second
- Warn if the user selects a switching period below the minimum
  recommended value from GBT Memo 288
- Include user-facing help text summarizing when each switching
  mode is appropriate

### VEGAS Mode Selection

Using the velocity information from Page 1 and the frequency/resolution
from Page 2, choose the best VEGAS mode for each source and frequency.
Minimize the number of distinct VEGAS modes needed.  See
`data/vegas_modes.json` for mode specifications and constraints.

Use Doppler-shifted frequencies (not rest frequencies) when
determining spectral window placement.

---

## Page 4: Observing Strategy

Auto-generate an observing strategy using all prior information:

- Initial pointing and focusing corrections
- AutoOOF procedure (when appropriate for the receiver)
- Main observing procedures using the appropriate [scan
  types](https://gbtdocs.readthedocs.io/en/latest/references/observing/scan_types.html)
- Additional pointing/focusing corrections per best practices

Users can modify the strategy (skip procedures, change scan types).

---

## Page 5: Scheduling Block Review

Generate complete Astrid [scheduling
blocks](https://gbtdocs.readthedocs.io/en/latest/references/observing/sb_commands.html).

- One scheduling block per unique combination of source and receiver
- Multiple VEGAS setups sharing the same source and receiver go in
  the same scheduling block
- Display in an editor with Python syntax highlighting
- Users can edit directly
- See [example scheduling
  blocks](https://gbtdocs.readthedocs.io/en/latest/references/observing/sb_examples.html)
  for spectral line best practices

---

## Page 6: Save

Allow the user to save each scheduling block to disk.
