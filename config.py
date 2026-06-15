"""
OpenChord — instruments/om-27/config.py
Instrument-specific configuration for the Suzuki Omnichord OM-27.

This file contains everything specific to the OM-27:
  - GPIO assignments (mapped to AY-5-1317A DIP-40 footprint)
  - Key matrix layout (3 rows x 9 cols, circle of fifths)
  - Root note mappings for normal / flat / sharp modifier modes
  - Power supply and output logic details

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
REPLACED_IC        = "AY-5-1317A"
DOWNSTREAM_DIVIDER = "CD4520 (replacing M747)"


# =============================================================================
# Power supply and output logic
#
# The OM-27 uses a center-negative DC barrel jack (outer ring = +12V, 
# center pin = GND). Internally this is conventional positive-supply logic:
#   Logic HIGH = ~11-12V
#   Logic LOW  = GND
#
# Active-low inputs (e.g. pin 5 reset/mute) sit at 11-12V at rest
# and are triggered by grounding them. Output pins behave the same way.
#
# Output transistors: NPN (MMBT3904), open-collector pulling up to 12V.
#   GPIO HIGH -> transistor ON  -> collector pulled to GND    (logic LOW)
#   GPIO LOW  -> transistor OFF -> collector pulled to 12V via resistor (logic HIGH)
#
# NOTE: this is unverified. Scope the AY-5-1317A output pins before
# committing to a PCB layout. In particular, check whether the existing
# resistors on pins 29/31/32/34 are pullups to 12V or pulldowns to GND,
# as this determines whether direct GPIO connection might work without
# transistors.
#
# Set INVERT=False in freq_gen.init_sm() calls (standard NPN logic).
# =============================================================================

CENTER_NEGATIVE = False   # conventional positive supply, standard NPN outputs


# =============================================================================
# GPIO assignments
# =============================================================================

# Tone outputs (4 channels -> CD4520 adapter boards -> strum plate)
# Each via MMBT3904 NPN transistor, open-collector to 12V
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
GPIO_MODIFIER = 18  # modifier button  (AY pin 5 reset/mute signal, active LOW)
                    # pin 5 sits at 11-12V at rest; grounding it = active
                    # keep existing filter components on PCB trace if present

# Auto-bass from AY-5-1315 rhythm chip
# NOTE: AY-5-1315 operates at 12V logic. Verify signal levels before
# connecting directly to RP2350 GPIOs (3.3V tolerant).
# May need 68k + 33k voltage divider on each line (12V -> ~3V).
GPIO_BASS_B2  = 19  # AY pin 25
GPIO_BASS_B3  = 20  # AY pin 26
GPIO_BASS_B1  = 21  # AY pin 27

# Solder jumpers (read once at boot)
GPIO_JP1_SHARP        = 22  # open = flat modifier, GND = sharp modifier
GPIO_JP2_BARRY_HARRIS = 23  # open = off, GND = Barry Harris mode on

# Master tuning ADC
GPIO_TUNING_ADC = 26   # 10k trim pot between 3.3V and GND
                       # maps to 432-448 Hz; leave unconnected for ~440 Hz

# MIDI out (optional)
GPIO_MIDI_TX = 27      # UART1 TX, 31250 baud; harmless if unconnected


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

TUNING_OCTAVE = 7     # generate in octave 7; CD4520s divide down to 6, 5, 4


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
