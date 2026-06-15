"""
OpenChord — core/freq_gen.py
PIO-based direct frequency generator for RP2350/RP2040.

Generates square waves from the microcontroller's internal clock.
No external clock source required.

Two output modes supported via the INVERT parameter in init_sm():
  INVERT=False  positive logic  (NPN open-collector, pull to positive rail)
  INVERT=True   negative logic  (PNP open-collector, pull to GND/center tap)
                                 required for center-negative supply instruments

Frequency accuracy: RP2350 PLL locks to 12 MHz crystal -> 125 MHz ±50ppm.
That is less than 0.1 cent of pitch error — better than any RC oscillator.

Usage:
    from freq_gen import init_sm, set_freq, silence, SILENT
    sm = init_sm(sm_id=0, gpio=0, invert=True)
    set_freq(sm, NOTE_COUNTERS[C])
    silence(sm)
"""

import rp2
from machine import Pin

PIO_CLK = 125_000_000
SILENT  = 0x7FFFFFFF   # ~0.06 Hz — effectively DC / inaudible

# Counter formula:
#   Each PIO loop = 2 cycles (jmp + implicit)
#   Half period   = PIO_CLK / (2 * freq)
#   Counter       = half_period / 2 - 1 = PIO_CLK / (4 * freq) - 1

def pio_counter(freq):
    """Return PIO counter value for a given frequency in Hz."""
    return max(0, int(PIO_CLK / (4.0 * freq)) - 1)

def counter_to_freq(counter):
    """Return frequency in Hz for a given PIO counter value."""
    return PIO_CLK / (4.0 * (counter + 1))


# Positive logic — NPN open-collector or direct GPIO
# Idle LOW. set(pins,1) = HIGH = active half, set(pins,0) = LOW.
@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def _freq_gen_normal():
    pull(noblock)
    mov(y, osr)
    wrap_target()
    set(pins, 1)
    mov(x, y)
    label("hi")
    jmp(x_dec, "hi")
    set(pins, 0)
    mov(x, y)
    label("lo")
    jmp(x_dec, "lo")
    wrap()


# Inverted logic — PNP open-collector for center-negative supply instruments.
# Idle HIGH (PNP off = output silent).
# set(pins,0) = GPIO LOW  = PNP ON  = output pulled to GND (logic HIGH)
# set(pins,1) = GPIO HIGH = PNP OFF = output pulled to neg rail (logic LOW)
@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def _freq_gen_inverted():
    pull(noblock)
    mov(y, osr)
    wrap_target()
    set(pins, 0)
    mov(x, y)
    label("hi")
    jmp(x_dec, "hi")
    set(pins, 1)
    mov(x, y)
    label("lo")
    jmp(x_dec, "lo")
    wrap()


def init_sm(sm_id, gpio, invert=False):
    """
    Initialise a PIO state machine as a frequency generator.

    Args:
        sm_id:  PIO state machine index (0-11 on RP2350)
        gpio:   GPIO pin number for output
        invert: True for center-negative/PNP logic, False for normal

    Returns:
        Active StateMachine instance, pre-loaded with SILENT.
    """
    prog = _freq_gen_inverted if invert else _freq_gen_normal
    sm = rp2.StateMachine(
        sm_id, prog,
        freq=PIO_CLK,
        set_base=Pin(gpio, Pin.OUT)
    )
    sm.put(SILENT)
    sm.active(1)
    return sm


def set_freq(sm, counter):
    """Push a new counter value to a running state machine."""
    sm.put(counter)


def silence(sm):
    """Silence a state machine (effectively DC output)."""
    sm.put(SILENT)
