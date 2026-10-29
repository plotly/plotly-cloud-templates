/* Resize Plotly graphs (map + time series) when their host box changes, not only on window resize.
   Adapted from Houston_MSA assets/js/plotly-container-resize.js.

   Why: tab panels are hidden with display:none and the navbar collapses/expands,
   so a graph mounted while hidden is laid out at 0×0 or a stale size.
   A debounced ResizeObserver on each graph host calls Plotly.Plots.resize
   once the host is visible and its size has actually changed. */
(() => {
  const HOST_SELECTOR = ".map-container, .chart-container";
  const OBSERVED_ATTR = "data-plotly-resize-observed";
  const DEBOUNCE_MS = 150;

  const lastSize = new WeakMap();
  const timers = new WeakMap();

  function resizeHost(host) {
    const gd = host.querySelector(".js-plotly-plot");
    if (!gd || !window.Plotly?.Plots?.resize) {
      return;
    }
    const { width, height } = host.getBoundingClientRect();
    if (width <= 2 || height <= 2) {
      return; // hidden tab — wait until it is shown
    }
    const prev = lastSize.get(host);
    if (prev && Math.abs(prev.width - width) < 2 && Math.abs(prev.height - height) < 2) {
      return;
    }
    lastSize.set(host, { width, height });
    window.requestAnimationFrame(() => {
      try {
        window.Plotly.Plots.resize(gd);
      } catch (_e) {
        /* no-op */
      }
    });
  }

  function schedule(host) {
    clearTimeout(timers.get(host));
    timers.set(host, setTimeout(() => resizeHost(host), DEBOUNCE_MS));
  }

  const resizeObserver = window.ResizeObserver
    ? new ResizeObserver((entries) => entries.forEach((e) => schedule(e.target)))
    : null;

  function wireHosts() {
    if (!resizeObserver) {
      return;
    }
    document.querySelectorAll(HOST_SELECTOR).forEach((host) => {
      if (!host.hasAttribute(OBSERVED_ATTR)) {
        host.setAttribute(OBSERVED_ATTR, "1");
        resizeObserver.observe(host);
      }
    });
  }

  function boot() {
    wireHosts();
    // Dash renders the layout after DOMContentLoaded; pick up hosts as they mount.
    new MutationObserver(wireHosts).observe(document.body, { childList: true, subtree: true });
    let t;
    window.addEventListener("resize", () => {
      clearTimeout(t);
      t = setTimeout(() => document.querySelectorAll(HOST_SELECTOR).forEach(resizeHost), 100);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
