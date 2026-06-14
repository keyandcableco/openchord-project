"""
OpenChord — instruments/hammond-x5/config.py
Instrument-specific configuration for the Hammond X-5.

STATUS: STUB — needs verification against hardware.
Based on Filip Kindt's RP2040 TOG replacement at https://www.cctv.fm/post/rp2040-tog
and community reverse-engineering of the MM5833 chord IC.

The Hammond X-5 uses a fundamentally different power supply to the OM-27:
  - Multi-rail negative supply (GND, -18V, -25V, -33V)
  - Signals swing to negative voltages
  - Clock input requires AC coupling + bias network (see Filip's schematic)
  - Output transistors need to pull toward negative rail

This file is a starting point. If you own an X-5 and can verify or
correct these values, please open a pull request.
See docs/contributing.md for guidance.
"""

from chord_logic import C, Cs, D, Ds, E, F, Fs, G, Gs, A, As, B
Db=Cs; Eb=Ds; Gb=Fs; Ab=Gs; Bb=As

INSTRUMENT_NAME    = "Hammond X-5"
FIRMWARE_VERSION   = "OpenChord v1.0 (stub)"
REPLACED_IC        = "MM5833"
DOWNSTREAM_DIVIDER = "Unknown — needs verification"

# The X-5 uses negative-rail logic — different to OM-27 center-negative.
# Output transistors need different treatment. See docs/center-negative.md.
CENTER_NEGATIVE = True   # TODO: verify polarity and transistor type

# =============================================================================
# GPIO assignments — UNVERIFIED, needs hardware confirmation
# =============================================================================

GPIO_ROOT = 0
GPIO_3RD  = 1
GPIO_5TH  = 2
GPIO_BASS = 3

# Key matrix — X-5 has different layout to OM-27, needs schematic
# TODO: verify row/col count and pin assignments
GPIO_ROW_MAJ = 4
GPIO_ROW_MIN = 5
GPIO_ROW_7TH = 6

MATRIX_ROW_PINS = [GPIO_ROW_MAJ, GPIO_ROW_MIN, GPIO_ROW_7TH]
MATRIX_COL_PINS = []   # TODO: fill in from X-5 schematic
ROW_TO_TYPE     = ['maj', 'min', 'dom7']

# MM5833 has 6 outputs (not 13 like M083A) — only upper octave notes
# F#7, G7, G#7, A7, A#7, B7 (dividers 338, 319, 301, 284, 268, 253)
# Root layout differs from OM-27 — needs mapping from X-5 button PCB
COL_TO_ROOT_NORMAL = []  # TODO
COL_TO_ROOT_FLAT   = []  # TODO
COL_TO_ROOT_SHARP  = []  # TODO

GPIO_POWER    = 16
GPIO_MEMORY   = 17
GPIO_MODIFIER = 18

GPIO_BASS_B1 = 19   # TODO: verify rhythm chip bass select pins
GPIO_BASS_B2 = 20
GPIO_BASS_B3 = 21

GPIO_JP1_SHARP        = 22
GPIO_JP2_BARRY_HARRIS = 23
GPIO_TUNING_ADC       = 26
GPIO_MIDI_TX          = 27

TUNING_OCTAVE = 7

# Jingle encoding (same as OM-27)
JINGLE_BOOT    = C
JINGLE_NORMAL  = C
JINGLE_FLAT    = Cs
JINGLE_SHARP   = D
JINGLE_BH_ON   = E
JINGLE_BH_OFF  = Eb
JINGLE_MEM_ON  = G
JINGLE_MEM_OFF = Fs
JINGLE_TUNING  = A
