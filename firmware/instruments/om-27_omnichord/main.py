"""
OpenChord — instruments/om-27/main.py
Entry point for the Suzuki Omnichord OM-27 brain replacement.

Files needed on device root:
  main.py         this file
  config.py       OM-27 GPIO map and configuration
  freq_gen.py     core: PIO frequency generator
  tuning.py       core: frequency tables
  chord_logic.py  core: matrix scan, chord resolution, voicing, auto-bass
  midi.py         core: optional MIDI out
"""

from machine import Pin
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
# Hardware init
# =============================================================================

power = Pin(config.GPIO_POWER, Pin.OUT)
power.value(1)

# Master tuning — set TUNING_A4_HZ in config.py to retune
a4_hz         = config.TUNING_A4_HZ
note_counters  = build_note_counters(a4_hz, octave=config.TUNING_OCTAVE)
print_frequency_table(a4_hz, octave=config.TUNING_OCTAVE)

# Solder jumpers — read once at boot
_sharp_mode    = (Pin(config.GPIO_JP1_SHARP,        Pin.IN, Pin.PULL_UP).value() == 0)
_barry_harris  = (Pin(config.GPIO_JP2_BARRY_HARRIS, Pin.IN, Pin.PULL_UP).value() == 0)
_modifier_mode = 'sharp' if _sharp_mode else 'flat'
CHORD_VOICING  = build_voicings(_barry_harris)

# Runtime control pins
modifier_pin = Pin(config.GPIO_RES,    Pin.IN, Pin.PULL_UP)   # active LOW
memory_pin   = Pin(config.GPIO_MEMORY, Pin.IN, Pin.PULL_DOWN) # active HIGH

# Any Key Down output (AY pin 30)
ak_pin = Pin(config.GPIO_AK, Pin.OUT, value=0)

# 7th Select (AY pin 33): LOW = 7th output enabled
sel7_pin = Pin(config.GPIO_7SEL, Pin.OUT, value=1)  # start HIGH = 7th off

# Key matrix
row_pins, col_pins = init_matrix(config.MATRIX_ROW_PINS, config.MATRIX_COL_PINS)

# Auto-bass (MO output) reader
get_mo = build_auto_bass_reader(
    config.GPIO_BASS_B1,
    config.GPIO_BASS_B2,
    config.GPIO_BASS_B3,
    config.BASS_SELECT_TABLE
)

# Tone output state machines (NPN open-collector, non-inverted)
sm_root = init_sm(0, config.GPIO_ROOT, invert=False)
sm_3rd  = init_sm(1, config.GPIO_3RD,  invert=False)
sm_5th  = init_sm(2, config.GPIO_5TH,  invert=False)
sm_7th  = init_sm(3, config.GPIO_7TH,  invert=False)
sm_mo   = init_sm(4, config.GPIO_MO,   invert=False)

# MIDI (optional — harmless if GPIO_MIDI_TX pin unconnected)
if config.GPIO_MIDI_TX is not None:
    midi = MidiOut(tx_gpio=config.GPIO_MIDI_TX, channel=0)
else:
    midi = None

_memory_on = (memory_pin.value() == 1)

print("{} | {}".format(config.INSTRUMENT_NAME, config.FIRMWARE_VERSION))
print("A4={:.2f}Hz  modifier={}  BH={}  memory={}".format(
    a4_hz, _modifier_mode, _barry_harris, _memory_on))


# =============================================================================
# Startup jingle
# Encodes current settings as note choices — see config.py for mapping.
# =============================================================================

def play_note(note, duration_ms):
    counter = note_counters[note]
    if midi:
        midi.note_on(midi._midi(note, 5), 90)
    set_freq(sm_root, counter)
    utime.sleep_ms(duration_ms)
    silence(sm_root)
    if midi:
        midi.note_off(midi._midi(note, 5))
    utime.sleep_ms(60)

def startup_jingle():
    seq = [
        (config.JINGLE_BOOT,                                   150),
        (config.JINGLE_FLAT   if _modifier_mode == 'flat' else
         config.JINGLE_SHARP  if _modifier_mode == 'sharp' else
         config.JINGLE_NORMAL,                                 150),
        (config.JINGLE_BH_ON  if _barry_harris  else
         config.JINGLE_BH_OFF,                                 150),
        (config.JINGLE_MEM_ON if _memory_on     else
         config.JINGLE_MEM_OFF,                                150),
        (config.JINGLE_TUNING,                                 300),
    ]
    for note, dur in seq:
        play_note(note, dur)
    utime.sleep_ms(150)

startup_jingle()
print("Running.")


# =============================================================================
# MIDI helpers
# =============================================================================

def _midi_chord_on(voices):
    root_n, third_n, fifth_n, seventh_n, mo_n = voices
    midi.note_on(midi._midi(mo_n,    2), 90)
    midi.note_on(midi._midi(root_n,  4), 100)
    midi.note_on(midi._midi(third_n, 4), 95)
    midi.note_on(midi._midi(fifth_n, 4), 95)
    if seventh_n is not None:
        midi.note_on(midi._midi(seventh_n, 4), 90)

def _midi_chord_off(voices):
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

last_chord  = None    # (root, chord_type, slash_bass)
last_mo     = None    # last MO note for hold behaviour
active_midi = None    # currently sounding MIDI voices for note-off

while True:

    # Read modifier button (active LOW — sits at +12V at rest)
    modifier_held = (modifier_pin.value() == 0)
    if modifier_held:
        col_roots = (config.COL_TO_ROOT_SHARP if _modifier_mode == 'sharp'
                     else config.COL_TO_ROOT_FLAT)
    else:
        col_roots = config.COL_TO_ROOT_NORMAL

    memory_active = (memory_pin.value() == 1)

    # Scan key matrix
    pressed = scan_matrix(
        row_pins, col_pins,
        col_roots, config.ROW_TO_TYPE
    )

    # Drive AK (Any Key Down) output
    ak_pin.value(1 if pressed else 0)

    # Memory
    result = resolve_chord(pressed)
    if result is not None:
        last_chord = result
    elif not memory_active:
        last_chord = None

    active = last_chord

    if active is not None:
        root, chord_type, slash_bass = active

        # Get 5-voice chord voicing
        root_note, third_note, fifth_note, seventh_note, default_mo = \
            CHORD_VOICING[chord_type](root)

        # 7th Select pin
        has_7th = seventh_note is not None
        sel7_pin.value(0 if has_7th else 1)

        # MO output: slash chord overrides auto-bass
        if slash_bass is not None:
            mo_note = slash_bass
        else:
            mo_note = get_mo(root, chord_type, last_mo)
            if mo_note is None:
                mo_note = last_mo if last_mo is not None else default_mo
        last_mo = mo_note

        # Drive tone outputs
        set_freq(sm_root, note_counters[root_note])
        set_freq(sm_3rd,  note_counters[third_note])
        set_freq(sm_5th,  note_counters[fifth_note])
        if has_7th:
            set_freq(sm_7th, note_counters[seventh_note])
        else:
            silence(sm_7th)
        set_freq(sm_mo, note_counters[mo_note])

        # MIDI
        if midi:
            new_midi = (root_note, third_note, fifth_note, seventh_note, mo_note)
            if new_midi != active_midi:
                if active_midi is not None:
                    _midi_chord_off(active_midi)
                _midi_chord_on(new_midi)
                active_midi = new_midi

    else:
        silence(sm_root)
        silence(sm_3rd)
        silence(sm_5th)
        silence(sm_7th)
        silence(sm_mo)
        sel7_pin.value(1)
        last_mo = None

        if midi and active_midi is not None:
            _midi_chord_off(active_midi)
            active_midi = None

    utime.sleep_ms(5)
