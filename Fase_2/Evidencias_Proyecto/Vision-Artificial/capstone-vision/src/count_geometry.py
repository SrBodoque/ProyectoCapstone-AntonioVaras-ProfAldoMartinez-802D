"""Orientación conservadora del recorrido A -> B, sobre los polígonos H4.

No crea regiones ni líneas. Toda pertenencia sigue en ZoneProfile/point_location.
Las coordenadas de trabajo usan la distancia entre centroides como unidad,
compensando el aspecto de la imagen antes de calcular distancias y ángulos.
"""

import math
from dataclasses import dataclass

from .zones import EPS, ZoneError, ZoneProfile, point_location, signed_area

FORWARD_COS = math.sqrt(.5)  # Cono de 45 grados; política conservadora de H5.1.


def subtract(a, b):
    return a[0] - b[0], a[1] - b[1]


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def determinant(a, b):
    return a[0] * b[1] - a[1] * b[0]


def centroid(points):
    area = signed_area(points)
    terms = [(p, q, determinant(p, q)) for p, q in zip(points, points[1:] + points[:1])]
    return tuple(sum((p[k] + q[k]) * cross for p, q, cross in terms) / (6 * area)
                 for k in (0, 1))


def clearance(point, polygon):
    """Distancia a los segmentos del borde existente, no a una línea nueva."""
    distances = []
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        edge = subtract(b, a)
        fraction = max(0., min(1., dot(subtract(point, a), edge) / dot(edge, edge)))
        distances.append(math.dist(point, (a[0] + fraction * edge[0], a[1] + fraction * edge[1])))
    return min(distances)


def convex_polygon(points):
    points = list(points if signed_area(points) > 0 else tuple(reversed(points)))
    changed = True
    while changed and len(points) > 3:
        changed = False
        for i, p in enumerate(points):
            if abs(determinant(subtract(p, points[i - 1]), subtract(points[(i + 1) % len(points)], p))) <= EPS:
                del points[i]
                changed = True
                break
    for i, p in enumerate(points):
        if determinant(subtract(p, points[i - 1]), subtract(points[(i + 1) % len(points)], p)) <= EPS:
            raise ZoneError("Conteo ambiguo: H5.1 requiere zonas convexas y un recorrido aproximadamente recto. Revise la calibración A/B.")
    return tuple(points)


@dataclass(frozen=True)
class BoundaryExit:
    point: tuple[float, float]
    normal: tuple[float, float]
    anchor: tuple[float, float]
    direction: int


class RouteGeometry:
    def __init__(self, profile, margin):
        self.profile = ZoneProfile.from_dict(profile.to_dict())
        self.margin = margin
        self.aspect = profile.width / profile.height
        metric = lambda p: (p[0] * self.aspect, p[1])
        a, b = tuple(map(metric, profile.a)), tuple(map(metric, profile.b))
        self.origin = centroid(a)
        delta = subtract(centroid(b), self.origin)
        self.distance = math.hypot(*delta)
        if self.distance <= EPS:
            raise ZoneError("Conteo ambiguo: no hay orientación A -> B. Revise la calibración.")
        self.axis = (delta[0] / self.distance, delta[1] / self.distance)
        self.side = (-self.axis[1], self.axis[0])
        self.polygons = {"A": convex_polygon(tuple(self.project(p) for p in profile.a)),
                         "B": convex_polygon(tuple(self.project(p) for p in profile.b))}
        pa, pb = self.polygons["A"], self.polygons["B"]
        if max(p[0] for p in pa) > min(p[0] for p in pb) + EPS:
            raise ZoneError("Conteo ambiguo: A y B se solapan en la dirección del recorrido. Revise su alineación.")
        lateral = [(min(p[1] for p in poly), max(p[1] for p in poly)) for poly in (pa, pb)]
        common = min(v[1] for v in lateral) - max(v[0] for v in lateral)
        if common < .5 * min(v[1] - v[0] for v in lateral):
            raise ZoneError("Conteo ambiguo: las zonas no comparten un corredor suficiente. Revise A/B.")
        if any(clearance(centroid(poly), poly) <= margin for poly in (pa, pb)):
            raise ZoneError("Zonas demasiado estrechas para el margen del contador. Revise calibración o position_margin.")
        if not any(normal[0] >= FORWARD_COS - EPS and length > 2 * margin
                   for _, _, _, length, normal in self._edges("A")):
            raise ZoneError("Conteo ambiguo: A no tiene un borde frontal utilizable hacia B. Revise la calibración.")
        if not self._visible_exit("B", 1):
            raise ZoneError("No se puede observar una salida frontal de B dentro de la imagen. Revise la calibración; no se contará por desaparición.")

    def project(self, normalized):
        delta = subtract((normalized[0] * self.aspect, normalized[1]), self.origin)
        return dot(delta, self.axis) / self.distance, dot(delta, self.side) / self.distance

    def unproject(self, point):
        x = self.origin[0] + self.distance * (point[0] * self.axis[0] + point[1] * self.side[0])
        y = self.origin[1] + self.distance * (point[0] * self.axis[1] + point[1] * self.side[1])
        return x / self.aspect, y

    def classify(self, normalized):
        return self.profile.classify((normalized[0] * self.profile.width,
                                      normalized[1] * self.profile.height),
                                     self.profile.width, self.profile.height)

    def deep(self, zone, point):
        return zone in self.polygons and clearance(point, self.polygons[zone]) >= self.margin - EPS

    def _edges(self, zone):
        polygon = self.polygons[zone]
        for a, b in zip(polygon, polygon[1:] + polygon[:1]):
            edge = subtract(b, a)
            length = math.hypot(*edge)
            yield a, b, edge, length, (edge[1] / length, -edge[0] / length)

    def _visible_exit(self, zone, direction):
        for a, b, _, length, normal in self._edges(zone):
            if direction * normal[0] < FORWARD_COS - EPS or length <= 2 * self.margin:
                continue
            middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            beyond = self.unproject((middle[0] + direction * 2 * self.margin, middle[1]))
            if all(0 < value < 1 for value in beyond) and self.classify(beyond) == "FUERA":
                return True
        return False

    def exit_through(self, zone, previous, current, direction=1):
        """Exige cruzar un único borde frontal, alejado de sus vértices."""
        polygon = self.polygons[zone]
        if point_location(previous, polygon) < 0 or point_location(current, polygon) >= 0:
            return None
        movement = subtract(current, previous)
        length = math.hypot(*movement)
        if length <= EPS or direction * movement[0] / length < FORWARD_COS - EPS:
            return None
        hits = []
        for a, _, edge, edge_length, normal in self._edges(zone):
            denominator = determinant(movement, edge)
            if abs(denominator) <= EPS:
                continue
            offset = subtract(a, previous)
            t = determinant(offset, edge) / denominator
            u = determinant(offset, movement) / denominator
            if -EPS <= t <= 1 + EPS and -EPS <= u <= 1 + EPS:
                hits.append((t, u, edge_length, normal))
        if len(hits) != 1:
            return None  # Un vértice o una trayectoria tangente no acredita salida.
        t, u, edge_length, normal = hits[0]
        if (direction * normal[0] < FORWARD_COS - EPS
                or min(u, 1 - u) * edge_length < self.margin):
            return None
        cross = (previous[0] + t * movement[0], previous[1] + t * movement[1])
        return BoundaryExit(cross, normal, previous, direction)

    def beyond(self, crossing, point):
        delta = subtract(point, crossing.point)
        movement = subtract(point, crossing.anchor)
        length = math.hypot(*movement)
        return (dot(delta, crossing.normal) >= self.margin - EPS
                and crossing.direction * delta[0] >= self.margin - EPS
                and length > EPS
                and crossing.direction * movement[0] / length >= FORWARD_COS - EPS)
