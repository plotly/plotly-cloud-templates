"""Demo registry. Each module exposes SLUG, TITLE, GROUP, KICKER, ABOUT, view(), controls() and stats()."""

from . import cfd, point_cloud, procedural, slices, synthetic_volume, terrain, volume_rendering

DEMOS = [procedural, terrain, point_cloud, synthetic_volume, volume_rendering, slices, cfd]
BY_SLUG = {d.SLUG: d for d in DEMOS}
