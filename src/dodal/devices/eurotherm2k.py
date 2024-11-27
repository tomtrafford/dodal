import asyncio
import time
from enum import Enum
from typing import Callable, List, Optional

from bluesky.protocols import Location
from ophyd_async.core import AsyncStatus, StandardReadable, observe_value
from ophyd_async.epics.signal import epics_signal_r, epics_signal_rw

class Eurotherm2K(StandardReadable):
    """Device to represent a Eurotherm2k temperature controller

    Attributes:

    Args:
        prefix (str): PV prefix for this device
        name (str): unique name for this device
    """

    def __init__(self, prefix: str, name: str):
        self.temp = epics_signal_r(float, prefix + "PV:RBV")
        self.dsc = epics_signal_r(float, prefix + "DSC:")

        self.ramp_rate = epics_signal_rw(
            float, prefix + "RR:RBV", prefix + "RR:"
        )
        self.set_point = epics_signal_rw(
            float, prefix + "SP:RBV", prefix + "SP:"
        )

        self.error = epics_signal_r(str, prefix + "ERR:")

        self.set_readable_signals(
            read=(self.temp,), config=(self.ramp_rate, self.set_point)
        )

        super().__init__(name=name)
