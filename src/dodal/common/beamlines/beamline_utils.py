import inspect
from collections.abc import Callable
from typing import Final, TypeVar, cast

from bluesky.run_engine import call_in_bluesky_event_loop
from ophyd import Device as OphydV1Device
from ophyd.sim import make_fake_device
from ophyd_async.core import Device as OphydV2Device
from ophyd_async.core import wait_for_connection as v2_device_wait_for_connection

from dodal.common.types import UpdatingDirectoryProvider
from dodal.utils import AnyDevice, BeamlinePrefix, skip_device

DEFAULT_CONNECTION_TIMEOUT: Final[float] = 5.0

ACTIVE_DEVICES: dict[str, AnyDevice] = {}
BL = ""
DIRECTORY_PROVIDER: UpdatingDirectoryProvider | None = None


def set_beamline(beamline: str):
    global BL
    BL = beamline


def clear_devices():
    global ACTIVE_DEVICES
    for d in list(ACTIVE_DEVICES):
        del ACTIVE_DEVICES[d]


def clear_device(name: str):
    global ACTIVE_DEVICES
    del ACTIVE_DEVICES[name]


def list_active_devices() -> list[str]:
    global ACTIVE_DEVICES
    return list(ACTIVE_DEVICES.keys())


def active_device_is_same_type(
    active_device: AnyDevice, device: Callable[..., AnyDevice]
) -> bool:
    return inspect.isclass(device) and isinstance(active_device, device)


def wait_for_connection(
    device: AnyDevice,
    timeout: float = DEFAULT_CONNECTION_TIMEOUT,
    mock: bool = False,
) -> None:
    if isinstance(device, OphydV1Device):
        device.wait_for_connection(timeout=timeout)
    elif isinstance(device, OphydV2Device):
        call_in_bluesky_event_loop(
            v2_device_wait_for_connection(
                coros=device.connect(mock=mock, timeout=timeout)
            ),
        )
    else:
        raise TypeError(
            f"Invalid type {device.__class__.__name__} in _wait_for_connection"
        )


T = TypeVar("T", bound=AnyDevice)


@skip_device()
def device_instantiation(
    device_factory: Callable[..., T],
    name: str,
    prefix: str,
    wait: bool,
    fake: bool,
    post_create: Callable[[T], None] | None = None,
    bl_prefix: bool = True,
    **kwargs,
) -> T:
    """Method to allow generic creation of singleton devices. Meant to be used to easily
    define lists of devices in beamline files. Additional keyword arguments are passed
    directly to the device constructor.

    Arguments:
        device_factory: Callable    the device class
        name: str                   the name for ophyd
        prefix: str                 the PV prefix for the most (usually all) components
        wait: bool                  whether to run .wait_for_connection()
        fake: bool                  whether to fake with ophyd.sim
        post_create: Callable       (optional) a function to be run on the device after
                                    creation
        bl_prefix: bool             if true, add the beamline prefix when instantiating, if
                                    false the complete PV prefix must be supplied.
    Returns:
        The instance of the device.
    """
    already_existing_device: AnyDevice | None = ACTIVE_DEVICES.get(name)
    if fake:
        device_factory = cast(Callable[..., T], make_fake_device(device_factory))
    if already_existing_device is None:
        device_instance = device_factory(
            name=name,
            prefix=(
                f"{(BeamlinePrefix(BL).beamline_prefix)}{prefix}"
                if bl_prefix
                else prefix
            ),
            **kwargs,
        )
        ACTIVE_DEVICES[name] = device_instance
        if wait:
            wait_for_connection(device_instance, mock=fake)

    else:
        if not active_device_is_same_type(already_existing_device, device_factory):
            raise TypeError(
                f"Can't instantiate device of type {device_factory} with the same "
                f"name as an existing device. Device name '{name}' already used for "
                f"a(n) {type(already_existing_device)}."
            )
        device_instance = cast(T, already_existing_device)
    if post_create:
        post_create(device_instance)
    return device_instance


def set_directory_provider(provider: UpdatingDirectoryProvider):
    global PATH_PROVIDER

    PATH_PROVIDER = provider


def get_directory_provider() -> UpdatingDirectoryProvider:
    if PATH_PROVIDER is None:
        raise ValueError(
            "DirectoryProvider has not been set! Ophyd-async StandardDetectors will not be able to write!"
        )
    return PATH_PROVIDER
