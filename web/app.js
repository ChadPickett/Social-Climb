"use strict";

const $ = (id) => document.getElementById(id);
const tokenKey = "socialClimbToken";

function getToken() {
  try { return localStorage.getItem(tokenKey) || ""; } catch { return ""; }
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", "X-App-Token": getToken(), ...(options.headers || {}) },
  });
  if (res.status === 401) {
    throw new Error("This device isn't connected yet. On your computer, open Social Climb and scan its QR code with this phone.");
  }
  if (!res.ok) {
    const text = await res.text();
    let detail = text;
    try { detail = JSON.parse(text).detail ?? text; } catch { /* not JSON */ }
    throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  return res.json();
}

// Builds DOM with textContent only: scraped captions are untrusted.
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else if (k === "href") { if (/^https?:\/\//.test(v)) node.href = v; }
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

const fmt = (n) => (n == null ? "–" : Intl.NumberFormat(undefined, { notation: "compact" }).format(n));
const hourLabel = (h) => new Date(2000, 0, 1, h).toLocaleTimeString([], { hour: "numeric" });

function stat(label, value, sub) {
  return el("div", { class: "stat" }, el("div", { class: "k" }, label), el("div", { class: "v" }, value),
    sub ? el("div", { class: "s" }, sub) : null);
}

function renderReport(r) {
  const s = r.stats;
  const d = r.draft;
  const t = s.timing;
  const tags = d.hashtags.map((h) => "#" + h).join(" ");
  const fullCaption = `${d.caption}\n\n${tags}`;
  const primary = s.windows[String(s.primary_window_days)];

  const goalRow = (name, g) => g ? stat(name, fmt(g.target), `stretch ${fmt(g.stretch)} · typical ${fmt(g.baseline)}`) : null;

  const windowTable = el("table", {},
    el("tr", {}, ["Window", "Posts", "Median likes", "Median comments", "Median views", "Top format"].map((h) => el("th", {}, h))),
    Object.entries(s.windows).map(([days, w]) => el("tr", {},
      el("td", {}, `${days} days`), el("td", {}, w.post_count),
      el("td", {}, fmt(w.likes?.median)), el("td", {}, fmt(w.comments?.median)),
      el("td", {}, fmt(w.views?.median)), el("td", {}, w.by_format?.[0]?.format ?? "–"))));

  const momentum = s.momentum_7d_vs_60d;
  const momentumText = momentum == null ? null
    : momentum >= 1.1 ? `Topic is heating up: last 7 days are performing ${Math.round((momentum - 1) * 100)}% above the 60-day norm.`
    : momentum <= 0.9 ? `Topic is cooling: last 7 days are ${Math.round((1 - momentum) * 100)}% below the 60-day norm.`
    : "Topic performance is steady versus the 60-day norm.";

  const copyBtn = el("button", { class: "small", type: "button", onclick: async (e) => {
    try { await navigator.clipboard.writeText(fullCaption); e.target.textContent = "Copied!"; }
    catch { e.target.textContent = "Copy failed"; }
  } }, "Copy caption");

  const root = $("report");
  root.replaceChildren(...[
    el("section", { class: "card" },
      el("h2", {}, `Your draft: ${r.topic}`),
      el("p", { class: "muted" }, `Format: ${d.format}  ·  source: ${r.data_source}  ·  ${new Date(r.generated_at).toLocaleString()}`),
      el("h3", {}, "Hook"), el("p", {}, d.hook),
      el("h3", {}, "Caption"), el("pre", { class: "caption" }, fullCaption),
      el("div", { class: "row end" }, copyBtn),
      el("h3", {}, "Content outline"), el("ol", {}, (d.content_outline || []).map((x) => el("li", {}, x))),
      el("h3", {}, "Visual direction"), el("p", {}, d.visual_direction),
      el("h3", {}, "Call to action"), el("p", {}, d.call_to_action),
      el("h3", {}, "Why it should work"), el("p", {}, d.why_it_should_work),
      el("h3", {}, "After you post"), el("p", {}, d.posting_notes)),

    el("section", { class: "card" },
      el("h2", {}, "When to post"),
      t ? el("div", { class: "stats" },
        stat("Next best slot", new Date(t.next_slot).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" }), s.timezone),
        stat("Best days", t.top_weekdays.join(", ") || "–"),
        stat("Best hours", t.top_hours.map(hourLabel).join(", ")))
        : el("p", { class: "muted" }, "Not enough data to recommend a time."),
      el("p", { class: "muted" }, `Based on the ${s.primary_window_days}-day window. Hours are when top posts were published in your time zone.`)),

    el("section", { class: "card" },
      el("h2", {}, "Metric goals"),
      el("div", { class: "stats" },
        goalRow("Likes", s.goals.likes), goalRow("Comments", s.goals.comments), goalRow("Views", s.goals.views)),
      el("p", { class: "muted" }, "Target = top 25% of analyzed posts, stretch = top 10%. These are benchmarks from established accounts; scale to your follower count."),
      momentumText ? el("p", {}, momentumText) : null),

    el("section", { class: "card" },
      el("h2", {}, "Performance by window"),
      el("div", { class: "table-wrap" }, windowTable),
      el("h3", {}, "Hashtags used by top performers"),
      el("div", { class: "chips" }, (primary.top_hashtags || []).map((h) => el("span", { class: "chip" }, `#${h.tag} · ${h.count}`))),
      el("h3", {}, "Searched"),
      el("div", { class: "chips" }, r.plan.hashtags.map((h) => el("span", { class: "chip" }, "#" + h))),
      el("p", { class: "muted" }, r.plan.rationale)),

    el("section", { class: "card" },
      el("h2", {}, "Top posts"),
      (primary.top_posts || []).map((p) => el("div", { class: "example" },
        el("a", { href: p.url, target: "_blank", rel: "noopener" }, `${p.owner ? "@" + p.owner : "Post"} · ${p.format}`),
        ` · ${fmt(p.likes)} likes · ${fmt(p.comments)} comments${p.views ? ` · ${fmt(p.views)} views` : ""}`,
        el("div", { class: "muted" }, p.caption)))),

    r.warnings?.length ? el("section", { class: "card error" }, el("h2", {}, "Warnings"),
      el("ul", {}, r.warnings.map((w) => el("li", {}, w)))) : null,
  ].filter(Boolean));
  root.classList.remove("hidden");
  root.scrollIntoView({ behavior: "smooth" });
}

function showError(msg) {
  $("error").textContent = msg;
  $("error").classList.toggle("hidden", !msg);
}

async function poll(jobId) {
  for (;;) {
    const job = await api(`/api/jobs/${jobId}`);
    $("log").replaceChildren(...job.log.map((l) => el("li", {}, l)));
    if (job.status === "done") return job.report;
    if (job.status === "error") throw new Error(job.error);
    await new Promise((r) => setTimeout(r, 1500));
  }
}

async function loadHistory() {
  try {
    const items = await api("/api/reports");
    $("history").replaceChildren(...(items.length ? items.map((r) =>
      el("li", { onclick: async () => renderReport(await api(`/api/reports/${r.id}`)) },
        r.topic, el("span", { class: "muted" }, ` · ${new Date(r.generated_at).toLocaleString()}`)))
      : [el("li", { class: "muted" }, "No reports yet.")]));
  } catch (e) { showError(e.message); }
}

let isHost = false;

async function loadMode() {
  try {
    const c = await api("/api/config");
    isHost = c.is_host;
    const fakeData = c.data_provider === "mock";
    const fakeAi = c.llm_provider === "mock";
    $("mode").textContent = [
      fakeData ? "Demo posts (made up)" : `Real posts via ${c.data_provider}`,
      fakeAi ? "placeholder AI" : `AI: ${c.llm_model}`,
    ].join(" · ");
    $("setup-text").textContent =
      fakeData && fakeAi ? "You're in demo mode: results use made-up posts and a placeholder AI so you can try the app. To analyze real Instagram posts, add your two keys in Settings."
      : fakeData ? "Almost there: add your Apify key in Settings so the app can collect real Instagram posts."
      : "Almost there: add your DeepSeek key in Settings so the AI can write your post.";
    $("setup").classList.toggle("hidden", !((fakeData || fakeAi) && isHost));
    $("phone").classList.toggle("hidden", !isHost);
    if (isHost) $("qr").src = `/api/phone/qr.svg?t=${Date.now()}`;
  } catch { /* shown by history load */ }
}

$("analyze-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  showError("");
  $("go").disabled = true;
  $("log").replaceChildren();
  $("progress").classList.remove("hidden");
  try {
    const { job_id } = await api("/api/analyze", {
      method: "POST",
      body: JSON.stringify({ topic: $("topic").value, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone }),
    });
    renderReport(await poll(job_id));
    loadHistory();
  } catch (err) {
    showError(err.message);
  } finally {
    $("go").disabled = false;
    $("progress").classList.add("hidden");
  }
});

const SETTING_FIELDS = ["apify_token", "llm_api_key", "apify_results_per_tag", "max_hashtags", "llm_base_url", "llm_model"];

async function openSettings() {
  $("settings-error").textContent = "";
  $("host-settings").classList.toggle("hidden", !isHost);
  $("guest-settings").classList.toggle("hidden", isHost);
  $("settings-save").classList.toggle("hidden", !isHost);
  if (isHost) {
    try {
      const s = await api("/api/settings");
      for (const f of SETTING_FIELDS) $(f).value = f.endsWith("key") || f.endsWith("token") ? "" : s[f];
      $("apify_token_status").textContent = s.apify_token_set ? "✓ Saved" : "Not set yet";
      $("llm_api_key_status").textContent = s.llm_api_key_set ? "✓ Saved" : "Not set yet";
    } catch (e) { $("settings-error").textContent = e.message; }
  }
  $("settings").showModal();
}

$("settings-btn").addEventListener("click", openSettings);
$("setup-btn").addEventListener("click", openSettings);
$("settings-form").addEventListener("submit", async (e) => {
  if (e.submitter?.value !== "save") return;  // Cancel just closes
  e.preventDefault();
  const changes = Object.fromEntries(SETTING_FIELDS.map((f) => [f, $(f).value.trim()]));
  try {
    await api("/api/settings", { method: "PUT", body: JSON.stringify(changes) });
    $("settings").close();
    loadMode();
  } catch (err) {
    $("settings-error").textContent = err.message;
  }
});

// A phone opened from the QR code carries its access token in the URL: keep it, then hide it.
const urlToken = new URLSearchParams(location.search).get("token");
if (urlToken) {
  try { localStorage.setItem(tokenKey, urlToken); } catch { /* private mode */ }
  history.replaceState(null, "", location.pathname);
}

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
loadMode().then(loadHistory);
