// Combat view. Displays what Python returns and sends the player's choice back. No rules here.

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const TYPE_HINT = {
  quick: "Quick · parry favoured",
  heavy: "Heavy · dodge favoured",
  ranged: "Ranged · dodge favoured",
  sweep: "Sweeping · dodge favoured",
};

let selectedTarget = null;
let handlers = {};

export function setCombatHandlers(h) {
  handlers = h;
}

function enemyCard(e) {
  const pct = Math.max(0, (e.hp / e.hp_max) * 100);
  const intent = e.intent
    ? `<div class="intent ${e.intent.attack ? "attack" : "idle"}">
         <span class="intent-tell">${e.intent.attack ? "⚠ " : ""}${esc(e.name)} ${esc(e.intent.tell)}.</span>
         ${e.intent.attack ? `<span class="intent-type">${esc(e.intent.label)} · ${esc(TYPE_HINT[e.intent.type] || e.intent.type)} · ${e.intent.dmg[0]}–${e.intent.dmg[1]} dmg</span>` : ""}
       </div>`
    : e.alive && !e.passive ? `<div class="intent idle"><span class="intent-tell muted">Waiting…</span></div>` : "";
  return `<div class="enemy ${e.alive ? "" : "dead"} ${e.passive ? "passive" : ""}">
    <div class="enemy-head"><strong>${esc(e.name)}</strong><span class="hp-num">${e.hp}/${e.hp_max}</span></div>
    <div class="track enemy-hp"><i style="width:${pct}%"></i></div>
    <div class="tags">${e.tags.map((t) => `<span class="tag-chip ${/EXPOSED/.test(t) ? "hot" : ""}">${esc(t)}</span>`).join("")}</div>
    ${intent}
  </div>`;
}

export function renderCombat(view, { pending, busy }) {
  const c = view.combat;
  $("combat-title").textContent = c.title;
  $("combat-turn").textContent = c.turn ? `Turn ${c.turn}` : "Opening";
  $("combat-goal").textContent = c.goal;
  $("combat-status").textContent = c.status || "";
  $("combat-status").hidden = !c.status;
  $("enemies").innerHTML = c.enemies.map(enemyCard).join("");

  // Narration (loading state is drawn by main.js while waiting)
  if (!pending) {
    const n = c.narration;
    $("combat-narration").innerHTML = n
      ? n.text.split(/\n+/).map((p) => `<p>${esc(p)}</p>`).join("") + (n.foreshadow ? `<p class="foreshadow">${esc(n.foreshadow)}</p>` : "")
      : "";
    $("combat-narration-meta").innerHTML = n
      ? `Narrated by ${esc(n.model)} · ${(n.ms / 1000).toFixed(1)}s` +
        (n.fallback ? ` <span class="fallback-chip">Fallback narrator — primary unavailable</span>` : "")
      : "";
  }

  // Outcome
  const out = $("combat-outcome");
  const controls = $("combat-controls");
  if (c.outcome && !pending) {
    controls.hidden = true;
    out.hidden = false;
    out.className = `combat-outcome ${c.outcome}`;
    out.innerHTML = c.outcome === "victory"
      ? `<h3>Victory</h3><p>${esc(c.title)} is won.</p><button class="btn primary" id="btn-continue">Continue</button>`
      : `<h3>Defeated</h3><p>You have fallen. The story does not go on without you.</p>
         <div class="row"><button class="btn primary" id="btn-retry-cp">Retry from checkpoint</button>
         <button class="btn ghost" id="btn-restart">Start a new game</button></div>`;
    $("btn-continue")?.addEventListener("click", () => handlers.cont());
    $("btn-retry-cp")?.addEventListener("click", () => handlers.retry());
    $("btn-restart")?.addEventListener("click", () => handlers.newGame());
  } else {
    out.hidden = true;
    controls.hidden = !!c.outcome;
  }

  // Targets
  const enabled = c.targets.filter((t) => t.enabled);
  if (!enabled.find((t) => t.id === selectedTarget)) {
    // Prefer an exposed weak point, then the first enabled target.
    selectedTarget = (enabled.find((t) => /EXPOSED/.test(t.note)) || enabled[0] || {}).id || null;
  }
  $("targets").innerHTML = c.targets.map((t) => `
    <label class="target ${t.enabled ? "" : "locked"} ${/EXPOSED/.test(t.note) ? "hot" : ""}" title="${esc(t.note)}">
      <input type="radio" name="target" value="${esc(t.id)}" ${t.id === selectedTarget ? "checked" : ""} ${t.enabled ? "" : "disabled"}>
      <span><strong>${esc(t.label)}</strong>${t.note ? `<small>${esc(t.note)}</small>` : ""}</span>
    </label>`).join("");
  $("targets").querySelectorAll("input").forEach((i) => i.addEventListener("change", () => (selectedTarget = i.value)));

  // Actions
  const lock = pending || busy || !!c.outcome;
  const groups = {
    Attack: c.actions.filter((a) => a.target),
    Defend: c.actions.filter((a) => !a.target && !a.item),
    Satchel: c.actions.filter((a) => a.item),
  };
  $("combat-actions").innerHTML = Object.entries(groups).filter(([, list]) => list.length).map(([name, list]) => `
    <div class="action-group"><span class="group-label">${name}</span>
      ${list.map((a) => `<button class="btn act ${a.target ? "primary" : ""}" data-id="${esc(a.id)}"
          ${!a.enabled || lock ? "disabled" : ""} title="${esc(a.reason)}">
          ${esc(a.label)}
          <span class="cost">${a.stamina ? `${a.stamina} St` : a.item ? "turn" : "free"}${a.magicka ? ` · ${a.magicka} Mg` : ""}</span>
        </button>`).join("")}
    </div>`).join("");
  const reasons = [...new Set(c.actions.filter((a) => !a.enabled).map((a) => a.reason))];
  $("action-hint").textContent = reasons.join(" ");
  $("action-hint").hidden = !reasons.length;
  $("combat-actions").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    const a = c.actions.find((x) => x.id === b.dataset.id);
    handlers.act(a.id, a.target ? selectedTarget : null);
  }));

  // Log
  let lastTurn = -1;
  $("combat-log").innerHTML = c.log.map((l) => {
    const head = l.turn !== lastTurn ? `<li class="log-turn">${l.turn ? `Turn ${l.turn}` : "Start"}</li>` : "";
    lastTurn = l.turn;
    return head + `<li class="log-${esc(l.who)}">${esc(l.text)}</li>`;
  }).join("");
  const box = $("combat-log");
  box.scrollTop = box.scrollHeight;
}
