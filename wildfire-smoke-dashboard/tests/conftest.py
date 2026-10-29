"""Build the Dash app once for the test session.

dash.get_asset_url / get_relative_path / strip_relative_path read the running app's
config, so the app must exist before the About page builders or routing helpers run.
"""

import app  # noqa: F401
