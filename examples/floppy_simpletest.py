# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2022 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

# On an Adafruit Feather M4 with Floppy Featherwing, do some track-to-track seeking.

import board
import adafruit_floppy

floppy = adafruit_floppy.MFMFloppy(
    densitypin=board.A0,
    indexpin=board.A1,
    selectpin=board.A2,
    motorpin=board.A3,
    directionpin=board.A4,
    steppin=board.A5,
    track0pin=board.D11,
    protectpin=board.D10,
    rddatapin=board.D9,
    sidepin=board.D6,
    readypin=board.D5,
)

floppy.selected = True
floppy.spin = True
floppy.track = 0
floppy.track = 3
floppy.track = 0
floppy.track = 79
floppy.track = 0
