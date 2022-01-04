# SPDX-FileCopyrightText: 2022 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
adafruit_floppy
===============

Interface with old floppy drives.


* Author(s): Jeff Epler
"""

from digitalio import DigitalInOut, Pull
from micropython import const
from adafruit_ticks import ticks_ms, ticks_add, ticks_less

_MOTOR_DELAY_MS = 1000
_STEP_DELAY_MS = 100

_STEP_IN = const(0)
_STEP_OUT = const(1)

try:
    import typing
    import microcontroller
except ImportError:
    pass


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
        self._side = DigitalInOut(sidepin)
        self._side.switch_to_output()
        self._ready = DigitalInOut(readypin)
        self._ready.pull = Pull.UP

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

        If unsuccsessful, sets the internatl track number to None and raises an exception."""
        self._track = None
        for _ in range(250):
            if not self._track0.value:
                self._track = 0
                break
            self._do_step(_STEP_OUT, 1)
        raise RuntimeError("Could not reach track 0")

    def _check_inpos(self) -> None:
        track = self._track
        drive_says_track0 = not self._track0.value
        we_think_track0 = track == 0
        if drive_says_track0 != we_think_track0:
            raise RuntimeError("Drive lost position")

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
        else:
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
        self._side = head == 0
