"""
OpenChord — core/chord_logic.py
Chord resolution, voicing, and key matrix scanning.

Instrument-agnostic. All instrument-specific configuration (GPIO assignments,
column-to-root mapping, voicing preferences) is passed in from the
instrument's main.py rather than hardcoded here.

Chord resolution priority:
  1. Two different roots, interval=5  -> sus4
  2. Two different roots, interval=2  -> sus2
  3. Two different roots, other       -> slash chord
  4. Three buttons same root          -> augmented
  5. min + dom7 same root             -> min7
  6. maj + dom7 same root             -> maj7
  7. maj + min  same root             -> dim
  8. Single button                    -> maj / min / dom7

Usage:
    from chord_logic import (
        scan_matrix, resolve_chord, build_voicings,
        C, Cs, D, Ds, E, F, Fs, G, Gs, A, As, B
    )
"""

import utime
from machine import Pin

# Note indices — import these for use in instrument configs
C, Cs, D, Ds, E, F, Fs, G, Gs, A, As, B = range(12)
Db=Cs; Eb=Ds; Gb=Fs; Ab=Gs; Bb=As

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


# =============================================================================
# Key matrix
# =============================================================================

def init_matrix(row_pins, col_pins):
    """
    Initialise key matrix GPIO pins.

    Args:
        row_pins: list of GPIO numbers for row drive outputs
        col_pins: list of GPIO numbers for column sense inputs

    Returns:
        (row_pin_objects, col_pin_objects)
    """
    rows = [Pin(p, Pin.OUT, value=0) for p in row_pins]
    cols = [Pin(p, Pin.IN, Pin.PULL_DOWN) for p in col_pins]
    return rows, cols


def scan_matrix(row_pins, col_pins, col_to_root, row_to_type, settle_us=10):
    """
    Scan key matrix and return list of (root, chord_type) for pressed buttons.

    Args:
        row_pins:    list of Pin objects (outputs)
        col_pins:    list of Pin objects (inputs)
        col_to_root: list mapping column index -> note index
        row_to_type: list mapping row index -> chord type string
        settle_us:   microseconds to wait after driving row high

    Returns:
        list of (root_note_index, chord_type_string)
    """
    pressed = []
    for ri, row in enumerate(row_pins):
        row.value(1)
        utime.sleep_us(settle_us)
        for ci, col in enumerate(col_pins):
            if col.value():
                pressed.append((col_to_root[ci], row_to_type[ri]))
        row.value(0)
    return pressed


# =============================================================================
# Chord resolution
# =============================================================================

def _resolve_single_root(types):
    """Resolve a set of chord types on one root to a single chord name."""
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
# =============================================================================

def _voice(r, t, fv, b):
    return (r % 12, t % 12, fv % 12, b % 12)


def build_voicings(barry_harris=False):
    """
    Build chord voicing table.

    Each voicing is a function: root -> (root_note, third_note, fifth_note, bass_note)
    All values are note indices (0-11).

    These map to the 4 frequency output channels:
      root_note  -> SM_ROOT -> divider chain 1 clock A
      third_note -> SM_3RD  -> divider chain 1 clock B
      fifth_note -> SM_5TH  -> divider chain 2 clock A
      bass_note  -> SM_BASS -> divider chain 2 clock B

    Barry Harris mode:
      Major -> Major 6th  (6th on 5th-slot, 5th displaced)
      Minor -> Minor 6th  (6th on 5th-slot, 5th displaced)
      Dim combo -> Fully diminished 7th

    Args:
        barry_harris: bool, enable Barry Harris voicings

    Returns:
        dict of chord_type -> voicing_function
    """
    if barry_harris:
        maj_v = lambda r: _voice(r, r+4, r+9,  r   )   # maj6
        min_v = lambda r: _voice(r, r+3, r+9,  r   )   # min6
        dim_v = lambda r: _voice(r, r+3, r+6,  r+9 )   # full dim7
    else:
        maj_v = lambda r: _voice(r, r+4, r+7,  r   )
        min_v = lambda r: _voice(r, r+3, r+7,  r   )
        dim_v = lambda r: _voice(r, r+3, r+6,  r   )

    return {
        'maj':  maj_v,
        'min':  min_v,
        'dom7': lambda r: _voice(r, r+4, r+7,  r+10),
        'min7': lambda r: _voice(r, r+3, r+7,  r+10),
        'maj7': lambda r: _voice(r, r+4, r+7,  r+11),
        'dim':  dim_v,
        'aug':  lambda r: _voice(r, r+4, r+8,  r   ),
        'sus4': lambda r: _voice(r, r+5, r+7,  r   ),
        'sus2': lambda r: _voice(r, r+2, r+7,  r   ),
    }


# =============================================================================
# Auto-bass
# =============================================================================

def build_auto_bass_reader(b1_gpio, b2_gpio, b3_gpio):
    """
    Build an auto-bass reader for a given set of GPIO pins.

    The AY-5-1315 rhythm chip drives a 2-bit (or 3-bit) value
    selecting which chord tone plays as the bass note, in sync
    with the auto-rhythm pattern.

    IMPORTANT: AY-5-1315 operates at 12V logic. Add voltage dividers
    (68k + 33k) on each line before connecting to RP2350 GPIOs.

    Args:
        b1_gpio, b2_gpio, b3_gpio: GPIO pin numbers for bass select bits

    Returns:
        Function: get_bass(root, chord_type) -> note_index or None
    """
    from machine import Pin
    b1 = Pin(b1_gpio, Pin.IN, Pin.PULL_DOWN)
    b2 = Pin(b2_gpio, Pin.IN, Pin.PULL_DOWN)
    b3 = Pin(b3_gpio, Pin.IN, Pin.PULL_DOWN)
    last = [None]

    def get_bass(root, chord_type):
        bv2, bv3 = b2.value(), b3.value()

        if not bv2 and not bv3:
            return None                          # silence

        if bv2 and not bv3:
            note = root % 12                     # root

        elif not bv2 and bv3:
            note = (root + 7) % 12              # 5th

        else:
            # Chord-aware 3rd / 7th
            if chord_type in ('dom7', 'min7'):
                iv = 10
            elif chord_type == 'maj7':
                iv = 11
            elif chord_type in ('min', 'min6', 'dim', 'aug'):
                iv = 3
            else:
                iv = 4
            note = (root + iv) % 12

        last[0] = note
        return note

    return get_bass
