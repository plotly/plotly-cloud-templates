import pandas as pd

supply_df = pd.DataFrame(
    [
        [1, "Resource ID_0", "P1"],
        [3, "Spot Market Lep", "P2"],
        [5, "Resource ID_2", "P1"],
        [7, "Resource ID_3", "P3"],
        [4, "Spot Market Spod", "P1"],
        [3, "Spot Market Lep", "P2"],
        [5, "Resource ID_2", "P3"],
        [4, "Spot Market Spod", "P3"],
    ],
    columns=["2023", "Resource 1", "Product"],
)

spod_df = pd.DataFrame(
    [
        [3, "Resource ID_4", "Spot Market Spod"],
        [2, "Resource ID_5", "Spot Market Spod"],
        [1, "Resource ID_5", "Spot Market Spod"],
        [2, "Resource ID_2", "Spot Market Spod"],
        [1, "Resource ID_3", "Spot Market Lep"],
        [5, "Resource ID_0", "Spot Market Lep"],
    ],
    columns=["2023", "Resource 1", "Offtake Owner"],
)


test_links = [
    ((0, 7), 1),
    ((1, 8), 6),
    ((2, 7), 5),
    ((3, 9), 7),
    ((4, 7), 4),
    ((2, 9), 5),
    ((4, 9), 4),
    ((5, 4), 3),
    ((6, 4), 3),
    ((2, 4), 2),
    ((3, 1), 1),
    ((0, 1), 5),
]
