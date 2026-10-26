# From Figma to Dash: webinar script

**Webinar:** From Figma to Dash: Mockups to production apps
**Date:** November 10 @ 11am EST
**Speaker:** Athiru Pathiraja, Plotly

---

## Slide 1: Title

- Welcome everyone, thanks for joining
- Today's webinar: taking a Figma design all the way to a deployed Dash app using an AI agent and a set of MCP servers
- By the end you'll have a concrete picture of how the handoff from design to code actually works, not just in theory
- Quick agenda: we'll go through the problem, the architecture, then a live demo, and leave time for polls and questions
- [fill in: any housekeeping, recording notice, chat instructions]

---

## Slide 2: Meet the speaker

- Athiru Pathiraja, [fill in job title] at Plotly
- I work with clients to turn complex data into dashboards and data apps built on Dash and Plotly
- Background in software engineering across banking, investment, and agri-tech
- Computer Engineering degree from Concordia University
- The work I do day to day: a client shows up with a prototype, a Figma file, a notebook, a spreadsheet, or sometimes just a sketch, and we figure out how to make it a real, maintainable app
- That's the exact workflow we're going through today

---

## Slide 3: Poll 1

**Launch poll:** "How do you turn design mockups into Dash apps today?"
- A: Rebuild them by hand in code
- B: Start from a Dash template
- C: Use an AI coding agent
- D: We skip mockups entirely
- E: Other (comment in chat)

*While the poll is open:*
- No wrong answers here, we just want a read on where people are starting from
- If you picked A, rebuild by hand, you're going to see something useful today
- If you picked C, you're already using agents, so we'll get into specifics of which tools make it work better
- Leave the poll open for 30 seconds, then share results and riff briefly on what you see

*After results:*
- [ad lib based on actual results]
- The point of this webinar is to get everyone further along the C path, with less guessing

---

## Slide 4: The handoff problem

*This slide has a Figma mockup screenshot on the left and three bullet points on the right.*

- The rebuild tax
  - A designer hands you a Figma file and you have to recreate it in code, from scratch, without any of the decisions baked in
  - Colors, spacing, fonts, layout, which sidebar collapses and which doesn't, all of it has to be re-decided or guessed
  - This is where projects stall, and it's where quality tends to degrade
- Agents can read the design
  - The Figma MCP gives the agent direct access to the file: hex values, component names, variable collections, spacing, text styles, all of it
  - The Dash docs MCP and the DMC llms.txt give the agent current, version-accurate documentation
  - So instead of the agent guessing what a `dmc.AppShell` looks like, it looks up the actual props in the DMC llms.txt
- Code your team can maintain
  - The goal is not "it works once." It's Python your team can open six months later and understand
  - Components in `components/`, callbacks in `callbacks/`, pure utility functions in `utils/` with tests
  - The app we're demoing today has 111 passing tests on the pure functions, so you can refactor without worrying
- The slide in the room: [fill in: point to the screenshot, name the specific Figma file we're about to demo]

---

## Slide 5: Architecture

*This slide shows four boxes: Figma design, AI agent + skills, Dash app, real data, with a bottom note about the design system.*

- Figma design: the agent reads frames, variables, and text styles through the Figma MCP. You don't export anything
- AI agent + skills: Claude Code with the Figma MCP, the Dash docs MCP, the DMC llms.txt, and an `AGENTS.md` that sets the project structure
- Dash app: a standard Dash + DMC project, nothing exotic, your team can read and extend it
- Real data: six public sources replace the mockup placeholders
- Design system: the brand carries into every app built this way, because the agent reads the Figma variables each time

---

## Slide 6: What you'll learn

*Two stacked sections: design system in Dash, then connect your real data.*

- Design system: Figma variables become `theme.py` once, and every DMC component picks up the brand from there
- Real data: `scripts/fetch_data.py` builds a snapshot in `data/`, and callbacks wire it into the layout
- You'll see both in the demo, so I'll keep this one quick

---

## Slide 7: Demo time

*Slide reads: "A Figma mockup becomes a working Dash app with an AI agent, MCP servers and skills."*

### Before the demo: set the scene

- The project: California Wildfire Smoke and Respiratory Health Dashboard
- Three wildfire seasons:
  - 2020, Aug 1 to Oct 31: August Complex, SCU and LNU lightning complexes, Creek, North Complex
  - 2021, Jul 1 to Sep 30: Dixie, Caldor, Monument, River Complex
  - 2025 LA, Jan 1 to Feb 15: Palisades and Eaton fires
- The client is a public health analyst who knows Figma and knows what the app should do, but doesn't write Python or web code
- They handed us a Figma file with a full component library and four screen frames
- Today we're walking through how that becomes the running app

---

### Part A: Figma walkthrough

**Open the Figma file (figma.com/design/dhdKWUdlwCRBFNj2kLqDKX)**

*Target: about 2 minutes. Navigate as you talk, don't narrate every control.*

- Two pages: Screens and Components
- Screens page has four frames: Map View, Time Series, About the Data, and an article page
  - Map View: header with tabs, sidebar of controls on the left, map in the center, stats rail on the right
  - Time Series: county trend lines over AQI bands. The sidebar goes dark on this tab, a deliberate design choice
  - About the Data: editorial article index, one article per data source
- Components page, spend about 20 seconds here
  - Variables in four collections: Primitives, Data, Semantic, Layout
  - 44 IBM Plex text styles, 2 shadow styles, named components
- [fill in: play prototype animations if wired up]
- Point to make before moving on: the designer used components and variables, not one-off shapes. When the agent reads this file, it gets exact hex values, not guesses

---

### Part B: Claude Code and the tooling

**Open Claude Code in the project folder**

- Show `claude mcp list`: two servers wired in, `figma` and `plotly-dash-documentation`
- Plus two local files the agent reads: the DMC llms.txt in the project root and `AGENTS.md`

**Figma MCP**
- `get_design_context`: returns the frame as structured layout data, not just a screenshot
- `get_variable_defs`: returns the variable collections, so the agent reads the actual hex values
- `get_screenshot`: a rendered frame image for visual reference
- Without this, the agent copies colors from a PNG. With it, it reads `#294c60` directly from the Figma file
- To connect: `claude mcp add --transport http figma https://mcp.figma.com/mcp`, then `/mcp` to sign in

**Plotly Dash docs MCP**
- `search_pages`, `get_page_as_markdown`, `list_pages`
- Dash 4.0 changed some callback patterns. The MCP always returns the current docs, not whatever the model last trained on
- To connect: `claude mcp add --transport http plotly-dash-documentation https://dash.plotly.com/_mcp` (no auth)

**DMC llms.txt**
- A plain-text dump of the DMC docs site, written for models to read
- The DMC 2.8.0 llms.txt sits in the project root. About 1.8 MB, roughly 460K tokens
- The agent searches it for the component it needs. DMC 2.x changed a lot of props from 1.x, so checking the llms.txt keeps it from inventing them
- Where to get it: [fill in URL on dash-mantine-components.com]

**Skills and `AGENTS.md`**
- Skills are markdown files the agent loads for specific tasks: palette validation, naming conventions, callback patterns
- `AGENTS.md` in the repo root is read at the start of each session. It sets the folder layout, the data loading pattern (once at import), the callback pattern (thin glue, pure work in `utils/`), and the instruction to look up DMC props in the llms.txt before using a component
- [fill in: if you have a Plotly-standard AGENTS.md template to show]

---

### Part C: Live prompts

*Run 2 or 3 prompts live to show the agent in action. Have the finished app open on another branch or in another terminal as a fallback.*

**Suggested prompt 1: read the Figma variables**
- Prompt: "Read the variable collections from this Figma frame and update `theme.py` to match. Use the Primitives collection for raw hex values and the Semantic collection for Mantine token overrides."
- Paste the Figma frame URL that includes the node-id
- Shows: `get_variable_defs`, then the agent editing `theme.py`
- Talk track while it runs: "This is the step that would otherwise mean copying 50 hex values by hand. The agent reads the Figma file directly."

*After the theme prompt finishes, open `theme.py` and briefly point at three things:*
- Five brand colors, each expanded to a 10-shade Mantine scale. Slate replaces Mantine's built-in gray, so borders and dimmed text follow the brand automatically
- IBM Plex set as `fontFamily`
- Shadow tokens `xs` and `sm` from the Figma shadow styles
- "Components work the same way, so let's do the Stat card next"

**Suggested prompt 2: build a component from a Figma node**
- Prompt: "Build the Stat card component from this Figma node as a `dmc.Card`. Look up the props in the DMC llms.txt before writing any code."
- Paste the node URL for a `Stat/*` component
- Shows: the agent searching the llms.txt, then writing `components/stat_cards.py`
- Talk track: "Notice it checked the llms.txt before writing. DMC 2.x changed a lot of props, so that step is what keeps it from inventing them."

**Suggested prompt 3: a small design change**
- Prompt: "The sidebar opacity slider should match the Figma spec. Check the current value and update it if it differs."
- A small, bounded change that demonstrates the agent reading Figma and comparing it to existing code
- [fill in: adjust this to whatever will be a visually clear diff in the webinar]

*Keep the finished branch ready. If a prompt goes sideways, switch to it without ceremony.*

---

### Part E: Show it running

- Run: `.venv/bin/python app.py` (serves on port 8054)
- Click through the app:
  - Change the season dropdown from 2020 to 2021 to 2025 LA
  - Press play on the day slider and let it run for a few steps, then pause
  - Toggle the smoke layer on and off
  - Change the county shading from "Outlines only" to "Asthma ED visit rate"
  - Switch to the Time Series tab (notice the sidebar goes dark)
  - Select a different county in the multiselect
  - Click a day in the time series chart and watch the map jump to it
  - Switch to About the Data and open one article
- Put the Figma frame and the running app side by side
  - Point out a specific design detail that carried over, such as the card shadows, the charcoal rail on the right, or the tab underline style
- Run the tests: `.venv/bin/python -m pytest`
  - 111 tests, all on pure utility functions
  - Makes the point that the generated code is testable, not just a big callback blob
  - [fill in: run this before the webinar to confirm count is still accurate]

---

## Slide 8: Poll 2

**Launch poll:** "What would you build first from a Figma design?"
- A: Internal dashboards
- B: Customer-facing analytics
- C: Reporting apps
- D: Prototypes to test ideas
- E: Other (comment in chat)

*While the poll is open:*
- Take questions from the chat during the 30-second window
- The answers to this question shape what tools matter most to you
  - Internal dashboards: the DMC llms.txt matters most for getting component props right
  - Customer-facing analytics: the Figma MCP matters most, since brand fidelity is harder to negotiate
  - Prototypes: a faster workflow where you care less about tests and more about speed

*Questions to be ready for:*
- Does it match the Figma pixel for pixel? [fill in your honest answer based on the actual demo output]
- How much did you fix by hand after the agent ran? [fill in]
- Does the Figma have to use components and variables, or does a flat design work? Using components and variables makes a big difference. A flat design still works, but the agent is guessing more about intent
- Can this workflow work with Dash Bootstrap Components instead of DMC? Yes. Swap in the DBC llms.txt [fill in: confirm a DBC llms.txt exists] and update `AGENTS.md`
- Is the data in this app live? No. It's a preprocessed snapshot. Re-running `fetch_data.py` refreshes it
- What does the agent actually send to the MCP servers? For Figma: a file key and a node ID. For the Dash docs MCP: a search query. The DMC llms.txt is a local file, so nothing gets sent anywhere for it

---

## Slide 9: Q&A

- Type questions in the chat box
- [fill in: how you prefer to handle raised hands vs. chat vs. moderator queue]
- Backup questions if the queue is light:
  - "How do you decide when to use a skill vs. just a good prompt?"
  - "What breaks most often when an AI agent builds a Dash app without the MCPs?"
  - "How do you handle a Figma design that doesn't use components at all?"

---

## Slide 10: Thank you

- Book a 30-minute walkthrough: plotly.com/get-demo
- Email: info@plotly.com
- Twitter/X: @plotly, @plotlygraphs
- Next webinar: [fill in next title, date, and link at plotly.com/webinars/[slug]]

*Closing talking point:*
- The tools covered today: Figma MCP, Plotly Dash docs MCP, DMC llms.txt, Claude Code, and an `AGENTS.md` that sets the project structure
- The workflow: build the Figma with components and variables, wire in the MCPs, scaffold with `AGENTS.md`, build, test, deploy
- [fill in: whether you'll share the repo and any materials]

---

## Open items to fill in before the webinar

- Your job title (slide 2)
- LinkedIn handle (slide 2)
- Which Figma prototype flows are actually wired up for the animation demo (slide 7, Part A)
- The AGENTS.md template, whether Plotly has a standard one to reference (slide 7, Part B)
- The exact Plotly Cloud deploy command or connector you plan to show (slide 7, deploy step)
- Whether attendees get the repo link and where (slide 10)
- Honest answers to: "Does it match Figma pixel-for-pixel?" and "How much did you fix by hand?" (slide 8, questions)
- The next webinar title, date, and slug (slide 10)
- Run `.venv/bin/python -m pytest` before the webinar to confirm test count
- Confirm the Figma file at `figma.com/design/dhdKWUdlwCRBFNj2kLqDKX` is still accessible and the prototype animations are ready to play
- Update slide 4 and slide 5 in the deck: both still say "Dash Mantine Components MCP server" but the demo now uses the DMC llms.txt
- Get the DMC llms.txt download URL from dash-mantine-components.com and add it to slide 7, Part B
- Copy `llms.txt` into the project root before the demo. It currently lives in the BCM mosquito dashboard repo, not in this one
- Confirm whether a DBC llms.txt exists, for the DBC question in slide 8
