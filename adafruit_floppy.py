import time
from digitalio import DigitalInOut, Pull
from micropython import const
from adafruit_ticks import ticks_ms, ticks_add, ticks_less

motor_delay_ms = 1000
step_delay_ms = 100

STEP_IN = const(0)
STEP_OUT = const(1)

try:
    import typing
    import microcontroller
except ImportError:
    pass


def OptionalDigitalInOut(
    maybe_pin: Optional[microcontroller.Pin],
) -> typing.Optional[DigitalInOut]:
    return None if maybe_pin is None else DigitalInOut(maybe_pin)


def sleep_deadline_ms(deadline):
    while ticks_less(ticks_ms(), deadline):
        pass


def sleep_ms(interval):
    sleep_deadline_ms(ticks_add(ticks_ms(), interval))


class Floppy:
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
        self._wrdata = OptionalDigitalInOut(wrdatapin)
        self._wrgate = OptionalDigitalInOut(wrgatepin)
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
        for i in range(count):
            sleep_ms(step_delay_ms)
            self._step.value = True
            sleep_ms(step_delay_ms)
            self._step.value = False

    def find_track0(self):
        for i in range(250):
            if not self._track0.value:
                self._track = 0
                break
            self._do_step(STEP_OUT, 1)

    def _check_inpos(self)->None:
        track = self._track
        drive_says_track0 = not self._track0.value
        we_think_track0 = track == 0
        if drive_says_track0 != we_think_track0:
            raise RuntimeError("Drive lost position")

    @property
    def track(self) -> typing.Optional[int]:
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
            self._do_step(STEP_OUT, -delta)
        else:
            self._do_step(STEP_IN, delta)

        self._track = track
        self._check_inpos()

    @property
    def spin(self) -> bool:
        return not self._motor.value

    @spin.setter
    def spin(self, motor_on: bool) -> None:
        if self.spin == motor_on:
            return

        self._motor.value = not motor_on
        if motor_on:
            sleep_ms(motor_delay_ms)
            deadline = ticks_add(ticks_ms(), 10_000)

            while ticks_less(ticks_ms(), deadline):
                if not self._index.value:
                    break
            else:
                raise RuntimeError("Didn't find an index pulse")

    @property
    def selected(self) -> bool:
        return not self._select.value

    @selected.setter
    def selected(self, select: bool) -> None:
        self._select.value = not select

    @property
    def side(self) -> bool:
        return not self._side.value

    @side.setter
    def side(self, head: bool) -> None:
        self._side = not head
