from dataclasses import dataclass
from enum import Enum
from typing import List, Literal, Optional, Tuple

import numpy as np
from ophyd import Component as Cpt
from ophyd.status import AndStatus, Status

from dodal.devices.aperture import Aperture
from dodal.devices.logging_ophyd_device import InfoLoggingDevice
from dodal.devices.scatterguard import Scatterguard
from dodal.log import LOGGER

Aperture5d = Tuple[float, float, float, float, float]


class InvalidApertureMove(Exception):
    pass


class PositionName(str, Enum):
    LARGE = "large"
    MEDIUM = "medium"
    SMALL = "small"
    INVALID = "invalid"
    ROBOT_LOAD = "robot_load"


@dataclass
class AperturePositions:
    """Holds tuples (miniap_x, miniap_y, miniap_z, scatterguard_x, scatterguard_y)
    representing the motor positions needed to select a particular aperture size.
    """

    LARGE: Aperture5d
    MEDIUM: Aperture5d
    SMALL: Aperture5d
    ROBOT_LOAD: Aperture5d

    # one micrometre tolerance
    TOLERANCE_MM: float = 0.001

    def _distance_check(
        self,
        target: Aperture5d,
        present: Aperture5d,
    ) -> bool:
        return np.allclose(present, target, self.tolerance)

    @classmethod
    def match_to_name(self, present_position: Aperture5d) -> PositionName:
        assert AperturePositions.position_valid(present_position)
        positions: List[(Literal, Aperture5d)] = [
            (PositionName.LARGE, self.LARGE),
            (PositionName.MEDIUM, self.MEDIUM),
            (PositionName.SMALL, self.SMALL),
            (PositionName.ROBOT_LOAD, self.ROBOT_LOAD),
        ]

        for position_name, position_constant in positions:
            if AperturePositions._distance_check(position_constant, present_position):
                return position_name

        return PositionName.INVALID

    @classmethod
    def from_gda_beamline_params(cls, params):
        return cls(
            LARGE=(
                params["miniap_x_LARGE_APERTURE"],
                params["miniap_y_LARGE_APERTURE"],
                params["miniap_z_LARGE_APERTURE"],
                params["sg_x_LARGE_APERTURE"],
                params["sg_y_LARGE_APERTURE"],
            ),
            MEDIUM=(
                params["miniap_x_MEDIUM_APERTURE"],
                params["miniap_y_MEDIUM_APERTURE"],
                params["miniap_z_MEDIUM_APERTURE"],
                params["sg_x_MEDIUM_APERTURE"],
                params["sg_y_MEDIUM_APERTURE"],
            ),
            SMALL=(
                params["miniap_x_SMALL_APERTURE"],
                params["miniap_y_SMALL_APERTURE"],
                params["miniap_z_SMALL_APERTURE"],
                params["sg_x_SMALL_APERTURE"],
                params["sg_y_SMALL_APERTURE"],
            ),
            ROBOT_LOAD=(
                params["miniap_x_ROBOT_LOAD"],
                params["miniap_y_ROBOT_LOAD"],
                params["miniap_z_ROBOT_LOAD"],
                params["sg_x_ROBOT_LOAD"],
                params["sg_y_ROBOT_LOAD"],
            ),
        )

    def position_valid(self, pos: Aperture5d) -> bool:
        """
        Check if argument 'pos' is a valid position in this AperturePositions object.
        """
        options = [self.LARGE, self.MEDIUM, self.SMALL, self.ROBOT_LOAD]
        return pos in options


class ApertureScatterguard(InfoLoggingDevice):
    aperture = Cpt(Aperture, "-MO-MAPT-01:")
    scatterguard = Cpt(Scatterguard, "-MO-SCAT-01:")
    aperture_positions: Optional[AperturePositions] = None
    aperture_name: PositionName = PositionName.INVALID
    APERTURE_Z_TOLERANCE = 3  # Number of MRES steps

    def load_aperture_positions(self, positions: AperturePositions):
        LOGGER.info(f"{self.name} loaded in {positions}")
        self.aperture_positions = positions

    def _update_name(self, pos: Aperture5d) -> None:
        name = AperturePositions.match_to_name(pos)
        self.aperture_name = name

    def set(self, pos: Aperture5d) -> AndStatus:
        try:
            assert isinstance(self.aperture_positions, AperturePositions)
            assert self.aperture_positions.position_valid(pos)
        except AssertionError as e:
            raise InvalidApertureMove(repr(e))
        self._update_name(pos)
        return self._safe_move_within_datacollection_range(*pos)

    def _safe_move_within_datacollection_range(
        self,
        aperture_x: float,
        aperture_y: float,
        aperture_z: float,
        scatterguard_x: float,
        scatterguard_y: float,
    ) -> Status:
        """
        Move the aperture and scatterguard combo safely to a new position.
        See https://github.com/DiamondLightSource/hyperion/wiki/Aperture-Scatterguard-Collisions
        for why this is required.
        """
        # EpicsMotor does not have deadband/MRES field, so the way to check if we are
        # in a datacollection position is to see if we are "ready" (DMOV) and the target
        # position is correct
        ap_z_in_position = self.aperture.z.motor_done_move.get()
        # CASE still moving
        if not ap_z_in_position:
            status: Status = Status(obj=self)
            status.set_exception(
                InvalidApertureMove(
                    "ApertureScatterguard z is still moving. Wait for it to finish "
                    "before triggering another move."
                )
            )
            return status
        current_ap_z = self.aperture.z.user_setpoint.get()
        tolerance = self.APERTURE_Z_TOLERANCE * self.aperture.z.motor_resolution.get()
        # CASE invalid target position
        if abs(current_ap_z - aperture_z) > tolerance:
            raise InvalidApertureMove(
                "ApertureScatterguard safe move is not yet defined for positions "
                "outside of LARGE, MEDIUM, SMALL, ROBOT_LOAD. "
                f"Current aperture z ({current_ap_z}), outside of tolerance ({tolerance}) from target ({aperture_z})."
            )

        # CASE moves along Z
        current_ap_y = self.aperture.y.user_readback.get()
        if aperture_y > current_ap_y:
            sg_status: AndStatus = self.scatterguard.x.set(
                scatterguard_x
            ) & self.scatterguard.y.set(scatterguard_y)
            sg_status.wait()
            final_status = (
                sg_status
                & self.aperture.x.set(aperture_x)
                & self.aperture.y.set(aperture_y)
                & self.aperture.z.set(aperture_z)
            )
            return final_status

        # CASE does not move along Z
        else:
            ap_status: AndStatus = (
                self.aperture.x.set(aperture_x)
                & self.aperture.y.set(aperture_y)
                & self.aperture.z.set(aperture_z)
            )
            ap_status.wait()
            final_status = (
                ap_status
                & self.scatterguard.x.set(scatterguard_x)
                & self.scatterguard.y.set(scatterguard_y)
            )
            return final_status
