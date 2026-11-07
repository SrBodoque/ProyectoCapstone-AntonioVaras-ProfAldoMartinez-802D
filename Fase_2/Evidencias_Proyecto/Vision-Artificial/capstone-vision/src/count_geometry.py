"""Solo pertenencia H4. No exige línea final, bordes de salida, ángulos o velocidad."""

from .zones import ZoneProfile


class ZoneGeometry:
    def __init__(self, profile):
        # La aplicación aporta el perfil semántico validado por count_orientation.
        self.profile = ZoneProfile.from_dict(profile.to_dict())

    def classify(self, normalized):
        return self.profile.classify((normalized[0] * self.profile.width,
                                      normalized[1] * self.profile.height),
                                     self.profile.width, self.profile.height)
