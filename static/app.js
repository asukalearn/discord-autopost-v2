const $ = (id) => document.getElementById(id);

const feedback = $("feedback");
const statusPill = $("status-pill");
const statusLabel = $("status-label");
const consoleEl = $("console");

function setFeedback(msg, isError = false) {
  feedback.textContent = msg || "";
  feedback.style.color = isError ? "var(--danger)" : "var(--muted)";
}

function collectConfig() {
  return {
    tokens: $("tokens").value,
    message: $("message").value,
    channels: $("channels").value,
    notify_webhook_url: $("notify_webhook_url").value,
    embed_title: $("embed_title").value,
    embed_description: $("embed_description").value,
    embed_color: $("embed_color").value,
    embed_footer: $("embed_footer").value,
    embed_thumbnail_url: $("embed_thumbnail_url").value,
  };
}

async function saveConfig() {
  setFeedback("Menyimpan...");
  try {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectConfig()),
    });
    const data = await res.json();
    setFeedback(data.message, !data.ok);
  } catch (e) {
    setFeedback("Gagal menyimpan konfigurasi.", true);
  }
}

async function startBot() {
  await saveConfig();
  setFeedback("Menyalakan bot...");
  try {
    const res = await fetch("/api/start", { method: "POST" });
    const data = await res.json();
    setFeedback(data.message, !data.ok);
  } catch (e) {
    setFeedback("Gagal menyalakan bot.", true);
  }
}

async function stopBot() {
  setFeedback("Menghentikan bot...");
  try {
    const res = await fetch("/api/stop", { method: "POST" });
    const data = await res.json();
    setFeedback(data.message, !data.ok);
  } catch (e) {
    setFeedback("Gagal menghentikan bot.", true);
  }
}

function renderLogs(logs, running) {
  if (!logs.length) {
    consoleEl.innerHTML = '<div class="console__empty">Belum ada aktivitas.</div>';
    return;
  }
  const atBottom = consoleEl.scrollHeight - consoleEl.scrollTop - consoleEl.clientHeight < 24;
  consoleEl.innerHTML = logs
    .map((line) => `<div class="console__line">${escapeHtml(line)}</div>`)
    .join("");
  if (running) {
    consoleEl.innerHTML += '<span class="console__cursor"></span>';
  }
  if (atBottom) consoleEl.scrollTop = consoleEl.scrollHeight;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

async function pollStatus() {
  try {
    const res = await fetch("/api/status");
    if (res.status === 401 || res.redirected) {
      window.location.href = "/login";
      return;
    }
    const data = await res.json();
    statusPill.dataset.state = data.running ? "running" : "stopped";
    statusLabel.textContent = data.running ? "RUNNING" : "STOPPED";
    renderLogs(data.logs, data.running);
  } catch (e) {
    // diam
  }
}

$("save-btn").addEventListener("click", saveConfig);
if ($("save-btn-2")) $("save-btn-2").addEventListener("click", saveConfig);
$("start-btn").addEventListener("click", startBot);
$("stop-btn").addEventListener("click", stopBot);

// Color picker sync
const colorPicker = $("embed_color_picker");
const colorText = $("embed_color");
if (colorPicker && colorText) {
  colorPicker.addEventListener("input", () => {
    colorText.value = colorPicker.value;
  });
  colorText.addEventListener("input", () => {
    if (/^#[0-9A-Fa-f]{6}$/.test(colorText.value)) {
      colorPicker.value = colorText.value;
    }
  });
}

// Theme toggle
const root = document.documentElement;
$("theme-toggle").addEventListener("click", () => {
  const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
  root.setAttribute("data-theme", next);
  localStorage.setItem("autopost-theme", next);
});

pollStatus();
setInterval(pollStatus, 2500);