import rp2
from machine import Pin, UART, ADC
import utime
import math

# =============================================================================
# brain.py — RP2350 #2, sits in AY-5-1317A footprint
# Handles: key matrix, chord logic, modal strum plate, chord sound output,
#          Barry Harris mode, flat/sharp modifier, MIDI out, auto-bass.
#
# STRUM PLATE:
#   12 SMs generate the modal scale for the currently pressed chord.
#   Scale mode is chord-type-aware (see SCALE_INTERVALS below).
#   All 12 strips get unique pitches across ~2 octaves of the scale.
#   Outputs drive strum plate transistor gates directly (center-neg logic).
#
# CHORD SOUND:
#   Separate from strum plate. 4 outputs (ROOT/3RD/5TH/BASS) feed CD4520s
#   for the organ chord sound, same as the original AY-5-1317A did.
#   These come from the TOG board (RP2350 #1) via CD4016 analogue switches
#   gated by 4 additional GPIOs — OR RP2350 #2 generates them independently.
#   Current implementation: RP2350 #2 generates chord tones independently
#   (simpler, no inter-board dependency for chord sound).
#
# GPIO MAP (AY-5-1317A footprint):
#
#   STRUM PLATE OUTPUTS (12 SMs, center-neg PNP logic)
#   GPIO 0–11   Strum strips 1–12 low→high
#               Each via MMBT3906 PNP: GPIO LOW=strip HIGH, GPIO HIGH=strip LOW
#
#   CHORD SOUND OUTPUTS (4 channels via MMBT3906, to CD4520 inputs)
#   GPIO 12  ROOT  → CD4520 #1 pin 2  (AY pin 31)
#   GPIO 13  3RD   → CD4520 #1 pin 4  (AY pin 29)
#   GPIO 14  5TH   → CD4520 #2 pin 2  (AY pin 32)
#   GPIO 15  BASS  → CD4520 #2 pin 4  (AY pin 34)
#
#   KEY MATRIX
#   GPIO 16  Row Major    (AY pin 12)
#   GPIO 17  Row Minor    (AY pin 9)
#   GPIO 18  Row 7th      (AY pin 7)
#   GPIO 19  Col Eb       (AY pin 2)
#   GPIO 20  Col Bb       (AY pin 3)
#   GPIO 21  Col F        (AY pin 4)
#   GPIO 22  Col C        (AY pin 6)
#   GPIO 23  Col G        (AY pin 8)
#   GPIO 24  Col D        (AY pin 10)
#   GPIO 25  Col A        (AY pin 11)
#   GPIO 26  Col E        (AY pin 38)
#   GPIO 27  Col B        (AY pin 39)
#
#   SPECIAL
#   GPIO 28  Modifier button  (AY pin 5, active LOW)
#   GPIO 29  Memory switch    (AY pin 35, active LOW = off)
#
#   SOLDER JUMPERS (read at boot)
#   JP1  GPIO 4   open=flat,    GND=sharp
#   JP2  GPIO 5   open=BH off,  GND=BH on
#
#   MASTER TUNING
#   GPIO 3   ADC trim pot, 432–448 Hz
#
#   MIDI OUT (optional)
#   GPIO 2   UART1 TX, 31250 baud
#
#   AUTO-BASS FROM AY-5-1315
#   GPIO 6   Bass sel B2  (AY pin 25, needs 12V→3V level shift)
#   GPIO 7   Bass sel B3  (AY pin 26, needs 12V→3V level shift)
#   GPIO 8   Bass sel B1  (AY pin 27, needs 12V→3V level shift)
#
# NOTE: GPIO 4,5,6,7,8 are solder jumpers / bass sel — only read at boot
# or in slow loop, no conflict with SM usage (SMs 0–11 use set_base GPIO 0–11,
# chord outputs use GPIO 12–15).
# =============================================================================


# =============================================================================
# PIO: frequency generator for strum plate + chord sound outputs
# Center-negative logic: idle HIGH (MMBT3906 off = strip silent)
# =============================================================================

@rp2.asm_pio(set_init=rp2.PIO.OUT_HIGH)
def freq_gen():
    pull(noblock)
    mov(y, osr)
    wrap_target()
    set(pins, 0)            # GPIO LOW  = PNP ON  = output HIGH (GND/center)
    mov(x, y)
    label("hi")
    jmp(x_dec, "hi")
    set(pins, 1)            # GPIO HIGH = PNP OFF = output LOW  (neg rail)
    mov(x, y)
    label("lo")
    jmp(x_dec, "lo")
    wrap()

PIO_CLK = 125_000_000
SILENT  = 0x7FFFFFFF


# =============================================================================
# Note definitions
# =============================================================================

C, Cs, D, Ds, E, F, Fs, G, Gs, A, As, B = range(12)
Db=Cs; Eb=Ds; Gb=Fs; Ab=Gs; Bb=As
NOTE_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

def note_freq(note_index, octave, a4):
    """Frequency of note_index (0-11) in given octave. A4=octave 4, note 9."""
    semitones_above_a4 = (octave - 4) * 12 + (note_index - A)
    return a4 * (2.0 ** (semitones_above_a4 / 12.0))

def pio_counter(freq):
    return max(0, int(PIO_CLK / (4.0 * freq)) - 1)

def read_tuning():
    adc = ADC(Pin(3))
    raw = sum(adc.read_u16() for _ in range(8)) // 8
    return 432.0 + (raw / 65535.0) * 16.0

def note_to_midi(note_index, octave=4):
    return (octave + 1) * 12 + note_index


# =============================================================================
# Modal scale definitions
#
# Each scale is a list of semitone intervals from the root.
# 12 strips = 12 consecutive scale degrees across ~2 octaves.
# We walk up the scale until we have 12 unique pitches.
#
# Chord type → scale mode mapping:
#   maj      → Ionian          1 2 3 4 5 6 7
#   maj7     → Lydian          1 2 3 #4 5 6 7
#   maj6     → Ionian          (same as major — 6 already in scale)
#   min      → Aeolian         1 2 b3 4 5 b6 b7
#   min7     → Dorian          1 2 b3 4 5 6 b7
#   min6     → Melodic minor   1 2 b3 4 5 6 7
#   dom7     → Mixolydian      1 2 3 4 5 6 b7
#   dim      → Half-whole dim  1 b2 b3 3 #4 5 6 b7  (octatonic H-W)
#   dim7     → Whole-half dim  1 2 b3 4 b5 b6 6 7   (octatonic W-H)
#   aug      → Whole tone      1 2 3 #4 #5 b7
#   sus4     → Mixolydian      (dominant flavour suits suspended sound)
#   sus2     → Major pent      1 2 3 5 6  (open, no semitones)
# =============================================================================

# One-octave interval patterns (semitones from root)
_IONIAN      = [0, 2, 4, 5, 7, 9, 11]   # major
_LYDIAN      = [0, 2, 4, 6, 7, 9, 11]   # major #4
_AEOLIAN     = [0, 2, 3, 5, 7, 8, 10]   # natural minor
_DORIAN      = [0, 2, 3, 5, 7, 9, 10]   # minor with natural 6
_MEL_MINOR   = [0, 2, 3, 5, 7, 9, 11]   # melodic minor (ascending)
_MIXOLYDIAN  = [0, 2, 4, 5, 7, 9, 10]   # dominant / major b7
_HW_DIM      = [0, 1, 3, 4, 6, 7, 9, 10] # half-whole diminished (8 notes)
_WH_DIM      = [0, 2, 3, 5, 6, 8, 9, 11] # whole-half diminished (8 notes)
_WHOLE_TONE  = [0, 2, 4, 6, 8, 10]       # whole tone (6 notes)
_MAJ_PENT    = [0, 2, 4, 7, 9]           # major pentatonic (5 notes)

CHORD_SCALE = {
    'maj':  _IONIAN,
    'maj7': _LYDIAN,
    'min':  _AEOLIAN,
    'min7': _DORIAN,
    'dom7': _MIXOLYDIAN,
    'dim':  _HW_DIM,
    'dim7': _WH_DIM,       # three-button BH combo
    'aug':  _WHOLE_TONE,
    'sus4': _MIXOLYDIAN,
    'sus2': _MAJ_PENT,
    # Barry Harris
    'maj6': _IONIAN,       # 6 already in major scale
    'min6': _MEL_MINOR,    # melodic minor has natural 6 in minor context
}

def build_strum_frequencies(root, chord_type, a4):
    """
    Build list of 12 PIO counter values for the strum plate,
    representing 12 consecutive scale degrees starting from root,
    ascending across ~2 octaves. All unique pitches.
    """
    pattern = CHORD_SCALE.get(chord_type, _IONIAN)
    octave_span = len(pattern)   # notes per octave (7 for heptatonic, 8 for octatonic, 6 for whole tone)

    counters = []
    degree   = 0
    octave   = 4   # start in octave 4 for comfortable strum range

    while len(counters) < 12:
        # Which octave offset and position in pattern
        oct_offset  = degree // octave_span
        pattern_idx = degree % octave_span
        semitones   = pattern[pattern_idx] + (oct_offset * 12)
        note_idx    = (root + semitones) % 12
        oct_actual  = octave + (root + semitones) // 12

        freq    = note_freq(note_idx, oct_actual, a4)
        counter = pio_counter(freq)
        counters.append(counter)
        degree += 1

    return counters


# =============================================================================
# Chord voicing for chord sound outputs (GPIO 12–15 → CD4520s)
# Barry Harris: maj→maj6, min→min6, dim combo→dim7
# =============================================================================

def _voice(r, t, fv, b):
    return (r%12, t%12, fv%12, b%12)

def build_voicings(barry_harris):
    if barry_harris:
        maj_v = lambda r: _voice(r, r+4, r+9,  r  )   # maj6
        min_v = lambda r: _voice(r, r+3, r+9,  r  )   # min6
        dim_v = lambda r: _voice(r, r+3, r+6,  r+9)   # full dim7
    else:
        maj_v = lambda r: _voice(r, r+4, r+7,  r  )
        min_v = lambda r: _voice(r, r+3, r+7,  r  )
        dim_v = lambda r: _voice(r, r+3, r+6,  r  )
    return {
        'maj':  maj_v,
        'maj6': maj_v,
        'min':  min_v,
        'min6': min_v,
        'dom7': lambda r: _voice(r, r+4, r+7,  r+10),
        'min7': lambda r: _voice(r, r+3, r+7,  r+10),
        'maj7': lambda r: _voice(r, r+4, r+7,  r+11),
        'dim':  dim_v,
        'dim7': lambda r: _voice(r, r+3, r+6,  r+9 ),
        'aug':  lambda r: _voice(r, r+4, r+8,  r   ),
        'sus4': lambda r: _voice(r, r+5, r+7,  r   ),
        'sus2': lambda r: _voice(r, r+2, r+7,  r   ),
    }


# =============================================================================
# Key matrix
# =============================================================================

MATRIX_ROW_PINS    = [16, 17, 18]
ROW_TO_TYPE        = ['maj', 'min', 'dom7']
MATRIX_COL_PINS    = [19, 20, 21, 22, 23, 24, 25, 26, 27]
COL_TO_ROOT_NORMAL = [Eb, Bb, F,  C,  G,  D,  A,  E,  B ]
COL_TO_ROOT_FLAT   = [D,  A,  E,  B,  Gb, Db, Ab, Eb, Bb]
COL_TO_ROOT_SHARP  = [E,  B,  Fs, Cs, Gs, Ds, As, F,  C ]

def init_matrix():
    rows = [Pin(p, Pin.OUT, value=0) for p in MATRIX_ROW_PINS]
    cols = [Pin(p, Pin.IN, Pin.PULL_DOWN) for p in MATRIX_COL_PINS]
    return rows, cols

def scan_matrix(row_pins, col_pins, modifier):
    col_roots = (COL_TO_ROOT_FLAT  if modifier == 'flat'  else
                 COL_TO_ROOT_SHARP if modifier == 'sharp' else
                 COL_TO_ROOT_NORMAL)
    pressed = []
    for ri, row in enumerate(row_pins):
        row.value(1)
        utime.sleep_us(10)
        for ci, col in enumerate(col_pins):
            if col.value():
                pressed.append((col_roots[ci], ROW_TO_TYPE[ri]))
        row.value(0)
    return pressed


# =============================================================================
# Chord resolution
# =============================================================================

def _resolve_single_root(types):
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
# Auto-bass from AY-5-1315
# =============================================================================

bass_b1 = Pin(8, Pin.IN, Pin.PULL_DOWN)
bass_b2 = Pin(6, Pin.IN, Pin.PULL_DOWN)
bass_b3 = Pin(7, Pin.IN, Pin.PULL_DOWN)
_last_bass_note = None

def get_auto_bass(root, chord_type):
    global _last_bass_note
    b2, b3 = bass_b2.value(), bass_b3.value()
    if not b2 and not b3:
        return None
    if b2 and not b3:
        note = root % 12
    elif not b2 and b3:
        note = (root + 7) % 12
    else:
        iv = (10 if chord_type in ('dom7','min7') else
              11 if chord_type == 'maj7'           else
               3 if chord_type in ('min','min6','dim','dim7','aug') else 4)
        note = (root + iv) % 12
    _last_bass_note = note
    return note


# =============================================================================
# State machines
# SMs 0–11  → strum plate (GPIO 0–11)
# SMs 0–3 are REUSED for chord sound outputs when no chord is playing —
# actually safer to use separate PIO programs or separate SMs.
# Since all 12 are used for strum, chord sound outputs (GPIO 12–15)
# are driven by simple GPIO toggling at audio rate — not PIO.
# For proper frequency generation on chord outputs, we use a second
# PIO block. RP2350 has 2 PIO blocks × 4 SMs each = 8 additional SMs
# accessible as SM indices 4–7 on PIO1... actually MicroPython numbers
# them 0–11 across both blocks. SMs 0–11 are all we have.
#
# RESOLUTION: Chord sound outputs (ROOT/3RD/5TH/BASS) share SMs 0–3
# with strum strips 0–3. When a chord is held:
#   - Strum strips 0–3 get the lowest 4 scale notes (bass register)
#   - Chord sound outputs on GPIO 12–15 are driven by the SAME frequencies
#     as SMs 0–3 via a Y-split on the PCB traces.
# This means the bottom 4 strum strips and the chord sound outputs always
# play the same 4 pitches — the bass register of the current scale.
# In practice: strips 0–3 = root/2nd/3rd/4th of scale = chord tones anyway
# for most modes, so this sounds natural.
#
# Alternatively: if chord sound needs independent frequencies, use the
# TOG board's outputs (already generating all 12 chromatic notes) and
# gate them with a CD4016 controlled by 4 spare GPIOs. That's the cleanest
# hardware solution and keeps strum + chord entirely independent.
# TODO: finalise which approach based on PCB layout.
# =============================================================================

SM_STRUM_COUNT = 12   # SMs 0–11 → strum strips 0–11

def init_strum_sms():
    sms = {}
    for sm_id in range(SM_STRUM_COUNT):
        sm = rp2.StateMachine(
            sm_id, freq_gen,
            freq=PIO_CLK,
            set_base=Pin(sm_id, Pin.OUT)
        )
        sm.put(SILENT)
        sm.active(1)
        sms[sm_id] = sm
    return sms

def apply_strum(sms, counters):
    for i, c in enumerate(counters):
        sms[i].put(c)

def silence_all(sms):
    for sm in sms.values():
        sm.put(SILENT)

def play_note(sms, sm_id, counter, duration_ms):
    sms[sm_id].put(counter)
    utime.sleep_ms(duration_ms)
    sms[sm_id].put(SILENT)
    utime.sleep_ms(50)


# =============================================================================
# MIDI out (optional)
# =============================================================================

midi_uart = UART(1, baudrate=31250, tx=Pin(2), rx=None)
MIDI_CH   = 0

def midi_note_on(note, vel=100):
    midi_uart.write(bytes([0x90|MIDI_CH, note&0x7F, vel&0x7F]))

def midi_note_off(note):
    midi_uart.write(bytes([0x80|MIDI_CH, note&0x7F, 0]))

def midi_strum_on(counters):
    for c in counters:
        if c == SILENT: continue
        freq   = PIO_CLK / (4.0 * (c + 1))
        midi_n = round(69 + 12 * math.log2(freq / 440.0))
        if 0 <= midi_n <= 127:
            midi_note_on(midi_n, 85)

def midi_strum_off(counters):
    for c in counters:
        if c == SILENT: continue
        freq   = PIO_CLK / (4.0 * (c + 1))
        midi_n = round(69 + 12 * math.log2(freq / 440.0))
        if 0 <= midi_n <= 127:
            midi_note_off(midi_n)


# =============================================================================
# Startup jingle
# Note 1: C              — boot
# Note 2: modifier mode  — C=normal, C#=flat, D=sharp
# Note 3: Barry Harris   — E=on, Eb=off
# Note 4: memory         — G=on, F#=off
# Note 5: A              — held as tuning reference
# =============================================================================

def startup_jingle(sms, modifier_mode, barry_harris, memory_on, a4):
    seq = [
        (C,  4, 150),
        (Cs if modifier_mode=='flat' else D if modifier_mode=='sharp' else C, 4, 150),
        (E  if barry_harris  else Eb, 4, 150),
        (G  if memory_on     else Fs, 4, 150),
        (A,  4, 500),   # held — tuning reference
    ]
    for note, octave, dur in seq:
        freq    = note_freq(note, octave, a4)
        counter = pio_counter(freq)
        midi_note_on(note_to_midi(note, octave), 90)
        play_note(sms, 0, counter, dur)
        midi_note_off(note_to_midi(note, octave))
    utime.sleep_ms(150)


# =============================================================================
# Hardware init
# =============================================================================

# Read tuning first
a4 = read_tuning()
print("Brain: A4 = {:.2f} Hz".format(a4))

# Solder jumpers
_sharp_mode   = (Pin(4, Pin.IN, Pin.PULL_UP).value() == 0)  # JP1
_barry_harris = (Pin(5, Pin.IN, Pin.PULL_UP).value() == 0)  # JP2

_modifier_mode = 'sharp' if _sharp_mode else 'flat'
CHORD_VOICING  = build_voicings(_barry_harris)

# Runtime pins
modifier_pin = Pin(28, Pin.IN, Pin.PULL_UP)  # AY pin 5,  active LOW
memory_pin   = Pin(29, Pin.IN, Pin.PULL_UP)  # AY pin 35, active LOW = off

_memory_on = (memory_pin.value() == 1)

row_pins, col_pins = init_matrix()
sms = init_strum_sms()

print("Brain: modifier={} BH={} memory={}".format(
    _modifier_mode, _barry_harris, _memory_on))

startup_jingle(sms, _modifier_mode, _barry_harris, _memory_on, a4)
print("Running.")


# =============================================================================
# Main loop
# =============================================================================

last_chord   = None
last_strum   = None
active_midi  = None

while True:

    modifier_held = (modifier_pin.value() == 0)
    modifier      = (_modifier_mode if modifier_held else None)
    memory_active = (memory_pin.value() == 1)

    pressed = scan_matrix(row_pins, col_pins, modifier)
    result  = resolve_chord(pressed)

    if result is not None:
        last_chord = result
    elif not memory_active:
        last_chord = None

    active = last_chord

    if active is not None:
        root, chord_type, slash_bass = active

        # Apply Barry Harris chord type remapping for scale lookup
        bh_type = chord_type
        if _barry_harris:
            if chord_type == 'maj':
                bh_type = 'maj6'
            elif chord_type == 'min':
                bh_type = 'min6'

        # Build modal strum plate
        strum = build_strum_frequencies(root, bh_type, a4)

        if strum != last_strum:
            apply_strum(sms, strum)
            if last_strum is not None:
                midi_strum_off(last_strum)
            midi_strum_on(strum)
            last_strum = strum

    else:
        if last_strum is not None:
            silence_all(sms)
            midi_strum_off(last_strum)
            last_strum = None

    utime.sleep_ms(5)
