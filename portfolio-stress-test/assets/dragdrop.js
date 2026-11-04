// Drag items (VaR models, stress scenarios, positions) from the sidebar onto the canvas.
// A drop writes {kind, id} into the item-drop store; app.py adds the item to the
// comparison for its kind. Clicking an item, or pressing Enter on it, adds it too.
(function () {
  let dragging = null; // {kind, id, el}

  const closest = (el, sel) => (el && el.closest ? el.closest(sel) : null);
  const canvas = () => document.getElementById("canvas");

  document.addEventListener("dragstart", (e) => {
    const item = closest(e.target, "[data-item-kind]");
    if (!item) return;
    dragging = { kind: item.dataset.itemKind, id: item.dataset.itemId, el: item };
    e.dataTransfer.setData("text/plain", dragging.id); // Firefox will not start a drag without data
    e.dataTransfer.effectAllowed = "copy";
    item.classList.add("is-dragging");
    document.body.classList.add("dragging-item", "dragging-" + dragging.kind);
  });

  document.addEventListener("dragend", () => {
    if (dragging) dragging.el.classList.remove("is-dragging");
    document.body.classList.remove("dragging-item", "dragging-var", "dragging-scenario", "dragging-position");
    const c = canvas();
    if (c) c.classList.remove("over");
    dragging = null;
  });

  document.addEventListener("dragover", (e) => {
    if (!dragging) return;
    const c = closest(e.target, "#canvas");
    canvas().classList.toggle("over", !!c);
    if (!c) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  });

  document.addEventListener("dragleave", (e) => {
    const c = canvas();
    if (c && !c.contains(e.relatedTarget)) c.classList.remove("over");
  });

  document.addEventListener("drop", (e) => {
    if (!dragging || !closest(e.target, "#canvas")) return;
    e.preventDefault();
    canvas().classList.remove("over");
    if (window.dash_clientside && window.dash_clientside.set_props) {
      window.dash_clientside.set_props("item-drop", {
        data: { kind: dragging.kind, id: dragging.id, t: Date.now() },
      });
    }
  });

  // Enter or Space on a sidebar item adds it, like a click
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const item = closest(e.target, "[data-item-kind]");
    if (!item) return;
    e.preventDefault();
    item.click();
  });
})();
