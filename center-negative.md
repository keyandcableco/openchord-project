# Power supply and output logic in vintage chord instruments

## Center-negative barrel jacks

Some vintage instruments use a center-negative DC power supply — meaning the
center pin of the barrel connector is GND and the outer ring is the positive
supply voltage. This is the opposite of the more common center-positive
convention used by most modern gear (Boss pedals, for example, are
center-negative; most cheap wall warts are center-positive).

The Omnichord OM-27 uses a center-negative 12V supply. This is just a
connector wiring convention and does not imply anything unusual about the
internal circuit logic.

## OM-27 internal logic levels (unverified, needs scope confirmation)

Internally the OM-27 appears to use conventional positive-supply logic:
- Logic HIGH = ~11-12V (toward positive rail)
- Logic LOW  = GND

Evidence for this: pin 5 of the AY-5-1317A (reset/mute) sits at 11-12V at
rest and is activated by grounding it — standard active-low behaviour on a
positive supply.

The output pins (29, 31, 32, 34) are assumed to behave similarly, but this
needs to be verified with an oscilloscope before committing to a PCB layout.
Specifically:
- Are the resistors on those output pins pullups to 12V or pulldowns to GND?
- What voltage swing does the AY-5-1317A actually produce on those pins?
- What logic threshold do the M747/CD4520 inputs require?

## Output transistors

Based on the above, NPN transistors (MMBT3904) in open-collector configuration
are the working assumption for the tone outputs:

```
RP2350 GPIO ──── 1kΩ ──── MMBT3904 base
                           MMBT3904 emitter ──── GND
                           MMBT3904 collector ──── output to CD4520 clock
                                                       │
                                                     10kΩ
                                                       │
                                                    +12V rail
```

- GPIO HIGH → transistor ON  → collector pulled to GND     (logic LOW)
- GPIO LOW  → transistor OFF → collector pulled to 12V via 10kΩ (logic HIGH)

It's also possible that direct GPIO connection (3.3V into a 12V logic input)
might work without transistors, depending on what threshold the CD4520 inputs
actually need. Worth trying on the bench before adding transistors.

## The Hammond X-5: a genuinely different case

The Hammond X-5 uses a multi-rail negative supply (GND, -18V, -25V, -33V)
where signals actually swing to negative voltages. This is a substantially
more complex interfacing problem. Filip Kindt's write-up at
https://www.cctv.fm/post/rp2040-tog covers the AC coupling and bias network
needed for the clock input, and the transistor arrangement for the outputs.

If you're working on an X-5, read that first.

## General advice

Before wiring any RP2350 GPIO to a vintage instrument's IC pins:
1. Measure the supply voltage on the IC's VDD pin
2. Scope an output pin while the instrument is running to see the actual voltage swing
3. Check input pin voltages at rest and when active
4. Make sure nothing exceeds 3.3V before it reaches a GPIO

When in doubt, use a voltage divider or level shifter rather than connecting
directly. RP2350 GPIOs are not 5V tolerant, let alone 12V tolerant.
