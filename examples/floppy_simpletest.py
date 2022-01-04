# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2022 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

# On an Adafruit Feather M4 with appropriate connections, do some
# track-to-track seeking.
import board
import adafruit_floppy

floppy = adafruit_floppy.Floppy(
    densitypin=board.D5,
    indexpin=board.D6,
    selectpin=board.A5,
    motorpin=board.D9,
    directionpin=board.D10,
    steppin=board.D11,
    track0pin=board.A4,
    protectpin=board.A3,
    rddatapin=board.D12,
    sidepin=board.A1,
    readypin=board.A0,
)

floppy.selected = True
floppy.spin = True
floppy.track = 0
floppy.track = 3
floppy.track = 0
floppy.track = 79
floppy.track = 0
