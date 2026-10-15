"""Shale lithofacies regions on the Quartz / Carbonate / Clay ternary diagram.

Each region is (name, family, vertices); vertices are (quartz, carbonate, clay)
percentages. Family indexes theme.ROCK_TYPE_FILLS.
"""

ROCK_TYPES = [
    ("Carbonate Dominated", 0, [(0, 100, 0), (20, 80, 0), (0, 80, 20)]),
    ("Silica Dominated", 0, [(100, 0, 0), (80, 20, 0), (80, 0, 20)]),
    ("Clay Dominated", 0, [(0, 20, 80), (0, 0, 100), (20, 0, 80)]),
    (
        "Silica-rich Carbonate Mudstone",
        1,
        [(20, 80, 0), (10, 80, 10), (40, 50, 10), (50, 50, 0)],
    ),
    (
        "Silica-rich Argillaceous Mudstone",
        1,
        [(40, 10, 50), (10, 10, 80), (20, 0, 80), (50, 0, 50)],
    ),
    (
        "Carbonate-rich Argillaceous Mudstone",
        1,
        [(0, 50, 50), (0, 20, 80), (10, 10, 80), (10, 40, 50)],
    ),
    (
        "Carbonate-rich Siliceous Mudstone",
        1,
        [(80, 10, 10), (50, 10, 40), (50, 0, 50), (80, 0, 20)],
    ),
    (
        "Clay-rich Siliceous Mudstone",
        1,
        [(80, 20, 0), (80, 10, 10), (50, 40, 10), (50, 50, 0)],
    ),
    (
        "Clay-rich Carbonate Mudstone",
        1,
        [(10, 80, 10), (0, 80, 20), (0, 50, 50), (10, 50, 40)],
    ),
    ("Carbonate Siliceous Mudstone", 2, [(50, 50, 0), (30, 50, 20), (50, 30, 20)]),
    ("Argillaceous Carbonate Mudstone", 2, [(20, 50, 30), (0, 50, 50), (20, 30, 50)]),
    ("Argillaceous Siliceous Mudstone", 2, [(50, 20, 30), (30, 20, 50), (50, 0, 50)]),
    ("Mixed Siliceous Mudstone", 3, [(80, 10, 10), (50, 40, 10), (50, 10, 40)]),
    (
        "Mixed Mudstone",
        3,
        [(30, 50, 20), (20, 50, 30), (20, 30, 50), (30, 20, 50), (50, 20, 30), (50, 30, 20)],
    ),
    ("Mixed Argillaceous Mudstone", 3, [(40, 10, 50), (10, 40, 50), (10, 10, 80)]),
    ("Mixed Carbonate Mudstone", 3, [(40, 50, 10), (10, 80, 10), (10, 50, 40)]),
]
