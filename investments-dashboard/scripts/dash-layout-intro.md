# Video Script: Dash Layout — Dash Fundamentals Chapter 1
**Target length:** Under 5 minutes  
**Format:** Screen recording with voiceover, code running live  
**Narration word count:** ~515 words (~4 min at 130 wpm + visual pauses)

---

## Beat 1 — Hook `[0:00–0:20]`

**[VISUAL]** Open on the finished bar chart app already running at `localhost:8050` — fruits grouped by city, interactive, polished.

**[NARRATION]**
> "This is a Dash app. Interactive, browser-based, deployable anywhere — and we just built it in about 20 lines of Python. No JavaScript. No HTML files. No CSS from scratch. Let me show you how."

---

## Beat 2 — The Why `[0:20–0:55]`

**[VISUAL]** Briefly show a terminal with pandas output, or a static matplotlib plot — the kind of thing you'd share as a screenshot.

**[NARRATION]**
> "If you work with data in Python, you've probably hit this wall. You've got a great analysis — a dataframe, a Plotly chart — but getting it in front of someone else means emailing a screenshot or sending a CSV and hoping they run the same environment.
>
> Building a proper web app means learning a frontend framework, and suddenly you're context-switching between Python and JavaScript.
>
> Dash is the bridge. You stay in Python, and Dash handles the web layer."

---

## Beat 3 — Your First App `[0:55–2:00]`

**[VISUAL]** Open `app.py` in the editor — the bar chart example. Highlight each section as you mention it.

**[NARRATION]**
> "Let's look at what we're actually writing. Three things happen here.
>
> First, we create data — just a standard pandas DataFrame.
>
> Then we create a Plotly figure with `px.bar`. Standard Plotly Express.
>
> And then comes the Dash part: `app.layout`. This is where you describe what your app looks like — a tree of Python component objects.
>
> `html.Div` is a wrapper. `html.H1` is a heading. `dcc.Graph` takes our Plotly figure and renders it as an interactive chart in the browser.
>
> Run it with `python app.py`, open localhost:8050, and there it is."

**[VISUAL]** Terminal running, browser opens to the app.

> "Notice `debug=True` — that turns on hot reload. Change the title, save the file — your browser updates instantly. No restart needed."

---

## Beat 4 — Styling with HTML Components `[2:00–2:50]`

**[VISUAL]** Switch to the dark-mode styled app. Show the `style={}` dict in the editor.

**[NARRATION]**
> "Now let's customize it. Every `dash.html` component maps to an HTML tag, and you control it entirely through Python keyword arguments.
>
> The `style` property works like inline HTML styles — except it's a Python dictionary. Keys are camelCase: `textAlign` instead of `text-align`, `backgroundColor` instead of `background-color`. And `class` becomes `className`.
>
> That's it. Every HTML attribute you know works the same way, just in Python syntax."

---

## Beat 5 — Core Components `[2:50–3:40]`

**[VISUAL]** Show the components showcase app — dropdowns, sliders, radio items, checkboxes all visible.

**[NARRATION]**
> "Beyond HTML wrappers, Dash gives you `dash.dcc` — the Dash Core Components. Dropdowns, sliders, radio buttons, text inputs, graphs — all ready to go.
>
> These aren't plain HTML. They're React components under the hood, which is why they're interactive out of the box.
>
> Everything is declarative. Every option is a keyword argument. And if you ever want to know what's available, just run `help(dcc.Dropdown)` in your Python console — it lists every parameter with a description."

---

## Beat 6 — Reusable Components `[3:40–4:10]`

**[VISUAL]** Show the `generate_table()` function from the table example.

**[NARRATION]**
> "Here's something that doesn't get talked about enough. Because your layout is Python, you can write functions that generate UI.
>
> This function takes a pandas DataFrame and returns a fully-formed HTML table component — no template language, no Jinja, no string interpolation. Just Python.
>
> That's the real unlock here: you can compose, loop, and abstract your UI the same way you write any other Python code."

---

## Beat 7 — Summary + CTA `[4:10–4:30]`

**[VISUAL]** Quick cut back to the running bar chart app.

**[NARRATION]**
> "So: a Dash layout is a tree of Python components. `dash.html` gives you HTML tags. `dash.dcc` gives you interactive components. And because it's all Python, you can compose it like any other code.
>
> This is chapter one. The app looks good — but it doesn't do anything yet. In part two, we wire up callbacks to make it actually interactive. Link's in the description."

---

## Production Notes
- Keep a brisk pace through code — don't read every line, just call out what matters
- For Beat 3, hover or highlight `app.layout`, `html.Div`, `dcc.Graph` as each is mentioned
- Hot reload demo in Beat 3: actually make a live edit on screen — change `'Hello Dash'` to something, save, show the browser update
- Beat 5: interact with the dropdowns and slider briefly to show they work before the narration
- Outro card: link to [Dash Fundamentals Part 2: Basic Callbacks](https://dash.plotly.com/docs/basic-callbacks)
