"""
OpenChord — instruments/om-27/config.py
Instrument-specific configuration for the Suzuki Omnichord OM-27.

This file contains everything that is specific to the OM-27:
  - GPIO assignments (mapped to AY-5-1317A DIP-40 footprint)
  - Key matrix layout (3 rows x 9 cols, circle of fifths)
  - Root note mappings for normal / flat / sharp modifier modes
  - Power supply polarity
  - Downstream divider chip info

To adapt OpenChord to a different instrument, copy this file,
update the values below, and update main.py to import your config.
See docs/contributing.md for a full guide.
"""

from chord_logic import C, Cs, D, Ds, E, F, Fs, G, Gs, A, As, B
Db=Cs; Eb=Ds; Gb=Fs; Ab=Gs; Bb=As

# =============================================================================
# Instrument identity
# =============================================================================

INSTRUMENT_NAME    = "Suzuki Omnichord OM-27"
FIRMWARE_VERSION   = "OpenChord v1.0"
REPLACED_IC        = "AY-5-1317A"       # IC footprint this board sits in
DOWNSTREAM_DIVIDER = "CD4520 (was M747)" # octave divider chips downstream


# =============================================================================
# Power supply
# =============================================================================

# The OM-27 uses a center-negative battery supply.
# Center tap = 0V = GND = logic HIGH in original circuit.
# Negative terminal = logic LOW.
# Output transistors must be PNP (MMBT3906), pulling toward GND.
# Set INVERT=True in freq_gen.init_sm() calls.
CENTER_NEGATIVE = True


# =============================================================================
# GPIO assignments
# =============================================================================

# Tone outputs (4 channels -> CD4520 adapter boards -> strum plate)
# Each via MMBT3906 PNP transistor (center-negative logic)
GPIO_ROOT = 0    # ROOT -> CD4520 #1 clock A  (AY pin 31)
GPIO_3RD  = 1    # 3RD  -> CD4520 #1 clock B  (AY pin 29)
GPIO_5TH  = 2    # 5TH  -> CD4520 #2 clock A  (AY pin 32)
GPIO_BASS = 3    # BASS -> CD4520 #2 clock B  (AY pin 34)

# Key matrix
GPIO_ROW_MAJ = 4   # AY pin 12
GPIO_ROW_MIN = 5   # AY pin 9
GPIO_ROW_7TH = 6   # AY pin 7
GPIO_COL_EB  = 7   # AY pin 2
GPIO_COL_BB  = 8   # AY pin 3
GPIO_COL_F   = 9   # AY pin 4
GPIO_COL_C   = 10  # AY pin 6
GPIO_COL_G   = 11  # AY pin 8
GPIO_COL_D   = 12  # AY pin 10
GPIO_COL_A   = 13  # AY pin 11
GPIO_COL_E   = 14  # AY pin 38
GPIO_COL_B   = 15  # AY pin 39

# Special inputs
GPIO_POWER    = 16  # power enable out
GPIO_MEMORY   = 17  # memory switch    (AY pin 35, active LOW = off)
GPIO_MODIFIER = 18  # modifier button  (AY pin 5 reset signal, active LOW)
                    # keep existing 500p + 250k filter on PCB trace

# Auto-bass from AY-5-1315 rhythm chip (needs 68k+33k level shift, 12V->3V)
GPIO_BASS_B2  = 19  # AY pin 25
GPIO_BASS_B3  = 20  # AY pin 26
GPIO_BASS_B1  = 21  # AY pin 27

# Solder jumpers (read once at boot)
GPIO_JP1_SHARP       = 22  # open=flat modifier, GND=sharp modifier
GPIO_JP2_BARRY_HARRIS = 23  # open=off, GND=Barry Harris mode on

# Master tuning ADC
GPIO_TUNING_ADC = 26   # 10k trim pot between 3.3V and GND, 432-448 Hz range

# MIDI out (optional — harmless if unconnected)
GPIO_MIDI_TX = 27      # UART1 TX, 31250 baud


# =============================================================================
# Key matrix layout
# =============================================================================

MATRIX_ROW_PINS = [GPIO_ROW_MAJ, GPIO_ROW_MIN, GPIO_ROW_7TH]
MATRIX_COL_PINS = [
    GPIO_COL_EB, GPIO_COL_BB, GPIO_COL_F, GPIO_COL_C,
    GPIO_COL_G,  GPIO_COL_D,  GPIO_COL_A, GPIO_COL_E, GPIO_COL_B
]
ROW_TO_TYPE = ['maj', 'min', 'dom7']

# Circle of fifths, left to right: Eb Bb F C G D A E B
COL_TO_ROOT_NORMAL = [Eb, Bb, F,  C,  G,  D,  A,  E,  B ]

# Flat modifier: lowers each root 1 semitone
# Reveals genuinely new roots: Gb, Db, Ab
COL_TO_ROOT_FLAT   = [D,  A,  E,  B,  Gb, Db, Ab, Eb, Bb]

# Sharp modifier: raises each root 1 semitone
# Same black keys approached from below
COL_TO_ROOT_SHARP  = [E,  B,  Fs, Cs, Gs, Ds, As, F,  C ]


# =============================================================================
# Tuning
# =============================================================================

TUNING_OCTAVE = 7     # generate frequencies in octave 7
                      # CD4520 chains divide down to octaves 6, 5, 4


# =============================================================================
# Startup jingle note encoding
# =============================================================================
# Note 1: C              always (boot)
# Note 2: modifier mode  C=normal, C#=flat, D=sharp
# Note 3: Barry Harris   E=on, Eb=off
# Note 4: memory         G=on, F#=off
# Note 5: A (held)       tuning reference
JINGLE_BOOT    = C
JINGLE_NORMAL  = C
JINGLE_FLAT    = Cs
JINGLE_SHARP   = D
JINGLE_BH_ON   = E
JINGLE_BH_OFF  = Eb
JINGLE_MEM_ON  = G
JINGLE_MEM_OFF = Fs
JINGLE_TUNING  = A
