"""
OpenChord — core/freq_gen.py
PIO-based direct frequency generator for RP2350/RP2040.

Generates square waves from the microcontroller's internal clock.
No external clock source required.

Two output modes supported via the INVERT parameter in init_sm():
  INVERT=False  positive logic  (NPN open-collector, pull to positive rail)
  INVERT=True   negative logic  (PNP open-collector, pull to GND/center tap)
                                 required for center-negative supply instruments

The state machines run at the full system clock (no freq= argument, so the
PIO clock divider is exactly 1): PIO_CLK = machine.freq(), 150 MHz on the
RP2350 and 125 MHz on the RP2040 by default. If you change machine.freq(),
do it before importing this module.

Frequency accuracy: each period is a whole number of PIO_CLK cycles, so
rounding costs at most half a cycle: under 0.06 cent up to C9 (8.4 kHz) at
125 MHz, less at 150 MHz. The 12 MHz crystal's tolerance (typically ±50ppm,
under 0.1 cent; not verified for the RP2350-Zero's part) shifts every note by
the same amount, like a tiny change of A4.

Usage:
    from freq_gen import init_sm, set_freq, silence, SILENT
    sm = init_sm(sm_id=0, gpio=0, invert=True)
    set_freq(sm, NOTE_COUNTERS[C])
    silence(sm)
"""

import rp2
import machine
from machine import Pin

PIO_CLK = machine.freq()   # SM clock = system clock (clkdiv 1)
SILENT  = 0                # counter 0 = pin parked at its idle level

# Counter formula (every PIO instruction takes 1 cycle, see the program):
#   high half = (counter >> 1) + 6 + (counter & 1) cycles
#   low half  = (counter >> 1) + 6 cycles
#   period    = counter + 12 cycles
#   counter   = round(PIO_CLK / freq) - 12

def pio_counter(freq):
    """Return PIO counter value for a given frequency in Hz."""
    return max(1, int(PIO_CLK / freq + 0.5) - 12)

def counter_to_freq(counter, pio_clk=None):
    """Return frequency in Hz for a given PIO counter value (0.0 = SILENT)."""
    if counter == SILENT:
        return 0.0
    return (pio_clk or PIO_CLK) / (counter + 12)


# Positive logic — NPN open-collector or direct GPIO
# Idle LOW. set(pins,1) = HIGH = active half, set(pins,0) = LOW.
# Each period starts by taking the newest counter from the TX FIFO. When the
# FIFO is empty, pull(noblock) copies X (the current counter) into OSR, so the
# note carries on. A new counter therefore takes effect at the next period
# boundary, with no runt half. Counter 0 parks the pin LOW and polls the FIFO
# every 5 cycles.
@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW, out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def _freq_gen_normal():
    label("top")
    wrap_target()
    pull(noblock)           # new counter, or X if the FIFO is empty
    mov(x, osr)             # X holds the counter between periods
    jmp(not_x, "off")       # 0 = SILENT
    set(pins, 1)
    out(y, 1)               # Y = counter bit 0, OSR = counter >> 1
    jmp(not_y, "even")
    nop()                   # odd counter: high half one cycle longer
    label("even")
    mov(y, osr)      [1]
    label("hi")
    jmp(y_dec, "hi")
    set(pins, 0)
    mov(y, osr)
    label("lo")
    jmp(y_dec, "lo")
    wrap()
    label("off")
    set(pins, 0)            # idle LOW while silent
    jmp("top")


# Inverted logic — PNP open-collector for center-negative supply instruments.
# Idle HIGH (PNP off = output silent).
# set(pins,0) = GPIO LOW  = PNP ON  = output pulled to GND (logic HIGH)
# set(pins,1) = GPIO HIGH = PNP OFF = output pulled to neg rail (logic LOW)
@rp2.asm_pio(set_init=rp2.PIO.OUT_HIGH, out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def _freq_gen_inverted():
    label("top")
    wrap_target()
    pull(noblock)
    mov(x, osr)
    jmp(not_x, "off")
    set(pins, 0)
    out(y, 1)
    jmp(not_y, "even")
    nop()
    label("even")
    mov(y, osr)      [1]
    label("hi")
    jmp(y_dec, "hi")
    set(pins, 1)
    mov(y, osr)
    label("lo")
    jmp(y_dec, "lo")
    wrap()
    label("off")
    set(pins, 1)            # idle HIGH while silent (PNP off)
    jmp("top")


# Last counter pushed to each state machine (keyed by id(sm))
_last = {}


def init_sm(sm_id, gpio, invert=False):
    """
    Initialise a PIO state machine as a frequency generator.

    Args:
        sm_id:  PIO state machine index (0-11 on RP2350)
        gpio:   GPIO pin number for output
        invert: True for center-negative/PNP logic, False for normal

    Returns:
        Active StateMachine instance, pre-loaded with SILENT.

    Each program is 14 instructions; one PIO block (32 words) can hold both.
    """
    prog = _freq_gen_inverted if invert else _freq_gen_normal
    sm = rp2.StateMachine(
        sm_id, prog,
        set_base=Pin(gpio, Pin.OUT, value=1 if invert else 0)
    )
    sm.put(SILENT)
    sm.active(1)
    _last[id(sm)] = SILENT
    return sm


def set_freq(sm, counter):
    """
    Send a new counter value to a running state machine. Never blocks.

    Pushes only when the value has changed and the SM has already taken the
    previous one (TX FIFO empty). Otherwise it does nothing and the next call
    retries, so call it on every main-loop pass with the note you want.
    The SM switches at the end of its current period.
    """
    if _last.get(id(sm)) == counter or sm.tx_fifo():
        return
    sm.put(counter)
    _last[id(sm)] = counter


def silence(sm):
    """Silence a state machine (pin held at its idle level)."""
    set_freq(sm, SILENT)
