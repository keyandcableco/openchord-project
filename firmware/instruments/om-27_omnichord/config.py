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
# The OM-27 has two supply rails: +12V and +5V (from 78L05). No negative rail.
#
# The AY-5-1317A is P-channel MOS. In the OM-27, Suzuki almost certainly
# wired VSS = +12V and VDD = GND — the standard approach for running
# P-channel ICs on a positive supply. Logic levels:
#   Logic HIGH = +12V (VSS)
#   Logic LOW  = GND  (VDD)
#
# Confirmed: pin 5 (reset/mute) sits at +12V at rest, triggered by grounding.
#
# Output transistors: NPN (MMBT3904), open-collector to +12V.
#   GPIO LOW  → transistor OFF → collector pulled to +12V via 10kΩ → HIGH
#   GPIO HIGH → transistor ON  → collector pulled to GND             → LOW
#
# UNVERIFIED — scope the output pins before committing to PCB.
# Worth trying direct GPIO first on bench: 3.3V may register as valid
# HIGH on a 12V CMOS input (threshold typically 30-50% of VDD).
# =============================================================================

CENTER_NEGATIVE = False


# =============================================================================
# GPIO assignments
# =============================================================================

# Tone outputs (5 channels, NPN MMBT3904 open-collector to +12V)
GPIO_ROOT = 0    # ROOT output  → AY pin 31 → CD4520 #1 clock A
GPIO_3RD  = 1    # 3RD output   → AY pin 29 → CD4520 #1 clock B
GPIO_5TH  = 2    # 5TH output   → AY pin 28 → CD4520 #2 clock A
GPIO_7TH  = 3    # 7TH output   → AY pin 32 → CD4520 #2 clock B
                 # silent (DC HIGH) on non-7th chords
GPIO_MO   = 4    # MO / special effect → AY pin 34
                 # carries auto-bass tone selected by AY-5-1315 B1/B2/B3

# 7th Select (AY pin 33): ground enables 7th output on pin 32.
# We drive LOW when a 7th chord is active, HIGH otherwise.
GPIO_7SEL = 5    # → AY pin 33

# Key matrix rows (outputs, idle HIGH, driven LOW to scan)
# Each row has two AY pins — tie both pads together on the daughterboard.
GPIO_ROW_MAJ = 6   # AY pins 11 + 12  (Major row)
GPIO_ROW_MIN = 7   # AY pins 9  + 10  (Minor row)
GPIO_ROW_7TH = 8   # AY pins 7  + 8   (Seventh row)

# Key matrix columns (inputs, PULL_UP, sense LOW on press)
# The OM-27 uses 6 column pins covering 9 roots via tritone sharing:
#   AY pin 39: Eb AND A   (same physical pin, different buttons)
#   AY pin 40: Bb AND E
#   AY pin 3:  F  AND B
#   AY pin 36: C  only
#   AY pin 37: G  only
#   AY pin 38: D  only
# Note: AY pins 13-24 (frequency inputs from M083A) are NOT matrix columns
# in the OM-27 — they are dedicated M083A connections, left unconnected
# on the daughterboard since we generate frequencies internally.
GPIO_COL_EbA = 9    # AY pin 39  (Eb / A)
GPIO_COL_BbE = 10   # AY pin 40  (Bb / E)
GPIO_COL_FB  = 11   # AY pin 3   (F  / B)
GPIO_COL_C   = 12   # AY pin 36  (C)
GPIO_COL_G   = 13   # AY pin 37  (G)
GPIO_COL_D   = 14   # AY pin 38  (D)

# Special inputs / outputs
GPIO_MIDI_TX = 15   # UART1 TX (optional) — verify pin capability on RP2350-Zero
GPIO_POWER   = 16   # Power enable out
GPIO_AK      = 17   # Any Key Down drive → AY pin 30
                    # Goes HIGH when any chord button is pressed.
                    # Check whether this connects to downstream circuitry.
GPIO_MEMORY  = 18   # Memory/Sustain switch → AY pin 35
                    # Active HIGH (logic 1 = memory on). PULL_DOWN so
                    # floating = memory off.
GPIO_RES     = 19   # Reset/modifier button → AY pin 5
                    # Sits at +12V at rest; pressing grounds it. PULL_UP.
                    # Repurposed as flat/sharp modifier button.

# Auto-bass select from AY-5-1315 rhythm chip (AY-5-1317A pins 25-27)
# AY-5-1315 outputs at +12V — add 68kΩ+33kΩ voltage dividers. Essential.
GPIO_BASS_B3 = 20   # AY pin 25  (B3)
GPIO_BASS_B2 = 21   # AY pin 26  (B2)
GPIO_BASS_B1 = 22   # AY pin 27  (B1)

# Solder jumpers (read once at boot; open = pull-up HIGH, bridged = GND)
GPIO_JP1_SHARP        = 23  # JP1: open = flat modifier, GND = sharp modifier
GPIO_JP2_BARRY_HARRIS = 24  # JP2: open = BH off, GND = Barry Harris on

# GPIOs 25-29 free for future use


# =============================================================================
# Key matrix layout
# =============================================================================

MATRIX_ROW_PINS = [GPIO_ROW_MAJ, GPIO_ROW_MIN, GPIO_ROW_7TH]

MATRIX_COL_PINS = [
    GPIO_COL_EbA, GPIO_COL_BbE, GPIO_COL_FB,
    GPIO_COL_C,   GPIO_COL_G,   GPIO_COL_D
]

ROW_TO_TYPE = ['maj', 'min', 'dom7']

# Column-to-root mapping.
# Shared pins carry two roots (tritone pairs) — each entry is either a
# single note index or a list of two. scan_matrix() handles both.
# Pressing one physical button only ever fires one root; the shared pin
# design just means both roots are electrically possible from one pin.
#
#                   pin39   pin40   pin3    pin36  pin37  pin38
COL_TO_ROOT_NORMAL = [[Eb,A],[Bb,E],[F,B],   C,     G,     D  ]

# Flat modifier: shifts each column down 1 semitone.
# On shared columns, both roots shift — reveals Db, Ab, and Gb.
COL_TO_ROOT_FLAT   = [[D,Ab],[A,Eb],[E,Bb],  B,     Fs,    Db ]

# Sharp modifier: shifts each column up 1 semitone.
COL_TO_ROOT_SHARP  = [[E,As],[B,F], [Fs,C],  Cs,    Gs,    Ds ]


# =============================================================================
# Tuning
# =============================================================================

TUNING_OCTAVE = 7      # generate in octave 7; CD4520s divide to 6, 5, 4
TUNING_A4_HZ  = 440.0  # change here to retune
                        # e.g. 432.0, 443.0, 415.0 (baroque)


# =============================================================================
# B1/B2/B3 truth table for MO output (auto-bass from AY-5-1315)
# From AY-5-1317A datasheet, pins 25-27.
# (B1, B2, B3) → semitone interval from root, or None = hold last / chord-aware
# =============================================================================

BASS_SELECT_TABLE = {
    (0, 0, 0): None,   # no change / hold last
    (0, 0, 1): 0,      # ROOT
    (0, 1, 0): 7,      # 5th
    (0, 1, 1): None,   # 3rd — chord-aware (handled in get_mo())
    (1, 1, 1): None,   # 7th — chord-aware (handled in get_mo())
    (1, 1, 0): 5,      # 4th
    (1, 0, 1): 9,      # 6th
}


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
