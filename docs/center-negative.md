# Power supply and output logic in vintage chord instruments

## Center-negative barrel jacks

Some vintage instruments use a center-negative DC power supply — the center
pin of the barrel connector is GND and the outer ring is the positive voltage.
This is just a connector wiring convention, opposite to the more common
center-positive used by most modern gear.

The Omnichord OM-27 uses a center-negative 12V supply. The OM-27 PCB has
two supply rails: +12V and +5V (from a 78L05 regulator). There is no
negative rail.

## AY-5-1317A supply configuration in the OM-27

The AY-5-1317A is a P-channel MOS IC. Its datasheet specifies standard
conditions of VDD = -15V and VSS = 0V — but that reflects General
Instrument's standard P-channel test setup, not necessarily how Suzuki
used it in the OM-27.

The standard approach for running a P-channel IC on a positive supply is
to flip the reference: connect VSS to the positive rail (+12V) and VDD to
GND. The chip only cares about the voltage difference between its rails.
With VSS = +12V and VDD = GND, the IC operates on a 12V supply with the
same 12V swing specified in the datasheet.

Under this interpretation (which fits the OM-27's known supply rails):
- AY-5-1317A logic HIGH = +12V (VSS)
- AY-5-1317A logic LOW  = GND  (VDD)
- Active outputs pull toward +12V

This is consistent with pin 5 (reset/mute) sitting at +12V at rest and
being triggered by grounding it.

**Unverified — confirm with a scope before wiring.**

## M747 / CD4520 supply and logic levels

From the M747 datasheet: conventional positive-supply COS/MOS, VDD = 5-15V
positive, VSS = GND. Logic HIGH ≈ VDD, Logic LOW ≈ 0V. The M747 clocks on
the positive-going edge of the clock input.

The CD4520 replacement also clocks on the positive-going edge (with ENABLE
held HIGH), so it matches M747 behaviour directly.

The AY-5-1317A's active outputs (toward +12V) drive the M747/CD4520 clock
inputs HIGH. Our NPN transistor outputs do the same thing.

## Output transistors

NPN (MMBT3904), open-collector to +12V:

```
RP2350 GPIO ──── 1kΩ ──── MMBT3904 base
                           MMBT3904 emitter ──── GND
                           MMBT3904 collector ──── output to CD4520 clock
                                                       │
                                                     10kΩ
                                                     │
                                                   +12V rail
```

- GPIO LOW  → transistor OFF → collector pulled to +12V via 10kΩ → logic HIGH ✓
- GPIO HIGH → transistor ON  → collector pulled to GND             → logic LOW  ✓

The M747/CD4520 clocks on the rising edge (GND → +12V), which happens when
the GPIO goes LOW and the transistor switches off.

Worth trying direct GPIO connection first on the bench. CMOS inputs typically
threshold at 30-50% of VDD, so 3.3V into a 12V-supplied CMOS input may
register as a valid HIGH and save four components.

## AY-5-1315 output levels

The AY-5-1315 rhythm chip (same P-channel MOS family, same supply
convention) drives its B1/B2/B3 bass-select outputs toward +12V when
active. These connect to RP2350 GPIO inputs.

**These will damage the RP2350 if connected directly.** Add a voltage
divider on each line: 68kΩ from signal to node, 33kΩ from node to GND.
This gives ~3.0V at the GPIO from a 12V signal. Do not skip this.

## RP2350 Errata 9 — PULL_DOWN unreliable on floating pins

The RP2350 has a known silicon errata (Errata 9): GPIO pins configured
with PULL_DOWN can latch at approximately 2.1V when the pin is floating,
due to an analogue design error in the GPIO pads. This is not fixable in
MicroPython without low-level C workarounds.

**Impact for OpenChord:** The 12 key matrix column sense pins would all be
floating when no button is pressed. Using PULL_DOWN would make them
unreliable.

**Workaround:** Use PULL_UP on column inputs and drive rows LOW instead of
HIGH during scanning. A button press pulls the column LOW (detectable as
`not col.value()`). This is already implemented in `core/chord_logic.py`.

If you are adapting OpenChord to a new instrument and your matrix requires
PULL_DOWN for some reason, you will need to add explicit GPIO pad
reconfiguration before each read — see the RP2350 datasheet errata section
for the recommended C-level mitigation.

## General wiring advice

Before connecting any RP2350 GPIO to a vintage instrument:
1. Measure VDD and VSS on the target IC to confirm supply orientation
2. Scope an output pin while the instrument is running to see actual voltage swing
3. Confirm nothing exceeds 3.3V before it reaches a GPIO input
4. When in doubt, use a resistor divider or level shifter

RP2350 GPIOs are not 5V tolerant, let alone 12V tolerant.
