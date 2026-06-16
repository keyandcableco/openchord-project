"""
OpenChord — instruments/om-27/main.py
Entry point for the Suzuki Omnichord OM-27 brain replacement.

Files needed on device root:
  main.py, config.py, freq_gen.py, tuning.py, chord_logic.py, midi.py
"""

from machine import Pin
import rp2
import array
import utime

import config
from freq_gen import init_sm, set_freq, silence, SILENT
from tuning import build_note_counters, print_frequency_table
from chord_logic import (
    init_matrix, scan_matrix, resolve_chord, build_voicings,
    build_auto_bass_reader,
    C, Cs, D, Ds, E, F, Fs, G, Gs, A, As, B
)
from midi import MidiOut

Eb=Ds; Bb=As; Gb=Fs; Db=Cs; Ab=Gs


# =============================================================================
# WS2812 PIO program (defined here, SM started AFTER all other init)
# =============================================================================

@rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW,
             out_shiftdir=rp2.PIO.SHIFT_LEFT,
             autopull=True,
             pull_thresh=24)
def _ws2812():
    T1 = 2
    T2 = 5
    T3 = 3
    wrap_target()
    label("bitloop")
    out(x, 1)              .side(0) [T3 - 1]
    jmp(not_x, "do_zero")  .side(1) [T1 - 1]
    jmp("bitloop")         .side(1) [T2 - 1]
    label("do_zero")
    nop()                  .side(0) [T2 - 1]
    wrap()

_led_buf = array.array("I", [0])
_led_sm  = None   # started after all other SMs are running

def _led_init():
    global _led_sm
    rp2.StateMachine(11).active(0)
    utime.sleep_ms(50)
    _led_sm = rp2.StateMachine(11, _ws2812, freq=8_000_000, sideset_base=Pin(16))
    _led_sm.active(1)
    utime.sleep_ms(50)

def led_set(r, g, b, brightness=0.2):
    if _led_sm is None:
        return
    ri = int(r * brightness)
    gi = int(g * brightness)
    bi = int(b * brightness)
    # Empirically determined byte order for this LED
    _led_buf[0] = (ri << 16) | (gi << 8) | bi
    _led_sm.put(_led_buf, 8)
    utime.sleep_ms(10)

def led_off():
    led_set(0, 0, 0)


# =============================================================================
# Hardware init
# =============================================================================

print("--- OpenChord boot ---")

power = Pin(config.GPIO_POWER, Pin.OUT)
power.value(1)
print("Power enable: OK")

# Master tuning
a4_hz        = config.TUNING_A4_HZ
note_counters = build_note_counters(a4_hz, octave=config.TUNING_OCTAVE)
print_frequency_table(a4_hz, octave=config.TUNING_OCTAVE)
print("Frequency table: OK")

# Solder jumpers
_sharp_mode    = (Pin(config.GPIO_JP1_SHARP,        Pin.IN, Pin.PULL_UP).value() == 0)
_barry_harris  = (Pin(config.GPIO_JP2_BARRY_HARRIS, Pin.IN, Pin.PULL_UP).value() == 0)
_modifier_mode = 'sharp' if _sharp_mode else 'flat'
CHORD_VOICING  = build_voicings(_barry_harris)
print("Jumpers: JP1={} JP2={}".format(_sharp_mode, _barry_harris))

# Runtime pins
modifier_pin = Pin(config.GPIO_RES,    Pin.IN, Pin.PULL_UP)
memory_pin   = Pin(config.GPIO_MEMORY, Pin.IN, Pin.PULL_DOWN)
print("Control pins: OK")

# Any Key Down and 7th Select
ak_pin   = Pin(config.GPIO_AK,   Pin.OUT, value=0)
sel7_pin = Pin(config.GPIO_7SEL, Pin.OUT, value=1)
print("Output control pins: OK")

# Key matrix
row_pins, col_pins = init_matrix(config.MATRIX_ROW_PINS, config.MATRIX_COL_PINS)
print("Key matrix: {} rows, {} cols".format(len(row_pins), len(col_pins)))

# Auto-bass
get_mo = build_auto_bass_reader(
    config.GPIO_BASS_B1,
    config.GPIO_BASS_B2,
    config.GPIO_BASS_B3,
    config.BASS_SELECT_TABLE
)
print("Auto-bass reader: OK")

# Tone SMs — start these before LED SM
print("Starting state machines...")
sm_root = init_sm(0, config.GPIO_ROOT, invert=False)
print("  SM0 ROOT: OK")
sm_3rd  = init_sm(1, config.GPIO_3RD,  invert=False)
print("  SM1 3RD:  OK")
sm_5th  = init_sm(2, config.GPIO_5TH,  invert=False)
print("  SM2 5TH:  OK")
sm_7th  = init_sm(3, config.GPIO_7TH,  invert=False)
print("  SM3 7TH:  OK")
sm_mo   = init_sm(4, config.GPIO_MO,   invert=False)
print("  SM4 MO:   OK")

# MIDI
if config.GPIO_MIDI_TX is not None:
    try:
        midi = MidiOut(tx_gpio=config.GPIO_MIDI_TX, channel=0)
        print("MIDI: OK on GPIO {}".format(config.GPIO_MIDI_TX))
    except Exception as e:
        print("MIDI: FAILED ({}) — continuing without".format(e))
        midi = None
else:
    midi = None
    print("MIDI: disabled")

# LED — init LAST, after all other SMs are running
_led_init()
led_set(255, 255, 255)   # white = almost ready
print("LED: OK")

_memory_on = (memory_pin.value() == 1)

print("{} | {}".format(config.INSTRUMENT_NAME, config.FIRMWARE_VERSION))
print("A4={:.2f}Hz  modifier={}  BH={}  memory={}".format(
    a4_hz, _modifier_mode, _barry_harris, _memory_on))

led_set(0, 255, 0)   # green = running
print("Running. Waiting for button presses...")
print("(Blue = button detected, Green = idle, blinks every ~2s)")


# =============================================================================
# MIDI helpers
# =============================================================================

def _midi_chord_on(voices):
    if not midi: return
    root_n, third_n, fifth_n, seventh_n, mo_n = voices
    midi.note_on(midi._midi(mo_n,    2), 90)
    midi.note_on(midi._midi(root_n,  4), 100)
    midi.note_on(midi._midi(third_n, 4), 95)
    midi.note_on(midi._midi(fifth_n, 4), 95)
    if seventh_n is not None:
        midi.note_on(midi._midi(seventh_n, 4), 90)

def _midi_chord_off(voices):
    if not midi: return
    root_n, third_n, fifth_n, seventh_n, mo_n = voices
    midi.note_off(midi._midi(mo_n,    2))
    midi.note_off(midi._midi(root_n,  4))
    midi.note_off(midi._midi(third_n, 4))
    midi.note_off(midi._midi(fifth_n, 4))
    if seventh_n is not None:
        midi.note_off(midi._midi(seventh_n, 4))


# =============================================================================
# Main loop
# =============================================================================

NOTE_NAMES   = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
last_chord   = None
last_mo      = None
active_midi  = None
_tick        = 0
_last_active = False

while True:

    modifier_held = (modifier_pin.value() == 0)
    col_roots = (config.COL_TO_ROOT_SHARP if modifier_held and _modifier_mode == 'sharp'
                 else config.COL_TO_ROOT_FLAT if modifier_held
                 else config.COL_TO_ROOT_NORMAL)

    memory_active = (memory_pin.value() == 1)

    pressed = scan_matrix(row_pins, col_pins, col_roots, config.ROW_TO_TYPE)
    ak_pin.value(1 if pressed else 0)

    result = resolve_chord(pressed)
    if result is not None:
        last_chord = result
    elif not memory_active:
        last_chord = None

    active = last_chord

    if active is not None:
        root, chord_type, slash_bass = active

        if not _last_active:
            root_name = NOTE_NAMES[root] if isinstance(root, int) else '?'
            print("Chord: {} {}".format(root_name, chord_type))
            led_set(0, 0, 255)   # blue = chord detected

        _last_active = True
        _tick = 0

        root_note, third_note, fifth_note, seventh_note, default_mo = \
            CHORD_VOICING[chord_type](root)

        has_7th = seventh_note is not None
        sel7_pin.value(0 if has_7th else 1)

        if slash_bass is not None:
            mo_note = slash_bass
        else:
            mo_note = get_mo(root, chord_type, last_mo)
            if mo_note is None:
                mo_note = last_mo if last_mo is not None else default_mo
        last_mo = mo_note

        set_freq(sm_root, note_counters[root_note])
        set_freq(sm_3rd,  note_counters[third_note])
        set_freq(sm_5th,  note_counters[fifth_note])
        if has_7th:
            set_freq(sm_7th, note_counters[seventh_note])
        else:
            silence(sm_7th)
        set_freq(sm_mo, note_counters[mo_note])

        new_midi = (root_note, third_note, fifth_note, seventh_note, mo_note)
        if new_midi != active_midi:
            if active_midi is not None:
                _midi_chord_off(active_midi)
            _midi_chord_on(new_midi)
            active_midi = new_midi

    else:
        if _last_active:
            print("Released")
            led_set(0, 255, 0)   # back to green

        _last_active = False

        silence(sm_root)
        silence(sm_3rd)
        silence(sm_5th)
        silence(sm_7th)
        silence(sm_mo)
        sel7_pin.value(1)
        last_mo = None

        if active_midi is not None:
            _midi_chord_off(active_midi)
            active_midi = None

        # Heartbeat blink when idle
        _tick += 1
        if _tick >= 400:
            if _led_buf[0]:
                led_off()
            else:
                led_set(0, 255, 0)
            _tick = 0

    utime.sleep_ms(5)