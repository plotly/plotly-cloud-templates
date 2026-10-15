# Video Script: Basic Dash Callbacks — Dash Fundamentals Chapter 2
**Target length:** Under 5 minutes  
**Format:** Screen recording with voiceover, code running live  
**Narration word count:** ~510 words (~4 min at 130 wpm + visual pauses)

---

## Beat 1 — Hook `[0:00–0:20]`

**[VISUAL]** Open on the gapminder scatter plot with the year slider. Drag the slider — the chart animates smoothly through decades of data.

**[NARRATION]**
> "In the last chapter, we built a Dash layout. It looked great — but it didn't do anything. This is what happens when you add callbacks. One slider, one chart, fully connected. Let me show you how it works."

---

## Beat 2 — The Why: Reactive Programming `[0:20–0:55]`

**[VISUAL]** Stay on the gapminder app, or cut to a simple spreadsheet visual.

**[NARRATION]**
> "The mental model here is a spreadsheet. When you change a cell, every cell that depends on it updates automatically. You don't call a function — the dependency is declared, and the system handles the rest.
>
> Dash works exactly the same way. You declare: when this input changes, call this function and put the result in that output. Dash handles the wiring. This is reactive programming — and it's the entire foundation of how Dash apps become interactive."

---

## Beat 3 — Anatomy of a Callback `[0:55–2:10]`

**[VISUAL]** Open the simple text input example in the editor. Highlight each section as you talk through it.

**[NARRATION]**
> "Let's start with the simplest possible example. A text box and a div — typing in the box updates the div.
>
> The layout is what you already know: a `dcc.Input` with an `id`, and an empty `html.Div` with an `id`. No value set on the div — we'll let the callback populate it.
>
> Now the callback. The `@callback` decorator is where the wiring happens. `Output` is what you want to update — the `children` property of `my-output`. `Input` is what triggers it — the `value` property of `my-input`.
>
> The function underneath receives the current value of the input and returns whatever should go in the output. That's it.
>
> A few things worth noting: the `id` in the decorator must match exactly the `id` in your layout. And the decorator has to sit directly above the function — no blank lines between them."

**[VISUAL]** Run the app, type in the text box, show the div updating live.

---

## Beat 4 — Real Demo: Slider → Graph `[2:10–3:05]`

**[VISUAL]** Open the gapminder `app.py`. Highlight the `@callback` and then the function body.

**[NARRATION]**
> "Now let's look at a real example. The `dcc.Slider` has an `id` of `year-slider`, and its `value` property is the input. The `dcc.Graph` is the output — specifically its `figure` property.
>
> Whenever the slider moves, Dash calls `update_figure` with the selected year. The function filters the dataframe down to that year, builds a new Plotly scatter plot, and returns it. Dash puts it in the graph.
>
> Notice `fig.update_layout(transition_duration=500)` — that's what gives the smooth animation between years. One line."

---

## Beat 5 — Multiple Inputs `[3:05–3:30]`

**[VISUAL]** Show the multi-input example's `@callback` decorator — 5 inputs listed.

**[NARRATION]**
> "You're not limited to one input. This example drives a chart from two dropdowns, two radio buttons, and a slider — five inputs, one output.
>
> The pattern is the same: just list more `Input` items in the decorator. The callback receives them as positional arguments, in the same order. Any one of them changing triggers the function."

---

## Beat 6 — State `[3:30–4:15]`

**[VISUAL]** Open the State / button example. Show both the `Input` and `State` lines in the decorator.

**[NARRATION]**
> "Now let's talk about `State`. Sometimes you want to read a value without that value triggering the callback. Classic example: a form with a Submit button.
>
> Here, the two text inputs are `State` — Dash reads their values, but typing in them does nothing. The `html.Button` is the `Input` — clicking it fires the callback. Dash passes all the `State` values into the function automatically.
>
> The rule is simple: `Input` triggers, `State` reads. Everything else about the function is the same."

---

## Beat 7 — Summary + CTA `[4:15–4:30]`

**[VISUAL]** Quick cut back to the gapminder app with the slider moving.

**[NARRATION]**
> "Callbacks are the engine of every Dash app. Declare your inputs and outputs, write a Python function, and Dash handles the rest. One input or five, one output or many — the pattern doesn't change.
>
> Chapter 3 goes deeper: clicking on charts to drive other charts. Interactive graphing. Link's in the description."

---

## Production Notes
- Beat 1: actually drag the slider on camera — the animation is the hook
- Beat 3: slow down here — this is the first time the viewer sees a decorator. Hover over `Output` then `Input` as you name them
- Beat 3 live demo: type something in the text box slowly, pause so the viewer sees the div react
- Beat 4: pause after showing `transition_duration=500` — it's a satisfying "one line does this" moment
- Beat 5: you don't need to run this app — just show the decorator in the editor. The point is the pattern, not the demo
- Beat 6: live demo here is useful — type in the text boxes, show nothing happens, then click Submit, show it fires
- Outro card: link to [Dash Fundamentals Part 3: Interactive Graphing](https://dash.plotly.com/docs/interactive-graphing)
