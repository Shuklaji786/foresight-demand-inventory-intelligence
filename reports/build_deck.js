const pptxgen = require("pptxgenjs");
const path = require("path");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5in
const W = 13.33, H = 7.5;

const NAVY = "1A1B3D";
const PURPLE = "6C5CE7";
const RED = "D64545";
const GREEN = "2E9E5B";
const BLUE = "5C6BC0";
const AMBER = "E0A526";
const GREY = "6B6F76";
const LIGHT = "F4F4F8";

const FIG = path.join(__dirname, "figures");

function titleSlide() {
  const s = pres.addSlide();
  s.background = { color: NAVY };
  s.addText("Project FORESIGHT", {
    x: 0.7, y: 2.55, w: 11.9, h: 1.0, fontSize: 40, bold: true, color: "FFFFFF",
    fontFace: "Arial", isTextBox: true, margin: 0,
  });
  s.addText("Demand & Inventory Intelligence — Executive Readout", {
    x: 0.7, y: 3.5, w: 11.9, h: 0.6, fontSize: 20, color: "C9CBEB",
    fontFace: "Arial", isTextBox: true, margin: 0,
  });
  s.addText("Prepared for: Head of Operations & Finance, NorthBay Living", {
    x: 0.7, y: 4.9, w: 11, h: 0.4, fontSize: 14, color: "9A9DC4", isTextBox: true, margin: 0,
  });
  s.addText("Zidio Development · Data Science & Analytics", {
    x: 0.7, y: 6.7, w: 8, h: 0.4, fontSize: 12, color: "7C7FB0", isTextBox: true, margin: 0,
  });
}

function sectionHeader(s, kicker, title) {
  s.addText(kicker.toUpperCase(), {
    x: 0.7, y: 0.42, w: 8, h: 0.35, fontSize: 12, color: PURPLE, bold: true,
    charSpacing: 1, isTextBox: true, margin: 0,
  });
  s.addText(title, {
    x: 0.7, y: 0.72, w: 11.9, h: 0.7, fontSize: 26, bold: true, color: NAVY,
    isTextBox: true, margin: 0,
  });
}

function bulletSlide(kicker, title, bullets, opts = {}) {
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  sectionHeader(s, kicker, title);
  const items = bullets.map((b, i) => ({
    text: b, options: {
      bullet: { code: "2022" }, color: "2A2A38", fontSize: opts.fontSize || 16,
      breakLine: i < bullets.length - 1, paraSpaceAfter: 14,
    },
  }));
  s.addText(items, { x: 0.7, y: 1.65, w: opts.w || 11.9, h: opts.h || 5.2, isTextBox: true, margin: 0, valign: "top" });
  return s;
}

function kpiCard(s, x, y, w, h, value, label, color) {
  s.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.08, fill: { color: LIGHT }, line: { color: LIGHT } });
  s.addText(value, { x: x + 0.15, y: y + 0.12, w: w - 0.3, h: h * 0.55, fontSize: 26, bold: true, color, isTextBox: true, margin: 0, align: "left" });
  s.addText(label, { x: x + 0.15, y: y + h * 0.6, w: w - 0.3, h: h * 0.35, fontSize: 12, color: GREY, isTextBox: true, margin: 0, align: "left" });
}

// 1. Title
titleSlide();

// 2. The situation
bulletSlide("The Brief", "NorthBay is guessing what to stock", [
  "~60 active SKUs across Furniture, Décor, and Small Appliances, planned on spreadsheets and gut feel.",
  "Best-sellers run out (lost sales); slow movers pile up (cash locked in markdowns).",
  "The ask: a weekly demand forecast, an early-warning system for stockouts and overstock, and a tool the ops team can use without a data scientist in the room.",
]);

// 3. Headline numbers
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  sectionHeader(s, "Headline Impact", "What FORESIGHT found, in rupees");
  kpiCard(s, 0.7, 1.8, 3.7, 1.7, "\u20B95.5 Cr", "Sales at risk from stockouts, next 6 weeks", RED);
  kpiCard(s, 4.65, 1.8, 3.7, 1.7, "\u20B988 L", "Capital locked in overstock", BLUE);
  kpiCard(s, 8.6, 1.8, 3.95, 1.7, "25 of 60", "SKUs need a reorder now", AMBER);
  s.addText(
    "The model's weekly SKU-level forecast beats a seasonal-naive baseline by roughly a third on backtest " +
    "(11.6% WAPE vs 17.5%), so the ₹ figures above are built on numbers the team can trust, not guesswork.",
    { x: 0.7, y: 3.9, w: 11.9, h: 1.0, fontSize: 16, color: "2A2A38", isTextBox: true, margin: 0 }
  );
  s.addText(
    "Recommendation: action the 25 \u201cReorder Now\u201d SKUs this week; run a markdown promotion on the 2 " +
    "\u201cMarkdown / Clear\u201d SKUs to free up capital before next quarter's stock intake.",
    { x: 0.7, y: 5.1, w: 11.9, h: 1.2, fontSize: 16, bold: true, color: NAVY, isTextBox: true, margin: 0 }
  );
}

// 4. Demand patterns (image)
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  sectionHeader(s, "What The Data Shows", "Demand is seasonal and promo-driven");
  s.addImage({ path: path.join(FIG, "01_total_weekly_demand.png"), x: 0.7, y: 1.6, w: 7.6, h: 3.5 });
  s.addText([
    { text: "Demand climbs through the year and spikes sharply during promo weeks.", options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 10 } },
    { text: "Promo weeks sell ~2x a normal week on average \u2014 the forecast must model this explicitly.", options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 10 } },
    { text: "A naive \u201caverage of last month\u201d approach would badly under- or over-shoot around every sale.", options: { bullet: { code: "2022" }, breakLine: false } },
  ], { x: 8.5, y: 1.7, w: 4.1, h: 3.3, fontSize: 14, color: "2A2A38", isTextBox: true, margin: 0, valign: "top" });
  s.addText("Source: reports/figures/01_total_weekly_demand.png \u2014 generated by src/eda.py", {
    x: 0.7, y: 5.25, w: 8, h: 0.3, fontSize: 9, color: GREY, italic: true, isTextBox: true, margin: 0,
  });
}

// 5. Concentration / top movers
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  sectionHeader(s, "What The Data Shows", "A small set of SKUs drives most of the volume");
  s.addImage({ path: path.join(FIG, "03_top_movers.png"), x: 0.7, y: 1.6, w: 7.6, h: 3.5 });
  s.addText([
    { text: "The top 10 SKUs account for a large share of units sold in the last 12 weeks.", options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 10 } },
    { text: "These deserve the tightest stockout monitoring \u2014 a missed reorder here is the costliest miss.", options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 10 } },
    { text: "A long tail of low-volume SKUs are the natural markdown / clear candidates.", options: { bullet: { code: "2022" }, breakLine: false } },
  ], { x: 8.5, y: 1.7, w: 4.1, h: 3.3, fontSize: 14, color: "2A2A38", isTextBox: true, margin: 0, valign: "top" });
}

// 6. Methodology (honest)
bulletSlide("How We Built It", "Forecast first proven against a baseline, honestly", [
  "Framed the metric (WAPE) and a 6-week forecast horizon before touching a model, per standard forecasting practice.",
  "Built a seasonal-naive baseline first \u2014 the bar every model has to clear.",
  "Trained a gradient-boosted model on lag, rolling-average, calendar, and promo features.",
  "Validated with rolling-origin backtesting (train on the past, test on the next block, repeat) \u2014 never a single random split, and no future data ever touches a feature.",
  "Result: 11.6% WAPE vs 17.5% for the baseline \u2014 the model wins, and we can show our work.",
], { fontSize: 15 });

// 7. Decisioning grid
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  sectionHeader(s, "Turning Forecasts Into Decisions", "Every SKU, plotted by risk");
  s.addImage({ path: path.join(FIG, "06_decisioning_grid.png"), x: 3.85, y: 1.35, w: 5.6, h: 5.6 });
  s.addText([
    { text: "Reorder Now: high stockout risk \u2014 raise a replenishment order.", options: { bullet: { code: "2022" }, color: RED, breakLine: true, paraSpaceAfter: 12 } },
    { text: "Markdown / Clear: high overstock \u2014 promote or discount.", options: { bullet: { code: "2022" }, color: BLUE, breakLine: true, paraSpaceAfter: 12 } },
    { text: "Watch / Volatile: high on both \u2014 review manually.", options: { bullet: { code: "2022" }, color: AMBER, breakLine: true, paraSpaceAfter: 12 } },
    { text: "Healthy: no action needed.", options: { bullet: { code: "2022" }, color: GREEN, breakLine: false } },
  ], { x: 0.7, y: 2.0, w: 2.9, h: 3.5, fontSize: 13, isTextBox: true, margin: 0, valign: "top" });
  s.addText("Bubble size = revenue at stake. This is the view the ops team uses to triage weekly.", {
    x: 0.7, y: 6.7, w: 11.9, h: 0.4, fontSize: 12, italic: true, color: GREY, isTextBox: true, margin: 0,
  });
}

// 8. What the client receives
bulletSlide("Delivered", "What NorthBay's team gets", [
  "A reproducible data pipeline \u2014 re-runs end to end from raw extracts with one command.",
  "A backtested, baseline-beating demand forecast for every SKU, 6 weeks out.",
  "A transparent stockout/overstock risk score with a recommended action and rupee value per SKU.",
  "A planning dashboard the ops team can use without a data scientist in the room.",
  "A deployed scoring service any system can call for a forecast + risk on demand.",
], { fontSize: 16 });

// 9. Limitations & next steps
bulletSlide("Honest Limitations & Next Steps", "What this doesn't cover yet", [
  "New SKUs with under 12 weeks of history fall back to category-level patterns \u2014 flagged as lower-confidence.",
  "The model was trained and validated on the provided extracts; a live data feed will need the same rolling-origin discipline before every retrain.",
  "Out of scope for this engagement: live system integrations, price optimization, and automated purchase orders \u2014 FORESIGHT recommends, it does not act.",
  "Suggested next step: pilot the \u201cReorder Now\u201d list for one ordering cycle, then compare actual stockouts against this month's forecast to calibrate trust.",
], { fontSize: 16 });

pres.writeFile({ fileName: path.join(__dirname, "executive_readout.pptx") }).then(() => {
  console.log("Deck written.");
});
