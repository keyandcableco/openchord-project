import rp2
from machine import Pin, ADC
import utime

# =============================================================================
# tog.py — RP2350 #1, sits in M083A footprint
# Generates 12 chromatic top-octave frequencies continuously.
# Outputs feed CD4520 divider chains for the chord sound circuit.
# This board has no knowledge of chords or key matrix.
# It just runs — set and forget.
#
# GPIO MAP (M083A footprint):
#   GPIO 0  → F12  C#  (SM 0)   M083A pin 4
#   GPIO 1  → F11  D   (SM 1)   M083A pin 5
#   GPIO 2  → F10  D#  (SM 2)   M083A pin 6
#   GPIO 3  → F9   E   (SM 3)   M083A pin 7
#   GPIO 4  → F8   F   (SM 4)   M083A pin 8
#   GPIO 5  → F7   F#  (SM 5)   M083A pin 9
#   GPIO 6  → F6   G   (SM 6)   M083A pin 10
#   GPIO 7  → F5   G#  (SM 7)   M083A pin 11
#   GPIO 8  → F4   A   (SM 8)   M083A pin 12
#   GPIO 9  → F3   A#  (SM 9)   M083A pin 13
#   GPIO 10 → F2   B   (SM 10)  M083A pin 14
#   GPIO 11 → F1   C   (SM 11)  M083A pin 15
#
#   GPIO 12  Master tuning ADC (trim pot, 10kΩ between 3.3V and GND)
#            432–448 Hz range. Float = 440 Hz.
#   GPIO 13  Power enable
# =============================================================================


@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def freq_gen():
    pull(block)             # block on first load, then noblock for updates
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

PIO_CLK = 125_000_000

C, Cs, D, Ds, E, F, Fs, G, Gs, A, As, B = range(12)
Db=Cs; Eb=Ds; Gb=Fs; Ab=Gs; Bb=As

# M083A outputs in pin order (F12 down to F1, C# through C)
# Maps SM index → note index
SM_TO_NOTE = [Cs, D, Ds, E, F, Fs, G, Gs, A, As, B, C]

def read_tuning():
    adc = ADC(Pin(12))
    raw = sum(adc.read_u16() for _ in range(8)) // 8
    return 432.0 + (raw / 65535.0) * 16.0

def pio_counter(freq):
    return max(0, int(PIO_CLK / (4.0 * freq)) - 1)

def note_freq(note, a4):
    # Note in octave 7: A7 = 36 semitones above A4
    semitones = 36 + (note - A)
    return a4 * (2.0 ** (semitones / 12.0))

# Init
power = Pin(13, Pin.OUT)
power.value(1)

a4 = read_tuning()
print("TOG: A4 = {:.2f} Hz".format(a4))

sms = []
for sm_id in range(12):
    note = SM_TO_NOTE[sm_id]
    freq = note_freq(note, a4)
    counter = pio_counter(freq)
    sm = rp2.StateMachine(
        sm_id, freq_gen,
        freq=PIO_CLK,
        set_base=Pin(sm_id, Pin.OUT)
    )
    sm.put(counter)
    sm.active(1)
    sms.append(sm)
    print("  SM{}: {} = {:.2f} Hz  counter={}".format(
        sm_id, ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][note],
        freq, counter))

print("TOG running — all 12 chromatic frequencies active")

# Nothing else to do — SMs run forever in hardware
while True:
    utime.sleep(10)
