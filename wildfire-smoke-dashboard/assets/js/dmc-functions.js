/* Functions referenced from Python as {"function": "<name>"} props (DMC pattern:
   window.dashMantineFunctions). Keep them small and pure. */
var dmcfuncs = (window.dashMantineFunctions = window.dashMantineFunctions || {});

/* Day slider thumb label: day index → "Sep 12". options.days is SEASON_DAYS[season]. */
dmcfuncs.dayLabel = function (value, { days }) {
  const iso = days && days[value];
  if (!iso) {
    return null;
  }
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
};
