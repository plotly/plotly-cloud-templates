## File Structure
my-dash-app/
├── app.py                # Main application file
├── assets/               # Static files (CSS, images, favicon)
├── pages/                # Directory for multi-page app routes
  └── home.py
  └── analytics.py
├── requirements.txt      # Python dependencies
└── AGENTS.md             # This file

If deploying to Dash Enterprise, also add:
├── Procfile              # Process declarations (required)
├── project.toml          # Build configuration (optional)
└── Aptfile               # System packages (optional)

If deploying to Plotly Cloud, also add:
└── plotly-cloud.toml     # Build configuration (optional)

## General Architecture
- **Global Variables**: Never use global variables to store user-specific state. All mutable state must live in the client browser using `dcc.Store` or URL parameters.
- **Server Variable**: Make sure the app file always exposes a server variable: `server = app.server`
- **Dash Pages**: If Snapshot Engine is used, do not use Dash Pages; use callback routing instead to navigate between views. Otherwise, use `dash.page_registry`, keep all pages in a `pages/` directory, and register each page with `dash.register_page(__name__)`.
- **App IDs**: Prefer descriptive IDs like `"sales-filter-dropdown"` over `"dropdown-1"`. IDs must be unique across the entire app, including all pages.
- **Loading Data**: Load data inside callbacks, not at import time. Avoid `df = pd.read_csv(...)` at module level. Data loaded at startup won't refresh until the process restarts. Fetch or refresh data inside the callback that needs it, or use a layout function (`def serve_layout(): ...`) when the layout must be rebuilt on each page load.
- **Server-side Filtering**: Filter, aggregate, and paginate data in Python before passing it to graphs or `AgGrid`. Only send the rows or points needed for the current view to the client.
- **Pin Dependencies**: Specify minimum or exact versions for `dash`, `plotly`, and component libraries in `requirements.txt` to avoid breaking changes on deploy.

## Callbacks
- **Dataset Size**: Do not pass massive datasets through `dcc.Store` if they can be cached server-side. Use `dcc.Store` only for lightweight state (IDs, UI toggles, query filters) with a maximum of 5MB.
- **Caching**: For large datasets, expensive database queries, heavy computations, or API requests, implement server-side caching using `flask_caching`. Decorate data-fetching operations with the `@cache.memoize()` pattern. Ensure the cache key includes relevant query parameters.
- **Input IDs**: Every `Input`, `Output`, and `State` ID referenced in a callback must be present in the layout when the callback fires. For dynamic or multi-page layouts, set `suppress_callback_exceptions = True`.
- **Prevent Callback Firing**: Apply `prevent_initial_call=True` in callback decorators that should not run on page load (e.g., actions triggered only by a button click).
- **Prevent Unnecessary Updates**: When a callback should leave an output unchanged, return `dash.no_update` instead of re-fetching or re-computing data. Use `raise PreventUpdate` to skip updating the entire callback.
- **Keep Callbacks Focused**: One callback per user interaction when possible. Split large callbacks into smaller, composable ones rather than updating many outputs from a single function.
- **Loading Spinners**: Show a spinner while data is loading to improve perceived performance by wrapping components that may be slow to update with `dcc.Loading`.
- **Background Callbacks**: Use background callbacks for long-running work. For tasks that take more than a few seconds, use `background=True` in the callback decorator, along with the configured manager: `manager=background_callback_manager`.
- **Validate Callback Outputs**: Return strings for `children`, lists of component objects for `children` on containers, dicts for `figure`, and lists of dicts for `AgGrid` `rowData` and `columnDefs`.

## Layout and Styling
- **Custom Style Sheets**: For external stylesheets and CSS files, put core layout styles, layout grids, and structural overrides into custom files inside the `assets/` directory.
- **Theme File**: Use a shared `theme.py` or `theme.js` containing color constants, spacing scales, and font definitions to pass values systematically.
- **Inline Styles**: Use inline Python dictionaries (`style={"marginRight": "10px"}`) only for highly dynamic, runtime-computed values (e.g., styling a component color based on a callback threshold). Avoid static inline styling blocks as much as possible.
- **Code Format**: Run `black` for Python formatting and Prettier for CSS formatting.

## Charts and Components
- **Graphing Library**: Use `plotly.express` for charts first—it is simpler and covers most use cases. Switch to `plotly.graph_objects` only when you need fine-grained control.
- **Component Libraries**: Prioritize component libraries in this order: Dash Design Kit (if you have access to it), then Dash Core Components combined with Dash HTML Components, then Dash Mantine Components, then Dash Bootstrap Components if required. Try to minimize the number of libraries required.
- **Data Tables**: Do not use `dash.datatable`; use `dash.AgGrid` instead.
- **AgGrid Configs**: When instantiating `dag.AgGrid`, always set the following properties:
  - `dashGridOptions={"theme": "themeBalham", "animateRows": True, "pagination": True, "paginationPageSize": 10}`
  - `columnSize="responsiveSizeToFit"`
  - `defaultColDef={"filter": True, "sortable": True}`

## Avoid Hallucinations
- Never use `app.run_server`; only use `app.run`
- Never use obsolete patterns like `app.validation_layout`. Modern Dash handles dynamic layouts smoothly; just use `suppress_callback_exceptions=True` on app initialization if building dynamic layouts.
- Never import `dash.dependencies` items individually (from `dash.dependencies import Input`). Always use the modern syntax: `from dash import Input, Output, State, callback, clientside_callback, no_update, ALL, MATCH`.
- Never write blocking `time.sleep` loops inside a callback in production contexts; use `dcc.Interval` for asynchronous long-polling or integrate an external task queue (like Celery/Redis) if handling long-running computations.
- Never assign to callback `Input` values or mutate callback arguments in place.
- Never use `dash_table.DataTable`; use `dash.AgGrid()` instead.
- Never put secrets, API keys, or credentials in layout code or `dcc.Store`. Use environment variables and server-side logic only.

## This Project
- **Component Library**: Dash Mantine Components (`dmc`) 2.x. Wrap the layout in `dmc.MantineProvider` with the theme from `theme.py`.
- **DMC Docs**: `llms.txt` in this folder is the full DMC documentation. Search it for a component before you use it, and use only the props it lists. Don't read the whole file; it is about 460K tokens.
- **Dash Docs**: For core Dash APIs (callbacks, `dcc`, layout, routing), look up the current docs with the `plotly-dash-documentation` MCP server.
- **Design Source**: The Figma design and its Make prototype are the source of truth for colors, type, layout and behavior. Read it with the Figma MCP server; never guess a hex value from a screenshot.