# SPDX-License-Identifier: GPL-3.0-or-later
"""A pinhole camera for pseudo-3D scenes.

World points are (x right, y up, z ahead). The camera can turn left and right
but never tilts. Lines and polygons are clipped at the near plane before
projection, so geometry passing beside or behind the viewer is cut cleanly
instead of smearing across the view.
"""

from dataclasses import dataclass
from math import cos, radians, sin

from PySide6.QtCore import QLineF, QPointF
from PySide6.QtGui import QPolygonF

from qade_engine.core.geometry import lerp

Point3 = tuple[float, float, float]

NEAR = 0.1


@dataclass(frozen=True, slots=True)
class Pose:
    """Where the camera stands and which way it faces.

    Attributes:
        x: World x.
        y: World y.
        z: World z.
        yaw: Heading in degrees. Positive turns right.
    """

    x: float
    y: float
    z: float
    yaw: float = 0.0

    def lerp(self, other: "Pose", amount: float) -> "Pose":
        """Interpolates towards another pose, such as between two steps.

        Args:
            other: The pose at ``amount == 1``.
            amount: How far towards it.

        Returns:
            The pose between.
        """
        return Pose(
            lerp(self.x, other.x, amount),
            lerp(self.y, other.y, amount),
            lerp(self.z, other.z, amount),
            lerp(self.yaw, other.yaw, amount),
        )


class Camera:
    """Projects world points for one frame.

    Attributes:
        pose: Where the camera is.
        focal: Focal length in view units.
        center_x: View x of the line of sight.
        horizon: View y of the camera's eye level.
    """

    def __init__(self, pose: Pose, focal: float, center_x: float, horizon: float):
        """Creates a camera.

        Args:
            pose: Where the camera is.
            focal: Focal length in view units. Bigger zooms in.
            center_x: View x of the line of sight.
            horizon: View y of the camera's eye level.
        """
        self.pose = pose
        self.focal = focal
        self.center_x = center_x
        self.horizon = horizon
        self._cos = cos(radians(pose.yaw))
        self._sin = sin(radians(pose.yaw))

    def to_view(self, point: Point3) -> Point3:
        """Converts a world point to camera space.

        Args:
            point: The world point.

        Returns:
            The point with x right, y up and z straight ahead of the camera.
        """
        dx = point[0] - self.pose.x
        dz = point[2] - self.pose.z
        return (
            dx * self._cos - dz * self._sin,
            point[1] - self.pose.y,
            dx * self._sin + dz * self._cos,
        )

    def depth(self, point: Point3) -> float:
        """Distance of a world point ahead of the camera.

        Args:
            point: The world point.

        Returns:
            The distance, negative behind the camera.
        """
        return self.to_view(point)[2]

    def _screen(self, view: Point3) -> QPointF:
        return QPointF(
            self.center_x + self.focal * view[0] / view[2],
            self.horizon - self.focal * view[1] / view[2],
        )

    def project(self, point: Point3) -> QPointF | None:
        """Projects a world point.

        Args:
            point: The world point.

        Returns:
            The point in view coordinates, or None behind the near plane.
        """
        view = self.to_view(point)
        return self._screen(view) if view[2] >= NEAR else None

    def line(self, start: Point3, end: Point3) -> QLineF | None:
        """Projects a world segment, clipped to the near plane.

        Args:
            start: One end.
            end: The other end.

        Returns:
            The segment in view coordinates, or None if wholly behind the
            near plane.
        """
        a, b = self.to_view(start), self.to_view(end)
        if a[2] < NEAR and b[2] < NEAR:
            return None
        if a[2] < NEAR:
            a = _cut(a, b)
        elif b[2] < NEAR:
            b = _cut(b, a)
        return QLineF(self._screen(a), self._screen(b))

    def polygon(self, points: list[Point3]) -> QPolygonF | None:
        """Projects a world polygon, clipped to the near plane.

        Args:
            points: The corners, in order.

        Returns:
            The polygon in view coordinates, or None if wholly behind the
            near plane.
        """
        view = [self.to_view(point) for point in points]
        clipped: list[Point3] = []
        for index, current in enumerate(view):
            previous = view[index - 1]
            if (current[2] >= NEAR) != (previous[2] >= NEAR):
                clipped.append(_cut(previous, current))
            if current[2] >= NEAR:
                clipped.append(current)
        if len(clipped) < 3:
            return None
        return QPolygonF([self._screen(point) for point in clipped])


def _cut(outside: Point3, inside: Point3) -> Point3:
    """Where the segment crosses the near plane."""
    amount = (NEAR - outside[2]) / (inside[2] - outside[2])
    return (
        lerp(outside[0], inside[0], amount),
        lerp(outside[1], inside[1], amount),
        NEAR,
    )
