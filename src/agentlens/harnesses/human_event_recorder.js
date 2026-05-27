/**
 * AgentLens Human Event Recorder
 *
 * Injected into pages during human VNC sessions via Playwright's
 * context.add_init_script(). Captures user interactions and stores
 * them for the HumanVNCActor to collect.
 *
 * Security: Uses safe DOM APIs only (createElement, textContent,
 * setAttribute). No innerHTML assignments.
 */
(() => {
  if (window.__agentlens_human_recorder_ready) return;
  window.__agentlens_human_recorder_ready = true;

  // ── Event storage ──────────────────────────────────────────────
  window.__agentlens_human_events = [];
  window.__agentlens_human_answer = null;
  window.__agentlens_human_done = false;
  window.__agentlens_human_start_time = Date.now();

  function recordEvent(type, detail) {
    window.__agentlens_human_events.push({
      type: type,
      timestamp: new Date().toISOString(),
      elapsed_ms: Date.now() - window.__agentlens_human_start_time,
      url: window.location.href,
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
      },
      ...detail,
    });
  }

  // ── Click recording ────────────────────────────────────────────
  document.addEventListener(
    "mousedown",
    (e) => {
      // Ignore clicks on our overlay
      if (e.target.closest && e.target.closest("#agentlens-overlay")) return;
      recordEvent("click", {
        x: e.clientX,
        y: e.clientY,
        page_x: e.pageX,
        page_y: e.pageY,
        button: e.button === 0 ? "left" : e.button === 2 ? "right" : "middle",
        target_tag: e.target.tagName || "",
        target_id: e.target.id || "",
        target_class: e.target.className || "",
        target_text: (e.target.textContent || "").slice(0, 100),
      });
    },
    true
  );

  // ── Double-click recording ─────────────────────────────────────
  document.addEventListener(
    "dblclick",
    (e) => {
      if (e.target.closest && e.target.closest("#agentlens-overlay")) return;
      recordEvent("double_click", {
        x: e.clientX,
        y: e.clientY,
        button: "left",
        target_tag: e.target.tagName || "",
        target_id: e.target.id || "",
      });
    },
    true
  );

  // ── Scroll recording (throttled) ──────────────────────────────
  let scrollTimer = null;
  let lastScrollX = window.scrollX;
  let lastScrollY = window.scrollY;
  window.addEventListener(
    "scroll",
    () => {
      if (scrollTimer) clearTimeout(scrollTimer);
      scrollTimer = setTimeout(() => {
        const dx = window.scrollX - lastScrollX;
        const dy = window.scrollY - lastScrollY;
        if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
          recordEvent("scroll", {
            scroll_x: dx,
            scroll_y: dy,
            position_x: window.scrollX,
            position_y: window.scrollY,
          });
        }
        lastScrollX = window.scrollX;
        lastScrollY = window.scrollY;
      }, 200);
    },
    true
  );

  // ── Keyboard recording ─────────────────────────────────────────
  document.addEventListener(
    "keydown",
    (e) => {
      if (e.target.closest && e.target.closest("#agentlens-overlay")) return;
      // Only record special keys (not regular typing which is captured by input)
      if (e.key.length > 1 || e.ctrlKey || e.metaKey || e.altKey) {
        recordEvent("keypress", {
          key: e.key,
          code: e.code,
          ctrl: e.ctrlKey,
          shift: e.shiftKey,
          alt: e.altKey,
          meta: e.metaKey,
          target_tag: e.target.tagName || "",
          target_id: e.target.id || "",
        });
      }
    },
    true
  );

  // ── Input/typing recording (throttled) ─────────────────────────
  let inputTimer = null;
  document.addEventListener(
    "input",
    (e) => {
      if (e.target.closest && e.target.closest("#agentlens-overlay")) return;
      if (inputTimer) clearTimeout(inputTimer);
      inputTimer = setTimeout(() => {
        recordEvent("type", {
          text: (e.target.value || "").slice(0, 500),
          target_tag: e.target.tagName || "",
          target_id: e.target.id || "",
          target_name: e.target.name || "",
        });
      }, 300);
    },
    true
  );

  // ── Navigation recording ───────────────────────────────────────
  let lastUrl = window.location.href;
  const navObserver = new MutationObserver(() => {
    if (window.location.href !== lastUrl) {
      recordEvent("navigation", {
        from_url: lastUrl,
        to_url: window.location.href,
      });
      lastUrl = window.location.href;
    }
  });
  navObserver.observe(document.documentElement, {
    childList: true,
    subtree: true,
  });

  // ── Floating overlay UI ────────────────────────────────────────
  // Built entirely with safe DOM APIs (createElement, textContent,
  // setAttribute). No innerHTML assignments.
  function buildOverlay() {
    const overlay = document.createElement("div");
    overlay.id = "agentlens-overlay";
    overlay.setAttribute(
      "style",
      [
        "position: fixed",
        "bottom: 20px",
        "right: 20px",
        "z-index: 2147483647",
        "font-family: -apple-system, BlinkMacSystemFont, sans-serif",
        "font-size: 14px",
        "background: rgba(30, 30, 30, 0.95)",
        "color: #fff",
        "border-radius: 12px",
        "padding: 16px",
        "box-shadow: 0 8px 32px rgba(0,0,0,0.4)",
        "min-width: 280px",
        "backdrop-filter: blur(10px)",
        "border: 1px solid rgba(255,255,255,0.1)",
      ].join(";")
    );

    // Title
    const title = document.createElement("div");
    title.setAttribute(
      "style",
      "font-weight: 700; font-size: 13px; margin-bottom: 10px; color: #4af; letter-spacing: 0.5px;"
    );
    title.textContent = "🔍 AgentLens — Human Session";
    overlay.appendChild(title);

    // Event counter
    const counter = document.createElement("div");
    counter.id = "agentlens-counter";
    counter.setAttribute(
      "style",
      "font-size: 12px; color: #aaa; margin-bottom: 12px;"
    );
    counter.textContent = "Actions recorded: 0";
    overlay.appendChild(counter);

    // Answer input
    const label = document.createElement("div");
    label.setAttribute(
      "style",
      "font-size: 12px; color: #ccc; margin-bottom: 4px;"
    );
    label.textContent = "Your answer:";
    overlay.appendChild(label);

    const input = document.createElement("textarea");
    input.id = "agentlens-answer-input";
    input.setAttribute("rows", "3");
    input.setAttribute(
      "style",
      [
        "width: 100%",
        "box-sizing: border-box",
        "background: rgba(255,255,255,0.1)",
        "border: 1px solid rgba(255,255,255,0.2)",
        "border-radius: 6px",
        "color: #fff",
        "padding: 8px",
        "font-size: 13px",
        "resize: vertical",
        "outline: none",
        "margin-bottom: 10px",
      ].join(";")
    );
    input.setAttribute(
      "placeholder",
      "Type your answer here before submitting..."
    );
    overlay.appendChild(input);

    // Submit button
    const submitBtn = document.createElement("button");
    submitBtn.id = "agentlens-submit-btn";
    submitBtn.setAttribute(
      "style",
      [
        "width: 100%",
        "padding: 10px",
        "background: linear-gradient(135deg, #0a84ff, #30d158)",
        "color: #fff",
        "border: none",
        "border-radius: 8px",
        "font-size: 14px",
        "font-weight: 600",
        "cursor: pointer",
        "transition: opacity 0.2s",
      ].join(";")
    );
    submitBtn.textContent = "✅ Submit Answer & Finish";
    submitBtn.addEventListener("click", () => {
      const answerInput = document.getElementById("agentlens-answer-input");
      const answer = answerInput ? answerInput.value.trim() : "";
      if (!answer) {
        // Flash the input border red briefly
        if (answerInput) {
          answerInput.setAttribute(
            "style",
            answerInput.getAttribute("style") +
              ";border-color: #ff3b30 !important;"
          );
          setTimeout(() => {
            answerInput.setAttribute(
              "style",
              answerInput
                .getAttribute("style")
                .replace(";border-color: #ff3b30 !important;", "")
            );
          }, 1500);
        }
        return;
      }
      recordEvent("final_answer", { answer: answer });
      window.__agentlens_human_answer = answer;
      window.__agentlens_human_done = true;

      // Show completion state
      submitBtn.textContent = "✓ Submitted!";
      submitBtn.setAttribute(
        "style",
        submitBtn.getAttribute("style") +
          ";background: #333; cursor: default; opacity: 0.7;"
      );
      submitBtn.disabled = true;
    });
    overlay.appendChild(submitBtn);

    // Minimize toggle
    const minimizeBtn = document.createElement("div");
    minimizeBtn.setAttribute(
      "style",
      [
        "position: absolute",
        "top: 8px",
        "right: 12px",
        "cursor: pointer",
        "font-size: 16px",
        "color: #888",
        "line-height: 1",
      ].join(";")
    );
    minimizeBtn.textContent = "—";
    let minimized = false;
    minimizeBtn.addEventListener("click", () => {
      const children = overlay.childNodes;
      for (let i = 1; i < children.length; i++) {
        if (children[i] !== minimizeBtn) {
          children[i].style.display = minimized ? "" : "none";
        }
      }
      minimized = !minimized;
      minimizeBtn.textContent = minimized ? "□" : "—";
    });
    overlay.appendChild(minimizeBtn);

    document.body.appendChild(overlay);

    // Update counter periodically
    setInterval(() => {
      const c = document.getElementById("agentlens-counter");
      if (c) {
        c.textContent =
          "Actions recorded: " + window.__agentlens_human_events.length;
      }
    }, 1000);
  }

  // Build overlay when DOM is ready
  if (document.body) {
    buildOverlay();
  } else {
    document.addEventListener("DOMContentLoaded", buildOverlay);
  }
})();
