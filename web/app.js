"use strict";
const $ = id => document.getElementById(id);
const sampleClaim = "The placement rate rose by at least 10 percentage points from 2024 to 2025.";
const key = "chartproof.audit.v1";
let state, editing, draft, cloudToken = "",
  health = {},
  requestNumber = 0;
const chartNames = {
  before: "Original figure",
  after: "Revised figure"
};

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
  if (a?.schema !== 1 || !usable(a.before) || !usable(a.after) || !Array.isArray(a.claims) || a.claims
    .length > 20 || a.claims.some(s => typeof s !== "string" || s.length > 360)) throw Error(
    "Choose a valid ChartProof version 1 audit.");
  return {
    ...a,
    results: []
  };
}

function sourceCard(side) {
  const c = state[side],
    box = el("article", undefined, "card"),
    head = el("div", undefined, "cardHead"),
    title = el("div");
  title.append(el("h3", chartNames[side]), el("small", (c.filename || "Uploaded chart") + " · page " + c
    .page));
  head.append(title, btn("Review / replace", () => openEdit(side)));
  const im = el("img");
  im.src = c.image;
  im.alt = c.metric + " chart, " + c.rows.map(r => r.year + " " + r.value + "%").join(", ");
  const meta = el("div", undefined, "chartMeta");
  meta.append(el("span", c.engine + " · " + (c.reviewed ? "Reviewed" : "Review required")), el("span", c.rows
    .map(r => r.year + "  " + r.value + "%").join("   /   ")));
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
  rh.append(el("span", result?.transition || "Awaiting check", "badge " + (result?.transition ===
    "Outdated claim" ? "alert" : result?.after?.status === "Insufficient evidence" ? "unknown" : "")));
  box.append(rh);
  if (result) {
    const details = el("details");
    if (i === 0) details.open = true;
    details.append(el("summary", "Inspect evidence"));
    const grid = el("div", undefined, "proof");
    grid.append(proofSide("Original", result.before), proofSide("Revision", result.after));
    details.append(grid);
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
  $("charts").replaceChildren(sourceCard("before"), sourceCard("after"));
  $("claimList").replaceChildren(...state.claims.map(resultRow));
  $("check").disabled = !state.claims.length || !state.before.reviewed || !state.after.reviewed;
}
async function runChecks() {
  if (!state) return;
  const id = ++requestNumber;
  if (!state.claims.length || !state.before.reviewed || !state.after.reviewed) {
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
      metric: c.metric,
      unit: c.unit,
      rows: c.rows.map(r => ({
        year: r.year,
        value: r.value
      }))
    });
    const r = await api("/api/check", {
      before: brief(state.before),
      after: brief(state.after),
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
  $("sourcePreview").src = c.image;
  $("metric").value = c.metric;
  $("values").value = c.rows.map(r => r.year + ", " + r.value).join("\n");
  $("confirmed").checked = false;
  $("editMessage").textContent = c.warning || "Check the source before saving.";
}

function openEdit(side) {
  editing = side;
  draft = structuredClone(state[side]);
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
async function readUpload() {
  const f = $("file").files[0];
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
    const old = state[editing];
    state.history.push({
      side: editing,
      at: new Date().toISOString(),
      oldSource: old.sha256,
      newSource: draft.sha256,
      previous: {
        metric: old.metric,
        rows: old.rows
      },
      reviewed: {
        metric,
        rows
      }
    });
    state[editing] = {
      ...draft,
      metric,
      rows,
      reviewed: true
    };
    state.results = [];
    state.visionComparisons = {};
    $("editor").close();
    render();
    runChecks();
  } catch (err) {
    $("editMessage").textContent = err.message;
  }
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
$("extract").onclick = readUpload;
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
    await loadExample();
  } catch (e) {
    note("Could not start the workspace: " + e.message);
  }
})();
