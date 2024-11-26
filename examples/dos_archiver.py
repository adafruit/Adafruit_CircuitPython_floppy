# SPDX-FileCopyrightText: Copyright (c) 2024 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import os
import sdcardio
import board
import storage
import adafruit_floppy

"""DOS floppy archiver for Adafruit Floppsy

Insert an SD card & hook up your floppy drive.
Open the REPL / serial connection
Insert a floppy and press Enter to archive it
Do this for as many floppies as you like."""

floppy = adafruit_floppy.Floppy(
    densitypin=board.DENSITY,
    indexpin=board.INDEX,
    selectpin=board.SELECT,
    motorpin=board.MOTOR,
    directionpin=board.DIRECTION,
    steppin=board.STEP,
    track0pin=board.TRACK0,
    protectpin=board.WRPROT,
    rddatapin=board.RDDATA,
    sidepin=board.SIDE,
    readypin=board.READY,
    wrdatapin=board.WRDATA,
    wrgatepin=board.WRGATE,
    floppydirectionpin=board.FLOPPY_DIRECTION,
    floppyenablepin=board.FLOPPY_ENABLE,
)

_image_counter = 0


def open_next_image(extension="img"):
    """Return an opened numbered file on the sdcard, such as "img01234.jpg"."""
    global _image_counter  # pylint: disable=global-statement
    try:
        os.stat("/sd")
    except OSError as exc:  # no SD card!
        raise RuntimeError("No SD card mounted") from exc
    while True:
        filename = "/sd/dsk%04d.%s" % (_image_counter, extension)
        _image_counter += 1
        try:
            os.stat(filename)
        except OSError:
            break
    print("Writing to", filename)
    return open(filename, "wb")


sdcard = sdcardio.SDCard(board.SPI(), board.SD_CS)
vfs = storage.VfsFat(sdcard)
storage.mount(vfs, "/sd")

dev = None
blockdata = bytearray(512)
baddata = b"BADDATA0" * 64

while True:
    if dev is not None:
        dev.floppy.keep_selected = False
    input("Insert disk and press ENTER")

    try:
        if dev is None:
            dev = adafruit_floppy.FloppyBlockDevice(floppy, keep_selected=True)
        else:
            dev.floppy.keep_selected = True
            dev.autodetect()
    except OSError as e:
        print(e)
        continue

    bad_blocks = good_blocks = 0
    total_blocks = dev.count()
    pertrack = dev.sectors * dev.heads
    with open_next_image() as f:
        for i in range(total_blocks):
            if i % pertrack == 0:
                print(end=f"{i//pertrack:02d}")
            try:
                dev.readblocks(i, blockdata)
                print(end=".")
                f.write(blockdata)
                good_blocks += 1
            except Exception as e:  # pylint: disable=broad-exception-caught
                bad_blocks += 1
                print(end="!")
                f.write(baddata)
            if i % pertrack == (pertrack // 2 - 1):
                print(end="|")
            if i % pertrack == (pertrack - 1):
                print()

    print(
        f"{good_blocks} good + {bad_blocks} bad blocks",
        f"out of {total_blocks} ({total_blocks//2}KiB)",
    )
