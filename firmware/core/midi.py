"""
OpenChord — core/midi.py
Optional MIDI out via UART.

Standard MIDI 1.0: 31250 baud, 8N1.
Harmless if TX pin is unconnected.

Hardware circuit (per MIDI 1.0 spec):
  GPIO_TX -> 1kΩ -> MMBT3906 base
  MMBT3906 emitter -> GND
  MMBT3906 collector -> 220Ω -> DIN-5 pin 5
  5V supply -> 220Ω -> DIN-5 pin 5  (current source)
  DIN-5 pin 2 -> GND
  DIN-5 pins 1,3 -> NC

For TRS MIDI (3.5mm, Type A):
  Tip   -> 220Ω -> collector (same as DIN pin 5)
  Ring  -> 220Ω -> 5V        (same as DIN pin 4)
  Sleeve -> GND

Usage:
    from midi import MidiOut
    midi = MidiOut(tx_gpio=27, channel=0)
    midi.note_on(60, velocity=100)
    midi.note_off(60)
    midi.chord_on(root=60, third=64, fifth=67, bass=48)
    midi.chord_off(root=60, third=64, fifth=67, bass=48)
"""

from machine import UART, Pin
import math


class MidiOut:
    def __init__(self, tx_gpio, channel=0):
        """
        Args:
            tx_gpio: GPIO pin number for UART TX
            channel: MIDI channel 0-15 (0 = channel 1)
        """
        self.uart = UART(1, baudrate=31250, tx=Pin(tx_gpio), rx=None)
        self.ch   = channel & 0x0F

    def note_on(self, note, velocity=100):
        if 0 <= note <= 127:
            self.uart.write(bytes([0x90 | self.ch, note & 0x7F, velocity & 0x7F]))

    def note_off(self, note):
        if 0 <= note <= 127:
            self.uart.write(bytes([0x80 | self.ch, note & 0x7F, 0]))

    def chord_on(self, root, third, fifth, bass,
                 chord_octave=4, bass_octave=2, velocity=95):
        """
        Send note-on for all four chord voices.
        Bass plays at bass_octave, chord tones at chord_octave.
        """
        self.note_on(self._midi(bass,  bass_octave),  velocity - 5)
        self.note_on(self._midi(root,  chord_octave), velocity + 5)
        self.note_on(self._midi(third, chord_octave), velocity)
        self.note_on(self._midi(fifth, chord_octave), velocity)

    def chord_off(self, root, third, fifth, bass,
                  chord_octave=4, bass_octave=2):
        self.note_off(self._midi(bass,  bass_octave))
        self.note_off(self._midi(root,  chord_octave))
        self.note_off(self._midi(third, chord_octave))
        self.note_off(self._midi(fifth, chord_octave))

    def counter_to_midi(self, counter, pio_clk=125_000_000):
        """Convert a PIO counter value to the nearest MIDI note number."""
        if counter >= 0x7FFFFFFF:
            return None
        freq   = pio_clk / (4.0 * (counter + 1))
        midi_n = round(69 + 12 * math.log2(freq / 440.0))
        return midi_n if 0 <= midi_n <= 127 else None

    @staticmethod
    def _midi(note_index, octave):
        return (octave + 1) * 12 + (note_index % 12)
