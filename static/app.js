// ============================
// State
// ============================
let currentData = null;
let currentTicker = "AAPL";
let currentPeriod = "1y";
let currentMarket = "US";
let currentNewsText = "";
let analysisContent = "";
let analysisType = "";
let analysisScore = 0;
let searchDebounceTimer = null;
let acSelectedIndex = -1;

// ============================
// Initialization
// ============================
document.addEventListener("DOMContentLoaded", () => {
  checkAuth();
  checkModelHealth();

  const tickerInput = document.getElementById("tickerInput");

  // 키보드 탐색: ↑/↓ 이동, Enter 선택/검색, Escape 닫기
  tickerInput.addEventListener("keydown", (e) => {
    const dropdown = document.getElementById("autocompleteDropdown");
    const items = dropdown.querySelectorAll(".autocomplete-item");
    const isOpen = dropdown.classList.contains("show") && items.length > 0;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (isOpen) {
        acSelectedIndex = Math.min(acSelectedIndex + 1, items.length - 1);
        updateAcHighlight(items);
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (isOpen) {
        acSelectedIndex = Math.max(acSelectedIndex - 1, 0);
        updateAcHighlight(items);
      }
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (isOpen && acSelectedIndex >= 0 && acSelectedIndex < items.length) {
        items[acSelectedIndex].click();
      } else {
        hideAutocomplete();
        loadStockData();
      }
    } else if (e.key === "Escape") {
      hideAutocomplete();
    }
  });

  // 자동완성: 입력 시 300ms debounce
  tickerInput.addEventListener("input", () => {
    acSelectedIndex = -1;
    clearTimeout(searchDebounceTimer);
    const q = tickerInput.value.trim();
    if (q.length < 1) {
      hideAutocomplete();
      return;
    }
    searchDebounceTimer = setTimeout(() => searchTicker(q), 300);
  });

  // 외부 클릭 시 자동완성 닫기
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".autocomplete-wrapper")) {
      hideAutocomplete();
    }
  });
});

function updateAcHighlight(items) {
  items.forEach((item, idx) => {
    item.classList.toggle("active", idx === acSelectedIndex);
  });
  // 선택된 항목이 보이도록 스크롤
  if (acSelectedIndex >= 0 && items[acSelectedIndex]) {
    items[acSelectedIndex].scrollIntoView({ block: "nearest" });
  }
}

// ============================
// Auth
// ============================
async function checkAuth() {
  try {
    const res = await fetch("/api/auth/me");
    const data = await res.json();
    if (data.logged_in) {
      document.getElementById("loggedOut").style.display = "none";
      document.getElementById("loggedIn").style.display = "flex";
      document.getElementById("userEmail").textContent = data.email;
    } else {
      document.getElementById("loggedOut").style.display = "block";
      document.getElementById("loggedIn").style.display = "none";
    }
  } catch (e) {}
}

async function logout() {
  try {
    await fetch("/api/auth/logout", { method: "POST" });
    document.getElementById("loggedOut").style.display = "block";
    document.getElementById("loggedIn").style.display = "none";
    document.getElementById("userEmail").textContent = "";
    showToast("로그아웃 되었습니다.", "info");
  } catch (e) {
    showToast("로그아웃 실패", "error");
  }
}

// ============================
// Market Change
// ============================
function onMarketChange() {
  currentMarket = document.getElementById("marketSelect").value;
  const tickerInput = document.getElementById("tickerInput");
  if (currentMarket === "KR") {
    tickerInput.placeholder = "종목명 또는 코드 (예: 삼성전자)";
    tickerInput.value = "";
  } else if (currentMarket === "HK") {
    tickerInput.placeholder = "종목명 또는 코드 (예: Tencent)";
    tickerInput.value = "";
  } else if (currentMarket === "SH") {
    tickerInput.placeholder = "종목명 또는 코드 (예: 贵州茅台)";
    tickerInput.value = "";
  } else {
    tickerInput.placeholder = "종목명 또는 티커 (예: AAPL)";
    tickerInput.value = "";
  }
  hideAutocomplete();
}

// ============================
// Autocomplete Search
// ============================
async function searchTicker(query) {
  const market = document.getElementById("marketSelect").value;
  try {
    const res = await fetch(
      `/api/stock/search?q=${encodeURIComponent(query)}&market=${market}`,
    );
    const data = await res.json();
    renderAutocomplete(data.results);
  } catch (e) {
    hideAutocomplete();
  }
}

function renderAutocomplete(results) {
  const dropdown = document.getElementById("autocompleteDropdown");
  if (!results || results.length === 0) {
    hideAutocomplete();
    return;
  }

  dropdown.innerHTML = results
    .map(
      (r) =>
        `<div class="autocomplete-item" onclick="selectTicker('${r.symbol}', '${r.name.replace(/'/g, "\\'")}')">
            <span class="ac-name">${r.name}</span>
            <span class="ac-symbol">${r.symbol}</span>
        </div>`,
    )
    .join("");
  dropdown.classList.add("show");
}

function selectTicker(symbol, name) {
  document.getElementById("tickerInput").value = symbol;
  currentTicker = symbol;
  hideAutocomplete();
  loadStockData();
}

function hideAutocomplete() {
  document.getElementById("autocompleteDropdown").classList.remove("show");
  acSelectedIndex = -1;
}

// ============================
// Stock Data
// ============================
async function loadStockData() {
  const tickerInput = document.getElementById("tickerInput");
  let ticker = tickerInput.value.trim();

  if (!ticker) {
    showToast("티커를 입력해주세요.", "error");
    return;
  }

  // 항상 DOM에서 현재 시장 값을 읽어 동기화
  currentMarket = document.getElementById("marketSelect").value;

  // 미국 시장인 경우 대문자 변환
  if (currentMarket === "US") {
    ticker = ticker.toUpperCase();
  }

  currentTicker = ticker;
  currentPeriod = document.getElementById("periodSelect").value;

  const btn = document.getElementById("searchBtn");
  setButtonLoading(btn, true);

  try {
    const [dataRes, newsRes] = await Promise.all([
      fetch(
        `/api/stock/data?symbol=${encodeURIComponent(ticker)}&period=${currentPeriod}`,
      ),
      fetch(`/api/stock/news?symbol=${encodeURIComponent(ticker)}`),
    ]);

    if (!dataRes.ok) {
      const err = await dataRes.json();
      throw new Error(err.detail || "데이터 로드 실패");
    }

    currentData = await dataRes.json();
    const newsData = await newsRes.json();

    // 타이틀 업데이트 (종목명 표시)
    const displayName = currentData.company_name || ticker;
    document.getElementById("mainTitle").textContent =
      `📈 ${displayName} (${ticker}) 실시간 차트 및 AI 분석`;

    renderChart(currentData);

    document.getElementById("currentPrice").textContent =
      currentData.current_price.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
    document.getElementById("currentRSI").textContent =
      currentData.current_rsi.toFixed(2);

    // 하모닉 패턴 지표 업데이트
    updatePatternIndicator(currentData.harmonic_pattern);

    renderNews(newsData.news);

    document.getElementById("aiAnalysisBtn").disabled = false;
    document.getElementById("dcfAnalysisBtn").disabled = false;
    document.getElementById("analysisResult").style.display = "none";

    showToast(`${ticker} 데이터 로드 완료`, "success");
  } catch (e) {
    showToast(e.message, "error");
  } finally {
    setButtonLoading(btn, false);
  }
}

// ============================
// Harmonic Pattern Indicator
// ============================
function updatePatternIndicator(pattern) {
  const typeEl = document.getElementById("patternType");
  const detailEl = document.getElementById("patternDetail");

  if (!pattern) {
    typeEl.textContent = "패턴 미감지";
    typeEl.className = "metric-value metric-sm";
    detailEl.textContent = "";
    return;
  }

  const label =
    pattern.type === "bullish" ? "📈 Bullish AB=CD" : "📉 Bearish AB=CD";
  typeEl.textContent = label;
  typeEl.className = `metric-value metric-sm ${pattern.type}`;
  detailEl.textContent = `C: ${pattern.c_retracement} / BC ext: ${pattern.bc_extension}\nAB≈CD: ${pattern.ab_cd_ratio} | 신뢰도: ${pattern.confidence}%`;
}

// ============================
// Chart Rendering (Plotly)
// ============================
function renderChart(data) {
  document.getElementById("chartPlaceholder").style.display = "none";
  document.getElementById("chart").style.display = "block";

  const candlestick = {
    x: data.dates,
    open: data.open,
    high: data.high,
    low: data.low,
    close: data.close,
    type: "candlestick",
    name: "Price",
    increasing: { line: { color: "#00cec9" } },
    decreasing: { line: { color: "#ff6b6b" } },
  };

  const upperBand = {
    x: data.dates,
    y: data.upper,
    type: "scatter",
    mode: "lines",
    name: "Upper Band",
    line: { color: "rgba(162, 155, 254, 0.4)", width: 1 },
  };

  const lowerBand = {
    x: data.dates,
    y: data.lower,
    type: "scatter",
    mode: "lines",
    name: "Lower Band",
    line: { color: "rgba(162, 155, 254, 0.4)", width: 1 },
    fill: "tonexty",
    fillcolor: "rgba(108, 92, 231, 0.05)",
  };

  const ma20 = {
    x: data.dates,
    y: data.ma20,
    type: "scatter",
    mode: "lines",
    name: "MA20",
    line: { color: "rgba(253, 203, 110, 0.6)", width: 1, dash: "dot" },
  };

  const traces = [candlestick, upperBand, lowerBand, ma20];

  // 하모닉 패턴 A→B→C→D 오버레이
  const annotations = [];
  const shapes = [];

  if (data.harmonic_pattern) {
    const p = data.harmonic_pattern;
    const pts = p.points;
    const lineColor =
      p.type === "bullish"
        ? "rgba(0, 206, 201, 0.8)"
        : "rgba(255, 107, 107, 0.8)";
    const fillColor =
      p.type === "bullish"
        ? "rgba(0, 206, 201, 0.08)"
        : "rgba(255, 107, 107, 0.08)";

    // A→B→C→D 연결선
    const harmonicLine = {
      x: pts.map((pt) => pt.date),
      y: pts.map((pt) => pt.price),
      type: "scatter",
      mode: "lines+markers",
      name: `AB=CD (${p.type})`,
      line: { color: lineColor, width: 2, dash: "dash" },
      marker: { size: 8, color: lineColor, symbol: "diamond" },
    };
    traces.push(harmonicLine);

    // 각 포인트에 라벨
    pts.forEach((pt) => {
      annotations.push({
        x: pt.date,
        y: pt.price,
        text: `<b>${pt.label}</b>`,
        showarrow: true,
        arrowhead: 0,
        arrowsize: 0.5,
        arrowcolor: lineColor,
        ax: 0,
        ay: pt.label === "A" || pt.label === "C" ? 30 : -30,
        font: { color: lineColor, size: 13, family: "Inter" },
        bgcolor: "rgba(15,15,26,0.8)",
        bordercolor: lineColor,
        borderwidth: 1,
        borderpad: 3,
      });
    });

    // PRZ 구간 (D 근처 반투명 직사각형)
    if (p.prz) {
      shapes.push({
        type: "rect",
        xref: "x",
        yref: "y",
        x0: pts[2].date,
        x1: pts[3].date,
        y0: p.prz.min,
        y1: p.prz.max,
        fillcolor: fillColor,
        opacity: 0.6,
        line: { color: lineColor, width: 1, dash: "dot" },
      });
    }
  }

  // 볼륨 스파이크 영역
  data.vol_spike_dates.forEach((d) => {
    shapes.push({
      type: "rect",
      xref: "x",
      yref: "paper",
      x0: d,
      x1: d,
      y0: 0,
      y1: 1,
      fillcolor: "rgba(253, 203, 110, 0.08)",
      opacity: 0.5,
      line: { width: 0 },
    });
  });

  const layout = {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { color: "#a0a0b8", family: "Inter, sans-serif", size: 11 },
    height: 480,
    margin: { t: 20, b: 40, l: 60, r: 20 },
    xaxis: {
      rangeslider: { visible: false },
      gridcolor: "rgba(255,255,255,0.03)",
      linecolor: "rgba(255,255,255,0.06)",
      tickcolor: "rgba(255,255,255,0.06)",
    },
    yaxis: {
      gridcolor: "rgba(255,255,255,0.03)",
      linecolor: "rgba(255,255,255,0.06)",
      tickcolor: "rgba(255,255,255,0.06)",
      side: "right",
    },
    showlegend: true,
    legend: {
      orientation: "h",
      y: -0.12,
      x: 0.5,
      xanchor: "center",
      font: { size: 10 },
    },
    shapes: shapes,
    annotations: annotations,
  };

  const config = {
    responsive: true,
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"],
  };

  Plotly.newPlot("chart", traces, layout, config);
}

// ============================
// News
// ============================
function renderNews(news) {
  const container = document.getElementById("newsList");

  if (!news || news.length === 0) {
    container.innerHTML =
      '<p class="placeholder-text">최근 주요 뉴스가 없습니다.</p>';
    currentNewsText = "최근 주요 뉴스가 없습니다.";
    return;
  }

  container.innerHTML = news
    .map(
      (item) =>
        `<a href="${item.link}" target="_blank" rel="noopener" class="news-item">${item.title}</a>`,
    )
    .join("");

  currentNewsText = news
    .map((item) => `- [${item.title}](${item.link})`)
    .join("\n");
}

// ============================
// LLM Model Health Check
// ============================
async function checkModelHealth() {
  const modelSelect = document.getElementById("modelSelect");
  if (!modelSelect) return;

  modelSelect.disabled = true;
  modelSelect.innerHTML = `<option value="">⏳ Checking model status...</option>`;

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 4000); // 4초 타임아웃 설정

    const res = await fetch("/api/analysis/model-health", { signal: controller.signal });
    clearTimeout(timeoutId);

    if (!res.ok) throw new Error("모델 상태를 가져오지 못했습니다.");

    const data = await res.json();
    modelSelect.innerHTML = data.models.map(m => {
      let statusColorEmoji = "🔴";
      let statusText = "Busy";
      if (m.status === "fast") {
        statusColorEmoji = "🟢";
        statusText = "Fast";
      } else if (m.status === "normal") {
        statusColorEmoji = "🟡";
        statusText = "Normal";
      }
      return `<option value="${m.id}">${m.label} (${statusColorEmoji} ${statusText}, ${m.latency.toLocaleString()}ms)</option>`;
    }).join("");

    modelSelect.value = data.recommended;
    modelSelect.disabled = false;
  } catch (e) {
    modelSelect.innerHTML = `
      <option value="gemini-3.5-flash">🚀 gemini-3.5-flash (🟢 Fast, Fallback)</option>
      <option value="gemini-3.1-pro">💡 gemini-3.1-pro (🟢 Fast, Fallback)</option>
      <option value="gemini-3.1-flash-lite">⚡ gemini-3.1-flash-lite (🟢 Fast, Fallback)</option>
      <option value="gemini-2.5-flash" selected>⚙️ gemini-2.5-flash (🟢 Fast, Fallback)</option>
    `;
    modelSelect.disabled = false;
    showToast("모델 상태 체크 실패. 기본값으로 설정합니다.", "warning");
  }
}

function onModelChange() {
  const modelSelect = document.getElementById("modelSelect");
  showToast(`선택된 모델: ${modelSelect.value}`, "info");
}

function setAnalysisUIState(isLoading) {
  const aiBtn = document.getElementById("aiAnalysisBtn");
  const dcfBtn = document.getElementById("dcfAnalysisBtn");
  const modelSelect = document.getElementById("modelSelect");

  if (aiBtn) aiBtn.disabled = isLoading;
  if (dcfBtn) dcfBtn.disabled = isLoading;
  if (modelSelect) modelSelect.disabled = isLoading;
}

// ============================
// AI Analysis (SSE Streaming)
// ============================
async function runAnalysis(type) {
  const btnId = type === "ai" ? "aiAnalysisBtn" : "dcfAnalysisBtn";
  const btn = document.getElementById(btnId);
  setButtonLoading(btn, true);

  setAnalysisUIState(true);

  // 분석 결과 숨기기, 진행 표시 보이기
  document.getElementById("analysisResult").style.display = "none";
  const progressDiv = document.getElementById("analysisProgress");
  const stepsDiv = document.getElementById("progressSteps");
  progressDiv.style.display = "block";
  stepsDiv.innerHTML = "";

  // SSE 엔드포인트 구성
  const endpoint =
    type === "ai" ? "/api/analysis/ai/stream" : "/api/analysis/dcf/stream";
  const modelSelect = document.getElementById("modelSelect");
  const params = new URLSearchParams({
    symbol: currentTicker,
    period: currentPeriod,
    model: modelSelect ? modelSelect.value : "gemini-2.5-flash",
    ...(type === "ai" ? { news_text: currentNewsText } : {}),
  });

  const url = `${endpoint}?${params.toString()}`;
  const stepElements = {};

  try {
    const eventSource = new EventSource(url);

    eventSource.addEventListener("step", (e) => {
      const data = JSON.parse(e.data);
      const stepId = `step-${data.step}`;

      if (data.status === "running") {
        // 새 단계 추가
        const stepEl = document.createElement("div");
        stepEl.className = "progress-step";
        stepEl.id = stepId;
        stepEl.innerHTML = `
                    <div class="step-icon running">⏳</div>
                    <span class="step-label active">${data.label}</span>
                `;
        stepsDiv.appendChild(stepEl);
        stepElements[data.step] = stepEl;
      } else if (data.status === "done") {
        const stepEl =
          stepElements[data.step] || document.getElementById(stepId);
        if (stepEl) {
          const icon = stepEl.querySelector(".step-icon");
          const label = stepEl.querySelector(".step-label");
          icon.className = "step-icon done";
          icon.textContent = "✓";
          label.className = "step-label";
          label.textContent = data.label;
          // 경과 시간 표시
          if (data.elapsed !== undefined) {
            const elapsedEl = document.createElement("span");
            elapsedEl.className = "step-elapsed";
            elapsedEl.textContent = `${data.elapsed}s`;
            stepEl.appendChild(elapsedEl);
          }
        }
      }
    });

    eventSource.addEventListener("result", (e) => {
      eventSource.close();
      const result = JSON.parse(e.data);
      analysisContent = result.content;
      analysisType = result.analysis_type;
      analysisScore = result.confidence_score;

      // 결과 표시
      const resultDiv = document.getElementById("analysisResult");
      resultDiv.style.display = "block";

      const title = type === "ai" ? "일반 AI 분석" : "DCF 전문 분석";
      const timeText = result.total_elapsed
        ? ` (${result.total_elapsed}s)`
        : "";
      document.getElementById("resultBadge").innerHTML =
        `<span>📊</span> [${title}] 신뢰도: ${analysisScore}점${timeText}`;

      document.getElementById("resultContent").innerHTML =
        marked.parse(analysisContent);
      showToast("분석 완료!", "success");
      resultDiv.scrollIntoView({ behavior: "smooth", block: "start" });

      // 차트에 가격 라인 추가
      if (result.price_levels) {
        addPriceLinesToChart(result.price_levels, result.analysis_type);
      }

      setButtonLoading(btn, false);
      setAnalysisUIState(false);
    });

    eventSource.addEventListener("error", (e) => {
      eventSource.close();
      try {
        const data = JSON.parse(e.data);
        showToast(data.message || "분석 실패", "error");
      } catch {
        showToast("분석 중 연결 오류 발생", "error");
      }
      progressDiv.style.display = "none";
      setButtonLoading(btn, false);
      setAnalysisUIState(false);
    });

    eventSource.onerror = () => {
      // EventSource가 완료 후 자동 재연결 시도하면 닫기
      if (eventSource.readyState === EventSource.CLOSED) return;
      eventSource.close();
      setButtonLoading(btn, false);
      setAnalysisUIState(false);
    };
  } catch (e) {
    showToast(e.message || "분석 실패", "error");
    progressDiv.style.display = "none";
    setButtonLoading(btn, false);
    setAnalysisUIState(false);
  }
}

// ============================
// Telegram
// ============================
async function sendTelegram() {
  if (!analysisContent) {
    showToast("먼저 분석을 실행해주세요.", "error");
    return;
  }

  const title = analysisType === "AI" ? "일반 AI 분석" : "DCF 전문 분석";
  const message = `**[${title}] ${currentTicker} 분석 결과**\n\n${analysisContent}`;

  try {
    const res = await fetch("/api/telegram/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    const result = await res.json();
    if (result.success) {
      showToast("텔레그램으로 전송되었습니다!", "success");
    } else {
      showToast(`전송 실패: ${result.message}`, "error");
    }
  } catch (e) {
    showToast("텔레그램 전송 중 오류 발생", "error");
  }
}

// ============================
// Chart Price Lines (Analysis)
// ============================
function addPriceLinesToChart(priceLevels, analysisType) {
  const chartEl = document.getElementById('chart');
  if (!chartEl || !chartEl.layout) return;

  // 이전 분석 라인/라벨 제거 (analysis- 접두어로 식별)
  const existingShapes = (chartEl.layout.shapes || []).filter(
    s => !s._analysisLine
  );
  const existingAnnotations = (chartEl.layout.annotations || []).filter(
    a => !a._analysisLine
  );

  const newShapes = [...existingShapes];
  const newAnnotations = [...existingAnnotations];

  const lineConfigs = analysisType === 'DCF'
    ? [
        { key: 'dcf_fair_value', label: 'DCF 적정가', color: '#ffd700', dash: 'solid' },
        { key: 'bull_value',     label: '강세 적정가', color: '#00cec9', dash: 'dot' },
        { key: 'bear_value',     label: '약세 적정가', color: '#ff6b6b', dash: 'dot' },
      ]
    : [
        { key: 'entry',     label: '진입가',      color: '#ffd700', dash: 'solid' },
        { key: 'target1',   label: '1차 목표가',   color: '#00cec9', dash: 'dash' },
        { key: 'target2',   label: '2차 목표가',   color: '#55efc4', dash: 'dash' },
        { key: 'stop_loss', label: '손절가',       color: '#ff6b6b', dash: 'solid' },
      ];

  for (const cfg of lineConfigs) {
    const price = priceLevels[cfg.key];
    if (price == null || isNaN(price)) continue;

    // 수평 가격 라인
    newShapes.push({
      type: 'line',
      xref: 'paper',
      yref: 'y',
      x0: 0, x1: 1,
      y0: price, y1: price,
      line: { color: cfg.color, width: 1.5, dash: cfg.dash },
      _analysisLine: true
    });

    // 우측 가격 라벨
    newAnnotations.push({
      xref: 'paper',
      yref: 'y',
      x: 1.0,
      y: price,
      text: `${cfg.label} ${price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`,
      showarrow: false,
      xanchor: 'right',
      font: { color: cfg.color, size: 10, family: 'Inter' },
      bgcolor: 'rgba(15,15,26,0.85)',
      borderpad: 3,
      bordercolor: cfg.color,
      borderwidth: 1,
      _analysisLine: true
    });
  }

  Plotly.relayout('chart', {
    shapes: newShapes,
    annotations: newAnnotations
  });
}

// ============================
// UI Helpers
// ============================
function setButtonLoading(btn, loading) {
  const textEl = btn.querySelector(".btn-text");
  const loaderEl = btn.querySelector(".btn-loader");

  if (loading) {
    if (textEl) textEl.style.display = "none";
    if (loaderEl) loaderEl.style.display = "inline-block";
    btn.disabled = true;
  } else {
    if (textEl) textEl.style.display = "inline";
    if (loaderEl) loaderEl.style.display = "none";
    btn.disabled = false;
  }
}

function showToast(message, type = "info") {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.className = `toast ${type} show`;

  setTimeout(() => {
    toast.classList.remove("show");
  }, 3000);
}

function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  sidebar.classList.toggle("open");
}

// 사이드바 외부 클릭 시 닫기 (모바일)
document.addEventListener("click", (e) => {
  const sidebar = document.getElementById("sidebar");
  const toggle = document.getElementById("sidebarToggle");

  if (
    window.innerWidth <= 768 &&
    sidebar.classList.contains("open") &&
    !sidebar.contains(e.target) &&
    !toggle.contains(e.target)
  ) {
    sidebar.classList.remove("open");
  }
});
