import os

import pandas as pd


def get_spot_data(forecast_version):
    path = f"data/forecast_version/{forecast_version}/dummy_spot_data.csv"
    df = pd.read_csv(path)
    return df


def get_supply_data(forecast_version):
    path = f"data/forecast_version/{forecast_version}/dummy_supply_data.csv"
    df = pd.read_csv(path)
    return df


def get_color_dict():
    path = "data/colors.csv"
    df = pd.read_csv(path)
    color_dict = dict(zip(df.name, df.color))
    return color_dict


def supply_filter_values():
    columns = [
        "Conversion Country",
        "Product",
        "Conversion Region",
        "Conversion Resource SubType",
        "Resource Region",
        "Resource Company",
    ]
    return {key: value for key, value in zip(columns, columns)}


def get_year_dropdown_vals(df):
    columns = df.columns
    years = [col for col in columns if col.isnumeric()]
    return years


def get_node_dropdown_vals(first_node):
    resource_columns = [
        "Resource Region",
        "Resource Country",
        "Resource Company",
        "Resource ID",
    ]
    columns = [
        "Conversion Company",
        "Conversion Country",
        "Product",
        "Conversion Region",
        "Conversion Resource SubType",
        "Conversion ID",
    ]
    if first_node:
        columns = resource_columns + columns
    data = [{"value": value, "label": value} for value in columns]
    return data


def get_filter_dropdown_vals(df, col):
    filters = df[col].unique()
    data = [{"value": filter, "label": filter} for filter in filters]
    return data


def get_top_x_values():
    options = [
        {"label": f"Top {val}", "value": str(val)} for val in range(5, 20, 5)
    ] + [{"label": "View All", "value": "view_all"}]
    return options


def get_forecast_version_values():
    forecast_versions = os.listdir("data/forecast_version")
    forecast_versions = [
        fv for fv in forecast_versions if not fv.startswith(".")
    ]
    dropdown_items = [{"label": fv, "value": fv} for fv in forecast_versions]
    return dropdown_items


def hex2rgb(hex_value):
    h = hex_value.strip("#")
    rgb = tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
    transparency_level = (0.2,)
    rgb_transparent = rgb + transparency_level
    return f"rgba{rgb_transparent}"
