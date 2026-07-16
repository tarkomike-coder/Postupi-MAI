const form = document.getElementById("search-form");
const input = document.getElementById("application-id");
const result = document.getElementById("result");
const message = document.getElementById("message");
const dataStatus = document.getElementById("data-status");
const homepageOverview = document.getElementById("homepage-overview");

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
    for (let j = 0; j < e.scripts.length; j += 1) {
      if (e.scripts[j].src === r) return;
    }
    k = e.createElement(t);
    a = e.getElementsByTagName(t)[0];
    k.async = 1;
    k.src = r;
    a.parentNode.insertBefore(k, a);
  })(window, document, "script", `https://mc.yandex.ru/metrika/tag.js?id=${window.MAI_METRIKA_ID}`, "ym");
  window.ym(window.MAI_METRIKA_ID, "init", {
    ssr: true,
    webvisor: true,
    clickmap: true,
    ecommerce: "dataLayer",
    referrer: document.referrer,
    url: location.href,
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

function fmtInt(value) {
  return new Intl.NumberFormat("ru-RU").format(asNumber(value));
}

function fmtScore(value) {
  return value === null || value === undefined ? "-" : fmtInt(value);
}

function fmtRatio(value) {
  return value === null || value === undefined
    ? "-"
    : new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 }).format(value);
}

function renderDashboardRows(rows, columns) {
  if (!rows?.length) {
    return '<p class="dashboard-empty">Данные по направлениям не загружены.</p>';
  }
  return `
    <div class="dashboard-table" role="table" style="--dashboard-columns:${Math.max(1, columns.length - 1)}">
      <div class="dashboard-table-head" role="row">
        ${columns.map((column) => `<span role="columnheader">${column.label}</span>`).join("")}
      </div>
      ${rows.map((row) => `
        <div class="dashboard-table-row" role="row">
          ${columns.map((column) => `<span role="cell">${column.render(row)}</span>`).join("")}
        </div>
      `).join("")}
    </div>
  `;
}

function directionCell(row) {
  return `<a class="direction-link" href="/directions/${row.group_id}"><strong>${row.name}</strong><small>${row.okso_code || "ОКСО не указан"}</small></a>`;
}

function directionPageId() {
  const match = window.location.pathname.match(/^\/directions\/(\d+)\/?$/);
  return match ? match[1] : null;
}

function renderHomepageOverview(data) {
  if (!homepageOverview) return;
  if (!data?.has_data) {
    homepageOverview.innerHTML = `
      <section class="dashboard-shell">
        <div class="loading-panel">
          <span class="spinner" aria-hidden="true"></span>
          <div>
            <h2>Загрузка данных</h2>
            <p>Получаем расчетные данные по направлениям.</p>
          </div>
        </div>
      </section>
    `;
    return;
  }
  const totals = data.totals || {};
  const directions = data.directions || data.cascade || [];
  homepageOverview.innerHTML = `
    <section class="dashboard-shell" aria-labelledby="overview-title">
      <div class="dashboard-head">
        <div>
          <p class="eyebrow">Публичные данные Госуслуг</p>
          <h2 id="overview-title">МАИ 2026: текущая картина по конкурсным спискам</h2>
          <p>Данные рассчитаны только по публичным конкурсным спискам Госуслуг. Сервис не является официальным сайтом МАИ и не публикует результаты зачисления.</p>
        </div>
        <span class="dashboard-source">Обновлено: ${fmtDate(data.updated_at)}</span>
      </div>

      <div class="dashboard-metrics">
        <div><strong>${fmtInt(totals.directions_count)}</strong><span>направлений очного бюджета</span></div>
        <div><strong>${fmtInt(totals.budget_places)}</strong><span>бюджетных мест</span></div>
        <div><strong>${fmtInt(totals.applicants_count)}</strong><span>поступающих в списках</span></div>
        <div><strong>${fmtInt(totals.consents_count)}</strong><span>согласий в списках</span></div>
      </div>

      <section class="dashboard-section">
        <div class="dashboard-section-head">
          <h3>Все направления: места, заявления, согласия и расчетный балл</h3>
          <p>В таблице приведены все направления из текущего снимка Госуслуг. Один поступающий может быть в нескольких конкурсных списках, поэтому расчет учитывает текущие согласия и приоритеты. <a class="inline-help" href="#faq-cascade" data-open-faq>Что значит учет приоритетов?</a></p>
        </div>
        ${renderDashboardRows(directions, [
          { label: "Направление", render: directionCell },
          { label: "Бюджетных мест", render: (row) => fmtInt(row.seats) },
          { label: "Заявлений в списке", render: (row) => fmtInt(row.applicants_count) },
          { label: "Согласий", render: (row) => fmtInt(row.consent_count) },
          { label: "Расчетный балл на бюджет", render: (row) => fmtScore(row.cutoff?.cascade) },
          { label: "Конкурс, чел./место", render: (row) => fmtRatio(row.applicants_per_place) },
        ])}
      </section>

      <section class="dashboard-note" aria-label="Как читать таблицу">
        <h3>Как читать таблицу</h3>
        <p><b>Расчетный балл на бюджет</b> - не официальный проходной балл и не итог зачисления. Это текущий ориентир по публичным спискам Госуслуг на момент обновления данных.</p>
        <p><b>Балл может быть выше 300</b>, если в данных Госуслуг к сумме ЕГЭ добавлены индивидуальные достижения.</p>
      </section>

      <section class="dashboard-section">
        <div class="dashboard-section-head">
          <h3>Направления с наибольшей конкурсной нагрузкой</h3>
          <p>Приведены направления с наибольшим числом поступающих на одно бюджетное место по текущим публичным спискам.</p>
        </div>
        ${renderDashboardRows(data.competition, [
          { label: "Направление", render: directionCell },
          { label: "Бюджетных мест", render: (row) => fmtInt(row.seats) },
          { label: "Поступающих", render: (row) => fmtInt(row.applicants_count) },
          { label: "Согласий", render: (row) => fmtInt(row.consent_count) },
          { label: "Поступающих на место", render: (row) => fmtRatio(row.applicants_per_place) },
        ])}
      </section>
    </section>
  `;
}

async function loadOverview() {
  if (!homepageOverview) return;
  try {
    const response = await fetch("/api/overview");
    if (!response.ok) throw new Error("overview unavailable");
    renderHomepageOverview(await response.json());
  } catch {
    homepageOverview.innerHTML = `
      <section class="dashboard-shell">
        <div class="dashboard-head">
          <div>
            <p class="eyebrow">Публичные данные Госуслуг</p>
            <h2>МАИ 2026: текущая картина по конкурсным спискам</h2>
            <p>Сводка временно недоступна. Поиск по коду поступающего работает отдельно.</p>
          </div>
        </div>
      </section>
    `;
  }
}

function renderDirectionApplicants(applicants) {
  if (!applicants?.length) {
    return '<p class="dashboard-empty">Расчетный список по направлению не сформирован.</p>';
  }
  return `
    <div class="direction-applicant-table" role="table">
      <div class="direction-applicant-head" role="row">
        <span role="columnheader">№</span>
        <span role="columnheader">Код поступающего</span>
        <span role="columnheader">Балл</span>
        <span role="columnheader">Приоритет</span>
        <span role="columnheader">Место в списке</span>
        <span role="columnheader">Статус</span>
      </div>
      ${applicants.map((item) => `
        <div class="direction-applicant-row" role="row">
          <span role="cell">${fmtInt(item.calculated_position)}</span>
          <span role="cell"><strong>${item.application_id}</strong></span>
          <span role="cell">${fmtScore(item.score)}</span>
          <span role="cell">${item.priority ?? "-"}</span>
          <span role="cell">${item.source_position ?? "-"}</span>
          <span role="cell">${item.status}</span>
        </div>
      `).join("")}
    </div>
  `;
}

function renderDirectionPage(data) {
  destroyCharts();
  const hero = document.querySelector(".hero");
  if (hero) hero.hidden = true;
  result.hidden = true;
  if (!homepageOverview) return;
  if (!data?.found) {
    homepageOverview.innerHTML = `
      <section class="dashboard-shell">
        <a class="back-link" href="/">← На главную</a>
        <h2>Направление не найдено</h2>
      </section>
    `;
    return;
  }
  const summary = data.summary || {};
  const cutoff = summary.cutoff || {};
  homepageOverview.innerHTML = `
    <section class="direction-page" aria-labelledby="direction-title">
      <a class="back-link" href="/">← На главную</a>
      <header class="direction-page-head">
        <div>
          <p class="eyebrow">МАИ 2026 · очный бюджет</p>
          <h2 id="direction-title">${data.name}</h2>
          <p>${data.okso_code || "ОКСО не указан"} · ${fmtInt(data.seats)} бюджетных мест · обновлено: ${fmtDate(data.updated_at)}</p>
        </div>
      </header>

      <div class="dashboard-metrics">
        <div><strong>${fmtInt(data.seats)}</strong><span>бюджетных мест</span></div>
        <div><strong>${fmtScore(cutoff.cascade)}</strong><span>расчетный балл на бюджет</span></div>
        <div><strong>${fmtInt(summary.consent_count)}</strong><span>согласий</span></div>
        <div><strong>${fmtInt(summary.applicants_count)}</strong><span>заявлений в списке</span></div>
      </div>

      <section class="direction-chart-grid" aria-label="Динамика направления">
        <div class="chart-card"><h3>Расчетный балл на бюджет</h3><div class="chart-box"><canvas id="direction-score-chart"></canvas></div></div>
        <div class="chart-card"><h3>Заявлений в списке</h3><div class="chart-box"><canvas id="direction-applicants-chart"></canvas></div></div>
        <div class="chart-card"><h3>Согласий</h3><div class="chart-box"><canvas id="direction-consents-chart"></canvas></div></div>
        <div class="chart-card"><h3>Конкурс, человек на место</h3><div class="chart-box"><canvas id="direction-competition-chart"></canvas></div></div>
      </section>

      <section class="dashboard-section">
        <div class="dashboard-section-head">
          <h3>Расчетный список с учетом согласий и приоритетов</h3>
          <p>В списке находятся поступающие с согласием, которые остаются на этом направлении после учета приоритетов. Если поступающий проходит на направление с более высоким приоритетом, здесь он не считается конкурентом.</p>
        </div>
        ${renderDirectionApplicants(data.applicants)}
      </section>
    </section>
  `;
  mountDirectionCharts(data);
  trackGoal("direction_open");
}

function mountDirectionCharts(data) {
  destroyCharts();
  if (!window.Chart || !data?.history?.length) return;
  const labels = data.history.map((point) => fmtDate(point.date));
  const options = chartDefaults();
  const line = (canvasId, label, values, color) => {
    const target = document.getElementById(canvasId);
    if (!target) return;
    chartInstances.push(new Chart(target, {
      type: "line",
      data: {
        labels,
        datasets: [{
          label,
          data: values,
          borderColor: color,
          backgroundColor: color,
          tension: 0.25,
          spanGaps: true,
        }],
      },
      options,
    }));
  };
  line("direction-score-chart", "расчетный балл", data.history.map((point) => point.calculated_budget_score), "#30d17e");
  line("direction-applicants-chart", "заявлений", data.history.map((point) => point.applicants_count), "#4d8cff");
  line("direction-consents-chart", "согласий", data.history.map((point) => point.consent_count), "#ffb648");
  line("direction-competition-chart", "человек на место", data.history.map((point) => point.applicants_per_place), "#a778ff");
}

async function loadDirectionPage(groupId) {
  if (!homepageOverview) return;
  homepageOverview.innerHTML = `
    <section class="dashboard-shell loading-panel">
      <a class="back-link" href="/">← На главную</a>
      <span class="spinner" aria-hidden="true"></span>
      <div>
        <h2>Загрузка направления</h2>
        <p>Получаем динамику и расчетный список.</p>
      </div>
    </section>
  `;
  try {
    const response = await fetch(`/api/directions/${groupId}`);
    if (!response.ok) throw new Error("direction unavailable");
    renderDirectionPage(await response.json());
  } catch {
    homepageOverview.innerHTML = `
      <section class="dashboard-shell">
        <a class="back-link" href="/">← На главную</a>
        <h2>Направление временно недоступно</h2>
      </section>
    `;
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

function renderPrediction(prediction) {
  if (!prediction) return "";
  const isPassing = prediction.status === "passing";
  return `
    <section class="prediction ${isPassing ? "prediction-pass" : "prediction-wait"}">
      <div>
        <span class="prediction-label">Главный вывод по текущим данным</span>
        <h3>${isPassing ? "Куда проходит заявление" : "Ближайшее направление"}</h3>
        <strong>${prediction.name}</strong>
        <p>${prediction.okso_code || "ОКСО не указан"} · приоритет ${prediction.priority ?? "-"} · ${prediction.seats ?? "-"} бюджетных мест. ${isPassing ? "Нижние приоритеты ниже отмечены как резерв." : "До прохода не хватает мест."}</p>
      </div>
      <div class="prediction-score">
        <strong>${isPassing ? "проходит" : `+${prediction.needed_places}`}</strong>
        <span>${isPassing ? "по текущему расчету" : "мест нужно"}</span>
        <em>устойчивость: ${prediction.chance_percent ?? 1}%</em>
      </div>
    </section>
  `;
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
          <h3>Оценка устойчивости</h3>
          <p><b>Каскад</b> всех поступающих: куда каждый попадает с учетом согласий, баллов и приоритетов. Процент ниже - расчетная устойчивость текущего положения, не гарантия зачисления.</p>
        </div>
        <div class="real-chance">
          <strong>${chance.cascade_percent ?? 1}%</strong>
          <span>устойчивость позиции</span>
        </div>
      </div>
      <div class="scenario-grid">
        ${chanceItem(chance.current_percent ?? 1, "если считать только согласия")}
        ${chanceItem(chance.tempo_percent ?? 1, "по темпу изменений")}
        ${chanceItem(chance.stress_percent ?? 1, "риск новых согласий выше")}
      </div>
    </section>
  `;
}

function renderWhyPasses(direction, prediction) {
  if (!direction || !prediction) return "";
  const f = direction.facts || {};
  const c = direction.cascade || {};
  const passing = prediction.status === "passing";
  return `
    <section class="card why-card">
      <h3>${passing ? "Почему проходит" : "Почему не проходит"}</h3>
      <div class="why-grid">
        <div><strong>${direction.seats ?? "-"}</strong><span>бюджетных мест</span></div>
        <div><strong>${f.real_competitor_position ?? "-"}</strong><span>место по каскаду</span></div>
        <div><strong>${c.real_competitors_above ?? 0}</strong><span>реально впереди</span></div>
        <div><strong>${f.consent_position ?? "-"}</strong><span>место по согласиям</span></div>
        <div><strong>${c.leaving_by_cascade ?? 0}</strong><span>уходят выше</span></div>
        <div><strong>${c.waiting_without_consent ?? 0}</strong><span>без согласия выше</span></div>
      </div>
      <p>${passing ? "Сейчас заявление находится внутри числа бюджетных мест после расчета приоритетов. Остальные направления ниже по приоритету работают как резерв." : "Сейчас по расчету нужно, чтобы освободились места или изменилась картина согласий."}</p>
    </section>
  `;
}

function renderRiskNote() {
  return `
    <section class="card risk-note">
      <h3>Что может изменить ситуацию</h3>
      <ul>
        <li>новые согласия от людей выше в списке;</li>
        <li>обновление данных на Госуслугах;</li>
        <li>уточнение льготных, целевых и БВИ-позиций;</li>
        <li>изменение приоритетов, если оно доступно поступающим.</li>
      </ul>
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

function renderDirections(directions, prediction) {
  return `
    <h2 class="section-title">Направления</h2>
    <div class="directions">
      ${directions.map((item) => {
        const f = item.facts;
        const isSelected = prediction?.status === "passing" && prediction.group_id === item.group_id;
        const isReserve = prediction?.status === "passing" && !isSelected;
        const reservePasses = isReserve && (f.real_gap_to_budget ?? 9999) <= 0;
        const statusText = isSelected
          ? "основной проход"
          : reservePasses
            ? "резерв: проходит"
            : isReserve
              ? "резерв"
              : missingText(f.real_gap_to_budget);
        return `
          <article class="direction-card ${isSelected ? "direction-primary" : ""} ${isReserve ? "direction-reserve" : ""}">
            <div class="direction-head">
              <div>
                <h3>${item.name}</h3>
                <div class="sub">${item.okso_code || "ОКСО не указан"} · ${item.seats ?? "-"} мест на бюджете · приоритет ${f.priority ?? "-"}</div>
              </div>
              <span class="pill">${isSelected ? "основной" : isReserve ? "резерв" : `${item.chance?.cascade_percent ?? 1}%`}</span>
            </div>
            <div class="compact-metrics">
              <div class="metric"><strong>${f.position ?? "-"}</strong><span>общий список</span></div>
              <div class="metric"><strong>${f.consent_position ?? "-"}</strong><span>по согласиям</span></div>
              <div class="metric"><strong>${f.real_competitor_position ?? "-"}</strong><span>по каскаду</span></div>
              <div class="${reservePasses ? "metric status-pass status-reserve-pass" : isReserve ? "metric status-reserve" : statusMetricClass(f.real_gap_to_budget)}"><strong>${statusText}</strong><span>${reservePasses ? "если станет первым" : "Текущий расчёт"}</span></div>
            </div>
            <div class="direction-foot">
              <span>${isReserve ? "Резервное направление: будет актуально, если верхний приоритет не сработает." : directionStatus(item)} Перед заявлением: ${item.cascade?.real_competitors_above ?? 0} реально мешают, ${item.cascade?.leaving_by_cascade ?? 0} уходят выше, ${item.cascade?.waiting_without_consent ?? 0} без согласия.</span>
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
    <h2 class="section-title">Сравнение направлений</h2>
    <div class="charts-grid">
      <section class="chart-card">
        <h3>Кто реально мешает</h3>
        <div class="chart-box"><canvas id="chart-real"></canvas></div>
      </section>
      <section class="chart-card">
        <h3>Кто может добавить риск</h3>
        <div class="chart-box"><canvas id="chart-waiting"></canvas></div>
      </section>
      <section class="chart-card">
        <h3>Места в списках</h3>
        <div id="position-table" class="position-table"></div>
      </section>
      <section class="chart-card">
        <h3>Оценка устойчивости</h3>
        <div class="chart-box"><canvas id="chart-chance"></canvas></div>
      </section>
    </div>
  `;
}

function renderPositionTable(directions) {
  const target = document.getElementById("position-table");
  if (!target) return;
  target.innerHTML = `
    <div class="position-table-head">
      <span>Направление</span>
      <span>место в общем списке</span>
      <span>место среди согласий</span>
      <span>место по каскаду</span>
    </div>
    ${directions.map((item) => `
      <div class="position-table-row">
        <strong>${shortName(item.name)}</strong>
        <span>${item.facts.position ?? "-"}</span>
        <span>${item.facts.consent_position ?? "-"}</span>
        <span class="position-cascade">${item.facts.real_competitor_position ?? "-"}</span>
      </div>
    `).join("")}
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

  renderPositionTable(directions);

  chartInstances.push(new Chart(document.getElementById("chart-waiting"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "без согласия выше", data: directions.map((item) => item.cascade?.waiting_without_consent || 0), backgroundColor: "#4d8cff" },
      ],
    },
    options,
  }));

  chartInstances.push(new Chart(document.getElementById("chart-chance"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "устойчивость позиции, %", data: directions.map((item) => item.chance?.cascade_percent || 1), backgroundColor: colors[4] },
        { label: "при новых согласиях выше, %", data: directions.map((item) => item.chance?.stress_percent || 1), backgroundColor: colors[5] },
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
          <h2>Код ${data.application_id || ""} не найден</h2>
          <p>Ищем код поступающего, он же ID поступающего в конкурсных списках Госуслуг. Номер заявления, СНИЛС или другой длинный идентификатор может быть другим числом и по нему публичные списки не ищутся.</p>
        </div>
      </section>
    `;
    trackGoal("search_not_found");
    return;
  }

  trackGoal("search_found");
  const best = bestDirection(data.directions);
  const predictedDirection = data.prediction
    ? data.directions.find((item) => item.group_id === data.prediction.group_id) || best
    : best;
  result.hidden = false;
  result.innerHTML = `
    <section class="summary">
      <div>
        <h2>Код поступающего ${data.application_id}</h2>
        <p>${isAfterDeadline ? "Приём документов завершён. " : ""}${applicantSummary(data.directions)} Лучший текущий ориентир: ${best.name}, ${directionStatus(best)}.</p>
      </div>
      <div class="summary-meta">
        <span class="pill">${data.summary.directions_count} направл.</span>
        <span class="pill">Данные: ${fmtDate(data.data_updated_at)}</span>
        <span class="pill">${daysLeftText(data)}</span>
      </div>
    </section>
    ${renderPrediction(data.prediction)}
    ${renderWhyPasses(predictedDirection, data.prediction)}
    <div class="overview-grid">
      ${isAfterDeadline ? renderTerms() : renderChance(data, best)}
      ${renderRiskNote()}
    </div>
    ${renderDirections(data.directions, data.prediction)}
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
  const normalizedApplicationId = input.value.replace(/\D+/g, "");
  if (!normalizedApplicationId) {
    showMessage("Введите код поступающего цифрами.", true);
    return;
  }
  input.value = normalizedApplicationId;
  const button = form.querySelector("button");
  button.disabled = true;
  button.textContent = "Ищем";
  trackGoal("search_submitted");
  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ application_id: normalizedApplicationId }),
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

document.addEventListener("click", (event) => {
  const link = event.target.closest("[data-open-faq]");
  if (!link) return;
  const faq = document.querySelector(".faq-block");
  if (faq) faq.open = true;
});

document.addEventListener("click", (event) => {
  const link = event.target.closest(".direction-link");
  if (!link) return;
  trackGoal("direction_click");
});

loadMetrika();
loadStatus();
const currentDirectionId = directionPageId();
if (currentDirectionId) {
  loadDirectionPage(currentDirectionId);
} else {
  loadOverview();
}
