import { api } from "./api.js";
import { applySceneArt, setMusic } from "./assets.js";
import { renderCreate } from "./create.js";
import { renderCombat, setCombatHandlers } from "./combat.js";
import { renderShop, showShopError } from "./shop.js";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let current = null;
let busy = false;

// ---------- Model status ----------
const STATUS_TEXT = {
  checking: "Checking narrator…",
  online: "Gemini ready (online)",
  missing_key: "Gemini key missing",
  loaded: "Local Qwen ready",
  idle: "Local Qwen ready",
  narrating: "Narrating…",
  fallback: "Fallback narrator active",
  unreachable: "Narrator unreachable",
  missing: "Narrator model missing",
  setup: "Server setup incomplete",
  error: "Narrator error",
};

function setModelStatus(state, detail = "") {
  const el = $("model-status");
  el.dataset.state = state;
  el.querySelector(".label").textContent = STATUS_TEXT[state] || state;
  el.title = detail;
}

async function pollStatus() {
  if (busy) return;
  try {
    const s = await api.status();
    const fb = s.fallback || {};
    setModelStatus(s.state, s.ok ? `${s.model} via ${s.runtime} at ${s.url}` : s.error);
    const chain = (s.chain || []).map((c) => c.label).join(" → ");
    $("dm-info").textContent = s.runtime === "gemini"
      ? (s.ok ? `Narration: ${chain || "Google Gemini"}. Rules, rolls and state are decided by the game engine.` : s.error)
      : s.ok
      ? `Narration: ${s.model} via local ${s.runtime}. ${fb.configured ? `Gemini (${fb.model}) is standing by as an online fallback.` : "No online fallback configured."} Rules, rolls and state are decided by the game engine.`
      : s.state === "fallback"
        ? `Local Qwen is unavailable. Narration is coming from Google Gemini (${fb.model}) over the internet as a fallback. Rules, rolls and state are still decided by the game engine.`
        : `${s.error} ${fb.configured ? "" : "No Gemini fallback is configured."}`;
  } catch (e) {
    setModelStatus("error", e.message);
  }
}

// ---------- Character creation ----------
function showCreate(options) {
  $("view-game").hidden = true;
  $("view-create").hidden = false;
  $("btn-new").hidden = true;
  renderCreate(options, async (fields) => render(await api.newGame(fields)));
}

// ---------- Dashboard ----------
function bar(name, val, max) {
  $(`bar-${name}`).style.width = `${Math.max(0, Math.min(100, (val / max) * 100))}%`;
  $(`val-${name}`).textContent = `${val}/${max}`;
}

export const PROVIDER_LABEL = { gemini: "Google Gemini", qwen_cloud: "Qwen (hosted)", qwen_local: "Qwen (local)", qwen: "Qwen (local)" };

export function narrMeta(n) {
  const fb = n.fallback ? ` <span class="fallback-chip">Fallback: ${esc(PROVIDER_LABEL[n.provider] || n.provider)} — primary narrator unavailable</span>` : "";
  return `Narrated by ${esc(n.model)} · ${(n.ms / 1000).toFixed(1)}s${n.tokens ? ` · ${n.tokens} tokens` : ""}${fb}`;
}

function renderParagraphs(text) {
  return text
    .replace(/\*\*?([^*]+)\*\*?/g, "$1")
    .split(/\n\s*\n|\n/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((p) => `<p>${esc(p)}</p>`)
    .join("");
}

function render(view) {
  current = view;
  if (!view.has_save) return showCreate(view.options);

  $("view-create").hidden = true;
  $("view-game").hidden = false;
  $("btn-new").hidden = false;

  const c = view.character, s = view.stats;
  $("char-name").textContent = c.name;
  $("char-meta").textContent = `${c.pronouns} · ${c.ancestry_label} · ${c.origin_label}`;
  $("char-appearance").textContent = c.appearance;
  $("portrait-initial").textContent = c.name.trim().charAt(0).toUpperCase();
  bar("health", s.health, s.health_max);
  bar("stamina", s.stamina, s.stamina_max);
  bar("magicka", s.magicka, s.magicka_max);
  $("val-gold").textContent = s.gold;
  $("val-weight").textContent = `${s.weight} / ${s.weight_max}`;
  const eq = s.equipment;
  $("equipment").innerHTML = [["Weapon", eq.weapon], ["Enchantment", eq.enchant ? eq.enchant.charAt(0).toUpperCase() + eq.enchant.slice(1) : null], ["Helmet", eq.helmet], ["Cuirass", eq.cuirass], ["Boots", eq.boots]]
    .map(([k, v]) => `<dt>${k}</dt><dd class="${v ? "" : "muted"}">${esc(v || "None")}</dd>`).join("");
  $("inventory").innerHTML = view.inventory.map((i) => `<li><span>${esc(i.label)}</span><b>×${i.count}</b></li>`).join("")
    || `<li class="muted">Empty</li>`;
  $("journal").innerHTML = view.journal.map((j) => `<li>${esc(j.title)}</li>`).join("") || `<li class="muted">Nothing yet.</li>`;

  const inCombat = !!view.combat;
  $("combat-view").hidden = !inCombat;
  document.querySelector(".panel.scene").hidden = inCombat;
  setMusic(inCombat ? "combat" : view.scene.music);

  if (inCombat) {
    $("combat-error").hidden = true;
    renderCombat(view, { pending: view.narration_pending, busy });
  } else {
    $("scene-title").textContent = view.scene.title;
    $("scene-title-art").textContent = view.scene.title;
    $("scene-objective").textContent = view.scene.objective;
    applySceneArt($("scene-art"), view.scene.art);
    const fx = view.scene_effects || [];
    $("scene-effects").hidden = !fx.length;
    $("scene-effects").innerHTML = fx.map((f) => `<span>✦ ${esc(f)}</span>`).join("");
    const narr = view.narration;
    $("narration").innerHTML = narr ? renderParagraphs(narr.text) : "";
    $("narration-meta").innerHTML = narr ? narrMeta(narr) : "";
    $("scene-error").hidden = true;
    renderActions(view);
    renderShop(view.shop, view.notice, shopOp);
  }
  if (view.narration_pending) narrate();
}

function renderActions(view) {
  const box = $("actions");
  if (view.scene.final && !view.narration_pending) {
    box.innerHTML = `<div class="notice"><strong>${view.scene.ending ? "The End — thank you for playing." : "End of the current build."}</strong> ${view.scene.ending ? "Your choice echoes beneath Suryagarh. Start a new game to choose differently." : ""}</div>`;
    return;
  }
  box.innerHTML = view.actions.map((a) => `<button class="btn primary" data-action="${a.id}">${a.combat ? "⚔ " : ""}${esc(a.label)}</button>`).join("");
  box.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => doAction(b.dataset.action)));
}

// Generic request wrapper: locks input, renders the result, reports errors in the right panel.
async function send(fn) {
  if (busy) return;
  busy = true;
  if (current?.combat) $("combat-actions").querySelectorAll("button").forEach((b) => (b.disabled = true));
  else $("actions").querySelectorAll("button").forEach((b) => (b.disabled = true));
  try {
    const view = await fn();
    busy = false;
    render(view);
  } catch (e) {
    busy = false;
    if (current) render(current);
    showError(e.message, false);
  }
}

const doAction = (id) => send(() => api.action(id));

async function shopOp(op, id) {
  if (busy) return;
  busy = true;
  try {
    const view = await api.shop(op, id);
    busy = false;
    render(view);
  } catch (e) {
    busy = false;
    showShopError(e.message);
  }
}

setCombatHandlers({
  act: (action, target) => send(() => api.combat(action, target)),
  cont: () => send(() => api.action("continue")),
  retry: () => send(() => api.retry()),
  newGame: () => $("btn-new").click(),
});

async function narrate() {
  if (busy) return;
  busy = true;
  setModelStatus("narrating");
  const inCombat = !!current?.combat;
  const box = inCombat ? $("combat-narration") : $("narration");
  const started = Date.now();
  box.innerHTML = `<div class="loading"><span class="spinner"></span><span>The Fates are weaving…</span><small id="loading-time"></small></div>`;
  if (inCombat) $("combat-narration-meta").textContent = "";
  const tick = setInterval(() => {
    const t = $("loading-time");
    if (t) t.textContent = `${Math.round((Date.now() - started) / 1000)}s`;
  }, 1000);
  if (!inCombat) $("actions").innerHTML = "";
  try {
    const view = await api.narrate();
    clearInterval(tick);
    busy = false;
    pollStatus();
    render(view);
  } catch (e) {
    clearInterval(tick);
    busy = false;
    setModelStatus(e.model_error ? "error" : "unreachable", e.message);
    box.innerHTML = "";
    showError(e.message, true);
  }
}

function showError(msg, retry) {
  const el = current?.combat ? $("combat-error") : $("scene-error");
  el.innerHTML = `<strong>${retry ? "Narration failed." : "Action failed."}</strong> ${esc(msg)}` +
    (retry ? ` <button class="btn small" id="btn-retry">Retry</button>` : "");
  el.hidden = false;
  if (retry) $("btn-retry").addEventListener("click", () => { el.hidden = true; narrate(); });
}

$("btn-new").addEventListener("click", async () => {
  if (busy) return;
  if (!confirm("Start a new game? Your current save will be erased.")) return;
  render(await api.reset());
});

// ---------- Boot ----------
(async function boot() {
  pollStatus();
  setInterval(pollStatus, 10000);
  try {
    render(await api.state());
  } catch (e) {
    document.body.insertAdjacentHTML("beforeend", `<p class="error fatal">${esc(e.message)}</p>`);
  }
})();
