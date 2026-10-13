"use strict";

const $ = (id) => document.getElementById(id);
let runtime = null;
let allocations = [];
let activeConfiguration = null;
let busy = false;

function setStatus(message, kind = "neutral") {
  $("status").textContent = message;
  $("status").dataset.kind = kind;
}

function parseFactors(raw) {
  const result = {};
  for (const entry of raw.split(",").map((v) => v.trim()).filter(Boolean)) {
    const eq = entry.indexOf("=");
    if (eq <= 0 || eq === entry.length - 1) {
      throw new Error("Covariates must be comma-separated NAME=VALUE pairs.");
    }
    const name = entry.slice(0, eq).trim();
    const value = entry.slice(eq + 1).trim();
    if (!name || !value || Object.hasOwn(result, name)) {
      throw new Error("Covariate names and values must be nonempty and names must be unique.");
    }
    result[name] = value;
  }
  return result;
}

function readConfiguration() {
  const arms = $("arms").value.split(",").map((v) => v.trim()).filter(Boolean);
  const ratio = $("ratio").value.split(",").map((v) => Number(v.trim()));
  const method = $("method").value;
  const sizes = method === "minimize" ? [] : $("sizes").value.split(",").map((v) => Number(v.trim()));
  const probability = method === "minimize" ? Number($("probability").value) : 0.8;
  if (arms.length < 2 || new Set(arms).size !== arms.length) {
    throw new Error("Enter at least two distinct treatment arms.");
  }
  if (ratio.length !== arms.length || ratio.some((n) => !Number.isInteger(n) || n <= 0)) {
    throw new Error("Enter one positive integer ratio per arm.");
  }
  if (sizes.some((n) => !Number.isInteger(n) || n <= 0 || n % ratio.reduce((a, b) => a + b, 0) !== 0)) {
    throw new Error("Every block size must be a positive multiple of the ratio total.");
  }
  if (!Number.isFinite(probability) || probability <= 0 || probability > 1) {
    throw new Error("Minimization probability must be between 0 (exclusive) and 1.");
  }
  return { method, arms, ratio, sizes, probability };
}

const bridge = `
import json
from trial_randomizer.block import BlockRandomizer
from trial_randomizer.minimization import MinimizationRandomizer
from trial_randomizer.stratified import StratifiedBlockRandomizer
_engine = None
_configuration = None

def allocate_from_json(raw):
    global _engine, _configuration
    data = json.loads(raw)
    configuration = (data["method"], tuple(data["arms"]), tuple(data["ratio"]),
                     tuple(data["sizes"]), data["probability"])
    if _engine is None or configuration != _configuration:
        if data["method"] == "block":
            _engine = BlockRandomizer(data["arms"], data["ratio"], data["sizes"])
        elif data["method"] == "stratified":
            _engine = StratifiedBlockRandomizer(data["arms"], data["ratio"], data["sizes"])
        elif data["method"] == "minimize":
            _engine = MinimizationRandomizer(data["arms"], data["ratio"], p_biased_coin=data["probability"])
        else:
            raise ValueError("Unknown allocation method")
        _configuration = configuration
    if data["method"] == "block":
        arm, bid, bsize = _engine.next()
        result = {"arm": arm, "block_id": bid, "block_size": bsize}
    elif data["method"] == "stratified":
        arm, bid, bsize, _ = _engine.assign(data["factors"])
        result = {"arm": arm, "block_id": bid, "block_size": bsize}
    else:
        arm, reason, scores = _engine.assign(data["factors"])
        result = {"arm": arm, "reason": reason, "scores": scores}
    return json.dumps(result)
`;

async function initialize() {
  $("assign").disabled = true;
  setStatus("Loading Python runtime and allocation modules…");
  try {
    runtime = await window.loadPyodide();
    runtime.FS.mkdirTree("/home/pyodide/trial_randomizer");
    for (const file of ["__init__.py", "block.py", "minimization.py", "stratified.py"]) {
      const response = await fetch("./trial_randomizer/" + file);
      if (!response.ok) throw new Error("Python module " + file + " returned HTTP " + response.status);
      runtime.FS.writeFile("/home/pyodide/trial_randomizer/" + file, await response.text());
    }
    await runtime.runPythonAsync(bridge);
    setStatus("Python runtime ready. Local demonstration only.", "ready");
    $("assign").disabled = false;
  } catch (error) {
    setStatus("Runtime unavailable: " + error.message + ". Internet access is required on first load.", "error");
  }
}

function resetSession(message = "Session cleared. No data was stored.") {
  allocations = [];
  activeConfiguration = null;
  if (runtime) runtime.runPython("_engine = None; _configuration = None");
  $("results").replaceChildren();
  $("count").textContent = "0";
  $("export").disabled = true;
  setStatus(message, "ready");
}

function renderRow(entry) {
  const row = document.createElement("tr");
  const cells = [
    entry.seq, entry.method, entry.arm,
    entry.block_id ?? "—", entry.block_size ?? "—",
    entry.reason ?? "—", entry.stratum
  ];
  for (const value of cells) {
    const td = document.createElement("td");
    td.textContent = String(value);
    row.appendChild(td);
  }
  $("results").appendChild(row);
}

async function assign() {
  if (!runtime || busy) return;
  busy = true;
  $("assign").disabled = true;
  try {
    const config = readConfiguration();
    const factors = config.method === "block" ? {} : parseFactors($("factors").value);
    const signature = JSON.stringify(config);
    if (activeConfiguration && signature !== activeConfiguration) {
      throw new Error("Configuration changed. Clear the session before allocating again.");
    }
    const payload = { ...config, factors };
    runtime.globals.set("allocation_payload", JSON.stringify(payload));
    const resultJson = await runtime.runPythonAsync("allocate_from_json(allocation_payload)");
    const result = JSON.parse(resultJson);
    const entry = {
      seq: allocations.length + 1, method: config.method,
      stratum: Object.entries(factors).map(([k, v]) => k + "=" + v).join("; "),
      ...result
    };
    activeConfiguration = signature;
    allocations.push(entry);
    renderRow(entry);
    $("count").textContent = String(allocations.length);
    $("export").disabled = false;
    setStatus("Allocation generated locally. This is not an authenticated trial allocation.", "ready");
  } catch (error) {
    setStatus("Allocation not performed: " + error.message, "error");
  } finally {
    busy = false;
    $("assign").disabled = !runtime;
  }
}

function csvCell(value) {
  let text = String(value ?? "");
  if (/^\s*[=+@-]/.test(text)) text = "'" + text;
  return '"' + text.replaceAll('"', '""') + '"';
}

function exportCsv() {
  if (!allocations.length) return;
  const cols = ["seq", "method", "arm", "block_id", "block_size", "reason", "stratum"];
  const content = [cols.join(","), ...allocations.map((row) => cols.map((col) => csvCell(row[col])).join(","))].join("\r\n") + "\r\n";
  const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "trial-randomizer-demo.csv";
  a.click();
  URL.revokeObjectURL(url);
}

function updateMethod() {
  const method = $("method").value;
  $("factor-wrap").hidden = method === "block";
  $("prob-wrap").hidden = method !== "minimize";
  $("sizes-wrap").hidden = method === "minimize";
  $("method-note").textContent = method === "block"
    ? "Allocates sequentially from shuffled, ratio-balanced blocks."
    : method === "stratified"
      ? "Each distinct covariate combination has an independent block sequence."
      : "Balances marginal covariate counts using ratio-normalized Pocock–Simon scoring.";
}

$("assign").addEventListener("click", assign);
$("reset").addEventListener("click", () => resetSession());
$("export").addEventListener("click", exportCsv);
$("method").addEventListener("change", updateMethod);
updateMethod();
initialize();
