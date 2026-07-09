const form = document.getElementById("search-form");
const input = document.getElementById("application-id");
const result = document.getElementById("result");
const message = document.getElementById("message");
const dataStatus = document.getElementById("data-status");

const deadline = new Date("2026-07-25T17:00:00+03:00");

function fmtDate(value) {
  if (!value) return "дата не загружена";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function deadlinePassed(data) {
  const value = data?.deadline ? new Date(data.deadline) : deadline;
  return Date.now() >= value.getTime();
}

function daysLeftText(data) {
  const value = data?.deadline ? new Date(data.deadline) : deadline;
  const ms = value.getTime() - Date.now();
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

function fact(label, value) {
  const shown = value === null || value === undefined ? "—" : value;
  return `<div class="fact"><strong>${shown}</strong><span>${label}</span></div>`;
}

function gapText(gap) {
  if (gap === 0) return "Внутри бюджетной зоны по текущему расчёту.";
  if (gap === null || gap === undefined) return "Недостаточно данных для вывода.";
  if (gap <= 5) return `Рядом с бюджетной зоной: разрыв ${gap}.`;
  return `Вне бюджетной зоны: разрыв ${gap}.`;
}

function renderDirections(directions, isAfterDeadline) {
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
                <span>${item.okso_code || "ОКСО не указан"} · ${item.seats ?? "—"} бюджетных мест</span>
              </div>
              <span class="pill">Приоритет ${f.priority ?? "—"}</span>
            </div>
            <div class="facts">
              ${fact("Балл", f.score)}
              ${fact("Место в общем списке", f.position)}
              ${fact("Место среди согласий", f.consent_position)}
              ${fact("Место среди реальных конкурентов", f.real_competitor_position)}
              ${fact("Выше с согласием", f.above_with_consent)}
              ${fact("Выше без согласия", f.above_without_consent)}
              ${fact("Разрыв до зоны", f.real_gap_to_budget)}
              ${fact("Согласие", f.consent ? "есть" : "нет")}
            </div>
            ${isAfterDeadline ? "" : `<div class="outlook">${gapText(f.real_gap_to_budget)}</div>`}
          </article>
        `;
      }).join("")}
    </div>
  `;
}

function renderForecast(data) {
  if (deadlinePassed(data)) return "";
  const directions = data.directions || [];
  const aboveWithout = directions.reduce((sum, item) => sum + (item.facts.above_without_consent || 0), 0);
  const close = directions.some((item) => (item.facts.real_gap_to_budget ?? 99) <= 5);
  return `
    <h2 class="section-title">Что может измениться до 25 июля</h2>
    <div class="forecast">
      <section class="forecast-item">
        <h3>По темпу последних дней</h3>
        <p>Смотрим, как менялось число согласий выше в списке. История станет точнее после нескольких обновлений данных.</p>
      </section>
      <section class="forecast-item">
        <h3>Если темп согласий сохранится</h3>
        <p>${close ? "Часть направлений рядом с границей, поэтому важны новые согласия выше." : "Главный риск сейчас — заявления выше без согласия."}</p>
      </section>
      <section class="forecast-item">
        <h3>Напряжённый сценарий</h3>
        <p>Выше без согласия: ${aboveWithout}. Если многие подтвердят согласие, разрыв до бюджетной зоны может вырасти.</p>
      </section>
    </div>
  `;
}

function renderChart(points) {
  if (!points || points.length < 2) {
    return `<p class="note">История начнёт отображаться после нескольких обновлений данных.</p>`;
  }
  const width = 640;
  const height = 190;
  const pad = 24;
  const values = points.map((p) => p.real_competitor_position || p.position).filter((v) => Number.isFinite(v));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  const coords = points.map((p, i) => {
    const value = p.real_competitor_position || p.position;
    const x = pad + (i * (width - pad * 2)) / Math.max(1, points.length - 1);
    const y = pad + ((value - min) * (height - pad * 2)) / span;
    return `${x},${y}`;
  }).join(" ");
  return `
    <svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="История позиции">
      <polyline fill="none" stroke="#2669d9" stroke-width="4" points="${coords}"></polyline>
      ${points.map((p, i) => {
        const value = p.real_competitor_position || p.position;
        const x = pad + (i * (width - pad * 2)) / Math.max(1, points.length - 1);
        const y = pad + ((value - min) * (height - pad * 2)) / span;
        return `<circle cx="${x}" cy="${y}" r="5" fill="#16875d"><title>${fmtDate(p.date)}: место ${value}</title></circle>`;
      }).join("")}
    </svg>
  `;
}

function renderHistory(history) {
  if (!history || !history.length) return "";
  return `
    <h2 class="section-title">История</h2>
    <div class="history-list">
      ${history.map((item) => `
        <section class="chart-card">
          <h3>${item.name}</h3>
          ${renderChart(item.points)}
        </section>
      `).join("")}
    </div>
  `;
}

function renderResult(data) {
  const isAfterDeadline = deadlinePassed(data);
  if (!data.found) {
    result.hidden = false;
    result.innerHTML = `
      <section class="summary">
        <div>
          <h2>Номер не найден</h2>
          <p>Номер заявления не найден в очных бюджетных конкурсах МАИ. Проверьте номер и учтите, что платные и заочные конкурсы в MVP не проверяются.</p>
        </div>
      </section>
    `;
    trackGoal("search_not_found");
    return;
  }
  trackGoal("search_found");
  result.hidden = false;
  result.innerHTML = `
    <section class="summary">
      <div>
        <h2>Заявление ${data.application_id}</h2>
        <p>${isAfterDeadline ? "Приём документов завершён. " : ""}${data.summary.status}</p>
      </div>
      <div class="summary-meta">
        <span class="pill">${data.summary.directions_count} направл.</span>
        <span class="pill">Данные: ${fmtDate(data.data_updated_at)}</span>
        <span class="pill">${daysLeftText(data)}</span>
      </div>
    </section>
    ${renderDirections(data.directions, isAfterDeadline)}
    ${renderForecast(data)}
    ${renderHistory(data.history)}
    <p class="note">Сервис показывает аналитику по текущим данным Госуслуг. Это не официальный результат зачисления.</p>
  `;
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
      showMessage(data.message || "Слишком много запросов подряд. Поиск временно ограничен, попробуйте позже.", true);
      return;
    }
    if (!response.ok) {
      showMessage("Поиск недоступен. Попробуйте позже.", true);
      return;
    }
    renderResult(data);
  } catch {
    showMessage("Поиск недоступен. Попробуйте позже.", true);
  } finally {
    button.disabled = false;
    button.textContent = "Найти";
  }
});

loadMetrika();
loadStatus();
