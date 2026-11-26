"""
"Why Plotly" drawer + "View source" link, shared by every app in plotly-cloud-templates.

    from why_plotly import add_why_plotly
    ...
    app.layout = ...
    add_why_plotly(app, "<this app's folder name>")

Self-contained: the stylesheet is injected into the page by add_why_plotly, it only
uses plain Dash HTML components plus one clientside callback (ids prefixed "wp-"),
so it works with any component library, theme, layout function or multi-page app.

SOURCE OF TRUTH: shared/why_plotly.py at the repo root. Each app carries a copy
because Plotly Cloud deploys an app folder on its own. Edit the shared file, then
run `python shared/sync_why_plotly.py` to update every app. Don't edit app copies.
"""

from dash import Input, Output, clientside_callback, html

REPO_URL = "https://github.com/plotly/plotly-cloud-templates"

# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

TITLE = "Why Plotly: a production platform IT can govern"
INTRO = (
    "Dash Enterprise is the secure production platform for organizations scaling AI-powered app "
    "development. Domain experts at your organisation get one consistent way to deploy and run the data "
    "apps that improve decisions and workflows. IT keeps full control over who can access them, what they "
    "can reach and the resources they use."
)
BADGES = [
    "SOC 2 Type II",
    "ISO 27001",
    "ISO 27701",
    "ISO 42001",
    "Runs in your cloud or air-gapped",
    "SSO: Entra ID · Okta · SAML · OIDC · LDAP",
]

QA_TITLE = "The questions IT, security and risk will ask, answered"
QA_INTRO = "Every point below is a platform capability, so each new app inherits it without extra code."
QA = [
    ("Identity & access", "Who can sign in, and who sees what?", [
        "Single sign-on through your identity provider: Entra ID, Okta, Ping, SAML 2.0, OIDC or LDAP / Active Directory.",
        "Three roles: everyone is a viewer, licensed users build and deploy, admins run the platform. Map them to your IdP groups.",
        "New apps start Restricted. The platform checks access before a request reaches the app, so there is no login code to write or audit.",
    ]),
    ("Infrastructure & data", "Where does it run, and does our data leave?", [
        "One Helm install into a single namespace of your existing EKS, AKS or GKE cluster. No dedicated cluster needed.",
        "Apps, users and data stay in your network, with fully air-gapped installs supported.",
        "Apps reach databases and buckets through Kubernetes workload identity, so no credentials sit in code.",
    ]),
    ("Application security", "Is the code and runtime hardened?", [
        "App images in your private container registry; app code in your GitHub organisation under your review rules.",
        "Read-only filesystems, seccomp profiles, and no sudo or privilege escalation by default.",
        "Independent penetration testing; the summary and security pack are available via trust.plotly.com.",
    ]),
    ("AI agents (MCP)", "What can AI agents reach?", [
        "MCP is off for every app until its owner or an admin turns it on.",
        "Agents sign in as a real user and get exactly that user's access, nothing more.",
        "So teams can point Claude or Copilot at governed apps instead of exporting data to them.",
    ]),
    ("Continuity", "What happens when something breaks?", [
        "Scheduled and on-demand backups to your own S3, Azure Blob or GCS bucket, optionally encrypted before upload.",
        "Backups include SSO settings, users and groups; apps redeploy automatically after a restore.",
        "Backup, restore and app operations run as durable workflows that resume after a node failure.",
    ]),
    ("Cost & capacity", "Can one app take down the rest?", [
        "Admins set CPU and memory limits per app, workspace and database; owners cannot raise their own.",
        "An app that exceeds its memory limit is stopped, not left to starve the cluster.",
        "Autoscaling runs only within the minimum and maximum replica counts you set.",
    ]),
    ("Audit & lifecycle", "Can we see everything, and what happens when people leave?", [
        "One App Manager lists every app with its owner, co-owners, access groups, logs and viewer analytics.",
        "Every deployment is a git commit with an author and a timestamp.",
        "Admins transfer one or all of a leaver's apps, with databases, access and settings intact. No orphaned apps.",
    ]),
    ("Licensing", "What does it cost as adoption grows?", [
        "No per-viewer fees: anyone in the company can use an app once it's shared.",
        "Seats only for the people who build and own apps.",
        "One platform for hundreds of apps, instead of one infrastructure project per app.",
    ]),
]

STEPS_TITLE = "How an app goes from idea to governed production"
STEPS = [
    ("Build", "In Plotly Studio, an AI coding tool or a browser workspace. It's all standard Python."),
    ("Deploy", "git push or one click. The platform builds the container, so there's no Dockerfile or ticket."),
    ("Restrict", "The app is private by default. The owner shares it with IdP groups."),
    ("Operate", "Admins see usage, limits, logs and owners in one console."),
    ("Extend to AI", "Optionally switch on MCP. Agents inherit the same access rules."),
]

ROLES_TITLE = "Roles at a glance"
ROLES = [
    ("viewer", "Everyone who signs in (default)",
     "View the apps they have been granted, via the Portal or a direct link."),
    ("licensed_user", "People who build apps (one seat each)",
     "Create, deploy and own apps, workspaces, databases and data sources; share with groups; enable MCP."),
    ("admin", "Platform team",
     "Manage users, seats, resource limits, backups and access policy; transfer app ownership."),
]

DEPLOY_TITLE = "Where it can run"
DEPLOY = [
    ("Plotly Cloud", "Fully managed. This demo runs here. Live in minutes, with no infrastructure to run."),
    ("Your cloud (VPC)", "Dash Enterprise on your AKS, EKS or GKE cluster. Data never leaves your tenancy."),
    ("Behind your firewall", "Dash Enterprise in your private network, including air-gapped, for regulated data."),
]

COMPARE_TITLE = "Dashboards vs DIY vs a governed app platform"
COMPARE_COLS = ["Power BI / Tableau", "DIY: AI-generated apps, self-hosted", "Plotly Dash Enterprise"]
COMPARE = [
    ("Analytics logic",
     "DAX and Power Query. Python visuals render as static images in a sandbox.",
     "Anything Python can do.",
     "Anything Python can do, running live in callbacks that re-run on every interaction."),
    ("Build speed",
     "Fast for standard reports; custom logic hits a ceiling quickly.",
     "Very fast with AI coding assistants (Claude, Copilot, Cursor).",
     "Equally fast: AI coding tools, Plotly Studio and browser-based App Workspaces all produce standard Dash code."),
    ("Getting to production",
     "Publish to the Power BI Service.",
     "Every app becomes its own infra project: Docker, Kubernetes, TLS, reverse proxy, patching.",
     "One-click deploy. Containerised and served for you, in Plotly Cloud or on your own Kubernetes (AKS, EKS, GKE)."),
    ("Authentication",
     "Entra ID.",
     "Hand-rolled per app, and audited per app.",
     "Configured once at platform level: Entra ID, Okta, SAML, LDAP. Every app inherits it."),
    ("Licensing as adoption grows",
     "Per-user (Pro / PPU) or capacity SKUs.",
     "'Free' until you count the engineers running it.",
     "No per-viewer fees. Seats are only for people who build apps."),
    ("Knowing what's running",
     "Workspace administration.",
     "Shadow apps on laptops, VMs and personal cloud accounts.",
     "App Manager: every app's owner, access groups, logs, env vars and viewer analytics in one place."),
    ("Data residency & security",
     "Microsoft cloud tenancy.",
     "Depends on whoever built it.",
     "Runs in your VPC or behind your firewall. SOC 2 Type II, ISO 27001 / 27701 / 42001; pentest report via trust.plotly.com."),
]

FOOTNOTE = (
    "Capabilities as documented for Dash Enterprise 6.3 (dash.plotly.com/dash-enterprise). Security "
    "documentation and the penetration-test summary are available on request via trust.plotly.com."
)

# ---------------------------------------------------------------------------
# Icons (inline SVG paths so no icon library is needed)
# ---------------------------------------------------------------------------

_GITHUB_SVG = (
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='white'>"
    "<path d='M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49"
    "-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82"
    ".72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15"
    "-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82"
    " 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48"
    " 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z'/></svg>"
)


# ---------------------------------------------------------------------------
# Styles (all scoped under .wp-*)
# ---------------------------------------------------------------------------

CSS = """
/* Reset: host apps often style *, h1-h3, li, button globally; keep the drawer identical everywhere. */
.wp-root, .wp-root * {
  font-family: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
  text-transform: none !important;
  letter-spacing: normal !important;
  box-sizing: border-box;
  text-shadow: none !important;
}
.wp-root ul { list-style: disc outside !important; margin: 0; }
.wp-root ol { list-style: none !important; margin: 0; }
.wp-root li { margin: 0; padding: 0; background: none; border: 0; }
.wp-root li::before, .wp-root li::marker { color: inherit; }
.wp-root .wp-eyebrow, .wp-root .wp-card-kicker {
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
}
.wp-root .wp-title { letter-spacing: -0.01em !important; }
.wp-root code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace !important; }

.wp-root {
  --wp-brand: #5a4fcf;
  --wp-brand-2: #7a6ff0;
  --wp-ink: #16181d;
  --wp-ink-2: #4b5160;
  --wp-muted: #6f7686;
  --wp-line: #e4e6ec;
  --wp-soft: #f5f5fb;
  --wp-surface: #ffffff;
  font-family: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

/* Floating buttons */

.wp-fabs {
  position: fixed;
  left: 16px;
  bottom: 16px;
  z-index: 2400;
  display: flex;
  gap: 8px;
}

.wp-root .wp-fab {
  border: 0;
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 36px;
  padding: 0 14px;
  border-radius: 999px;
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
  color: #fff;
  text-decoration: none;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(20, 20, 40, 0.18);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  user-select: none;
}

.wp-fab:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(20, 20, 40, 0.24);
  color: #fff;
}

.wp-fab-dark { background: #24292f; }
.wp-fab-brand { background: linear-gradient(135deg, var(--wp-brand), var(--wp-brand-2)); }
.wp-icon { width: 16px; height: 16px; display: block; }
.wp-spark { font-size: 13px; }

.wp-fab:focus-visible, .wp-close:focus-visible {
  outline: 2px solid var(--wp-brand);
  outline-offset: 2px;
}

/* Drawer */

.wp-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2500;
  background: rgba(15, 17, 26, 0.45);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease;
  margin: 0;
}

.wp-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 2501;
  width: min(760px, 100vw);
  display: flex;
  flex-direction: column;
  background: var(--wp-surface);
  color: var(--wp-ink);
  box-shadow: -12px 0 40px rgba(15, 17, 26, 0.25);
  transform: translateX(100%);
  visibility: hidden;
  transition: transform 0.25s ease, visibility 0s linear 0.25s;
  text-align: left;
  font-size: 14px;
  line-height: 1.5;
}

.wp-is-open .wp-backdrop { opacity: 1; pointer-events: auto; }
.wp-is-open .wp-drawer {
  transform: none;
  visibility: visible;
  transition: transform 0.25s ease, visibility 0s;
}
.wp-is-open .wp-fabs { display: none; }

.wp-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid var(--wp-line);
  flex: none;
}

.wp-src {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 12px;
  border-radius: 6px;
  background: #24292f;
  color: #fff;
  font-weight: 600;
  font-size: 13px;
  text-decoration: none;
}
.wp-src:hover { background: #000; color: #fff; }

.wp-close {
  border: 0;
  background: transparent;
  padding: 0;
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  font-size: 24px;
  line-height: 1;
  color: var(--wp-ink-2);
  cursor: pointer;
  margin: 0;
}
.wp-close:hover { background: var(--wp-soft); }

.wp-scroll {
  overflow-y: auto;
  padding: 0 28px 28px;
}

.wp-drawer h2, .wp-drawer h3, .wp-drawer p, .wp-drawer ul, .wp-drawer ol { margin: 0; }

.wp-hero {
  margin: 0 -28px 8px;
  padding: 28px 28px 24px;
  background: linear-gradient(160deg, #f2f0ff 0%, #ffffff 70%);
  border-bottom: 1px solid var(--wp-line);
}

.wp-eyebrow {
  color: var(--wp-brand);
  font-weight: 700;
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 6px;
}

.wp-title {
  font-size: 24px;
  line-height: 1.2;
  font-weight: 750;
  letter-spacing: -0.01em;
  color: var(--wp-ink);
}

.wp-intro {
  margin-top: 10px !important;
  color: var(--wp-ink-2);
  font-size: 15px;
  max-width: 62ch;
}

.wp-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 16px;
}

.wp-badge {
  padding: 4px 10px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #d9d5fb;
  color: #3d3497;
  font-size: 12px;
  font-weight: 600;
}

.wp-drawer section { margin-top: 28px; }

.wp-h {
  font-size: 16px;
  font-weight: 700;
  color: var(--wp-ink);
  margin-bottom: 10px !important;
}

.wp-muted { color: var(--wp-muted); margin: -4px 0 12px !important; }

.wp-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.wp-card {
  border: 1px solid var(--wp-line);
  border-radius: 10px;
  padding: 14px 16px;
  background: var(--wp-surface);
}

.wp-card-kicker {
  color: var(--wp-brand);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.wp-card-q {
  font-weight: 650;
  margin: 2px 0 8px;
}

.wp-card ul {
  padding-left: 18px;
  color: var(--wp-ink-2);
  font-size: 13px;
}
.wp-card li + li { margin-top: 5px; }

.wp-steps {
  list-style: none;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.wp-steps li {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border-radius: 10px;
  background: var(--wp-soft);
  font-size: 13px;
  color: var(--wp-ink-2);
}
.wp-steps li b { display: block; color: var(--wp-ink); font-size: 14px; }

.wp-step-n {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--wp-brand);
  color: #fff;
  font-weight: 700;
  font-size: 12px;
}

.wp-table-wrap { overflow-x: auto; }

.wp-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.wp-table th, .wp-table td {
  text-align: left;
  vertical-align: top;
  padding: 9px 10px;
  border-bottom: 1px solid var(--wp-line);
  color: var(--wp-ink-2);
}

.wp-table thead th {
  color: var(--wp-ink);
  font-weight: 700;
  border-bottom: 2px solid var(--wp-line);
}

.wp-table tbody th { color: var(--wp-ink); font-weight: 650; white-space: nowrap; }
.wp-table code {
  background: var(--wp-soft);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
  color: #3d3497;
}

.wp-compare { min-width: 640px; }
.wp-compare .wp-us { background: #f4f2ff; color: var(--wp-ink); }
.wp-compare thead .wp-us { color: var(--wp-brand); }

.wp-deploys {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.wp-deploy {
  border: 1px solid var(--wp-line);
  border-radius: 10px;
  padding: 14px;
  font-size: 13px;
  color: var(--wp-ink-2);
}
.wp-deploy b { display: block; color: var(--wp-ink); font-size: 14px; margin-bottom: 4px; }

.wp-ctas {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 28px;
}

.wp-cta {
  display: inline-flex;
  align-items: center;
  height: 40px;
  padding: 0 18px;
  border-radius: 8px;
  background: var(--wp-brand);
  color: #fff;
  font-weight: 650;
  text-decoration: none;
}
.wp-cta:hover { background: #4a40b8; color: #fff; }
.wp-cta-ghost { background: transparent; color: var(--wp-brand); border: 1px solid #d9d5fb; }
.wp-cta-ghost:hover { background: var(--wp-soft); color: var(--wp-brand); }

.wp-foot {
  margin-top: 20px !important;
  color: var(--wp-muted);
  font-size: 12px;
}

@media (max-width: 640px) {
  .wp-scroll { padding: 0 16px 24px; }
  .wp-hero { margin: 0 -16px 8px; padding: 20px 16px; }
  .wp-grid, .wp-deploys { grid-template-columns: 1fr; }
  .wp-steps { grid-template-columns: 1fr; }
  .wp-steps li { flex-direction: row; align-items: flex-start; }
  .wp-step-n { flex: none; }
  .wp-fabs { left: 12px; bottom: 12px; }
}
"""


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def _h(text):
    return html.H3(text, className="wp-h")


def _drawer_body():
    return [
        html.Div(
            [
                html.Div("Plotly Dash Enterprise", className="wp-eyebrow"),
                html.H2(TITLE, className="wp-title"),
                html.P(INTRO, className="wp-intro"),
                html.Div([html.Span(b, className="wp-badge") for b in BADGES], className="wp-badges"),
            ],
            className="wp-hero",
        ),
        html.Section(
            [
                _h(QA_TITLE),
                html.P(QA_INTRO, className="wp-muted"),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(area, className="wp-card-kicker"),
                                html.Div(question, className="wp-card-q"),
                                html.Ul([html.Li(p) for p in points]),
                            ],
                            className="wp-card",
                        )
                        for area, question, points in QA
                    ],
                    className="wp-grid",
                ),
            ]
        ),
        html.Section(
            [
                _h(STEPS_TITLE),
                html.Ol(
                    [
                        html.Li([html.Span(str(i), className="wp-step-n"),
                                 html.Div([html.B(name), html.Span(desc)])])
                        for i, (name, desc) in enumerate(STEPS, 1)
                    ],
                    className="wp-steps",
                ),
            ]
        ),
        html.Section(
            [
                _h(ROLES_TITLE),
                html.Div(
                    html.Table(
                        [
                            html.Thead(html.Tr([html.Th("Role"), html.Th("Who"), html.Th("Can")])),
                            html.Tbody([
                                html.Tr([html.Td(html.Code(r)), html.Td(who), html.Td(can)])
                                for r, who, can in ROLES
                            ]),
                        ],
                        className="wp-table",
                    ),
                    className="wp-table-wrap",
                ),
            ]
        ),
        html.Section(
            [
                _h(DEPLOY_TITLE),
                html.Div(
                    [html.Div([html.B(name), html.Span(desc)], className="wp-deploy") for name, desc in DEPLOY],
                    className="wp-deploys",
                ),
            ]
        ),
        html.Section(
            [
                _h(COMPARE_TITLE),
                html.Div(
                    html.Table(
                        [
                            html.Thead(html.Tr([html.Th("")] + [
                                html.Th(c, className="wp-us" if i == len(COMPARE_COLS) - 1 else None)
                                for i, c in enumerate(COMPARE_COLS)
                            ])),
                            html.Tbody([
                                html.Tr([html.Th(row[0], scope="row")] + [
                                    html.Td(cell, className="wp-us" if i == len(row) - 2 else None)
                                    for i, cell in enumerate(row[1:])
                                ])
                                for row in COMPARE
                            ]),
                        ],
                        className="wp-table wp-compare",
                    ),
                    className="wp-table-wrap",
                ),
            ]
        ),
        html.Div(
            [
                html.A("Explore Dash Enterprise", href="https://plotly.com/dash/", target="_blank",
                       rel="noopener", className="wp-cta"),
                html.A("Security & trust center", href="https://trust.plotly.com", target="_blank",
                       rel="noopener", className="wp-cta wp-cta-ghost"),
            ],
            className="wp-ctas",
        ),
        html.P(FOOTNOTE, className="wp-foot"),
    ]


def why_plotly_component(app_dir):
    """Floating "Source" + "Why Plotly" buttons and the drawer they open.

    app_dir: this app's folder name in the plotly-cloud-templates repo, used
    for the GitHub link.
    """
    source_url = f"{REPO_URL}/tree/main/{app_dir}"
    github_icon = html.Img(src=_GITHUB_SVG, alt="", className="wp-icon")
    return html.Div(
        [
            html.Div(
                [
                    html.A(
                        [github_icon, html.Span("View source")],
                        href=source_url, target="_blank", rel="noopener", className="wp-fab wp-fab-dark",
                        title="See this app's code on GitHub",
                    ),
                    html.Button(
                        [html.Span("✦", className="wp-spark"), html.Span("Why Plotly")],
                        id="wp-open", n_clicks=0, className="wp-fab wp-fab-brand",
                    ),
                ],
                className="wp-fabs",
            ),
            html.Div(id="wp-backdrop", n_clicks=0, className="wp-backdrop"),
            html.Aside(
                [
                    html.Div(
                        [
                            html.A([github_icon, html.Span("This app on GitHub")],
                                   href=source_url, target="_blank", rel="noopener", className="wp-src"),
                            html.Button("×", id="wp-close", n_clicks=0, className="wp-close", title="Close"),
                        ],
                        className="wp-bar",
                    ),
                    html.Div(_drawer_body(), className="wp-scroll"),
                ],
                className="wp-drawer",
                role="dialog",
                **{"aria-label": "Why Plotly"},
            ),
        ],
        id="wp-root",
        className="wp-root",
    )


clientside_callback(
    """
    function () {
        const open = dash_clientside.callback_context.triggered_id === "wp-open";
        return open ? "wp-root wp-is-open" : "wp-root";
    }
    """,
    Output("wp-root", "className"),
    Input("wp-open", "n_clicks"),
    Input("wp-close", "n_clicks"),
    Input("wp-backdrop", "n_clicks"),
    prevent_initial_call=True,
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def add_why_plotly(app, app_dir):
    """Add the drawer, source link and styles to `app`. Call once, after app.layout is set.

    app_dir: this app's folder name in the repo, used for the GitHub link.
    """
    extra = why_plotly_component(app_dir)
    layout = app.layout

    def wrap(content):
        # display: contents keeps the wrapper out of the host app's CSS layout.
        return html.Div([content, extra], style={"display": "contents"})

    if callable(layout):
        app.layout = lambda *args, **kwargs: wrap(layout(*args, **kwargs))
    else:
        app.layout = wrap(layout)

    # Dash snapshots a layout function into validation_layout the first time it is set,
    # before this wrapper existed, so add the drawer ids to it too.
    if app.validation_layout is not None:
        app.validation_layout = html.Div([app.validation_layout, extra])

    original_interpolate = app.interpolate_index

    def interpolate_index(**kwargs):
        kwargs["css"] = kwargs.get("css", "") + f"<style>{CSS}</style>"
        return original_interpolate(**kwargs)

    app.interpolate_index = interpolate_index
    return app
