"use strict";
const $ = id => document.getElementById(id);
const sampleClaim = "The placement rate rose by at least 10 percentage points from 2024 to 2025.";
const key = "chartproof.audit.v1";
let state, editing, draft, cloudToken = "",
  health = {},
  requestNumber = 0;
const chartNames = {before: "Original figure", after: "Revised figure"};
let quickSide = "before";
let enteringSide = "before";
function emptyState() {
  return {schema: 1, mode: "verify", before: null, after: null, claims: [],
    results: [], history: [], links: {}, visionComparisons: {}};
}
function comparing() {return state?.mode === "compare";}
function selectedAfter() {return comparing() ? state.after : state.before;}
function ready() {return !!(state?.before?.reviewed && selectedAfter()?.reviewed);}

function el(tag, txt, cls) {
  const n = document.createElement(tag);
  if (txt !== undefined) n.textContent = txt;
  if (cls) n.className = cls;
  return n;
}

function note(txt) {
  $("message").textContent = txt;
}

function btn(txt, fn, cls = "") {
  const b = el("button", txt, cls);
  b.type = "button";
  b.onclick = fn;
  return b;
}
async function api(path, obj, token = "") {
  const opts = obj === undefined ? {} : {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-chartproof-token": token
    },
    body: JSON.stringify(obj)
  };
  const resp = await fetch(path, opts);
  const result = await resp.json();
  if (!resp.ok) throw Error(result.detail || "Request failed.");
  return result;
}

function download(name, value) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], {
    type: "application/json"
  }));
  const a = el("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function persist() {
  try {
    localStorage.setItem(key, JSON.stringify(state));
    $("saveState").textContent = "Saved in this browser";
  } catch {
    $("saveState").textContent = "Storage full · export this audit";
  }
}

function usable(c) {
  return c && typeof c.metric === "string" && Array.isArray(c.rows) && c.rows.length <= 80 && typeof c
    .image === "string" && /^data:image\/(?:jpeg|png);base64,[A-Za-z0-9+/=]+$/.test(c.image) && c.image
    .length < 3500000;
}

function validate(a) {
  if (a?.schema !== 1 || (a.before !== null && !usable(a.before)) ||
      (a.after != null && !usable(a.after)) || !Array.isArray(a.claims) || a.claims
    .length > 20 || a.claims.some(s => typeof s !== "string" || s.length > 360)) throw Error(
    "Choose a valid ChartProof version 1 audit.");
  return {...a, mode: a.mode === "verify" ? "verify" : "compare", results: []};
}

function quickUpload(side) {
  quickSide = side;
  $("quickFile").click();
}
function sourceCard(side) {
  const c = state[side], box = el("article", undefined, "card"),
    head = el("div", undefined, "cardHead"), title = el("div"),
    actions = el("div", undefined, "cardActions");
  title.append(el("h3", comparing() ? chartNames[side] : "Chart evidence"));
  title.append(el("small", c ? (c.filename || "Reviewed data") + " · " + (c.engine || "Manual") :
    "No chart uploaded"));
  head.append(title);
  if (!c) {
    box.classList.add("emptyCard");
    const body = el("div", undefined, "emptyCardBody");
    body.append(el("p", "Add " + (side === "after" ? "the new chart" : "the original chart") +
      " to continue your comparison."));
    const choose = el("div", undefined, "cardActions");
    choose.append(btn("Upload chart", () => quickUpload(side), "accent"),
      btn("Paste values / CSV", () => openDataEntry(side), "quiet"));
    body.append(choose);
    box.append(head, body);
    return box;
  }
  actions.append(btn("Review / replace", () => openEdit(side)),
    btn("Paste values / CSV", () => openDataEntry(side), "quiet"));
  head.append(actions);
  const im = el("img");
  im.src = c.image;
  im.alt = c.metric + " chart: " + c.rows.map(r => r.year + " " + r.value + "%").join(", ");
  const meta = el("div", undefined, "chartMeta");
  meta.append(el("span", (c.engine || "Reviewed data") + " · " +
    (c.reviewed ? "Reviewed" : "Review required")),
    el("span", c.rows.map(r => r.year + "  " + r.value + "%").join("   /   ")));
  box.append(head, im, meta);
  return box;
}

function proofSide(label, v) {
  const box = el("div");
  box.append(el("small", label + " · " + v.status), el("code", v.formula || v.reason));
  if (v.evidence.length) box.append(el("p", v.evidence.map(r => r.year + " = " + r.value + "%").join(" · ")));
  return box;
}
async function directVision(index, where, button) {
  const audit = state,
    claim = audit.claims[index],
    figures = [audit.before, audit.after];
  const token = cloudToken || window.prompt("ChartProof server access token");
  if (!token) return;
  cloudToken = token;
  button.disabled = true;
  where.textContent = "Checking both chart images with Azure…";
  try {
    const results = [];
    for (const [i, side] of ["before", "after"].entries()) {
      const r = await api("/api/vision", {
        file: figures[i].image.split(",")[1],
        claim
      }, token);
      results.push(chartNames[side] + ": " + r.status + ". " + r.reason);
    }
    if (state !== audit || state.before !== figures[0] || state.after !== figures[1] || !state.claims
      .includes(claim)) return;
    where.textContent = results.join(" / ");
    state.visionComparisons = {
      ...(state.visionComparisons || {}),
      [claim]: results
    };
    persist();
  } catch (e) {
    where.textContent = e.message;
  } finally {
    button.disabled = false;
  }
}

function resultRow(claim, i) {
  const result = state.results[i],
    box = el("article", undefined, "result"),
    rh = el("div", undefined, "rhead");
  rh.append(el("span", claim));
  const status = result ? (comparing() ? result.transition : result.after.status) : "Awaiting check";
  const className = result && (status === "Outdated claim" || status === "Contradicted") ?
    "alert" : result && status === "Insufficient evidence" ? "unknown" : "";
  rh.append(el("span", status, "badge " + className));
  box.append(rh);
  if (result) {
    const details = el("details");
    if (i === 0) details.open = true;
    details.append(el("summary", "Inspect evidence"));
    const grid = el("div", undefined, "proof");
    if (comparing()) grid.append(proofSide("Original", result.before),
      proofSide("Revised", result.after));
    else grid.append(proofSide("Chart evidence", result.after));
    details.append(grid);
    const impact = result.revision_impact;
    if (impact && comparing()) {
      const changes = impact.changes.map(row => row.kind === "added"
        ? row.year + ": added " + row.after + "%"
        : row.kind === "removed" ? row.year + ": removed " + row.before + "%"
          : row.year + ": " + row.before + "% → " + row.after + "%");
      const summary = impact.metric_changed ? "Metric label changed. " : "";
      const digest = impact.source_changed === true ? " Source file hash changed."
        : impact.source_changed === false ? " Source file hash unchanged." : "";
      const relevance = impact.claim_years_changed ? " Referenced evidence changed."
        : " Referenced values unchanged.";
      details.append(el("p", "Revision impact · " + summary +
        (changes.join("; ") || "No year/value changes.") + relevance + digest));
    }
    if (result.after.correction) details.append(el("p", "Suggested wording · " + result.after.correction));
    details.append(el("small", result.binding_source + " · model operation: " + result.check.model_label +
      " · check: " + result.check.operation + " · comparison uses printed values."));
    if (health.azure_vision_configured) {
      const p = el("p", (state.visionComparisons?.[claim] || []).join(" / "));
      const baseline = btn("Compare with Foundry vision", () => directVision(i, p, baseline), "linkbtn");
      details.append(document.createElement("br"), baseline, p);
    }
    box.append(details);
  }
  box.append(btn("Link a calculation", () => openBinding(claim), "linkbtn"), document.createTextNode(
  "  ·  "));
  box.append(btn("Remove claim", () => {
    state.claims.splice(i, 1);
    state.results.splice(i, 1);
    delete state.visionComparisons?.[claim];
    delete state.links?.[claim];
    persist();
    render();
    runChecks();
  }, "remove"));
  return box;
}

function render() {
  if (!state) return;
  const isComparison = comparing();
  $("verifyMode").classList.toggle("chosen", !isComparison);
  $("compareMode").classList.toggle("chosen", isComparison);
  $("verifyMode").setAttribute("aria-pressed", String(!isComparison));
  $("compareMode").setAttribute("aria-pressed", String(isComparison));
  $("modeNote").textContent = isComparison ?
    "Compare original and revised figures. Verify both sets of values before running checks." :
    "Check whether your statement agrees with one reviewed chart. No previous version needed.";
  $("uploadZone").hidden = !!state.before;
  $("charts").classList.toggle("single", !isComparison);
  const cards = isComparison ? [sourceCard("before"), sourceCard("after")] :
    state.before ? [sourceCard("before")] : [];
  $("charts").replaceChildren(...cards);
  $("claimList").replaceChildren(...state.claims.map(resultRow));
  $("claimHint").textContent = state.before?.metric ?
    "Use the exact metric name: “" + state.before.metric + "”. Specify years and units." :
    "Use the metric on your chart, such as Placement rate or CBSE pass rate.";
  $("emptyResults").hidden = !!state.results.length;
  $("emptyResults").textContent = !state.before ? "First upload a chart or paste a table." :
    !ready() ? "Review and confirm " + (isComparison ? "both charts" : "your chart") +
      " to enable verification." :
    !state.claims.length ? "Add a numerical statement above to see the evidence and verdict." :
    "Click Run verification to calculate the result.";
  $("check").disabled = !ready() || !state.claims.length;
  $("export").disabled = !(state.before && (isComparison ? state.after : true));
}

async function runChecks() {
  if (!state) return;
  const id = ++requestNumber;
  if (!state.claims.length || !ready()) {
    state.results = [];
    $("export").disabled = false;
    persist();
    render();
    return;
  }
  state.results = [];
  persist();
  render();
  $("check").disabled = true;
  $("export").disabled = true;
  try {
    const brief = c => ({
      reviewed: c.reviewed,
      sha256: c.sha256,
      metric: c.metric,
      unit: c.unit,
      rows: c.rows.map(r => ({
        year: r.year,
        value: r.value
      }))
    });
    const r = await api("/api/check", {
      before: brief(state.before),
      after: brief(selectedAfter()),
      claims: state.claims,
      links: state.links || {}
    });
    if (id !== requestNumber) return;
    state.results = r.results;
    persist();
    render();
    note("");
  } catch (e) {
    if (id === requestNumber) {
      state.results = [];
      persist();
      render();
      note(e.message);
    }
  } finally {
    if (id === requestNumber) $("export").disabled = false;
  }
}
async function loadExample() {
  const scenario = $("scenario").value;
  $("load").disabled = true;
  try {
    const [before, after] = await Promise.all([api("/api/sample/original"), api("/api/sample/" +
    scenario)]);
    state = {
      schema: 1,
      mode: "compare",
      before,
      after,
      claims: [sampleClaim, "Placement rate was at least 65% in 2025."],
      results: [],
      history: [],
      links: {},
      visionComparisons: {}
    };
    render();
    await runChecks();
  } catch (e) {
    note(e.message);
  } finally {
    $("load").disabled = false;
  }
}

function fillEditor(c) {
  $("sourcePreview").hidden = !c?.image;
  if (c?.image) $("sourcePreview").src = c.image;
  else $("sourcePreview").removeAttribute("src");
  $("metric").value = c?.metric || "";
  $("values").value = (c?.rows || []).map(r => r.year + ", " + r.value).join("\n");
  $("confirmed").checked = false;
  $("apply").disabled = !c?.image;
  $("editMessage").textContent = c?.image ?
    (c.warning || "Verify every recognized value against the source, then confirm.") :
    "Choose a chart image or a PDF, then click Read file.";
}

function openEdit(side) {
  editing = side;
  draft = state[side] ? structuredClone(state[side]) :
    {image: "", rows: [], metric: "", reviewed: false, unit: "%", page: 1, pages: 1};
  $("editTitle").textContent = chartNames[side];
  $("file").value = "";
  $("page").value = "1";
  $("engine").value = "local";
  cloudUI();
  fillEditor(draft);
  $("editor").showModal();
}

function cloudUI() {
  const isCloud = $("engine").value === "azure";
  $("cloudNote").hidden = !isCloud;
  $("tokenLabel").hidden = !isCloud;
  $("token").value = cloudToken;
}
async function readUpload(chosenFile) {
  const f = chosenFile || $("file").files[0];
  if (!f) {
    $("editMessage").textContent = "Choose a file first.";
    return;
  }
  if (f.size > 3 * 1024 * 1024) {
    $("editMessage").textContent = "Choose a file up to 3 MiB or crop the chart to a single page.";
    return;
  }
  const page = Number($("page").value),
    engine = $("engine").value;
  $("extract").disabled = true;
  $("apply").disabled = true;
  $("editMessage").textContent = "Reading the selected page…";
  try {
    const bytes = await new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result.split(",")[1]);
      r.onerror = reject;
      r.readAsDataURL(f);
    });
    cloudToken = $("token").value;
    const r = await api("/api/extract", {
      file: bytes,
      page,
      engine
    }, cloudToken);
    draft = {
      ...r,
      filename: f.name
    };
    fillEditor(draft);
    $("file").value = "";
    $("apply").disabled = false;
  } catch (e) {
    $("editMessage").textContent = e.message;
  } finally {
    $("extract").disabled = false;
  }
}

function applyEdit(e) {
  e.preventDefault();
  if (!$("confirmed").checked) return;
  try {
    const rows = $("values").value.trim().split(/\n/).map(line => {
      const match = line.trim().match(/^((?:19|20)\d{2})\s*,\s*(\d{1,3}(?:\.\d{1,4})?)\s*%?$/);
      if (!match || Number(match[2]) > 100) throw Error(
        "Use one year, percentage pair on each line (2024, 60).");
      return {
        year: match[1],
        value: match[2],
        box: draft.rows.find(r => r.year === match[1] && Number(r.value) === Number(match[2]))?.box ||
          null
      };
    });
    if (new Set(rows.map(r => r.year)).size !== rows.length) throw Error("Each year must appear once.");
    const metric = $("metric").value.trim();
    if (!/^[A-Za-z][A-Za-z0-9 &'/-]{0,79}$/.test(metric)) throw Error(
      "Use a short English metric name matching the chart.");
    saveFigure(editing, {...draft, metric, rows, reviewed: true});
    $("editor").close();
  } catch (err) {
    $("editMessage").textContent = err.message;
  }
}
function saveFigure(side, figure) {
  const old = state[side];
  if (old) {
    state.history.push({side, at: new Date().toISOString(),
      oldSource: old.sha256 || null, newSource: figure.sha256 || null,
      previous: {metric: old.metric, rows: old.rows},
      reviewed: {metric: figure.metric, rows: figure.rows}});
  }
  state[side] = figure;
  state.results = [];
  state.visionComparisons = {};
  render();
  runChecks();
}

function openDataEntry(side) {
  enteringSide = side;
  $("entryMetric").value = state[side]?.metric || state.before?.metric || "";
  $("entryRows").value = state[side]?.rows?.map(r => r.year + "," + r.value).join("\n") || "";
  $("entryCsv").value = "";
  $("entryConfirm").checked = false;
  $("entryMessage").textContent = "";
  $("dataEntry").showModal();
}
function parseDataRows(raw) {
  const lines = raw.trim().split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  if (!lines.length) throw Error("Enter at least one year and percentage.");
  if (/^year\s*[,;\t]/i.test(lines[0])) lines.shift();
  if (!lines.length || lines.length > 12) throw Error("Use between 1 and 12 year/percentage rows.");
  const rows = lines.map(line => {
    const columns = line.split(/[,;\t]/).map(x => x.trim().replace(/^"|"$/g, ""));
    const year = columns[0], number = columns[1]?.replace(/%$/, "").trim();
    if (columns.length !== 2 || !/^(19|20)\d{2}$/.test(year) ||
        !/^\d{1,3}(?:\.\d{1,4})?$/.test(number) || Number(number) > 100)
      throw Error("Each row needs a four-digit year and a percentage (example: 2025,66).");
    return {year, value: number, box: null};
  });
  if (new Set(rows.map(row => row.year)).size !== rows.length)
    throw Error("Each year can appear only once.");
  return rows.sort((a, b) => a.year.localeCompare(b.year));
}
function dataChart(metric, rows) {
  const canvas = document.createElement("canvas");
  canvas.width = 920; canvas.height = 520;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, 920, 520);
  ctx.fillStyle = "#173e37"; ctx.font = "bold 33px Arial";
  ctx.fillText(metric, 62, 78);
  const base = 410, width = 770 / rows.length, barWidth = Math.min(64, width * .56);
  ctx.strokeStyle = "#e0e9e4"; ctx.lineWidth = 2;
  for (const y of [170, 250, 330, 410]) {
    ctx.beginPath();ctx.moveTo(75, y);ctx.lineTo(846, y);ctx.stroke();
  }
  rows.forEach((row, i) => {
    const x = 75 + width * (i + .5), h = Number(row.value) * 2.45;
    ctx.fillStyle = "#237a61";ctx.fillRect(x - barWidth/2, base-h, barWidth, h);
    ctx.fillStyle = "#153c36";ctx.font = "bold " + (rows.length > 7 ? 16 : 22) + "px Arial";
    ctx.textAlign = "center";ctx.fillText(row.value + "%", x, base-h-13);
    ctx.fillStyle = "#576d60";ctx.font = "18px Arial";ctx.fillText(row.year, x, 456);
  });
  ctx.textAlign = "left";ctx.fillStyle = "#6b7e75";ctx.font = "14px Arial";
  ctx.fillText("User-entered values • not an authenticated source", 62, 494);
  return canvas.toDataURL("image/png");
}
let bindingText = "";

function bindFields() {
  const one = $("bindOp").value === "lookup";
  $("startWrap").hidden = one;
  $("bindFrom").required = !one;
  $("directionWrap").hidden = one;
}

function openBinding(text) {
  bindingText = text;
  const match = state.results.find(r => r.claim === text)?.check || {},
    old = state.links?.[text] || match;
  const ys = state.before.rows.map(r => r.year).sort();
  $("bindClaim").textContent = text;
  $("bindMetric").value = state.before.metric;
  $("bindOp").value = ["lookup", "points", "relative"].includes(old.operation) ? old.operation : "points";
  $("bindFrom").value = old.years?.[0] || ys.at(-2) || "";
  $("bindTo").value = old.years?.at(-1) || ys.at(-1) || "";
  $("bindDir").value = String(old.direction || 1);
  $("bindComp").value = old.compare || ">=";
  $("bindTarget").value = old.target || "";
  $("bindConfirm").checked = false;
  $("bindMsg").textContent = "";
  bindFields();
  $("binding").showModal();
}
$("bindOp").onchange = bindFields;
$("closeBind").onclick = () => $("binding").close();
$("autoBind").onclick = () => {
  delete state.links?.[bindingText];
  $("binding").close();
  runChecks();
};
$("bindForm").onsubmit = e => {
  e.preventDefault();
  if (!$("bindConfirm").checked) return;
  const op = $("bindOp").value,
    from = $("bindFrom").value,
    to = $("bindTo").value;
  if (op !== "lookup" && from === to) {
    $("bindMsg").textContent = "Choose two different years.";
    return;
  }
  const link = {
    operation: op,
    metric: $("bindMetric").value,
    years: op === "lookup" ? [to] : [from, to],
    direction: Number($("bindDir").value),
    compare: $("bindComp").value,
    target: $("bindTarget").value
  };
  state.links = {
    ...(state.links || {}),
    [bindingText]: link
  };
  state.history.push({
    at: new Date().toISOString(),
    claim: bindingText,
    calculation: link
  });
  $("binding").close();
  runChecks();
};
async function benchmark() {
  try {
    const m = await api("/api/evaluation");
    const area = $("benchBody");
    area.replaceChildren();
    const grid = el("div", undefined, "scores");
    const parts = [
      ["Outdated claims caught", m.stale_detected + " / " + m.stale_total],
      ["Unnecessary redesign alerts", m.cosmetic_alerts + " / " + m.cosmetic_total],
      ["Missing evidence recognized", m.missing_recognized + " / " + m.missing_total]
    ];
    for (const [label, val] of parts) {
      const b = el("div", undefined, "scoreBox");
      b.append(el("small", label), el("strong", val));
      grid.append(b);
    }
    area.append(grid);
    const box = el("div", undefined, "benchTable");
    box.append(el("h2", "Evaluation conditions"), el("p", m.design), el("p",
        "OCR year/value pairs recovered exactly: " + m.ocr_pairs_correct + " / " + m.ocr_pairs_total +
        ". Correct revision verdicts: " + m.verdict_correct + " / " + m.verdict_total + "."),
      el("p", "Persistent-original baseline: " + m.persistence_correct + " / " + m.verdict_total +
        " correct revision verdicts. The benchmark records live Foundry results separately when configured."
        ), btn("Download full results", () => download("chartproof-benchmark.json", m)));
    area.append(box);
  } catch (e) {
    note(e.message);
  }
}
$("workspaceTab").onclick = () => tab(false);
$("benchmarkTab").onclick = () => tab(true);

function tab(b) {
  $("benchmark").hidden = !b;
  $("workspace").hidden = b;
  $("workspaceTab").classList.toggle("active", !b);
  $("benchmarkTab").classList.toggle("active", b);
  if (b) benchmark();
}
$("verifyMode").onclick = () => {state.mode = "verify";state.results = [];render();runChecks();};
$("compareMode").onclick = () => {state.mode = "compare";state.results = [];render();runChecks();};
$("startUpload").onclick = () => quickUpload("before");
$("openEntry").onclick = () => openDataEntry("before");
$("quickFile").onchange = async () => {
  const f = $("quickFile").files[0];
  $("quickFile").value = "";
  if (!f) return;
  openEdit(quickSide);
  await readUpload(f);
};
const dz = $("uploadZone");
dz.ondragover = event => {event.preventDefault();dz.classList.add("dragging");};
dz.ondragleave = () => dz.classList.remove("dragging");
dz.ondrop = async event => {
  event.preventDefault();dz.classList.remove("dragging");
  const f = event.dataTransfer?.files?.[0];
  if (f) {openEdit("before");await readUpload(f);}
};
$("closeEntry").onclick = () => $("dataEntry").close();
$("entryCsv").onchange = async () => {
  const f = $("entryCsv").files[0];
  if (!f) return;
  try {
    if (f.size > 100000) throw Error("Choose a CSV under 100 KB.");
    $("entryRows").value = await f.text();
    $("entryMessage").textContent = "CSV loaded. Check the values before continuing.";
  } catch (e) {$("entryMessage").textContent = e.message;}
};
$("entryForm").onsubmit = event => {
  event.preventDefault();
  try {
    const metric = $("entryMetric").value.trim();
    if (!/^[A-Za-z][A-Za-z0-9 &'/-]{0,79}$/.test(metric))
      throw Error("Use a short metric name like Placement rate.");
    const rows = parseDataRows($("entryRows").value);
    const figure = {metric, rows, image: dataChart(metric, rows),
      page: 1, pages: 1, unit: "%", reviewed: true, filename: "Entered percentage data",
      engine: "User-entered values", observed: {metric, rows}, sha256: null,
      warning: "Values supplied and confirmed by the user; source authenticity not verified."};
    saveFigure(enteringSide, figure);
    $("dataEntry").close();
  } catch (e) {$("entryMessage").textContent = e.message;}
};
$("claimForm").onsubmit = e => {
  e.preventDefault();
  const t = $("newClaim").value.trim();
  if (!t) return;
  if (state.claims.length >= 20 || state.claims.includes(t)) {
    note("Use a new sentence, up to 20 per audit.");
    return;
  }
  state.claims.push(t);
  $("newClaim").value = "";
  runChecks();
};
$("check").onclick = runChecks;
$("load").onclick = loadExample;
$("closeEdit").onclick = () => $("editor").close();
$("editForm").onsubmit = applyEdit;
$("extract").onclick = () => readUpload();
$("engine").onchange = cloudUI;
$("file").onchange = () => {
  $("apply").disabled = !!$("file").files.length;
  $("confirmed").checked = false;
};
$("editor").addEventListener("close", () => {
  $("apply").disabled = false;
});
$("export").onclick = () => {
  if (state) download("chartproof-audit.json", state);
};
$("restore").onclick = () => $("restoreFile").click();
$("restoreFile").onchange = async () => {
  try {
    const f = $("restoreFile").files[0];
    if (f.size > 8e6) throw Error("Choose a smaller audit.");
    const a = validate(JSON.parse(await f.text()));
    state = a;
    state.history = Array.isArray(a.history) ? a.history : [];
    render();
    await runChecks();
  } catch (e) {
    note(e.message);
  } finally {
    $("restoreFile").value = "";
  }
};
(async () => {
  try {
    health = await api("/healthz");
    $("health").textContent = health.local_ocr ? "Local OCR available" : "OCR unavailable";
    const option = $("engine").querySelector('[value="azure"]');
    option.disabled = !health.azure_extraction_configured;
    if (option.disabled) option.textContent = "Azure · setup required";
    let old;
    try {
      old = JSON.parse(localStorage.getItem(key));
    } catch {}
    if (old) {
      try {
        state = validate(old);
        render();
        await runChecks();
        return;
      } catch {}
    }
    state = emptyState();
    render();
    persist();
  } catch (e) {
    note("Could not start the workspace: " + e.message);
  }
})();
