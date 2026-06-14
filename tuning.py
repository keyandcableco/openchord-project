"""
OpenChord — core/tuning.py
Master tuning and frequency table generation.

Computes PIO counter values for all 12 chromatic notes across multiple
octaves, derived from a single A4 reference frequency.

The reference frequency can be:
  - Fixed (A4 = 440.0)
  - Read from an ADC-connected trim pot (432-448 Hz range)
  - Set programmatically

Usage:
    from tuning import read_tuning_adc, build_note_counters
    a4 = read_tuning_adc(gpio=26)          # or: a4 = 440.0
    counters = build_note_counters(a4, octave=7)
    # counters[C] -> PIO counter for C in octave 7
"""

from machine import ADC, Pin
from freq_gen import pio_counter

# Note indices
C, Cs, D, Ds, E, F, Fs, G, Gs, A, As, B = range(12)
Db=Cs; Eb=Ds; Gb=Fs; Ab=Gs; Bb=As

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Tuning ADC range
TUNING_MIN_HZ = 432.0
TUNING_MAX_HZ = 448.0


def note_freq(note_index, octave, a4=440.0):
    """
    Return frequency in Hz for a note index (0-11) in a given octave.
    A4 (note index 9, octave 4) = a4 Hz by definition.
    """
    semitones_above_a4 = (octave - 4) * 12 + (note_index - A)
    return a4 * (2.0 ** (semitones_above_a4 / 12.0))


def read_tuning_adc(gpio, samples=8):
    """
    Read a trim pot on the given ADC-capable GPIO.
    Maps 0-65535 ADC range to TUNING_MIN_HZ-TUNING_MAX_HZ.
    Averages multiple reads to reduce noise.
    Returns A4 frequency in Hz.
    Leave pin unconnected for approximately 440 Hz (mid-range pull-up).
    """
    adc = ADC(Pin(gpio))
    raw = sum(adc.read_u16() for _ in range(samples)) // samples
    return TUNING_MIN_HZ + (raw / 65535.0) * (TUNING_MAX_HZ - TUNING_MIN_HZ)


def build_note_counters(a4=440.0, octave=7):
    """
    Build dict of note_index -> PIO counter for all 12 chromatic notes
    in the specified octave.

    Default octave 7 is appropriate for instruments that use downstream
    binary dividers (M747, CD4520) to produce lower octaves.
    Use octave 4 or 5 for instruments driving audio directly.

    Returns:
        dict {note_index: counter_value}
    """
    return {
        note: pio_counter(note_freq(note, octave, a4))
        for note in range(12)
    }


def build_note_counters_multioctave(a4=440.0, octaves=(4, 5, 6, 7)):
    """
    Build dict of (note_index, octave) -> PIO counter for multiple octaves.
    Useful when driving strum plate strips directly without divider chips.

    Returns:
        dict {(note_index, octave): counter_value}
    """
    return {
        (note, oct): pio_counter(note_freq(note, oct, a4))
        for oct in octaves
        for note in range(12)
    }


def note_to_midi(note_index, octave=4):
    """Return MIDI note number for a given note index and octave."""
    return (octave + 1) * 12 + note_index


def print_frequency_table(a4=440.0, octave=7):
    """Print a human-readable frequency table for verification."""
    from freq_gen import PIO_CLK
    print("Frequency table — octave {}, A4={:.2f} Hz".format(octave, a4))
    for note in range(12):
        freq    = note_freq(note, octave, a4)
        counter = pio_counter(freq)
        actual  = PIO_CLK / (4.0 * (counter + 1))
        error   = (actual - freq) / freq * 1200  # cents
        print("  {:3s}{}: {:8.3f} Hz  counter={:5d}  actual={:.3f} Hz  err={:+.2f}¢".format(
            NOTE_NAMES[note], octave, freq, counter, actual, error))
