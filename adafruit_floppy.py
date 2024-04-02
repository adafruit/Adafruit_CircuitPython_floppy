# SPDX-FileCopyrightText: 2022 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
adafruit_floppy
===============

Interface with old floppy drives.


* Author(s): Jeff Epler
"""

import floppyio
from digitalio import DigitalInOut, Pull
from micropython import const
from adafruit_ticks import ticks_ms, ticks_add, ticks_less

_MOTOR_DELAY_MS = 1000
_STEP_DELAY_MS = 10

_STEP_IN = const(0)
_STEP_OUT = const(1)

try:
    import typing
    import microcontroller
    import circuitpython_typing  # pylint: disable=unused-import
except ImportError:
    pass


__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_floppy.git"


def _optionaldigitalinout(
    maybe_pin: typing.Optional[microcontroller.Pin],
) -> typing.Optional[DigitalInOut]:
    return None if maybe_pin is None else DigitalInOut(maybe_pin)


def _sleep_deadline_ms(deadline):
    while ticks_less(ticks_ms(), deadline):
        pass


def _sleep_ms(interval):
    _sleep_deadline_ms(ticks_add(ticks_ms(), interval))


class Floppy:  # pylint: disable=too-many-instance-attributes
    """Interface with floppy disk drive hardware"""

    _track: typing.Optional[int]

    def __init__(
        self,
        *,
        densitypin: microcontroller.Pin,
        indexpin: microcontroller.Pin,
        selectpin: microcontroller.Pin,
        motorpin: microcontroller.Pin,
        directionpin: microcontroller.Pin,
        steppin: microcontroller.Pin,
        track0pin: microcontroller.Pin,
        protectpin: microcontroller.Pin,
        rddatapin: microcontroller.Pin,
        sidepin: microcontroller.Pin,
        readypin: microcontroller.Pin,
        wrdatapin: typing.Optional[microcontroller.Pin] = None,
        wrgatepin: typing.Optional[microcontroller.Pin] = None,
        floppydirectionpin: typing.Optional[microcontroller.Pin] = None,
    ) -> None:
        self._density = DigitalInOut(densitypin)
        self._density.pull = Pull.UP
        self._index = DigitalInOut(indexpin)
        self._index.pull = Pull.UP
        self._select = DigitalInOut(selectpin)
        self._select.switch_to_output()
        self._motor = DigitalInOut(motorpin)
        self._motor.switch_to_output()
        self._direction = DigitalInOut(directionpin)
        self._direction.switch_to_output()
        self._step = DigitalInOut(steppin)
        self._step.switch_to_output()
        self._wrdata = _optionaldigitalinout(wrdatapin)
        self._wrgate = _optionaldigitalinout(wrgatepin)
        self._track0 = DigitalInOut(track0pin)
        self._track0.pull = Pull.UP
        self._protect = DigitalInOut(protectpin)
        self._protect.pull = Pull.UP
        self._rddata = DigitalInOut(rddatapin)
        self._rddata.pull = Pull.UP
        self._side = DigitalInOut(sidepin)
        self._side.switch_to_output(True)
        self._ready = DigitalInOut(readypin)
        self._ready.pull = Pull.UP

        self._floppydirection = _optionaldigitalinout(floppydirectionpin)
        if self._floppydirection:
            self._floppydirection.switch_to_output(True)

        self._track = None

    def _do_step(self, direction, count):
        self._direction.value = direction
        for _ in range(count):
            _sleep_ms(_STEP_DELAY_MS)
            self._step.value = True
            _sleep_ms(_STEP_DELAY_MS)
            self._step.value = False

    def find_track0(self):
        """Move the head out until the 'track0' signal becomes False

        If successful, sets the internal track number to 0.

        If unsuccsessful, sets the internatl track number to None and raises an exception.
        """
        self._track = None
        # First move off of track0. One of my drives would not function properly
        # without this initial move-off.
        for _ in range(4):
            self._do_step(_STEP_IN, 1)
        for _ in range(250):
            if not self._track0.value:
                self._track = 0
                self._check_inpos()
                return
            self._do_step(_STEP_OUT, 1)
        raise RuntimeError("Could not reach track 0")

    def _check_inpos(self) -> None:
        track = self._track
        drive_says_track0 = not self._track0.value
        we_think_track0 = track == 0
        if drive_says_track0 != we_think_track0:
            raise RuntimeError(f"Drive lost position (target={track}, track0 sensor {drive_says_track0})")

    @property
    def track(self) -> typing.Optional[int]:
        """The current track number, or None if the track number is unknown."""
        self._check_inpos()
        return self._track

    @track.setter
    def track(self, track: int) -> None:
        if self._track is None:
            self.find_track0()

        if track < 0:
            raise ValueError("Invalid seek to negative track number")

        delta = track - self.track
        if delta < 0:
            self._do_step(_STEP_OUT, -delta)
        elif delta > 0:
            self._do_step(_STEP_IN, delta)

        self._track = track
        self._check_inpos()

    @property
    def spin(self) -> bool:
        """True spins the floppy, False stops it"""
        return not self._motor.value

    @spin.setter
    def spin(self, motor_on: bool) -> None:
        if self.spin == motor_on:
            return

        self._motor.value = not motor_on
        if motor_on:
            _sleep_ms(_MOTOR_DELAY_MS)
            deadline = ticks_add(ticks_ms(), 10_000)

            while ticks_less(ticks_ms(), deadline):
                if not self._index.value:
                    break
            else:
                raise RuntimeError("Didn't find an index pulse")

    @property
    def selected(self) -> bool:
        """Select this drive.

        Set this property to True before doing anything with the drive."""
        return not self._select.value

    @selected.setter
    def selected(self, select: bool) -> None:
        self._select.value = not select

    @property
    def side(self) -> int:
        """The side (0/1) for read/write operations"""
        return int(not self._side.value)

    @side.setter
    def side(self, head: int) -> None:
        self._side.value = head == 0

    def flux_readinto(self, buf: "circuitpython_typing.WritableBuffer") -> int:
        """Read flux transition information into the buffer.

        The function returns when the buffer has filled, or when the index input
        indicates that one full revolution of data has been recorded.  Due to
        technical limitations, this process may not be interruptible by
        KeyboardInterrupt.

        :param buf: Read data into this buffer.
            Each element represents the time between successive zero-to-one transitions.
        :return: The actual number of bytes of read"""
        return floppyio.flux_readinto(buf, self._rddata, self._index)


class FloppyBlockDevice:
    """Wrap an MFMFloppy object into a block device suitable for `storage.VfsFat`

    The default heads/sectors/tracks setting are for 3.5", 1.44MB floppies.

    In the current implementation, the floppy is read-only.

    A cache is used for track 0 on cylinder 0 and for the last track accessed.

    Example::

        import storage
        import adafruit_floppy

        floppy = adafruit_floppy.Floppy(...)
        block_device = adafruit_floppy.FloppyBlockDevice(floppy)
        vfs = storage.VfsFat(f)
        storage.mount(vfs, '/floppy')
        print(os.listdir("/floppy"))
    """

    def __init__(self, floppy, heads=2, sectors=18, tracks=80, flux_buffer=None, t1_nom_ns: float=1000):
        self.floppy = floppy
        self.heads = heads
        self.sectors = sectors
        self.tracks = tracks
        self.flux_buffer = flux_buffer or buffer(sectors * 12 * 512)
        self.track0side0_cache = memoryview(bytearray(sectors * 512))
        self.track0side0_validity = bytearray(sectors)
        self.track_cache = memoryview(bytearray(sectors * 512))
        self.track_validity = bytearray(sectors)

        self._t2_5_max = round(2.5 * t1_nom_ns * floppyio.samplerate * 1e-9)
        self._t3_5_max = round(3.5 * t1_nom_ns * floppyio.samplerate * 1e-9)

        self._track_read(self.track0side0_cache, self.track0side0_validity, 0, 0)

        self.cached_track = -1
        self.cached_side = -1


    def deinit(self):
        """Deinitialize this object"""
        self.floppy.deinit()
        del self.flux_buffer
        del self.track0side0_cache
        del self.track_validity

    def sync(self):
        """Write out any pending data to disk (does nothing)"""

    def writeblocks(self, start, buf):  # pylint: disable=no-self-use
        """Write to the floppy (always raises an exception)"""
        raise OSError("Read-only filesystem")

    def count(self):
        """Return the floppy capacity in 512-byte units"""
        return self.heads * self.sectors * self.tracks

    def readblocks(self, start_block, buf):
        """Read a number of blocks from the flopppy"""
        buf = memoryview(buf).cast("B")
        for i in range(0, len(buf) // 512):
            self._readblock(start_block + i, buf[i * 512 : (i + 1) * 512])

    def _readblock(self, block, buf):
        if block > self.count():
            raise OSError("Read past end of media")
        track = block // (self.heads * self.sectors)
        block %= self.heads * self.sectors
        side = block // (self.sectors)
        block %= self.sectors
        trackdata, validity = self._get_track_data(track, side)
        if not validity[block]:
            raise OSError(f"Failed to read sector {track}/{side}/{block}")
        buf[:] = trackdata[block * 512 : (block + 1) * 512]

    def _get_track_data(self, track, side):
        if track == 0 and side == 0:
            return self.track0side0_cache, self.track0side0_validity
        if track != self.cached_track or side != self.cached_side:
            self._track_read(self.track_cache, self.track_validity, track, side)
        return self.track_cache, self.track_validity

    def _track_read(self, track_data, validity, track, side):
        self.floppy.selected = True
        self.floppy.spin = True
        self.floppy.track = track
        self.floppy.side = side
        self._mfm_readinto(track_data, validity)
        self.floppy.spin = False
        self.floppy.selected = False
        self.cached_track = track
        self.cached_side = side

    def _mfm_readinto(self, track_data, validity):
        for i in range(5):
            self.floppy.flux_readinto(self.flux_buffer)
            print("timing bins", self._t2_5_max, self._t3_5_max)
            n = floppyio.mfm_readinto(track_data, self.flux_buffer, self._t2_5_max, self._t3_5_max, validity, i==0)
            if n == self.sectors: break
