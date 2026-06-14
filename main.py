"""
OpenChord — instruments/om-27/main.py
Entry point for the Suzuki Omnichord OM-27 brain replacement.

Copy this file and config.py to the root of your RP2350-Zero,
along with all files from firmware/core/.

Files needed on device:
  main.py         (this file)
  config.py       (OM-27 specific configuration)
  freq_gen.py     (core)
  tuning.py       (core)
  chord_logic.py  (core)
  midi.py         (core)
"""

from machine import Pin
import utime

import config
from freq_gen import init_sm, set_freq, silence, SILENT
from tuning import read_tuning_adc, build_note_counters, print_frequency_table
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

# Master tuning — read first, everything else depends on it
a4_hz        = read_tuning_adc(config.GPIO_TUNING_ADC)
note_counters = build_note_counters(a4_hz, octave=config.TUNING_OCTAVE)
print_frequency_table(a4_hz, octave=config.TUNING_OCTAVE)

# Solder jumpers — read once at boot
_sharp_mode    = (Pin(config.GPIO_JP1_SHARP,        Pin.IN, Pin.PULL_UP).value() == 0)
_barry_harris  = (Pin(config.GPIO_JP2_BARRY_HARRIS, Pin.IN, Pin.PULL_UP).value() == 0)
_modifier_mode = 'sharp' if _sharp_mode else 'flat'

# Runtime control pins
modifier_pin = Pin(config.GPIO_MODIFIER, Pin.IN, Pin.PULL_UP)  # active LOW
memory_pin   = Pin(config.GPIO_MEMORY,   Pin.IN, Pin.PULL_UP)  # active LOW = off

# Key matrix
row_pins, col_pins = init_matrix(config.MATRIX_ROW_PINS, config.MATRIX_COL_PINS)

# Chord voicings
CHORD_VOICING = build_voicings(_barry_harris)

# Auto-bass from AY-5-1315
get_bass = build_auto_bass_reader(
    config.GPIO_BASS_B1,
    config.GPIO_BASS_B2,
    config.GPIO_BASS_B3
)

# Tone output state machines (PNP/inverted for center-negative supply)
sm_root = init_sm(0, config.GPIO_ROOT, invert=config.CENTER_NEGATIVE)
sm_3rd  = init_sm(1, config.GPIO_3RD,  invert=config.CENTER_NEGATIVE)
sm_5th  = init_sm(2, config.GPIO_5TH,  invert=config.CENTER_NEGATIVE)
sm_bass = init_sm(3, config.GPIO_BASS, invert=config.CENTER_NEGATIVE)

# MIDI (optional)
midi = MidiOut(tx_gpio=config.GPIO_MIDI_TX, channel=0)

_memory_on = (memory_pin.value() == 1)

print("{} | OpenChord".format(config.INSTRUMENT_NAME))
print("A4={:.2f}Hz  modifier={}  BH={}  memory={}".format(
    a4_hz, _modifier_mode, _barry_harris, _memory_on))


# =============================================================================
# Startup jingle
# Plays through tone output chain -> CD4520s -> strum plate -> speaker.
# Also sent as MIDI for any connected synth.
# Encodes current settings as note choices (see config.py for mapping).
# =============================================================================

def play_note(note, duration_ms):
    counter = note_counters[note]
    midi.note_on(midi._midi(note, 5), 90)
    set_freq(sm_root, counter)
    utime.sleep_ms(duration_ms)
    silence(sm_root)
    midi.note_off(midi._midi(note, 5))
    utime.sleep_ms(60)

def startup_jingle():
    seq = [
        (config.JINGLE_BOOT,                                      150),
        (config.JINGLE_FLAT   if _modifier_mode == 'flat'  else
         config.JINGLE_SHARP  if _modifier_mode == 'sharp' else
         config.JINGLE_NORMAL,                                    150),
        (config.JINGLE_BH_ON  if _barry_harris  else
         config.JINGLE_BH_OFF,                                    150),
        (config.JINGLE_MEM_ON if _memory_on     else
         config.JINGLE_MEM_OFF,                                   150),
        (config.JINGLE_TUNING,                                    500),
    ]
    for note, dur in seq:
        play_note(note, dur)
    utime.sleep_ms(150)

startup_jingle()
print("Running.")


# =============================================================================
# Main loop
# =============================================================================

last_chord  = None    # (root, chord_type, slash_bass)
active_midi = None    # (root, third, fifth, bass) currently sounding MIDI

while True:

    # Read modifier button and select root map
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
    result = resolve_chord(pressed)

    # Memory: hold last chord when buttons released if switch is on
    if result is not None:
        last_chord = result
    elif not memory_active:
        last_chord = None

    active = last_chord

    if active is not None:
        root, chord_type, slash_bass = active

        # Get chord voicing — (root_note, third_note, fifth_note, bass_note)
        root_note, third_note, fifth_note, default_bass = \
            CHORD_VOICING[chord_type](root)

        # Bass priority:
        #   1. Slash chord — explicit bass from second root press
        #   2. Auto-bass from AY-5-1315 rhythm chip
        #   3. Default bass from chord voicing
        if slash_bass is not None:
            bass_note = slash_bass
        else:
            auto = get_bass(root, chord_type)
            bass_note = auto if auto is not None else default_bass

        # Drive tone output state machines
        set_freq(sm_root, note_counters[root_note])
        set_freq(sm_3rd,  note_counters[third_note])
        set_freq(sm_5th,  note_counters[fifth_note])
        set_freq(sm_bass, note_counters[bass_note])

        # MIDI: note-off previous, note-on new (only on chord change)
        new_midi = (root_note, third_note, fifth_note, bass_note)
        if new_midi != active_midi:
            if active_midi is not None:
                midi.chord_off(*active_midi)
            midi.chord_on(*new_midi)
            active_midi = new_midi

    else:
        # Silence all outputs
        silence(sm_root)
        silence(sm_3rd)
        silence(sm_5th)
        silence(sm_bass)

        if active_midi is not None:
            midi.chord_off(*active_midi)
            active_midi = None

    utime.sleep_ms(5)   # ~200 Hz scan rate
