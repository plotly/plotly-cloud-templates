/*
 * Drill-Hole Cross-Section Explorer — port of the CodePen of the same name.
 *
 * The CodePen renders into a single #chart div with raw Plotly.js. Dash
 * unmounts/remounts the page on every SPA route change, so we wrap the
 * codepen body in a MutationObserver-driven init() that re-binds whenever
 * the #explorer-chart div appears in the DOM. assets/*.js loads on every
 * Dash page; the early-out at the top of init() makes this a no-op when
 * the explorer page isn't mounted.
 */
(function () {
  var initialized = false;
  var retryTimer = null;

  function scheduleRetry() {
    if (retryTimer) return;
    retryTimer = setTimeout(function () {
      retryTimer = null;
      init();
    }, 100);
  }

  function init() {
    var gd = document.getElementById("explorer-chart");
    if (!gd) {
      initialized = false;
      return;
    }
    if (initialized) return;
    // Dash 4 lazy-loads Plotly.js when a dcc.Graph mounts. Poll until it's
    // available rather than bailing once.
    if (!window.Plotly) {
      scheduleRetry();
      return;
    }
    initialized = true;

    /* ===== begin verbatim CodePen JS ===== */
    var holeNames = ["DH-001", "DH-002", "DH-003", "DH-004"];
    var holeColors = ["#2563eb", "#16a34a", "#d97706", "#9333ea"];
    var yAxes = ["y", "y2", "y3", "y4"];
    var xAxes = ["x", "x2", "x3", "x4"];
    var domainXs = [
      [0.05, 0.22],
      [0.3, 0.47],
      [0.55, 0.72],
      [0.8, 0.97],
    ];

    function makeLog(seed, nPoints) {
      var depths = [],
        values = [];
      var v = 30 + seed * 5;
      for (var i = 0; i <= nPoints; i++) {
        var d = i * (100 / nPoints);
        depths.push(d);
        v +=
          Math.sin(d * 0.12 + seed) * 3 +
          Math.cos(d * 0.07 - seed * 2) * 2 +
          (Math.random() - 0.5) * 4;
        v = Math.max(5, Math.min(95, v));
        if (d > 35 + seed * 3 && d < 70 - seed * 2) v += 15;
        values.push(v);
      }
      return { depths: depths, values: values };
    }

    var units = [
      {
        name: "Overburden",
        tops: [0, 0, 0, 0],
        bots: [10, 8, 13, 9],
        fill: "rgba(139,90,43,0.22)",
        line: "rgba(139,90,43,0.7)",
      },
      {
        name: "Upper Sandstone",
        tops: [10, 8, 13, 9],
        bots: [28, 25, 30, 26],
        fill: "rgba(194,178,128,0.22)",
        line: "rgba(194,178,128,0.7)",
      },
      {
        name: "Ore Zone",
        tops: [28, 25, 30, 26],
        bots: [68, 64, 72, 66],
        fill: "rgba(220,50,50,0.18)",
        line: "rgba(220,50,50,0.7)",
      },
      {
        name: "Lower Shale",
        tops: [68, 64, 72, 66],
        bots: [85, 82, 88, 84],
        fill: "rgba(80,120,80,0.18)",
        line: "rgba(80,120,80,0.7)",
      },
      {
        name: "Basement Gneiss",
        tops: [85, 82, 88, 84],
        bots: [100, 100, 100, 100],
        fill: "rgba(100,100,160,0.18)",
        line: "rgba(100,100,160,0.7)",
      },
    ];

    var traces = [];
    for (var h = 0; h < 4; h++) {
      var log = makeLog(h, 80);
      var c = holeColors[h];
      var r = parseInt(c.slice(1, 3), 16),
        g = parseInt(c.slice(3, 5), 16),
        b = parseInt(c.slice(5, 7), 16);
      traces.push({
        x: log.values,
        y: log.depths,
        xaxis: xAxes[h],
        yaxis: yAxes[h],
        type: "scatter",
        mode: "lines",
        name: holeNames[h],
        line: { color: c, width: 1.5 },
        fill: "tozerox",
        fillcolor: "rgba(" + r + "," + g + "," + b + ",0.18)",
        hoverinfo: "none",
      });
    }

    var baseShapes = [];

    units.forEach(function (u) {
      for (var i = 0; i < 3; i++) {
        baseShapes.push({
          type: "path",
          xref: "paper",
          yref: [yAxes[i], yAxes[i + 1], yAxes[i + 1], yAxes[i]],
          path:
            "M " +
            domainXs[i][1] +
            " " +
            u.tops[i] +
            " L " +
            domainXs[i + 1][0] +
            " " +
            u.tops[i + 1] +
            " L " +
            domainXs[i + 1][0] +
            " " +
            u.bots[i + 1] +
            " L " +
            domainXs[i][1] +
            " " +
            u.bots[i] +
            " Z",
          fillcolor: u.fill,
          line: { color: u.line, width: 1 },
        });
      }
    });

    for (var hh = 0; hh < 4; hh++) {
      baseShapes.push({
        type: "rect",
        xref: xAxes[hh],
        yref: yAxes[hh],
        x0: 0,
        x1: 100,
        y0: units[2].tops[hh],
        y1: units[2].bots[hh],
        fillcolor: "rgba(220,50,50,0.10)",
        line: { width: 0 },
        layer: "below",
      });
    }

    var depthRange = [105, -5];
    var valRange = [0, 100];

    function yAxisCfg(extra) {
      return Object.assign(
        {
          range: depthRange,
          gridcolor: "#ecedf0",
          zerolinecolor: "#e2e4e9",
          linecolor: "#d1d5db",
          tickfont: { color: "#6b7280", size: 9 },
        },
        extra || {}
      );
    }

    function xAxisCfg(domain, anchor, title) {
      return {
        domain: domain,
        anchor: anchor,
        range: valRange,
        gridcolor: "#ecedf0",
        zerolinecolor: "#e2e4e9",
        linecolor: "#d1d5db",
        tickfont: { color: "#6b7280", size: 9 },
        title: {
          text: title,
          font: { size: 11, color: "#4b5563" },
          standoff: 6,
        },
      };
    }

    var layout = {
      paper_bgcolor: "#fff",
      plot_bgcolor: "#fafbfc",
      font: { color: "#1e2028" },
      margin: { l: 55, r: 16, t: 44, b: 44 },
      showlegend: true,
      legend: {
        x: 0.5,
        y: 1.07,
        xanchor: "center",
        orientation: "h",
        bgcolor: "rgba(255,255,255,0)",
        font: { color: "#4b5563", size: 11 },
      },

      hoveranywhere: true,
      clickanywhere: true,
      hovermode: "closest",

      shapes: baseShapes.slice(),

      yaxis: yAxisCfg({
        domain: [0, 1],
        anchor: "x",
        title: {
          text: "Depth (m)",
          font: { size: 11, color: "#4b5563" },
          standoff: 6,
        },
      }),
      yaxis2: yAxisCfg({
        domain: [0, 1],
        anchor: "x2",
        title: {
          text: "Depth (m)",
          font: { size: 11, color: "#4b5563" },
          standoff: 6,
        },
      }),
      yaxis3: yAxisCfg({
        domain: [0, 1],
        anchor: "x3",
        title: {
          text: "Depth (m)",
          font: { size: 11, color: "#4b5563" },
          standoff: 6,
        },
      }),
      yaxis4: yAxisCfg({
        domain: [0, 1],
        anchor: "x4",
        title: {
          text: "Depth (m)",
          font: { size: 11, color: "#4b5563" },
          standoff: 6,
        },
      }),

      xaxis: xAxisCfg(domainXs[0], "y", "DH-001"),
      xaxis2: xAxisCfg(domainXs[1], "y2", "DH-002"),
      xaxis3: xAxisCfg(domainXs[2], "y3", "DH-003"),
      xaxis4: xAxisCfg(domainXs[3], "y4", "DH-004"),

      annotations: [],
    };

    var clicks = [];

    function dot(xa, ya, xval, depth) {
      var axObj =
        gd._fullLayout[ya === "y" ? "yaxis" : "yaxis" + ya.slice(1)];
      var xAxObj =
        gd._fullLayout[xa === "x" ? "xaxis" : "xaxis" + xa.slice(1)];
      var px = 4;
      var rx =
        (px * (xAxObj.range[1] - xAxObj.range[0])) / (xAxObj._length || 1);
      var ry =
        (px * (axObj.range[1] - axObj.range[0])) / (axObj._length || 1);
      return {
        type: "circle",
        xref: xa,
        yref: ya,
        x0: xval - rx,
        x1: xval + rx,
        y0: depth - ry,
        y1: depth + ry,
        fillcolor: "rgba(220,38,38,0.5)",
        line: { color: "#dc2626", width: 1.5 },
      };
    }

    function getClickInfo(data) {
      var depth, xval, holeIdx;
      if (data.points && data.points.length > 0) {
        var pt = data.points[0];
        depth = pt.y;
        xval = pt.x;
        var traceXa = pt.data.xaxis || "x";
        holeIdx =
          traceXa === "x" ? 0 : parseInt(traceXa.replace("x", "")) - 1;
      } else if (data.yvals && data.yvals.length > 0) {
        depth = data.yvals[0];
        xval = data.xvals ? data.xvals[0] : 50;
        if (data.xaxes && data.xaxes.length > 0) {
          var axId = data.xaxes[0]._id || "";
          holeIdx = axId === "x" ? 0 : parseInt(axId.replace("x", "")) - 1;
        }
      }
      if (depth !== undefined && holeIdx !== undefined) {
        return { depth: depth, xval: xval, holeIdx: holeIdx };
      }
      return null;
    }

    Plotly.newPlot(gd, traces, layout, {
      responsive: true,
      displayModeBar: true,
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
      displaylogo: false,
    }).then(function () {
      gd.on("plotly_hover", function (d) {
        var gs = gd._fullLayout._size;
        var layer = gd._fullLayout._hoverlayer;

        layer.selectAll(".pseudo-spike").remove();

        var yPos = d.event.offsetY;

        layer
          .insert("line", ":first-child")
          .attr({
            x1: gs.l,
            x2: gs.l + gs.w,
            y1: yPos,
            y2: yPos,
            "stroke-width": 1,
            stroke: "rgba(100,100,100,0.4)",
            "stroke-dasharray": "4,3",
          })
          .classed("pseudo-spike", true);

        var depthVal = d.yvals
          ? d.yvals[0]
          : d.points && d.points.length > 0
          ? d.points[0].y
          : null;
        if (depthVal !== null) {
          layer
            .append("rect")
            .attr({
              x: gs.l - 52,
              y: yPos - 9,
              width: 48,
              height: 18,
              rx: 3,
              fill: "#4b5563",
            })
            .classed("pseudo-spike", true);
          layer
            .append("text")
            .attr({
              x: gs.l - 48,
              y: yPos + 4,
              fill: "white",
              "font-size": "10px",
              "font-family": "Inter, Segoe UI, system-ui, sans-serif",
            })
            .text(depthVal.toFixed(1) + " m")
            .classed("pseudo-spike", true);
        }

        if (d.points && d.points.length > 0) {
          var pt = d.points[0];
          var tc = pt.data.line.color;
          var xax = pt.xaxis;
          var yax = pt.yaxis;

          var mkX =
            xax._offset +
            ((pt.x - xax.range[0]) / (xax.range[1] - xax.range[0])) *
              xax._length;
          var mkY =
            yax._offset +
            ((pt.y - yax.range[1]) / (yax.range[0] - yax.range[1])) *
              yax._length;

          layer
            .append("circle")
            .attr({
              cx: mkX,
              cy: mkY,
              r: 4.5,
              fill: tc,
              stroke: "white",
              "stroke-width": 2,
            })
            .classed("pseudo-spike", true);

          var yStr = pt.y.toFixed(1) + " m";
          var lblW = yStr.length * 6.5 + 18;
          var lblH = 20;
          var gap = 10;
          var lx = mkX + gap;
          if (lx + lblW > gs.l + gs.w) lx = mkX - lblW - gap;
          var ly = mkY - lblH / 2;

          layer
            .append("rect")
            .attr({ x: lx, y: ly, width: lblW, height: lblH, rx: 10, fill: tc })
            .classed("pseudo-spike", true);

          layer
            .append("text")
            .attr({
              x: lx + lblW / 2,
              y: ly + 13,
              fill: "white",
              "font-size": "10.5px",
              "font-family": "Inter, Segoe UI, system-ui, sans-serif",
              "font-weight": "600",
              "text-anchor": "middle",
            })
            .text(yStr)
            .classed("pseudo-spike", true);
        }

        var depth, holeName, xval;
        if (d.points && d.points.length > 0) {
          var pt2 = d.points[0];
          depth = pt2.y;
          xval = pt2.x;
          holeName = pt2.data.name;
        } else if (d.yvals && d.yvals.length > 0) {
          depth = d.yvals[0];
          xval = d.xvals ? d.xvals[0] : null;
          if (d.xaxes && d.xaxes.length > 0) {
            var axId = d.xaxes[0]._id || "";
            var hIdx = axId === "x" ? 0 : parseInt(axId.replace("x", "")) - 1;
            holeName = holeNames[hIdx] || "--";
          }
        }
        if (depth !== undefined) {
          var depthEl = document.getElementById("cursor-depth");
          var holeEl = document.getElementById("cursor-hole");
          var valueEl = document.getElementById("cursor-value");
          if (depthEl) depthEl.textContent = depth.toFixed(1) + " m";
          if (holeEl) holeEl.textContent = holeName || "--";
          if (valueEl)
            valueEl.textContent =
              xval !== null && xval !== undefined ? xval.toFixed(1) : "--";
        }
      });

      gd.on("plotly_unhover", function () {
        if (gd._fullLayout && gd._fullLayout._hoverlayer) {
          gd._fullLayout._hoverlayer.selectAll(".pseudo-spike").remove();
        }
        var depthEl = document.getElementById("cursor-depth");
        var holeEl = document.getElementById("cursor-hole");
        var valueEl = document.getElementById("cursor-value");
        if (depthEl) depthEl.textContent = "--";
        if (holeEl) holeEl.textContent = "--";
        if (valueEl) valueEl.textContent = "--";
      });

      gd.on("plotly_click", function (data) {
        var info = getClickInfo(data);
        if (!info) return;

        var distEl = document.getElementById("distance-result");
        var xa = xAxes[info.holeIdx];
        var ya = yAxes[info.holeIdx];

        if (clicks.length >= 2) {
          clicks = [];
          Plotly.relayout(gd, {
            shapes: baseShapes.slice(),
            annotations: [],
          });
          if (distEl) distEl.style.display = "none";
          return;
        }

        clicks.push({
          depth: info.depth,
          xval: info.xval,
          holeIdx: info.holeIdx,
          xa: xa,
          ya: ya,
        });

        if (clicks.length === 1) {
          if (distEl) {
            distEl.style.display = "block";
            distEl.innerHTML =
              "Point 1: <strong>" +
              info.depth.toFixed(1) +
              " m</strong> on " +
              holeNames[info.holeIdx];
          }
          Plotly.relayout(gd, {
            shapes: baseShapes.concat([dot(xa, ya, info.xval, info.depth)]),
            annotations: [],
          });
        } else {
          var a = clicks[0],
            b = clicks[1];

          if (a.holeIdx !== b.holeIdx) {
            clicks.pop();
            return;
          }

          var dist = Math.abs(b.depth - a.depth);
          var mx = (a.xval + b.xval) / 2;
          var my = (a.depth + b.depth) / 2;

          if (distEl) {
            distEl.style.display = "block";
            distEl.innerHTML =
              "<strong>" +
              dist.toFixed(1) +
              " m</strong> on " +
              holeNames[a.holeIdx];
          }

          Plotly.relayout(gd, {
            shapes: baseShapes.concat([
              dot(a.xa, a.ya, a.xval, a.depth),
              dot(b.xa, b.ya, b.xval, b.depth),
              {
                type: "line",
                xref: a.xa,
                yref: a.ya,
                x0: a.xval,
                y0: a.depth,
                x1: b.xval,
                y1: b.depth,
                line: { color: "#dc2626", width: 2 },
              },
            ]),
            annotations: [
              {
                x: mx,
                y: my,
                xref: a.xa,
                yref: a.ya,
                text: dist.toFixed(1) + " m",
                showarrow: false,
                font: { color: "#dc2626", size: 12 },
                bgcolor: "rgba(255,255,255,0.9)",
                bordercolor: "#dc2626",
                borderwidth: 1,
                borderpad: 4,
              },
            ],
          });
        }
      });
    });
    /* ===== end verbatim CodePen JS ===== */
  }

  var observer = new MutationObserver(function () {
    if (!document.getElementById("explorer-chart")) {
      initialized = false;
      return;
    }
    init();
  });

  if (document.body) {
    observer.observe(document.body, { childList: true, subtree: true });
  } else {
    document.addEventListener("DOMContentLoaded", function () {
      observer.observe(document.body, { childList: true, subtree: true });
      init();
    });
  }
  init();
})();
