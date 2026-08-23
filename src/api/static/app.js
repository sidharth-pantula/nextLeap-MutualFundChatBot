/**
 * Groww Mutual Fund FAQ Assistant - Client Application Logic
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Element References
  const chatForm = document.getElementById("chatForm");
  const queryInput = document.getElementById("queryInput");
  const sendBtn = document.getElementById("sendBtn");
  const clearChatBtn = document.getElementById("clearChatBtn");
  const messageThread = document.getElementById("messageThread");
  const chatFeed = document.getElementById("chatFeed");
  const heroWelcomeCard = document.getElementById("heroWelcomeCard");
  const typingIndicator = document.getElementById("typingIndicator");
  const schemeList = document.getElementById("schemeList");
  const themeToggleBtn = document.getElementById("themeToggleBtn");
  const chipsGrid = document.getElementById("chipsGrid");

  let isGenerating = false;
  let activeSchemeId = null;

  // ============================================================================
  // 1. Theme Management (Dark / Light)
  // ============================================================================
  const savedTheme = localStorage.getItem("groww_faq_theme") || "dark";
  document.documentElement.setAttribute("data-theme", savedTheme);

  themeToggleBtn.addEventListener("click", () => {
    const currentTheme = document.documentElement.getAttribute("data-theme");
    const newTheme = currentTheme === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", newTheme);
    localStorage.setItem("groww_faq_theme", newTheme);
  });

  // ============================================================================
  // 2. Fetch and Render Covered Schemes (Left Sidebar)
  // ============================================================================
  async function loadSchemes() {
    try {
      const res = await fetch("/api/schemes");
      if (!res.ok) throw new Error("Failed to load schemes");
      const schemes = await res.json();
      renderSchemeCards(schemes);
    } catch (err) {
      schemeList.innerHTML = `<div style="font-size:0.75rem; color:var(--text-muted); padding:10px;">Failed to load schemes.</div>`;
    }
  }

  function renderSchemeCards(schemes) {
    if (!schemes || schemes.length === 0) return;
    schemeList.innerHTML = "";

    schemes.forEach((s) => {
      const card = document.createElement("div");
      card.className = "scheme-card";
      card.dataset.schemeId = s.id;

      const nav = s.attributes?.current_nav || "N/A";
      const expense = s.attributes?.expense_ratio || "0.75%";
      const cleanExpense = expense.split("(")[0].trim();

      card.innerHTML = `
        <div class="scheme-name">${escapeHtml(s.name)}</div>
        <div class="scheme-meta-row">
          <span class="category-tag">${escapeHtml(s.category)}</span>
          <span class="nav-badge">NAV: ${escapeHtml(nav)}</span>
        </div>
        <div class="scheme-card-footer">
          <span class="scheme-stat">Expense: ${escapeHtml(cleanExpense)}</span>
          <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer" class="scheme-link-icon" title="Open official Groww page" onclick="event.stopPropagation()">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/></svg>
          </a>
        </div>
      `;

      card.addEventListener("click", () => {
        // Populate sample question for this scheme
        queryInput.value = `What is the expense ratio and exit load of ${s.name}?`;
        queryInput.focus();
      });

      schemeList.appendChild(card);
    });
  }

  // ============================================================================
  // 3. Handle Question Chips
  // ============================================================================
  chipsGrid.addEventListener("click", (e) => {
    const chip = e.target.closest(".query-chip");
    if (!chip) return;
    const query = chip.dataset.query;
    if (query) {
      queryInput.value = query;
      submitQuery(query);
    }
  });

  // ============================================================================
  // 4. Chat Submission & API Interaction
  // ============================================================================
  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query || isGenerating) return;
    submitQuery(query);
  });

  async function submitQuery(query) {
    // Hide Hero section once first message is submitted
    if (heroWelcomeCard) {
      heroWelcomeCard.style.display = "none";
    }

    // Append User Message
    appendUserMessage(query);
    queryInput.value = "";
    setGeneratingState(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query, scheme_id: activeSchemeId })
      });

      if (!response.ok) {
        throw new Error(`Server returned status: ${response.status}`);
      }

      const data = await response.json();
      appendAssistantMessage(data);
    } catch (error) {
      appendAssistantMessage({
        answer: "A network error occurred while connecting to the assistant. Please ensure the backend server is active and try again.\n\nSource: https://groww.in/mutual-funds\nLast updated from sources: 2026-08-23",
        source_url: "https://groww.in/mutual-funds",
        last_updated: "2026-08-23",
        is_refusal: true
      });
    } finally {
      setGeneratingState(false);
      queryInput.focus();
    }
  }

  function appendUserMessage(text) {
    const msg = document.createElement("div");
    msg.className = "message-user";
    msg.textContent = text;
    messageThread.appendChild(msg);
    scrollToBottom();
  }

  function appendAssistantMessage(data) {
    const card = document.createElement("div");
    card.className = `message-assistant ${data.is_refusal ? "is-refusal" : ""}`;

    // Extract body before Source & Last updated lines
    const rawAnswer = data.answer || "";
    const lines = rawAnswer.split("\n");
    const bodyLines = lines.filter(l => !l.startsWith("Source:") && !l.startsWith("Last updated from sources:"));
    const bodyText = bodyLines.join(" ").trim();

    const sourceUrl = data.source_url || "https://groww.in/mutual-funds";
    const lastUpdated = data.last_updated || "2026-08-23";

    const badgeLabel = data.is_refusal 
      ? "Refusal / Compliance Notice"
      : "Verified from Groww Scheme Data";
    const badgeClass = data.is_refusal ? "refusal-badge" : "";

    card.innerHTML = `
      <div class="assistant-header-row">
        <div class="assistant-tag-group">
          <span class="compliance-badge ${badgeClass}">${badgeLabel}</span>
        </div>
        <button class="btn-copy" title="Copy text to clipboard">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
        </button>
      </div>

      <div class="message-body">${escapeHtml(bodyText)}</div>

      <div class="message-footer-meta">
        <a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer" class="citation-chip" title="View Source Factsheet">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
          <span>Source: ${escapeHtml(formatUrlName(sourceUrl))}</span>
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/></svg>
        </a>
        <span class="timestamp-footer">Last updated from sources: ${escapeHtml(lastUpdated)}</span>
      </div>
    `;

    // Copy to clipboard handler
    const copyBtn = card.querySelector(".btn-copy");
    copyBtn.addEventListener("click", () => {
      navigator.clipboard.writeText(rawAnswer).then(() => {
        copyBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#00D09C" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`;
        setTimeout(() => {
          copyBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`;
        }, 1800);
      });
    });

    messageThread.appendChild(card);
    scrollToBottom();
  }

  // ============================================================================
  // 5. Utility & Helpers
  // ============================================================================
  function setGeneratingState(state) {
    isGenerating = state;
    sendBtn.disabled = state;
    typingIndicator.style.display = state ? "flex" : "none";
    if (state) scrollToBottom();
  }

  function scrollToBottom() {
    setTimeout(() => {
      chatFeed.scrollTop = chatFeed.scrollHeight;
    }, 50);
  }

  function formatUrlName(url) {
    if (!url) return "Official Source";
    if (url.includes("hdfc-mid-cap-fund")) return "HDFC Mid Cap Groww Page";
    if (url.includes("hdfc-small-cap-fund")) return "HDFC Small Cap Groww Page";
    if (url.includes("hdfc-nifty-50-index")) return "HDFC Nifty 50 Groww Page";
    if (url.includes("hdfc-nifty-next-50")) return "HDFC Next 50 Groww Page";
    if (url.includes("hdfc-multi-cap-fund")) return "HDFC Multi Cap Groww Page";
    if (url.includes("sebi.gov.in")) return "SEBI Investor Portal";
    if (url.includes("amfiindia.com")) return "AMFI Investor Portal";
    return url.replace(/^https?:\/\//, "");
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  clearChatBtn.addEventListener("click", () => {
    messageThread.innerHTML = "";
    if (heroWelcomeCard) {
      heroWelcomeCard.style.display = "block";
    }
  });

  // Initial Load
  loadSchemes();
});
