// Provisions panel: Arcanium, Armoury, Gear, Contracts. Python validates every purchase and swap.

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let tab = "arcanium";
let onOp = () => {};

function grouped(rows, render) {
  const groups = {};
  rows.forEach((r) => (groups[r.group] ||= []).push(r));
  return Object.entries(groups).map(([g, list]) =>
    `<h4>${esc(g)}</h4><div class="shop-grid">${list.map(render).join("")}</div>`).join("");
}

function buyRow(r) {
  return `<div class="shop-item ${r.can_buy ? "" : "dim"}">
    <div><strong>${esc(r.label)}</strong><small>${esc(r.desc)}${r.weight ? ` · ${r.weight} wt` : ""}</small></div>
    <button class="btn small ${r.can_buy ? "primary" : ""}" data-op="buy" data-id="${r.id}" ${r.can_buy ? "" : "disabled"}>
      ${r.reason && !r.can_buy ? esc(r.reason) : `${r.price} gold`}</button>
  </div>`;
}

function gearTab(s) {
  const eq = s.equipped.map((e) => `<div class="shop-item">
      <div><span class="slot">${esc(e.slot)}</span><strong>${esc(e.label || "—")}</strong></div>
      ${e.id && e.slot !== "weapon" ? `<button class="btn small" data-op="unequip" data-id="${e.slot}">Remove</button>` : ""}
    </div>`).join("");
  const en = s.enchants.length
    ? s.enchants.map((e) => `<div class="shop-item">
        <div><strong>${esc(e.label)}</strong><small>${e.magicka} Magicka per attack</small></div>
        ${e.active ? `<button class="btn small" data-op="unequip" data-id="enchant">Active · remove</button>`
                   : `<button class="btn small primary" data-op="equip" data-id="${e.id}">Activate</button>`}
      </div>`).join("")
    : `<p class="muted small">No enchantments known. Buy them at the Arcanium.</p>`;
  const bag = s.satchel.length
    ? s.satchel.map((i) => `<div class="shop-item">
        <div><strong>${esc(i.label)} ×${i.count}</strong><small>${i.kind} · ${i.weight} wt each</small></div>
        <div class="btns">
          ${i.can_equip ? `<button class="btn small primary" data-op="equip" data-id="${i.id}">Equip</button>` : ""}
          ${i.can_drink ? `<button class="btn small" data-op="drink" data-id="${i.id}">Drink</button>` : ""}
          <button class="btn small" data-op="sell" data-id="${i.id}">Sell ${i.sell}g</button>
        </div>
      </div>`).join("")
    : `<p class="muted small">Your satchel is empty.</p>`;
  return `<h4>Equipped · armour −${s.armour_pct}% damage</h4><div class="shop-grid">${eq}</div>
          <h4>Weapon enchantment</h4><div class="shop-grid">${en}</div>
          <h4>Satchel</h4><div class="shop-grid">${bag}</div>`;
}

function contractsTab(s) {
  return `<div class="shop-grid">${s.contracts.map((c) => `<div class="shop-item ${c.status === "open" ? "" : "dim"}">
      <div><strong>${esc(c.title)}</strong><small>${esc(c.desc)} — from ${esc(c.giver)}. Reward: ${esc(c.reward)} + loot.</small></div>
      ${c.status === "open" ? `<button class="btn small primary" data-op="contract" data-id="${c.id}">⚔ Take on</button>`
        : `<span class="muted small">${c.status === "done" ? "Completed" : "Not yet available"}</span>`}
    </div>`).join("")}</div>
    <p class="muted small">Optional side fights for gold. The story never requires them.</p>`;
}

export function renderShop(s, notice, handler) {
  onOp = handler;
  const box = $("provisions");
  box.hidden = !s;
  if (!s) return;
  const tabs = [["arcanium", "Arcanium"], ["armoury", "Armoury"], ["gear", "Gear & Satchel"], ["contracts", "Contracts"]];
  const body = tab === "arcanium" ? grouped(s.arcanium, buyRow)
    : tab === "armoury" ? grouped(s.armoury, buyRow)
    : tab === "gear" ? gearTab(s) : contractsTab(s);
  box.innerHTML = `
    <div class="prov-head">
      <div class="prov-tabs">${tabs.map(([id, l]) => `<button class="${id === tab ? "on" : ""}" data-tab="${id}">${l}</button>`).join("")}</div>
      <div class="prov-purse">${s.gold} gold · ${s.weight}/${s.weight_max} wt</div>
    </div>
    ${notice ? `<p class="prov-notice">✦ ${esc(notice)}</p>` : ""}
    <p id="prov-error" class="error" hidden></p>
    <div class="prov-body">${body}</div>`;
  box.querySelectorAll("[data-tab]").forEach((b) => b.addEventListener("click", () => { tab = b.dataset.tab; renderShop(s, notice, handler); }));
  box.querySelectorAll("[data-op]").forEach((b) => b.addEventListener("click", () => onOp(b.dataset.op, b.dataset.id)));
}

export function showShopError(msg) {
  const el = $("prov-error");
  if (el) { el.textContent = msg; el.hidden = false; }
}
