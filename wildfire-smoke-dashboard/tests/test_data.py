"""Data layer — smoke plumes are trimmed to the state outline at load."""

from shapely.geometry import shape

from utils.data import CA_OUTLINE, SMOKE_BY_DAY


def test_smoke_plumes_stay_inside_california():
    bound = CA_OUTLINE.buffer(1e-3)  # allow for the 1e-3 coordinate snapping
    feats = [f for day in SMOKE_BY_DAY.values() for f in day]
    assert feats, "expected some smoke features in the snapshot"
    outside = [f["properties"]["date"] for f in feats if not shape(f["geometry"]).within(bound)]
    assert not outside, f"smoke drawn outside California on {sorted(set(outside))[:5]}"
