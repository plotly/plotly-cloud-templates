import dash

from dash_opencellid import callbacks, data  # noqa: F401 (registers the callbacks)
from dash_opencellid.layout import layout

# Download (if needed) and load the dataset in the background so that the server can
# start answering requests right away
data.start_loading()

app = dash.Dash(__name__, title="World Cell Towers")
app.layout = layout
server = app.server

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
