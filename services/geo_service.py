import random
import logging


logger = logging.getLogger(__name__)


class GeoService:
    @staticmethod
    def get_jittered_coordinates(base_lat: float, base_long: float) -> tuple[float, float]:
        """Adds a tiny randomized offset (~5-15 meters) to simulate real GPS drift."""
        lat_offset = random.uniform(-0.00015, 0.00015)
        long_offset = random.uniform(-0.00015, 0.00015)
        coordinates = round(base_lat + lat_offset, 7), round(base_long + long_offset, 7)
        logger.debug("Generated jittered office coordinates.")
        return coordinates
