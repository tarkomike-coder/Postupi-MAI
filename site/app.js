const form = document.getElementById("search-form");
const input = document.getElementById("application-id");
const result = document.getElementById("result");
const message = document.getElementById("message");
const dataStatus = document.getElementById("data-status");

const deadline = new Date("2026-07-25T17:00:00+03:00");
let chartInstances = [];

function fmtDate(value) {
  if (!value) return "дата не загружена";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function deadlineValue(data) {
  return data?.deadline ? new Date(data.deadline) : deadline;
}

function deadlinePassed(data) {
  return Date.now() >= deadlineValue(data).getTime();
}

function daysLeftText(data) {
  const ms = deadlineValue(data).getTime() - Date.now();
  if (ms <= 0) return "Приём документов завершён";
  const days = Math.floor(ms / 86400000);
  const hours = Math.ceil((ms % 86400000) / 3600000);
  if (days <= 0) return `До завершения приёма: ${hours} ч.`;
  return `До завершения приёма: ${days} д. ${hours} ч.`;
}

function showMessage(text, isError = false) {
  message.hidden = false;
  message.className = isError ? "message error" : "message";
  message.textContent = text;
}

function clearMessage() {
  message.hidden = true;
  message.textContent = "";
}

function trackGoal(name) {
  if (window.ym && window.MAI_METRIKA_ID) {
    window.ym(window.MAI_METRIKA_ID, "reachGoal", name);
  }
}

function loadMetrika() {
  if (!window.MAI_METRIKA_ID) return;
  (function(m, e, t, r, i, k, a) {
    m[i] = m[i] || function() { (m[i].a = m[i].a || []).push(arguments); };
    m[i].l = 1 * new Date();
    k = e.createElement(t);
    a = e.getElementsByTagName(t)[0];
    k.async = 1;
    k.src = r;
    a.parentNode.insertBefore(k, a);
  })(window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");
  window.ym(window.MAI_METRIKA_ID, "init", {
    clickmap: true,
    trackLinks: true,
    accurateTrackBounce: true,
  });
}

async function loadStatus() {
  try {
    const response = await fetch("/api/status");
    const status = await response.json();
    if (status.has_data) {
      dataStatus.textContent = `Данные обновлены: ${fmtDate(status.updated_at)}`;
    } else {
      dataStatus.textContent = "Данные загружаются";
    }
  } catch {
    dataStatus.textContent = "Статус данных недоступен";
  }
}

function asNumber(value, fallback = 0) {
  return Number.isFinite(Number(value)) ? Number(value) : fallback;
}

function shortName(name) {
  if (!name) return "Направление";
  return name.length > 32 ? `${name.slice(0, 31)}...` : name;
}

function missingText(gap) {
  if (gap === null || gap === undefined) return "нет оценки";
  return gap <= 0 ? "проходит" : `нужно ${gap} мест`;
}

function statusMetricClass(gap) {
  if (gap === null || gap === undefined) return "metric status-neutral";
  return gap <= 0 ? "metric status-pass" : "metric status-wait";
}

function directionStatus(item) {
  const gap = item.facts.real_gap_to_budget;
  if (gap === null || gap === undefined) return "нужны новые данные для оценки";
  if (gap <= 0) return "проходит в текущем расчёте";
  return `нужно, чтобы освободилось ${gap} мест`;
}

function bestDirection(directions) {
  return [...directions].sort((a, b) => {
    const chance = (b.chance?.cascade_percent || 0) - (a.chance?.cascade_percent || 0);
    if (chance) return chance;
    return (a.facts.real_gap_to_budget ?? 9999) - (b.facts.real_gap_to_budget ?? 9999);
  })[0];
}

function applicantSummary(directions) {
  const first = directions[0]?.facts || {};
  const score = first.score ?? "нет данных";
  const consentCount = directions.filter((item) => item.facts.consent).length;
  return `Балл: ${score}. Согласие: ${consentCount ? `есть на ${consentCount} направл.` : "нет"}.`;
}

function chanceItem(value, label) {
  return `
    <div class="chance-item">
      <strong>${value}%</strong>
      <span>${label}</span>
    </div>
  `;
}

function renderChance(data, best) {
  const chance = best.chance || {};
  return `
    <section class="card chance-card">
      <div class="chance-head">
        <div>
          <h3>Реальные шансы</h3>
          <p><b>Каскад</b> всех поступающих: куда каждый попадёт с учётом согласий, баллов и приоритетов.</p>
        </div>
        <div class="real-chance">
          <strong>${chance.cascade_percent ?? 1}%</strong>
          <span>по текущему каскаду</span>
        </div>
      </div>
      <div class="scenario-grid">
        ${chanceItem(chance.current_percent ?? 1, "если считать только согласия")}
        ${chanceItem(chance.tempo_percent ?? 1, "по темпу изменений")}
        ${chanceItem(chance.stress_percent ?? 1, "если подтвердятся без согласия")}
      </div>
    </section>
  `;
}

function renderTerms() {
  return `
    <section class="card legend-note">
      <h3>Как читать числа</h3>
      <div><b>по согласиям</b> - место среди тех, кто уже подал согласие на это направление.</div>
      <div><b>по каскаду</b> - место после общего расчёта приоритетов: часть людей уходит на более желанные направления.</div>
      <div><b>Текущий расчёт</b> - проходит ли заявление сейчас. Если не проходит, указано, сколько мест должно освободиться.</div>
    </section>
  `;
}

function renderDirections(directions) {
  return `
    <h2 class="section-title">Направления</h2>
    <div class="directions">
      ${directions.map((item) => {
        const f = item.facts;
        return `
          <article class="direction-card">
            <div class="direction-head">
              <div>
                <h3>${item.name}</h3>
                <div class="sub">${item.okso_code || "ОКСО не указан"} · ${item.seats ?? "-"} мест на бюджете · приоритет ${f.priority ?? "-"}</div>
              </div>
              <span class="pill">${item.chance?.cascade_percent ?? 1}% по каскаду</span>
            </div>
            <div class="compact-metrics">
              <div class="metric"><strong>${f.position ?? "-"}</strong><span>общий список</span></div>
              <div class="metric"><strong>${f.consent_position ?? "-"}</strong><span>по согласиям</span></div>
              <div class="metric"><strong>${f.real_competitor_position ?? "-"}</strong><span>по каскаду</span></div>
              <div class="${statusMetricClass(f.real_gap_to_budget)}"><strong>${missingText(f.real_gap_to_budget)}</strong><span>Текущий расчёт</span></div>
            </div>
            <div class="direction-foot">
              <span>${directionStatus(item)}. Перед заявлением: ${item.cascade?.real_competitors_above ?? 0} реально мешают, ${item.cascade?.leaving_by_cascade ?? 0} уходят по каскаду, ${item.cascade?.waiting_without_consent ?? 0} без согласия.</span>
            </div>
          </article>
        `;
      }).join("")}
    </div>
  `;
}

function segmentWidth(value, total) {
  if (!total) return 0;
  return Math.max(4, Math.round((value / total) * 100));
}

function renderCascade(directions) {
  return `
    <h2 class="section-title">Каскад поступающих</h2>
    <section class="card cascade-list">
      ${directions.map((item) => {
        const c = item.cascade || {};
        const total = Math.max(1, c.total_above || 0);
        return `
          <div class="cascade-row">
            <div>
              <strong>${shortName(item.name)}</strong>
              <div class="sub">люди выше вашего заявления</div>
            </div>
            <div class="bar-track" aria-hidden="true">
              <span class="bar-real" style="width:${segmentWidth(c.real_competitors_above || 0, total)}%"></span>
              <span class="bar-leave" style="width:${segmentWidth(c.leaving_by_cascade || 0, total)}%"></span>
              <span class="bar-wait" style="width:${segmentWidth(c.waiting_without_consent || 0, total)}%"></span>
            </div>
            <div class="cascade-counts">
              <span>мешают: ${c.real_competitors_above ?? 0}</span>
              <span>уходят: ${c.leaving_by_cascade ?? 0}</span>
              <span>без согласия: ${c.waiting_without_consent ?? 0}</span>
            </div>
          </div>
        `;
      }).join("")}
    </section>
  `;
}

function renderCharts() {
  return `
    <h2 class="section-title">Динамика</h2>
    <div class="charts-grid">
      <section class="chart-card">
        <h3>Кто реально мешает</h3>
        <div class="chart-box"><canvas id="chart-real"></canvas></div>
      </section>
      <section class="chart-card">
        <h3>Кто может добавиться</h3>
        <div class="chart-box"><canvas id="chart-waiting"></canvas></div>
      </section>
      <section class="chart-card">
        <h3>Места в списках</h3>
        <div class="chart-box"><canvas id="chart-position"></canvas></div>
      </section>
      <section class="chart-card">
        <h3>Оценка шансов</h3>
        <div class="chart-box"><canvas id="chart-chance"></canvas></div>
      </section>
    </div>
  `;
}

function chartColors() {
  return ["#4d8cff", "#30d17e", "#ffb648", "#ff5c62", "#a778ff", "#23c7d9"];
}

function destroyCharts() {
  chartInstances.forEach((chart) => chart.destroy());
  chartInstances = [];
}

function chartDefaults() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: "#dce7ff", boxWidth: 12 } },
      tooltip: { intersect: false, mode: "index" },
    },
    scales: {
      x: { ticks: { color: "#9fb0cf" }, grid: { color: "rgba(111,149,221,0.18)" } },
      y: { ticks: { color: "#9fb0cf" }, grid: { color: "rgba(111,149,221,0.18)" } },
    },
  };
}

function mountCharts(data) {
  destroyCharts();
  if (!window.Chart || !data?.directions?.length) return;

  const colors = chartColors();
  const directions = data.directions;
  const labels = directions.map((item) => shortName(item.name));
  const options = chartDefaults();

  chartInstances.push(new Chart(document.getElementById("chart-real"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "реально перед заявлением", data: directions.map((item) => item.cascade?.real_competitors_above || 0), backgroundColor: "#ff5c62" },
        { label: "уходят по каскаду", data: directions.map((item) => item.cascade?.leaving_by_cascade || 0), backgroundColor: "#ffb648" },
      ],
    },
    options,
  }));

  chartInstances.push(new Chart(document.getElementById("chart-waiting"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "без согласия перед заявлением", data: directions.map((item) => item.cascade?.waiting_without_consent || 0), backgroundColor: "#4d8cff" },
      ],
    },
    options,
  }));

  chartInstances.push(new Chart(document.getElementById("chart-position"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "общий список", data: directions.map((item) => item.facts.position), backgroundColor: colors[0] },
        { label: "по согласиям", data: directions.map((item) => item.facts.consent_position), backgroundColor: colors[1] },
        { label: "по каскаду", data: directions.map((item) => item.facts.real_competitor_position), backgroundColor: colors[2] },
      ],
    },
    options: { ...options, indexAxis: "y" },
  }));

  chartInstances.push(new Chart(document.getElementById("chart-chance"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "по каскаду, %", data: directions.map((item) => item.chance?.cascade_percent || 1), backgroundColor: colors[4] },
        { label: "если подтвердятся без согласия, %", data: directions.map((item) => item.chance?.stress_percent || 1), backgroundColor: colors[5] },
      ],
    },
    options,
  }));
}

function renderResult(data) {
  destroyCharts();
  const isAfterDeadline = deadlinePassed(data);
  if (!data.found) {
    result.hidden = false;
    result.innerHTML = `
      <section class="summary">
        <div>
          <h2>Номер не найден</h2>
          <p>Заявление не найдено в очных бюджетных конкурсах МАИ на Госуслугах. Проверьте номер и источник данных.</p>
        </div>
      </section>
    `;
    trackGoal("search_not_found");
    return;
  }

  trackGoal("search_found");
  const best = bestDirection(data.directions);
  result.hidden = false;
  result.innerHTML = `
    <section class="summary">
      <div>
        <h2>Заявление ${data.application_id}</h2>
        <p>${isAfterDeadline ? "Приём документов завершён. " : ""}${applicantSummary(data.directions)} Лучший текущий ориентир: ${best.name}, ${directionStatus(best)}.</p>
      </div>
      <div class="summary-meta">
        <span class="pill">${data.summary.directions_count} направл.</span>
        <span class="pill">Данные: ${fmtDate(data.data_updated_at)}</span>
        <span class="pill">${daysLeftText(data)}</span>
      </div>
    </section>
    <div class="overview-grid">
      ${isAfterDeadline ? renderTerms() : renderChance(data, best)}
      ${renderTerms()}
    </div>
    ${renderDirections(data.directions)}
    ${isAfterDeadline ? "" : renderCascade(data.directions)}
    ${renderCharts()}
    <p class="note">Это аналитика по текущим данным Госуслуг.</p>
  `;
  mountCharts(data);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage();
  result.hidden = true;
  const button = form.querySelector("button");
  button.disabled = true;
  button.textContent = "Ищем";
  trackGoal("search_submitted");
  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ application_id: input.value.trim() }),
    });
    const data = await response.json();
    if (response.status === 429) {
      trackGoal("rate_limited");
      showMessage(data.message || "Слишком много запросов подряд. Поиск временно ограничен, повторите позже.", true);
      return;
    }
    if (!response.ok) {
      showMessage("Поиск недоступен. Повторите позже.", true);
      return;
    }
    renderResult(data);
  } catch {
    showMessage("Поиск недоступен. Повторите позже.", true);
  } finally {
    button.disabled = false;
    button.textContent = "Найти";
  }
});

loadMetrika();
loadStatus();
