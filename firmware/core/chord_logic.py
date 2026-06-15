"""
OpenChord — core/chord_logic.py
Chord resolution, voicing, key matrix scanning, and auto-bass.

Instrument-agnostic. All instrument-specific configuration is passed in
from the instrument's config.py.

Chord resolution priority:
  1. Two different roots, interval=5  -> sus4
  2. Two different roots, interval=2  -> sus2
  3. Two different roots, other       -> slash chord
  4. Three buttons same root          -> augmented
  5. min + dom7 same root             -> min7
  6. maj + dom7 same root             -> maj7
  7. maj + min  same root             -> dim
  8. Single button                    -> maj / min / dom7
"""

import utime
from machine import Pin

# Note indices
C, Cs, D, Ds, E, F, Fs, G, Gs, A, As, B = range(12)
Db=Cs; Eb=Ds; Gb=Fs; Ab=Gs; Bb=As

NOTE_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']


# =============================================================================
# Key matrix
# =============================================================================

def init_matrix(row_pins, col_pins):
    """
    Initialise key matrix GPIO pins.

    Args:
        row_pins: list of GPIO numbers for row drive outputs
        col_pins: list of GPIO numbers for column sense inputs
                  (these are the AY-5-1317A frequency input pins 13-24,
                   which double as matrix columns)

    Returns:
        (row_pin_objects, col_pin_objects)

    NOTE — RP2350 Errata 9:
        GPIO pins configured with PULL_DOWN can latch at ~2.1V when floating,
        due to an analogue design error in the RP2350 GPIO pads. This makes
        PULL_DOWN unreliable for column sense pins.
        Workaround: use PULL_UP and drive rows LOW instead of HIGH.
        A button press connects row (LOW) to column, pulling column LOW.
        scan_matrix() detects column going LOW (not HIGH) as a press.
    """
    rows = [Pin(p, Pin.OUT, value=1) for p in row_pins]  # idle HIGH
    cols = [Pin(p, Pin.IN, Pin.PULL_UP) for p in col_pins]
    return rows, cols


def scan_matrix(row_pins, col_pins, col_to_root, row_to_type, settle_us=10):
    """
    Scan key matrix and return list of (root, chord_type) for pressed buttons.

    Drives each row LOW in turn (PULL_UP on columns, idle HIGH).
    A button press connects the driven row (LOW) to a column, pulling it LOW.
    Detects column going LOW as a press.

    Workaround for RP2350 Errata 9 (PULL_DOWN unreliable on floating pins).

    Args:
        row_pins:    list of Pin objects (outputs, idle HIGH)
        col_pins:    list of Pin objects (inputs, PULL_UP)
        col_to_root: list mapping column index -> note index (0-11)
        row_to_type: list mapping row index -> chord type string
        settle_us:   microseconds to wait after driving row low

    Returns:
        list of (root_note_index, chord_type_string)
    """
    pressed = []
    for ri, row in enumerate(row_pins):
        row.value(0)                    # drive row LOW
        utime.sleep_us(settle_us)
        for ci, col in enumerate(col_pins):
            if not col.value():         # column pulled LOW = button pressed
                pressed.append((col_to_root[ci], row_to_type[ri]))
        row.value(1)                    # restore row HIGH
    return pressed


# =============================================================================
# Chord resolution
# =============================================================================

def _resolve_single_root(types):
    """Resolve a set of chord types pressed on one root to a chord name."""
    if 'maj' in types and 'min' in types and 'dom7' in types:
        return 'aug'
    if 'min' in types and 'dom7' in types:
        return 'min7'
    if 'maj' in types and 'dom7' in types:
        return 'maj7'
    if 'maj' in types and 'min' in types:
        return 'dim'
    for t in ('maj', 'min', 'dom7'):
        if t in types:
            return t
    return None


def resolve_chord(pressed):
    """
    Resolve a list of pressed (root, chord_type) buttons to a chord.

    Args:
        pressed: list of (root_note_index, chord_type_string)

    Returns:
        (root, chord_type, slash_bass) or None
        slash_bass is a note index or None
    """
    if not pressed:
        return None

    by_root = {}
    for root, ctype in pressed:
        by_root.setdefault(root, set()).add(ctype)

    roots = list(by_root.keys())

    if len(roots) == 2:
        r = sorted(roots, key=lambda x: len(by_root[x]), reverse=True)
        chord_root, second_root = r[0], r[1]
        ivl = (second_root - chord_root) % 12

        if ivl == 5:
            return (chord_root, 'sus4', None)
        if ivl == 2:
            return (chord_root, 'sus2', None)

        ctype = _resolve_single_root(by_root[chord_root])
        if ctype:
            return (chord_root, ctype, second_root)

    best = max(roots, key=lambda x: len(by_root[x]))
    ctype = _resolve_single_root(by_root[best])
    if ctype:
        return (best, ctype, None)

    return None


# =============================================================================
# Chord voicing
#
# Returns (root_note, third_note, fifth_note, seventh_note, default_mo_note)
# mapping to the 5 output channels:
#   root_note     -> GPIO_ROOT -> AY pin 31 -> CD4520 #1 clock A
#   third_note    -> GPIO_3RD  -> AY pin 29 -> CD4520 #1 clock B
#   fifth_note    -> GPIO_5TH  -> AY pin 28 -> CD4520 #2 clock A
#   seventh_note  -> GPIO_7TH  -> AY pin 32 -> CD4520 #2 clock B (7th chords only)
#   default_mo    -> GPIO_MO   -> AY pin 34 -> auto-bass default (root)
#
# seventh_note is None for non-7th chords (SM silenced, AY pin 32 = logic 0).
# Barry Harris mode: maj->maj6 (6th on 5th slot), min->min6, dim->full dim7.
# =============================================================================

def _voice(r, t, fv, sev, mo):
    return (r%12, t%12, fv%12, sev, mo%12 if mo is not None else None)

def build_voicings(barry_harris=False):
    """
    Build chord voicing table.

    Returns dict of chord_type -> function(root) ->
        (root_note, third_note, fifth_note, seventh_note, default_mo_note)

    seventh_note is None for chords without a 7th (GPIO_7TH silenced).
    default_mo_note is the MO output when B1/B2/B3 = 0,0,0 (hold) on boot.
    """
    if barry_harris:
        maj_v = lambda r: _voice(r, r+4, r+9,  None,  r)  # maj6
        min_v = lambda r: _voice(r, r+3, r+9,  None,  r)  # min6
        dim_v = lambda r: _voice(r, r+3, r+6,  r+9,   r)  # full dim7
    else:
        maj_v = lambda r: _voice(r, r+4, r+7,  None,  r)
        min_v = lambda r: _voice(r, r+3, r+7,  None,  r)
        dim_v = lambda r: _voice(r, r+3, r+6,  None,  r)

    return {
        'maj':  maj_v,
        'min':  min_v,
        'dom7': lambda r: _voice(r, r+4, r+7,  r+10,  r),
        'min7': lambda r: _voice(r, r+3, r+7,  r+10,  r),
        'maj7': lambda r: _voice(r, r+4, r+7,  r+11,  r),
        'dim':  dim_v,
        'aug':  lambda r: _voice(r, r+4, r+8,  None,  r),
        'sus4': lambda r: _voice(r, r+5, r+7,  None,  r),
        'sus2': lambda r: _voice(r, r+2, r+7,  None,  r),
    }


# =============================================================================
# Auto-bass (MO output) from AY-5-1315 rhythm chip
#
# The AY-5-1315 drives B1/B2/B3 (AY-5-1317A pins 25-27) to select which
# chord element plays on the MO output (pin 34) in sync with the rhythm.
#
# Full truth table from AY-5-1317A datasheet:
#   B1 B2 B3  Selection
#   0  0  0   No change (hold last)
#   0  0  1   ROOT
#   0  1  0   5th
#   0  1  1   3rd  (chord-aware: major or minor 3rd)
#   1  1  1   7th  (chord-aware: minor or major 7th)
#   1  1  0   4th
#   1  0  1   6th
#
# AY-5-1315 outputs at +12V logic — voltage dividers (68k+33k) required
# before connecting to RP2350 GPIOs. Do not skip.
#
# Usage:
#   reader = build_auto_bass_reader(b1_gpio, b2_gpio, b3_gpio, bass_table)
#   mo_note = reader(root, chord_type, last_mo_note)
# =============================================================================

def build_auto_bass_reader(b1_gpio, b2_gpio, b3_gpio, bass_select_table):
    """
    Build a closure that reads B1/B2/B3 and returns the MO note index.

    Args:
        b1_gpio, b2_gpio, b3_gpio: GPIO pin numbers (after level shifting)
        bass_select_table: dict from config.BASS_SELECT_TABLE

    Returns:
        Function: get_mo(root, chord_type, last_note) -> note_index or None
    """
    b1 = Pin(b1_gpio, Pin.IN, Pin.PULL_DOWN)
    b2 = Pin(b2_gpio, Pin.IN, Pin.PULL_DOWN)
    b3 = Pin(b3_gpio, Pin.IN, Pin.PULL_DOWN)

    def get_mo(root, chord_type, last_note):
        """
        Returns MO note index (0-11) or last_note if hold (0,0,0).
        """
        key = (b1.value(), b2.value(), b3.value())
        interval = bass_select_table.get(key)

        # Hold: return last note
        if key == (0, 0, 0):
            return last_note

        # 3rd: chord-aware
        if key == (0, 1, 1):
            interval = 3 if chord_type in ('min','min7','min6','dim','aug') else 4

        # 7th: chord-aware
        if key == (1, 1, 1):
            interval = 11 if chord_type == 'maj7' else 10

        if interval is None:
            return last_note

        return (root + interval) % 12

    return get_mo
