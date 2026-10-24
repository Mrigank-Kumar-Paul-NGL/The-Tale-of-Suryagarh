// Character creation wizard: Identity → Complexion → Eyes → Hair → Height → Review.
// Option lists and ancestry limits come from the server, which re-validates on submit.

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let opts, steps, groups, ancestryLabel, step = 0, reached = 0, onCreate;

const form = () => $("create-form");
const ancestry = () => form().elements.ancestry?.value;
const allowed = (o, a) => (!o.only.length || o.only.includes(a)) && !o.not.includes(a);

function optionNote(o) {
  if (o.not.length) return ` <i>(unavailable for ${o.not.map((a) => ancestryLabel[a]).join(", ")})</i>`;
  return "";
}

function radio(group, o) {
  return `<label class="radio" data-opt="${o.id}">
    <input type="radio" name="look_${group.id}" value="${o.id}">
    <span>${esc(o.label)}${optionNote(o)}</span></label>`;
}

function renderGroup(g) {
  const base = g.options.filter((o) => !o.only.length);
  const extra = {};
  g.options.filter((o) => o.only.length).forEach((o) => {
    const key = o.only.map((a) => ancestryLabel[a]).join(" & ");
    (extra[key] ||= []).push(o);
  });
  return `<div class="look-group">
    <h3>${esc(g.label)}</h3>
    <div class="radio-grid">${base.map((o) => radio(g, o)).join("")}</div>
    ${Object.entries(extra).map(([who, list]) => `
      <p class="unlock">Available to ${esc(who)} ancestry</p>
      <div class="radio-grid">${list.map((o) => radio(g, o)).join("")}</div>`).join("")}
  </div>`;
}

// Disable options the current ancestry can't use; move any invalid selection to a valid one.
function refreshLimits() {
  const a = ancestry();
  for (const g of groups) {
    const inputs = [...form().querySelectorAll(`input[name="look_${g.id}"]`)];
    inputs.forEach((inp) => {
      const ok = allowed(g.options.find((o) => o.id === inp.value), a);
      inp.disabled = !ok;
      inp.closest(".radio").classList.toggle("locked", !ok);
    });
    const checked = inputs.find((i) => i.checked);
    if (!checked || checked.disabled) {
      const pick = inputs.find((i) => i.value === g.default && !i.disabled) || inputs.find((i) => !i.disabled);
      if (pick) pick.checked = true;
    }
  }
}

function renderTabs() {
  $("create-steps").innerHTML = steps.map((s, i) =>
    `<button type="button" data-i="${i}" ${i > reached ? "disabled" : ""} ${i === step ? 'aria-current="step"' : ""}>${esc(s.label)}</button>`
  ).join('<span aria-hidden="true">•</span>');
  $("create-steps").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => go(+b.dataset.i)));
}

function go(i) {
  step = i;
  reached = Math.max(reached, i);
  form().querySelectorAll(".step").forEach((el) => (el.hidden = el.dataset.step !== steps[i].id));
  $("create-title").textContent = steps[i].title;
  $("step-next").textContent = steps[i].confirm;
  $("step-back").hidden = i === 0;
  $("create-error").hidden = true;
  if (steps[i].id === "details") renderReview();
  renderTabs();
  form().scrollIntoView({ block: "start", behavior: "smooth" });
}

function label(list, id) {
  return list.find((x) => x.id === id)?.label || id;
}

function renderReview() {
  const f = form().elements;
  const rows = [
    ["Name", f.name.value], ["Pronouns", f.pronouns.value],
    ["Ancestry", ancestryLabel[ancestry()]], ["Origin", label(opts.origins, f.origin.value)],
    ...groups.map((g) => [g.label, label(g.options, f[`look_${g.id}`].value)]),
  ];
  $("appearance-preview").innerHTML = `<dl class="kv review">${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>`;
}

function showError(msg) {
  $("create-error").textContent = msg;
  $("create-error").hidden = false;
}

async function submit(ev) {
  ev.preventDefault();
  const f = form().elements;
  if (steps[step].id === "identity") {
    if (!f.name.value.trim()) return showError("Give your character a name.");
    if (!f.pronouns.value.trim()) return showError("Enter pronouns.");
  }
  if (step < steps.length - 1) return go(step + 1);

  const payload = {
    name: f.name.value, pronouns: f.pronouns.value, ancestry: ancestry(), origin: f.origin.value,
    details: f.details.value,
    looks: Object.fromEntries(groups.map((g) => [g.id, f[`look_${g.id}`].value])),
  };
  const btn = $("step-next");
  btn.disabled = true;
  try {
    await onCreate(payload);
  } catch (e) {
    showError(e.message);
  } finally {
    btn.disabled = false;
  }
}

let wired = false;

export function renderCreate(options, createFn) {
  opts = options;
  onCreate = createFn;
  ancestryLabel = Object.fromEntries(opts.ancestries.map((a) => [a.id, a.label]));
  groups = opts.appearance.flatMap((s) => s.groups);
  steps = [
    { id: "identity", label: "Identity", title: "Who walks into the dark?", confirm: "Confirm identity" },
    ...opts.appearance.map((s) => ({ id: s.id, label: s.label, title: "Appearance", confirm: `Confirm ${s.label.toLowerCase()}` })),
    { id: "details", label: "Review", title: "Before the gates", confirm: "Enter Suryagarh" },
  ];

  $("ancestry-options").innerHTML = opts.ancestries.map((a, i) => `
    <label class="choice"><input type="radio" name="ancestry" value="${a.id}" ${i === 0 ? "checked" : ""}>
      <span><strong>${esc(a.label)}</strong><small>${esc(a.flavor)}</small></span></label>`).join("");
  $("origin-options").innerHTML = opts.origins.map((o, i) => `
    <label class="choice"><input type="radio" name="origin" value="${o.id}" ${i === 0 ? "checked" : ""}>
      <span><strong>${esc(o.label)}</strong><small>${esc(o.summary)}</small>
      <em class="tag">${o.returning ? "Returning" : "First arrival"}</em></span></label>`).join("");
  $("appearance-steps").innerHTML = opts.appearance.map((s) =>
    `<section class="step" data-step="${s.id}">${s.groups.map(renderGroup).join("")}</section>`).join("");

  form().reset();
  refreshLimits();
  step = 0;
  reached = 0;
  go(0);

  if (!wired) {
    wired = true;
    form().addEventListener("submit", submit);
    $("step-back").addEventListener("click", () => step > 0 && go(step - 1));
    $("ancestry-options").addEventListener("change", refreshLimits);
  }
}
