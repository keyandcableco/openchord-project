"""
OpenChord — instruments/om-27/config.py
Instrument-specific configuration for the Suzuki Omnichord OM-27.

Verified against AY-5-1317A datasheet and OM-27 PCB schematic.
Hardware untested — confirm with oscilloscope before committing to PCB.
"""

from chord_logic import C, Cs, D, Ds, E, F, Fs, G, Gs, A, As, B
Db=Cs; Eb=Ds; Gb=Fs; Ab=Gs; Bb=As

# =============================================================================
# Instrument identity
# =============================================================================

INSTRUMENT_NAME    = "Suzuki Omnichord OM-27"
FIRMWARE_VERSION   = "OpenChord v1.0"
REPLACED_IC        = "AY-5-1317A"
DOWNSTREAM_DIVIDER = "CD4520 (replacing M747)"


# =============================================================================
# Power supply and output logic
#
# The OM-27 uses a center-negative 12V DC barrel jack (outer ring = +12V,
# center pin = GND). Two supply rails: +12V and +5V (from 78L05). No
# negative rail.
#
# The AY-5-1317A is P-channel MOS. In the OM-27, Suzuki ran it with
# VSS = +12V and VDD = GND — the standard trick for P-channel ICs on a
# positive supply. Logic levels:
#   Logic HIGH = +12V (VSS)
#   Logic LOW  = GND  (VDD)
#
# Confirmed: pin 5 (reset/mute) sits at +12V at rest, triggered by grounding.
#
# Output transistors: NPN (MMBT3904), open-collector to +12V.
#   GPIO LOW  → transistor OFF → collector pulled to +12V via 10kΩ → HIGH
#   GPIO HIGH → transistor ON  → collector pulled to GND             → LOW
#
# The M747/CD4520s are conventional positive-supply COS/MOS (VSS=GND,
# VDD=+12V) and clock on the positive-going edge. Our NPN open-collector
# outputs rising to +12V provide that edge correctly.
#
# UNVERIFIED — scope the output pins before committing to a PCB.
# Also worth trying direct GPIO first: 3.3V may register as valid HIGH
# on a 12V CMOS input (threshold typically 30-50% of VDD).
#
# PIO logic: non-inverted. set_init=OUT_LOW. SILENT = GPIO LOW permanently
# = transistor OFF = output pulled HIGH = M747 sees DC HIGH = no clocking.
# Wait — DC HIGH means the M747 never sees a falling edge, so it never
# clocks. Correct for silence.
# =============================================================================

CENTER_NEGATIVE = False   # VSS=+12V, VDD=GND — positive logic, NPN outputs


# =============================================================================
# GPIO assignments
# =============================================================================

# Tone outputs (5 channels via MMBT3904 NPN open-collector to +12V)
# Mapped to AY-5-1317A output pin footprint.
GPIO_ROOT = 0    # ROOT output  → AY pin 31 → CD4520 #1 clock A
GPIO_3RD  = 1    # 3rd output   → AY pin 29 → CD4520 #1 clock B
GPIO_5TH  = 2    # 5th output   → AY pin 28 → CD4520 #2 clock A
GPIO_7TH  = 3    # 7th output   → AY pin 32 → CD4520 #2 clock B
                 # only active when a 7th chord is selected; silent otherwise
GPIO_MO   = 4    # MO/Special Effect output → AY pin 34
                 # carries whichever chord element the AY-5-1315 selects
                 # via B1/B2/B3 (auto-bass sequencer)

# Pin 33 (7 Sel): grounding this enables the 7th output on AY pin 32.
# We drive it LOW when a 7th chord is active, HIGH otherwise.
GPIO_7SEL = 5    # → AY pin 33

# Key matrix rows (outputs, driven HIGH one at a time to scan)
# Each row has two AY pins — tie both pads together on the daughterboard.
GPIO_ROW_MAJ = 6   # AY pins 11 + 12  (Major row)
GPIO_ROW_MIN = 7   # AY pins 9  + 10  (Minor row)
GPIO_ROW_7TH = 8   # AY pins 7  + 8   (Seventh row)

# Key matrix columns (inputs, PULL_DOWN)
# The AY-5-1317A's frequency input pins (13-24) double as matrix columns.
# In the OM-27, only 9 of the 12 chromatic positions are wired to buttons.
# Unwired positions (F#=pin18, G#=pin16, A#=pin14) are left as NC.
# Column order follows chromatic pin order on the IC (pin 24=C down to 13=B).
GPIO_COL_C  = 9    # AY pin 24  (C)
GPIO_COL_Cs = 10   # AY pin 23  (C# / Db)
GPIO_COL_D  = 11   # AY pin 22  (D)
GPIO_COL_Ds = 12   # AY pin 21  (D# / Eb)
GPIO_COL_E  = 13   # AY pin 20  (E)
GPIO_COL_F  = 14   # AY pin 19  (F)
GPIO_COL_Fs = 15   # AY pin 18  (F# / Gb) — NC in OM-27, no button
GPIO_COL_G  = 16   # AY pin 17  (G)
GPIO_COL_Gs = 17   # AY pin 16  (G# / Ab) — NC in OM-27, no button
GPIO_COL_A  = 18   # AY pin 15  (A)
GPIO_COL_As = 19   # AY pin 14  (A# / Bb) — NC in OM-27, no button
GPIO_COL_B  = 20   # AY pin 13  (B)

# Special inputs
GPIO_POWER  = 21   # power enable out
GPIO_AK     = 22   # Any Key Down input (AY pin 30) — goes HIGH when any
                   # button pressed. Optional — we know this from scanning,
                   # but it may connect to downstream circuitry (amp gate?).
                   # Check PCB trace before deciding whether to wire this.
GPIO_MEMORY = 23   # Sustain/memory switch (AY pin 35, active HIGH = on)
                   # Logic 1 (+12V) activates memory in original IC.
                   # Wire existing memory switch between +12V and this GPIO,
                   # or use PULL_DOWN and read as active HIGH.
GPIO_RES    = 24   # Reset input (AY pin 5, active LOW = reset/mute)
                   # Repurposed as flat/sharp modifier button.
                   # Sits at +12V at rest; pressing grounds it.
                   # Keep any existing filter components on PCB trace.

# Auto-bass select from AY-5-1315 rhythm chip (AY-5-1317A pins 25-27)
# AY-5-1315 outputs at +12V logic — add voltage dividers before GPIOs.
# 68kΩ + 33kΩ divider: 12V → ~3.0V. Essential — do not skip.
GPIO_BASS_B3 = 25  # AY pin 25  (B3, MSB)
GPIO_BASS_B2 = 26  # AY pin 26  (B2)
GPIO_BASS_B1 = 27  # AY pin 27  (B1, LSB)

# Solder jumpers (read once at boot, open = pull-up HIGH, bridged = GND)
GPIO_JP1_SHARP        = 28  # open = flat modifier, GND = sharp modifier
GPIO_JP2_BARRY_HARRIS = 29  # open = BH off, GND = BH on

# MIDI out (optional, harmless if unconnected)
# TODO: confirm which GPIO supports UART1 TX on RP2350-Zero and assign.
GPIO_MIDI_TX = 20     # UART1 TX on GPIO 20 (RP2350 alternate mapping)
                       # GPIO 20 maps to AY pin 18 (F# column) which is
                       # unwired in the OM-27 — no F# button exists.
                       # Safe to repurpose as MIDI TX.


# =============================================================================
# Key matrix layout
# =============================================================================

MATRIX_ROW_PINS = [GPIO_ROW_MAJ, GPIO_ROW_MIN, GPIO_ROW_7TH]

# All 12 chromatic column GPIOs in order C → B
# The 3 unwired columns (F#, G#, A#) are included but will never fire
# since no button connects to those AY pins in the OM-27.
MATRIX_COL_PINS = [
    GPIO_COL_C,  GPIO_COL_Cs, GPIO_COL_D,  GPIO_COL_Ds,
    GPIO_COL_E,  GPIO_COL_F,  GPIO_COL_Fs, GPIO_COL_G,
    GPIO_COL_Gs, GPIO_COL_A,  GPIO_COL_As, GPIO_COL_B
]

ROW_TO_TYPE = ['maj', 'min', 'dom7']

# Chromatic column order C through B — matches AY-5-1317A pin order
# F#, G#, A# positions included but unwired in OM-27
COL_TO_ROOT_NORMAL = [C,  Cs, D,  Ds, E,  F,  Fs, G,  Gs, A,  As, B ]

# Flat modifier: lower each root 1 semitone
# Reveals: B→Bb, E→Eb, A→Ab, D→Db, G→Gb, C→B, F→E etc.
# The three unwired columns (Fs, Gs, As) shift to F, G, A — already wired,
# so those remain silent (no button). Net new roots: depends on layout.
COL_TO_ROOT_FLAT   = [B,  C,  Cs, D,  Ds, E,  F,  Fs, G,  Gs, A,  As]

# Sharp modifier: raise each root 1 semitone
COL_TO_ROOT_SHARP  = [Cs, D,  Ds, E,  F,  Fs, G,  Gs, A,  As, B,  C ]


# =============================================================================
# Tuning
# =============================================================================

TUNING_OCTAVE = 7      # generate in octave 7; CD4520s divide to 6, 5, 4
TUNING_A4_HZ  = 440.0  # standard concert pitch — change here to retune
                        # e.g. 432.0 for old-style tuning, 443.0 for
                        # sharp orchestral pitch, 415.0 for baroque


# =============================================================================
# B1/B2/B3 truth table for MO output (auto-bass / special effect)
# From AY-5-1317A datasheet, pins 25-27.
# Key: (B1, B2, B3) → interval in semitones from root
# None = no change from last selection (hold)
# =============================================================================

BASS_SELECT_TABLE = {
    (0, 0, 0): None,   # no change / hold last
    (0, 0, 1): 0,      # ROOT
    (0, 1, 0): 7,      # 5th
    (0, 1, 1): None,   # 3rd — chord-aware, handled in get_auto_bass()
    (1, 1, 1): 10,     # 7th (minor 7th interval — adjust per chord type)
    (1, 1, 0): 5,      # 4th
    (1, 0, 1): 9,      # 6th
}
# Note: 3rd (0,1,1) is handled separately because it's chord-aware:
#   Major/7th chords → major 3rd (4 semitones)
#   Minor chords     → minor 3rd (3 semitones)
# 7th (1,1,1) is similarly chord-aware:
#   dom7/min7 → minor 7th (10), maj7 → major 7th (11)


# =============================================================================
# Startup jingle encoding
# =============================================================================
JINGLE_BOOT    = C
JINGLE_NORMAL  = C
JINGLE_FLAT    = Cs
JINGLE_SHARP   = D
JINGLE_BH_ON   = E
JINGLE_BH_OFF  = Eb
JINGLE_MEM_ON  = G
JINGLE_MEM_OFF = Fs
JINGLE_TUNING  = A
