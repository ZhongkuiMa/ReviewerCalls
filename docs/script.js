/**
 * ReviewerCalls - Main Site Script
 * Loads calls.json and renders sortable/filterable/searchable table via Grid.js
 */

(function () {
  "use strict";

  let grid = null;
  let allData = [];
  const nowrapStyle = { "white-space": "nowrap" };

  /* ==================== GitHub Stars ==================== */

  /**
   * Fetch GitHub stars count and update button
   */
  async function loadGitHubStars() {
    try {
      const response = await fetch("https://api.github.com/repos/ZhongkuiMa/ReviewerCalls", {
        headers: {
          "Accept": "application/vnd.github.v3+json"
        }
      });

      if (response.ok) {
        const data = await response.json();
        const stars = data.stargazers_count;
        const button = document.querySelector(".github-star-button");

        if (button && stars) {
          // Format stars (e.g., 1200 -> 1.2k)
          let starDisplay = stars.toString();
          if (stars >= 1000) {
            starDisplay = (stars / 1000).toFixed(1).replace(/\.0$/, "") + "k";
          } else if (stars >= 100) {
            starDisplay = stars.toString();
          }

          button.textContent = `⭐ ${starDisplay}`;
          button.setAttribute("title", `${stars} stars on GitHub - Star this project!`);
        }
      }
    } catch (error) {
      console.debug("Could not fetch GitHub stars:", error);
      // Silently fail - button will show default text
    }
  }

  /* ==================== Theme Management ==================== */

  /**
   * Initialize theme from localStorage or system preference
   */
  function initTheme() {
    const saved = localStorage.getItem("rc-theme");
    if (saved) {
      document.documentElement.setAttribute("data-theme", saved);
    }
    updateToggleIcon();
  }

  /**
   * Toggle between light and dark theme
   */
  function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("rc-theme", next);
    updateToggleIcon();
  }

  /**
   * Update theme toggle button icon
   */
  function updateToggleIcon() {
    const btn = document.getElementById("theme-toggle");
    if (!btn) return;
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    btn.textContent = isDark ? "\u2600" : "\u263E";
  }

  /* ==================== UI Components ==================== */

  /**
   * Generate badge HTML for rank display
   * @param {string} rank - Rank value (A, B, C, A*, etc.)
   * @returns {string} Badge HTML
   */
  function rankBadge(rank) {
    if (!rank || rank === "-") {
      return '<span class="badge badge-none">-</span>';
    }
    const cls = rank.startsWith("A") ? "badge-a" : rank === "B" ? "badge-b" : "badge-c";
    return `<span class="badge ${cls}">${rank}</span>`;
  }

  /**
   * Check if a call is new (added within last 7 days)
   * @param {string} dateStr - Date string in YYYY-MM format
   * @returns {boolean}
   */
  function isNew(dateStr) {
    if (!dateStr) return false;
    const callDate = new Date(`${dateStr}-01`);
    const today = new Date();
    const ageInDays = (today - callDate) / (1000 * 60 * 60 * 24);
    return ageInDays <= 7;
  }

  /* ==================== Filters ==================== */

  /**
   * Populate filter dropdown with unique values from data
   * @param {string} selectId - Select element ID
   * @param {Array} data - Data array
   * @param {string} key - Data property key
   */
  function populateFilter(selectId, data, key) {
    const select = document.getElementById(selectId);
    const values = [...new Set(data.map((d) => d[key]))].filter(Boolean).sort();

    // Special handling for area filter: show "CODE - Full Name"
    if (selectId === "filter-area") {
      const areaMap = {};
      data.forEach((call) => {
        if (call.area_code && call.area) {
          areaMap[call.area_code] = call.area;
        }
      });

      values.forEach((v) => {
        const opt = document.createElement("option");
        opt.value = v;
        opt.textContent = areaMap[v] ? `${v} - ${areaMap[v]}` : v;
        select.appendChild(opt);
      });
    } else {
      values.forEach((v) => {
        const opt = document.createElement("option");
        opt.value = v;
        opt.textContent = v;
        select.appendChild(opt);
      });
    }
  }

  /**
   * Get current filter values from UI
   * @returns {Object} Filter values
   */
  function getFilters() {
    return {
      area: document.getElementById("filter-area").value,
      ccf: document.getElementById("filter-ccf").value,
      core: document.getElementById("filter-core").value,
      role: document.getElementById("filter-role").value,
    };
  }

  /**
   * Check if any filters are currently active
   * @returns {boolean}
   */
  function hasActiveFilters() {
    const f = getFilters();
    return !!(f.area || f.ccf || f.core || f.role);
  }

  /**
   * Update visibility of clear filters button
   */
  function updateClearButton() {
    const btn = document.getElementById("clear-filters");
    if (btn) {
      btn.style.display = hasActiveFilters() ? "block" : "none";
    }
  }

  /**
   * Clear all filter selections
   */
  function clearAllFilters() {
    ["filter-area", "filter-ccf", "filter-core", "filter-role"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.value = "";
    });
    updateTable();
  }

  /**
   * Filter data based on current filter selections
   * @returns {Array} Filtered data
   */
  function filteredData() {
    const f = getFilters();
    return allData.filter((d) => {
      if (f.area && d.area_code !== f.area) return false;
      if (f.ccf && d.ccf !== f.ccf) return false;
      if (f.core && d.core !== f.core) return false;
      if (f.role && d.role !== f.role) return false;
      return true;
    });
  }

  /**
   * Convert data to Grid.js row format
   * @param {Array} data - Data array
   * @returns {Array} Grid.js rows
   */
  function toGridRows(data) {
    return data.map((d) => [
      { abbr: d.conference, date: d.date },
      d.name,
      d.area_code,
      d.date,
      d.ccf,
      d.core,
      { role: d.role, url: d.url }
    ]);
  }

  /* ==================== URL Management ==================== */

  /**
   * Sync filter state to URL query parameters
   */
  function filtersToUrl() {
    const f = getFilters();
    const params = new URLSearchParams();
    if (f.area) params.set("area", f.area);
    if (f.ccf) params.set("ccf", f.ccf);
    if (f.core) params.set("core", f.core);
    if (f.role) params.set("role", f.role);
    const qs = params.toString();
    const url = qs ? `?${qs}` : window.location.pathname;
    history.replaceState(null, "", url);
  }

  /**
   * Read filter state from URL query parameters
   */
  function urlToFilters() {
    const params = new URLSearchParams(window.location.search);
    ["area", "ccf", "core", "role"].forEach((key) => {
      const val = params.get(key);
      if (val) {
        const select = document.getElementById(`filter-${key}`);
        if (select) select.value = val;
      }
    });
  }

  /* ==================== Stats & UI Updates ==================== */

  /**
   * Update stats banner with current data counts
   * @param {Array} data - Current filtered data
   */
  function updateStats(data) {
    const banner = document.getElementById("stats-banner");
    if (!banner) return;
    const confs = new Set(data.map((d) => d.conference));
    const areas = new Set(data.map((d) => d.area_code));
    banner.innerHTML = `<strong>${data.length}</strong> active call${data.length !== 1 ? "s" : ""} ` +
      `across <strong>${confs.size}</strong> conference${confs.size !== 1 ? "s" : ""} ` +
      `in <strong>${areas.size}</strong> area${areas.size !== 1 ? "s" : ""}`;
  }

  /**
   * Display last updated date
   * @param {string} dateStr - ISO date string
   */
  function showLastUpdated(dateStr) {
    const el = document.getElementById("last-updated");
    if (!el || !dateStr) return;
    const d = new Date(`${dateStr}T00:00:00`);
    const formatted = d.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric"
    });
    el.textContent = `Last updated: ${formatted}`;
  }

  /**
   * Get current page size from selector
   * @returns {number} Page size
   */
  function getPageSize() {
    const el = document.getElementById("page-size");
    return el ? parseInt(el.value, 10) : 20;
  }

  /**
   * Handle page size change event
   */
  function onPageSizeChange() {
    const data = filteredData();
    grid.updateConfig({
      data: toGridRows(data),
      pagination: { limit: getPageSize() },
    }).forceRender();
  }

  /**
   * Update table with current filter state
   */
  function updateTable() {
    const data = filteredData();
    grid.updateConfig({ data: toGridRows(data) }).forceRender();
    updateStats(data);
    updateClearButton();
    filtersToUrl();

    const emptyState = document.getElementById("empty-state");
    if (emptyState) {
      emptyState.hidden = data.length > 0;
    }
  }

  /* ==================== Data Loading ==================== */

  const CACHE_KEY = "rc-calls-cache";
  const CACHE_DURATION = 30 * 60 * 1000; // 30 minutes
  const FETCH_TIMEOUT = 10000; // 10 seconds

  /**
   * Get cached data from localStorage if still valid
   * @returns {Object|null} Cached data or null
   */
  function getCachedData() {
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      if (!cached) return null;
      const { data, timestamp } = JSON.parse(cached);
      if (Date.now() - timestamp > CACHE_DURATION) {
        localStorage.removeItem(CACHE_KEY);
        return null;
      }
      return data;
    } catch (e) {
      console.warn("Failed to read cache:", e);
      return null;
    }
  }

  /**
   * Save data to localStorage cache
   * @param {Object} data - Data to cache
   */
  function setCachedData(data) {
    try {
      const cacheEntry = {
        data: data,
        timestamp: Date.now()
      };
      localStorage.setItem(CACHE_KEY, JSON.stringify(cacheEntry));
    } catch (e) {
      console.warn("Failed to write cache:", e);
    }
  }

  /**
   * Fetch data with timeout
   * @param {string} url - URL to fetch
   * @param {number} timeout - Timeout in milliseconds
   * @returns {Promise<Response>}
   */
  async function fetchWithTimeout(url, timeout) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(url, { signal: controller.signal });
      clearTimeout(timeoutId);
      return response;
    } catch (e) {
      clearTimeout(timeoutId);
      throw e;
    }
  }

  /* ==================== Initialization ==================== */

  /**
   * Initialize application
   */
  async function init() {
    initTheme();

    const toggleBtn = document.getElementById("theme-toggle");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", toggleTheme);
    }

    const loadingState = document.getElementById("loading-state");
    const emptyState = document.getElementById("empty-state");

    // Try cache first
    let payload = getCachedData();
    if (payload) {
      console.log("Using cached data");
      if (loadingState) loadingState.style.display = "none";
    } else {
      // Fetch from network
      try {
        const resp = await fetchWithTimeout("calls.json", FETCH_TIMEOUT);
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
        }
        payload = await resp.json();
        setCachedData(payload);
      } catch (e) {
        console.error("Failed to load calls.json:", e);
        if (loadingState) loadingState.style.display = "none";

        const isTimeout = e.name === "AbortError";
        const errorMsg = isTimeout
          ? "Request timed out. Please check your connection and <a href=\"#\" onclick=\"location.reload(); return false;\">try again</a>."
          : "Failed to load data. Please <a href=\"#\" onclick=\"location.reload(); return false;\">refresh the page</a> or try again later.";

        emptyState.innerHTML = `<p>${errorMsg}</p>`;
        emptyState.hidden = false;
        return;
      }

      if (loadingState) loadingState.style.display = "none";
    }

    allData = Array.isArray(payload) ? payload : payload.calls || [];

    if (!Array.isArray(payload) && payload.updated) {
      showLastUpdated(payload.updated);
    }

    if (allData.length === 0) {
      document.getElementById("empty-state").hidden = false;
      return;
    }

    populateFilter("filter-area", allData, "area_code");
    populateFilter("filter-role", allData, "role");
    urlToFilters();
    updateStats(filteredData());
    updateClearButton();

    grid = new gridjs.Grid({
      columns: [
        {
          name: "Abbr",
          width: "170px",
          attributes: { "data-column": "0", style: nowrapStyle },
          formatter: (cell) => {
            if (!cell || !cell.abbr) return cell;
            const badge = isNew(cell.date)
              ? '<span class="badge-new">NEW</span>'
              : '';
            return gridjs.html(`${cell.abbr}${badge}`);
          },
        },
        {
          name: "Conference",
          attributes: { "data-column": "1" }
        },
        {
          name: "Area",
          attributes: { "data-column": "2" }
        },
        {
          name: "Date",
          attributes: { "data-column": "3", style: nowrapStyle }
        },
        {
          name: "CCF",
          attributes: { "data-column": "4", style: nowrapStyle },
          formatter: (cell) => gridjs.html(rankBadge(cell)),
        },
        {
          name: "CORE",
          attributes: { "data-column": "5", style: nowrapStyle },
          formatter: (cell) => gridjs.html(rankBadge(cell)),
        },
        {
          name: "Role",
          attributes: { "data-column": "6", style: nowrapStyle },
          formatter: (cell) => {
            if (!cell || !cell.url) return cell.role || "";
            return gridjs.html(
              `<a href="${cell.url}"
                  class="role-link"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="View ${cell.role} call (opens in new tab)">
                ${cell.role}<span class="external-icon" aria-hidden="true">↗</span>
              </a>`
            );
          },
        },
      ],
      data: toGridRows(filteredData()),
      search: true,
      sort: true,
      pagination: { limit: getPageSize() },
      language: {
        search: { placeholder: "Search conferences..." },
        pagination: {
          showing: "Showing",
          results: () => "calls",
        },
      },
    });

    grid.render(document.getElementById("calls-table"));

    ["filter-area", "filter-ccf", "filter-core", "filter-role"].forEach((id) => {
      document.getElementById(id).addEventListener("change", updateTable);
    });

    const clearBtn = document.getElementById("clear-filters");
    if (clearBtn) {
      clearBtn.addEventListener("click", clearAllFilters);
    }

    const pageSizeEl = document.getElementById("page-size");
    if (pageSizeEl) {
      pageSizeEl.addEventListener("change", onPageSizeChange);
    }

    // Load GitHub stars count
    loadGitHubStars();
  }

  init();
})();
