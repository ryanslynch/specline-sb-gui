from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CoordSystem(Enum):
    J2000 = "J2000"
    B1950 = "B1950"
    GALACTIC = "Galactic"


class VelocityFrame(Enum):
    TOPOCENTRIC = "Topocentric"
    BARYCENTRIC = "Barycentric"
    LSRK = "LSRK"
    GALACTIC = "Galactic"
    CMB = "CMB"


class VelocityDefinition(Enum):
    RADIO = "Radio"
    OPTICAL = "Optical"
    RELATIVISTIC = "Relativistic"


class SwitchingMode(Enum):
    FREQUENCY = "Frequency"
    POSITION = "Position"


class ResolutionUnit(Enum):
    KHZ = "kHz"
    KM_S = "km/s"


@dataclass
class RestFrequency:
    """A single rest frequency with desired resolution."""

    freq_mhz: float = 0.0
    species: str = ""
    transition: str = ""
    resolution_value: float = 0.0
    resolution_unit: ResolutionUnit = ResolutionUnit.KHZ
    line_width_kms: Optional[float] = None  # expected line width in km/s (optional)


@dataclass
class Source:
    name: str = ""
    coord_system: CoordSystem = CoordSystem.J2000
    coord1: str = ""  # RA (sexagesimal) or l (degrees)
    coord2: str = ""  # Dec (sexagesimal) or b (degrees)
    velocity_kms: float = 0.0
    velocity_frame: VelocityFrame = VelocityFrame.TOPOCENTRIC
    velocity_definition: VelocityDefinition = VelocityDefinition.RADIO
    rest_freqs: list[RestFrequency] = field(default_factory=list)


@dataclass
class ReceiverConfig:
    """Configuration for a single receiver setup."""

    receiver_name: str = ""
    display_name: str = ""
    receiver_type: str = ""  # "prime_focus" or "gregorian"
    num_beams: int = 1
    vegas_mode: int = 0
    bandwidth_mhz: float = 0.0
    channels: int = 0
    resolution_khz: float = 0.0
    switching_mode: SwitchingMode = SwitchingMode.POSITION
    swper: float = 1.0
    swfreq_mhz: float = 0.0  # frequency throw for freq switching
    tint: float = 1.0
    doppler_tracking: bool = True
    total_duration_s: float = 0.0  # total integration time in seconds (0 = unset)
    rest_freqs_mhz: list[float] = field(default_factory=list)
    obs_freqs_mhz: list[float] = field(default_factory=list)
    beam_rest_freqs: Optional[dict[int, list[float]]] = None  # per-beam freq assignment
    active_beams: Optional[list[int]] = None  # None = use all beams


@dataclass
class SourceSetup:
    """Links a source to its receiver configurations."""

    source_name: str = ""
    receiver_configs: list[ReceiverConfig] = field(default_factory=list)


@dataclass
class ObservingStrategy:
    # Pointing and focus
    do_pointing: bool = True
    do_focus: bool = True
    # Cadence: "initial_only", "every_2_3hr", "hourly", "every_30_60min", "every_30_45min"
    pf_cadence: str = "initial_only"

    # AutoOOF (active surface correction, 40 GHz+)
    do_auto_oof: bool = False
    # Which receiver to use for OOF: "auto" (Ka if available), "ka", "q", "primary"
    oof_receiver: str = "auto"
    oof_source: str = ""  # optional calibrator source name for AutoOOF

    # Scan parameters
    scan_duration_s: float = 300.0  # seconds per on/off or track scan
    n_scans: int = 1  # number of scan repetitions


@dataclass
class ObservationModel:
    """Top-level container for the entire observation state."""

    sources: list[Source] = field(default_factory=list)

    # Frequency config: if True, all sources share the same rest freqs
    apply_freqs_to_all: bool = True
    global_rest_freqs: list[RestFrequency] = field(default_factory=list)

    # Observing setup (populated by setup page)
    source_setups: list[SourceSetup] = field(default_factory=list)

    # Per-group strategies: key = "source_name — receiver_display_name"
    strategies: dict[str, ObservingStrategy] = field(default_factory=dict)

    # Generated scheduling blocks: label -> script text
    generated_sbs: dict[str, str] = field(default_factory=dict)

    # Output
    output_path: str = ""
