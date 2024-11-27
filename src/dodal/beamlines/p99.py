from dodal.common.beamlines.beamline_utils import (
    device_instantiation,
    get_path_provider,
    set_path_provider,
    set_beamline,
)
from dodal.devices.motors import XYZPositioner
from dodal.devices.p99.sample_stage import FilterMotor, SampleAngleStage
from ophyd_async.fastcs.panda import HDFPanda

from dodal.log import set_beamline as set_log_beamline
from dodal.utils import get_beamline_name, skip_device

BL = get_beamline_name("BL99P")
set_log_beamline(BL)
set_beamline(BL)


def panda1(
    wait_for_connection: bool = True,
    fake_with_ophyd_sim: bool = False,
) -> HDFPanda:
    return device_instantiation(
        HDFPanda,
        "panda1",
        "-MO-PANDA-01:",
        wait_for_connection,
        fake_with_ophyd_sim,
        path_provider=get_path_provider(),
    )

def sample_angle_stage(
    wait_for_connection: bool = True, fake_with_ophyd_sim: bool = False
) -> SampleAngleStage:
    """Sample stage for p99"""

    return device_instantiation(
        SampleAngleStage,
        prefix="-MO-STAGE-01:",
        name="sample_angle_stage",
        wait=wait_for_connection,
        fake=fake_with_ophyd_sim,
    )


def sample_stage_filer(
    wait_for_connection: bool = True, fake_with_ophyd_sim: bool = False
) -> FilterMotor:
    """Sample stage for p99"""

    return device_instantiation(
        FilterMotor,
        prefix="-MO-STAGE-02:MP:SELECT",
        name="sample_stage_filer",
        wait=wait_for_connection,
        fake=fake_with_ophyd_sim,
    )


def sample_xyz_stage(
    wait_for_connection: bool = True, fake_with_ophyd_sim: bool = False
) -> XYZPositioner:
    return device_instantiation(
        FilterMotor,
        prefix="-MO-STAGE-02:",
        name="sample_xyz_stage",
        wait=wait_for_connection,
        fake=fake_with_ophyd_sim,
    )


def sample_lab_xyz_stage(
    wait_for_connection: bool = True, fake_with_ophyd_sim: bool = False
) -> XYZPositioner:
    return device_instantiation(
        FilterMotor,
        prefix="-MO-STAGE-02:LAB:",
        name="sample_lab_xyz_stage",
        wait=wait_for_connection,
        fake=fake_with_ophyd_sim,
    )
