"use strict";

const API_BASE = `http://${window.location.hostname || "127.0.0.1"}:8000`;
const nf = new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 0 });
const pf = new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 });
const df = new Intl.DateTimeFormat("fa-IR", { month: "short", day: "numeric" });
const fullDateFormatter = new Intl.DateTimeFormat("fa-IR", { year: "numeric", month: "short", day: "numeric" });
let dashboardController = null;
let aiController = null;

const $ = (selector) => document.querySelector(selector);
const elements = {
  select: $("#merchant-select"), loading: $("#loading-state"), error: $("#error-state"),
  errorMessage: $("#error-message"), retry: $("#retry-button"), dashboard: $("#dashboard"),
  opportunityList: $("#opportunity-list"), opportunityEmpty: $("#opportunity-empty"),
  aiForm: $("#ai-form"), aiQuestion: $("#ai-question"), aiSubmit: $("#ai-submit"),
  aiAnswer: $("#ai-answer"), aiError: $("#ai-error"),
  refreshStatus: $("#refresh-status"),
};

function formatNumber(value) { return nf.format(Number(value) || 0); }
function formatPercent(value) { return `${pf.format(Number(value) || 0)}٪`; }
function friendlyText(value) {
  return String(value || "")
    .replace(/sessions?/gi, "پرداخت")
    .replace(/Verified/gi, "تأییدشده")
    .replace(/retry/gi, "تلاش دوباره")
    .replace(/PSP(?:ها|های)?/gi, "مسیر پرداخت")
    .replace(/GMV/gi, "مبلغ پرداخت");
}
function setText(selector, value) { $(selector).textContent = value; }
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function copyText(value) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const field = el("textarea");
  field.value = value;
  field.setAttribute("readonly", "");
  field.style.position = "fixed";
  field.style.opacity = "0";
  document.body.append(field);
  field.select();
  const copied = document.execCommand("copy");
  field.remove();
  if (!copied) throw new Error("copy unavailable");
}

async function fetchJson(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, options);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("ارتباط با سرویس برقرار نشد. از روشن بودن سرویس مطمئن شوید.");
  }
  if (!response.ok) {
    const messages = {
      404: "اطلاعات این کسب‌وکار پیدا نشد.",
      422: "اطلاعات واردشده معتبر نیست.",
      502: "مشاور در حال حاضر پاسخ‌گو نیست.",
      503: "داده‌ها موقتاً در دسترس نیستند.",
    };
    let message = messages[response.status] || "در دریافت اطلاعات مشکلی پیش آمد.";
    throw new Error(message);
  }
  return response.json();
}

function showLoading(isInitial = false) {
  elements.error.classList.add("hidden");
  if (isInitial) {
    elements.loading.classList.remove("hidden");
    elements.dashboard.classList.add("hidden");
  } else {
    elements.dashboard.classList.add("is-loading");
    elements.refreshStatus.classList.remove("hidden");
  }
}

function showError(message) {
  elements.loading.classList.add("hidden");
  elements.dashboard.classList.add("hidden");
  elements.dashboard.classList.remove("is-loading");
  elements.refreshStatus.classList.add("hidden");
  elements.error.classList.remove("hidden");
  elements.errorMessage.textContent = message;
}

function renderScore(data) {
  const opportunity = data.opportunity_score || {};
  const score = Math.min(100, Math.max(0, Number(opportunity.value) || 0));
  setText("#growth-score", formatNumber(score));
  setText("#score-status", score >= 50 ? "فرصت قابل‌توجه" : score >= 20 ? "فرصت متوسط" : "فرصت محدود");
  setText("#score-meaning", opportunity.meaning || "سهم مبلغ پرداخت‌های غیرموفق از کل مبلغ مشاهده‌شده.");
  setText("#score-calculation", opportunity.calculation?.explanation || "");
  $("#score-ring").style.setProperty("--score", `${score * 3.6}deg`);
}

function impactEstimate(insight) {
  const evidence = insight.evidence || {};
  const amount = evidence.estimated_at_risk_gmv_opportunity ?? evidence.at_risk_gmv ?? evidence.repeat_customer_verified_gmv;
  if (amount !== undefined && amount !== null) return `${formatNumber(amount)} ریال`;
  if (evidence.estimated_recoverable_sessions !== undefined) return `${formatNumber(evidence.estimated_recoverable_sessions)} پرداخت`;
  if (evidence.gap_percentage_points !== undefined) return `${formatPercent(evidence.gap_percentage_points)} فاصله`;
  return "اثر مالی مستقیم محاسبه نشده";
}

function detailBlock(label, text, className = "") {
  const block = el("div", `detail-block ${className}`.trim());
  block.append(el("span", "", label), el("p", "", friendlyText(text) || "اطلاعاتی ثبت نشده است."));
  return block;
}

function calculationPanel(insight, index) {
  const calculation = insight.calculation || {};
  const panel = el("div", "calculation-panel hidden");
  panel.id = `calculation-${index}`;
  const rows = [
    ["شاخص", calculation.metric],
    ["روش محاسبه", calculation.formula],
    ["مقدار فعلی", calculation.current_period],
    ["مبنای مقایسه", calculation.baseline],
    ["داده بررسی‌شده", calculation.sample_size],
  ];
  const list = el("dl", "calculation-list");
  if (calculation.explanation) panel.append(el("p", "trace-explanation", calculation.explanation));
  rows.forEach(([term, value]) => {
    const row = el("div");
    row.append(el("dt", "", term), el("dd", "", value || "—"));
    list.append(row);
  });
  panel.append(el("strong", "panel-title", "رد محاسبه"), list);
  if (Array.isArray(calculation.filters) && calculation.filters.length) {
    const filters = el("div", "filter-list");
    filters.append(el("span", "", "شرایط محاسبه"));
    const ul = el("ul");
    calculation.filters.forEach((filter) => ul.append(el("li", "", filter)));
    filters.append(ul);
    panel.append(filters);
  }
  return panel;
}

function opportunityCard(insight, index) {
  const card = el("article", `opportunity-card ${index === 0 ? "featured" : ""}`);
  const top = el("div", "opportunity-top");
  const rank = el("span", "rank", `اولویت ${formatNumber(index + 1)}`);
  const confidenceLabels = { high: "اطمینان بالا", medium: "اطمینان متوسط", low: "اطمینان محدود" };
  top.append(rank, el("span", "confidence", confidenceLabels[insight.confidence] || "اطمینان محدود"));
  const title = el("h3", "", friendlyText(insight.title));
  const impact = el("div", "impact");
  impact.append(el("span", "", "برآورد اثر"), el("strong", "", impactEstimate(insight)), el("small", "", friendlyText(insight.impact)));
  const action = detailBlock("اقدام پیشنهادی", insight.action, "action");
  const copyAction = el("button", "copy-action", "کپی اقدام");
  copyAction.type = "button";
  copyAction.dataset.copyAction = friendlyText(insight.action);
  action.append(copyAction);
  const whyPanel = el("div", "why-panel hidden");
  whyPanel.id = `why-${index}`;
  whyPanel.append(detailBlock("چرا این پیشنهاد را می‌بینید؟", insight.problem), detailBlock("داده چه چیزی نشان می‌دهد؟", insight.cause));
  const controls = el("div", "card-controls");
  const whyButton = el("button", "secondary-button", "چرا این را می‌بینم؟");
  whyButton.type = "button"; whyButton.dataset.toggle = whyPanel.id; whyButton.setAttribute("aria-expanded", "false");
  const calcButton = el("button", "text-button calculation-button", "مشاهده روش محاسبه");
  calcButton.type = "button"; calcButton.dataset.toggle = `calculation-${index}`; calcButton.setAttribute("aria-expanded", "false");
  controls.append(whyButton, calcButton);
  card.append(top, title, impact, action, controls, whyPanel, calculationPanel(insight, index));
  return card;
}

function renderOpportunities(insights) {
  const items = Array.isArray(insights) ? insights.slice(0, 3) : [];
  elements.opportunityList.replaceChildren(...items.map(opportunityCard));
  elements.opportunityEmpty.classList.toggle("hidden", items.length > 0);
  setText("#opportunity-count", items.length ? `${formatNumber(items.length)} پیشنهاد` : "بدون اقدام فوری");
  setText("#opportunities-title", items.length ? `${formatNumber(items.length)} فرصت مهم برای اقدام` : "نتیجه بررسی فرصت‌ها");
  setText("#briefing", items.length
    ? `${formatNumber(items.length)} فرصت بر اساس اثر و میزان اطمینان برای شما مرتب شده است.`
    : "در داده‌های فعلی اقدام فوری شناسایی نشد؛ عملکرد را همچنان زیر نظر داشته باشید.");
}

function renderKpis(data) {
  setText("#verified-gmv", formatNumber(data.overview.verified_gmv));
  setText("#conversion-rate", formatPercent(data.overview.conversion_rate));
  setText("#payment-count", `${formatNumber(data.overview.successful_payments)} پرداخت موفق`);
  setText("#at-risk-gmv", formatNumber(data.overview.at_risk_gmv));
}

function renderDataPeriod(period) {
  if (!period?.start_date || !period?.end_date) {
    setText("#data-period", "بازه زمانی داده مشخص نیست");
    return;
  }
  const start = new Date(`${period.start_date}T00:00:00`);
  const end = new Date(`${period.end_date}T00:00:00`);
  setText(
    "#data-period",
    `بر اساس ${formatNumber(period.session_count)} پرداخت، از ${fullDateFormatter.format(start)} تا ${fullDateFormatter.format(end)}`
  );
}

function renderChart(rows) {
  const chart = $("#sales-chart");
  const empty = $("#chart-empty");
  const values = Array.isArray(rows) ? rows.filter((row) => Number.isFinite(Number(row.gmv))) : [];
  chart.replaceChildren();
  if (!values.length) { chart.classList.add("hidden"); empty.classList.remove("hidden"); return; }
  chart.classList.remove("hidden"); empty.classList.add("hidden");
  const width = 800, height = 220, padX = 18, padY = 24;
  const max = Math.max(...values.map((row) => Number(row.gmv)), 1);
  const points = values.map((row, index) => {
    const x = values.length === 1 ? width / 2 : padX + index * ((width - padX * 2) / (values.length - 1));
    const y = height - padY - (Number(row.gmv) / max) * (height - padY * 2);
    return { x, y, row };
  });
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("preserveAspectRatio", "none");
  const area = document.createElementNS(ns, "path");
  const line = document.createElementNS(ns, "polyline");
  const pointString = points.map(({ x, y }) => `${x},${y}`).join(" ");
  area.setAttribute("d", `M ${points[0].x} ${height - padY} L ${pointString.replaceAll(",", " ")} L ${points.at(-1).x} ${height - padY} Z`);
  area.setAttribute("class", "chart-area");
  line.setAttribute("points", pointString); line.setAttribute("class", "chart-line");
  svg.append(area, line);
  const labels = el("div", "chart-labels");
  const labelIndexes = [...new Set([0, Math.floor((values.length - 1) / 2), values.length - 1])];
  labelIndexes.forEach((index) => {
    const date = new Date(`${values[index].date}T00:00:00`);
    labels.append(el("span", "", Number.isNaN(date.valueOf()) ? values[index].date : df.format(date)));
  });
  chart.append(svg, labels);
  setText("#chart-total", `${formatNumber(values.reduce((sum, row) => sum + Number(row.gmv), 0))} ریال`);
}

function renderDashboard(data) {
  renderScore(data); renderOpportunities(data.insights); renderKpis(data);
  renderDataPeriod(data.data_period);
  renderChart(data.revenue?.gmv_by_day);
  elements.loading.classList.add("hidden");
  elements.error.classList.add("hidden");
  elements.dashboard.classList.remove("hidden", "is-loading");
  elements.refreshStatus.classList.add("hidden");
}

async function loadDashboard(merchantId, isInitial = false) {
  if (dashboardController) dashboardController.abort();
  const controller = new AbortController();
  dashboardController = controller;
  showLoading(isInitial);
  elements.select.disabled = true;
  elements.aiAnswer.classList.add("hidden"); elements.aiError.classList.add("hidden");
  try {
    const data = await fetchJson(`/api/merchant/${encodeURIComponent(merchantId)}/dashboard`, { signal: controller.signal });
    renderDashboard(data);
  } catch (error) {
    if (error.name !== "AbortError") showError(error.message || "امکان دریافت اطلاعات وجود ندارد.");
  } finally {
    if (dashboardController === controller && !controller.signal.aborted) elements.select.disabled = false;
  }
}

async function askAI(event) {
  event.preventDefault();
  const question = elements.aiQuestion.value.trim();
  if (!question) return;
  if (aiController) aiController.abort();
  const controller = new AbortController();
  aiController = controller;
  const merchantId = elements.select.value;
  elements.aiSubmit.disabled = true; elements.aiSubmit.textContent = "در حال بررسی…";
  elements.aiAnswer.classList.add("hidden"); elements.aiError.classList.add("hidden");
  try {
    const result = await fetchJson(`/api/merchant/${encodeURIComponent(merchantId)}/ai/chat`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }), signal: controller.signal,
    });
    if (elements.select.value !== merchantId) return;
    elements.aiAnswer.textContent = result.answer; elements.aiAnswer.classList.remove("hidden");
  } catch (error) {
    if (error.name === "AbortError") return;
    elements.aiError.textContent = error.message || "پاسخ آماده نشد."; elements.aiError.classList.remove("hidden");
  } finally {
    if (aiController === controller) {
      elements.aiSubmit.disabled = false; elements.aiSubmit.textContent = "بپرس";
    }
  }
}

async function initialize() {
  showLoading(true);
  try {
    const merchants = await fetchJson("/api/merchants");
    if (!Array.isArray(merchants) || !merchants.length) throw new Error("کسب‌وکاری در داده‌ها پیدا نشد.");
    elements.select.replaceChildren(...merchants.map((id) => {
      const option = el("option", "", `پذیرنده ${id}`); option.value = id; return option;
    }));
    elements.select.value = merchants.includes("M31") ? "M31" : merchants[0];
    await loadDashboard(elements.select.value, true);
  } catch (error) { showError(error.message || "اتصال به سرویس برقرار نشد."); }
}

document.addEventListener("click", (event) => {
  const copyButton = event.target.closest("[data-copy-action]");
  if (copyButton) {
    copyText(copyButton.dataset.copyAction).then(() => {
      copyButton.textContent = "کپی شد";
      window.setTimeout(() => { copyButton.textContent = "کپی اقدام"; }, 1600);
    }).catch(() => {
      copyButton.textContent = "کپی نشد";
    });
    return;
  }
  const button = event.target.closest("[data-toggle]");
  if (!button) return;
  const target = document.getElementById(button.dataset.toggle);
  if (!target) return;
  const expanded = button.getAttribute("aria-expanded") === "true";
  button.setAttribute("aria-expanded", String(!expanded));
  target.classList.toggle("hidden", expanded);
});
elements.select.addEventListener("change", (event) => {
  if (aiController) aiController.abort();
  loadDashboard(event.target.value);
});
elements.retry.addEventListener("click", initialize);
elements.aiForm.addEventListener("submit", askAI);
initialize();
