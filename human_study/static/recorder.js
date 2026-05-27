/**
 * AgentLens Study Recorder
 *
 * Injected into proxied study pages. Captures user interactions and
 * sends them to the study server API. Shows a floating overlay with
 * task goal and submit button.
 *
 * This runs on the participant's browser. All DOM manipulation uses
 * safe APIs (createElement, textContent, setAttribute).
 * No innerHTML assignments with user data.
 */
(() => {
  if (window.__agentlens_recorder_ready) return;
  window.__agentlens_recorder_ready = true;

  const SESSION_ID = window.__agentlens_session_id;
  const TASK_GOAL = window.__agentlens_task_goal;
  const API_BASE = window.__agentlens_api_base || '';
  const START_TIME = Date.now();

  // ── Event buffer ───────────────────────────────────────────────
  let eventBuffer = [];
  const FLUSH_INTERVAL = 3000; // Send events every 3 seconds

  function recordEvent(type, detail) {
    eventBuffer.push({
      type: type,
      timestamp: new Date().toISOString(),
      elapsed_ms: Date.now() - START_TIME,
      url: window.location.href,
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
      },
      ...detail,
    });
  }

  function flushEvents() {
    if (eventBuffer.length === 0) return;
    const batch = eventBuffer.splice(0);
    fetch(API_BASE + '/api/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: SESSION_ID, events: batch }),
    }).catch(err => {
      // Put events back if send failed
      eventBuffer.unshift(...batch);
    });
  }

  setInterval(flushEvents, FLUSH_INTERVAL);

  // ── Click recording ────────────────────────────────────────────
  document.addEventListener('mousedown', (e) => {
    if (e.target.closest && e.target.closest('#agentlens-study-overlay')) return;
    recordEvent('click', {
      x: e.clientX,
      y: e.clientY,
      page_x: e.pageX,
      page_y: e.pageY,
      button: e.button === 0 ? 'left' : e.button === 2 ? 'right' : 'middle',
      target_tag: e.target.tagName || '',
      target_id: e.target.id || '',
      target_class: (typeof e.target.className === 'string') ? e.target.className : '',
      target_text: (e.target.textContent || '').slice(0, 100),
    });
  }, true);

  // ── Double-click recording ─────────────────────────────────────
  document.addEventListener('dblclick', (e) => {
    if (e.target.closest && e.target.closest('#agentlens-study-overlay')) return;
    recordEvent('double_click', {
      x: e.clientX,
      y: e.clientY,
      button: 'left',
      target_tag: e.target.tagName || '',
      target_id: e.target.id || '',
    });
  }, true);

  // ── Scroll recording (throttled) ──────────────────────────────
  let scrollTimer = null;
  let lastScrollX = window.scrollX;
  let lastScrollY = window.scrollY;
  window.addEventListener('scroll', () => {
    if (scrollTimer) clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      const dx = window.scrollX - lastScrollX;
      const dy = window.scrollY - lastScrollY;
      if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
        recordEvent('scroll', {
          scroll_x: dx,
          scroll_y: dy,
          position_x: window.scrollX,
          position_y: window.scrollY,
        });
      }
      lastScrollX = window.scrollX;
      lastScrollY = window.scrollY;
    }, 250);
  }, true);

  // ── Keyboard recording ─────────────────────────────────────────
  document.addEventListener('keydown', (e) => {
    if (e.target.closest && e.target.closest('#agentlens-study-overlay')) return;
    if (e.key.length > 1 || e.ctrlKey || e.metaKey || e.altKey) {
      recordEvent('keypress', {
        key: e.key,
        code: e.code,
        ctrl: e.ctrlKey,
        shift: e.shiftKey,
        alt: e.altKey,
        meta: e.metaKey,
        target_tag: e.target.tagName || '',
        target_id: e.target.id || '',
      });
    }
  }, true);

  // ── Input/typing recording (throttled per element) ─────────────
  let inputTimer = null;
  document.addEventListener('input', (e) => {
    if (e.target.closest && e.target.closest('#agentlens-study-overlay')) return;
    if (inputTimer) clearTimeout(inputTimer);
    inputTimer = setTimeout(() => {
      recordEvent('type', {
        text: (e.target.value || '').slice(0, 500),
        target_tag: e.target.tagName || '',
        target_id: e.target.id || '',
        target_name: e.target.name || '',
      });
    }, 400);
  }, true);

  // ── Navigation recording ───────────────────────────────────────
  let lastUrl = window.location.href;
  const navObserver = new MutationObserver(() => {
    if (window.location.href !== lastUrl) {
      recordEvent('navigation', {
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
  function buildOverlay() {
    const overlay = document.createElement('div');
    overlay.id = 'agentlens-study-overlay';
    overlay.setAttribute('style', [
      'position: fixed',
      'bottom: 20px',
      'right: 20px',
      'z-index: 2147483647',
      'font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif',
      'font-size: 14px',
      'background: rgba(15, 15, 26, 0.97)',
      'color: #fff',
      'border-radius: 16px',
      'padding: 20px',
      'box-shadow: 0 12px 48px rgba(0,0,0,0.5)',
      'min-width: 320px',
      'max-width: 380px',
      'backdrop-filter: blur(20px)',
      'border: 1px solid rgba(255,255,255,0.1)',
    ].join(';'));

    // Header
    const header = document.createElement('div');
    header.setAttribute('style',
      'display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;'
    );

    const title = document.createElement('div');
    title.setAttribute('style',
      'font-weight:700;font-size:13px;color:#4af;letter-spacing:0.5px;'
    );
    title.textContent = '🔍 AgentLens Study';
    header.appendChild(title);

    // Minimize button
    const minBtn = document.createElement('div');
    minBtn.setAttribute('style',
      'cursor:pointer;font-size:18px;color:#666;width:24px;height:24px;' +
      'display:flex;align-items:center;justify-content:center;border-radius:6px;'
    );
    minBtn.textContent = '—';
    let minimized = false;
    header.appendChild(minBtn);
    overlay.appendChild(header);

    // Content wrapper (for minimize toggle)
    const content = document.createElement('div');
    content.id = 'agentlens-overlay-content';

    // Task goal
    const goalLabel = document.createElement('div');
    goalLabel.setAttribute('style',
      'font-size:11px;color:#666;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;'
    );
    goalLabel.textContent = 'Your Task';
    content.appendChild(goalLabel);

    const goalText = document.createElement('div');
    goalText.setAttribute('style',
      'font-size:13px;color:#ccc;line-height:1.5;margin-bottom:14px;' +
      'padding:10px;background:rgba(255,255,255,0.05);border-radius:8px;' +
      'border-left:3px solid #4af;'
    );
    goalText.textContent = TASK_GOAL;
    content.appendChild(goalText);

    // Event counter
    const counter = document.createElement('div');
    counter.id = 'agentlens-event-counter';
    counter.setAttribute('style',
      'font-size:12px;color:#555;margin-bottom:14px;'
    );
    counter.textContent = '📊 Actions recorded: 0';
    content.appendChild(counter);

    // Separator
    const sep = document.createElement('div');
    sep.setAttribute('style',
      'height:1px;background:rgba(255,255,255,0.08);margin-bottom:14px;'
    );
    content.appendChild(sep);

    // Answer label
    const ansLabel = document.createElement('div');
    ansLabel.setAttribute('style',
      'font-size:12px;color:#aaa;margin-bottom:6px;font-weight:500;'
    );
    ansLabel.textContent = '💬 Your Answer:';
    content.appendChild(ansLabel);

    // Answer textarea
    const textarea = document.createElement('textarea');
    textarea.id = 'agentlens-answer';
    textarea.setAttribute('rows', '3');
    textarea.setAttribute('placeholder', 'Type your answer before submitting...');
    textarea.setAttribute('style', [
      'width: 100%',
      'box-sizing: border-box',
      'background: rgba(255,255,255,0.06)',
      'border: 1px solid rgba(255,255,255,0.12)',
      'border-radius: 8px',
      'color: #fff',
      'padding: 10px 12px',
      'font-size: 13px',
      'font-family: Inter, -apple-system, sans-serif',
      'resize: vertical',
      'outline: none',
      'margin-bottom: 12px',
      'transition: border-color 0.2s',
    ].join(';'));
    textarea.addEventListener('focus', () => {
      textarea.setAttribute('style',
        textarea.getAttribute('style').replace(
          'border: 1px solid rgba(255,255,255,0.12)',
          'border: 1px solid #4af'
        )
      );
    });
    textarea.addEventListener('blur', () => {
      textarea.setAttribute('style',
        textarea.getAttribute('style').replace(
          'border: 1px solid #4af',
          'border: 1px solid rgba(255,255,255,0.12)'
        )
      );
    });
    content.appendChild(textarea);

    // Submit button
    const submitBtn = document.createElement('button');
    submitBtn.id = 'agentlens-submit-btn';
    submitBtn.setAttribute('style', [
      'width: 100%',
      'padding: 12px',
      'background: linear-gradient(135deg, #0a84ff, #30d158)',
      'color: #fff',
      'border: none',
      'border-radius: 10px',
      'font-size: 14px',
      'font-weight: 600',
      'cursor: pointer',
      'transition: all 0.2s',
      'font-family: Inter, -apple-system, sans-serif',
    ].join(';'));
    submitBtn.textContent = '✅ Submit Answer & Finish';

    submitBtn.addEventListener('mouseenter', () => {
      submitBtn.style.transform = 'scale(1.02)';
      submitBtn.style.boxShadow = '0 4px 16px rgba(10,132,255,0.3)';
    });
    submitBtn.addEventListener('mouseleave', () => {
      submitBtn.style.transform = 'scale(1)';
      submitBtn.style.boxShadow = 'none';
    });

    submitBtn.addEventListener('click', () => {
      const answer = textarea.value.trim();
      if (!answer) {
        textarea.setAttribute('style',
          textarea.getAttribute('style') + ';border-color: #ff3b30 !important;'
        );
        setTimeout(() => {
          textarea.setAttribute('style',
            textarea.getAttribute('style').replace(';border-color: #ff3b30 !important;', '')
          );
        }, 1500);
        return;
      }

      // Record final answer event
      recordEvent('final_answer', { answer: answer });

      // Flush remaining events
      flushEvents();

      // Submit answer
      submitBtn.textContent = '⏳ Submitting...';
      submitBtn.style.opacity = '0.7';
      submitBtn.disabled = true;

      fetch(API_BASE + '/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: SESSION_ID,
          answer: answer,
        }),
      })
      .then(r => r.json())
      .then(data => {
        // Show success state
        content.replaceChildren();

        const successIcon = document.createElement('div');
        successIcon.setAttribute('style',
          'text-align:center;font-size:48px;margin:20px 0 12px;'
        );
        successIcon.textContent = '🎉';
        content.appendChild(successIcon);

        const successMsg = document.createElement('div');
        successMsg.setAttribute('style',
          'text-align:center;font-size:16px;font-weight:600;color:#30d158;margin-bottom:8px;'
        );
        successMsg.textContent = 'Thank you!';
        content.appendChild(successMsg);

        const successDetail = document.createElement('div');
        successDetail.setAttribute('style',
          'text-align:center;font-size:13px;color:#888;'
        );
        successDetail.textContent = 'Your session has been recorded successfully.';
        content.appendChild(successDetail);
      })
      .catch(err => {
        submitBtn.textContent = '❌ Error — Try Again';
        submitBtn.style.opacity = '1';
        submitBtn.disabled = false;
      });
    });
    content.appendChild(submitBtn);

    overlay.appendChild(content);

    // Minimize toggle
    minBtn.addEventListener('click', () => {
      minimized = !minimized;
      content.style.display = minimized ? 'none' : 'block';
      minBtn.textContent = minimized ? '□' : '—';
      overlay.style.minWidth = minimized ? 'auto' : '320px';
    });

    document.body.appendChild(overlay);

    // Update counter
    setInterval(() => {
      const c = document.getElementById('agentlens-event-counter');
      if (c) {
        c.textContent = '📊 Actions recorded: ' + (eventBuffer.length + (window.__agentlens_total_sent || 0));
      }
    }, 1000);

    // Track total sent events for counter
    const origFlush = flushEvents;
    window.__agentlens_total_sent = 0;
  }

  // Build overlay when DOM is ready
  if (document.body) {
    buildOverlay();
  } else {
    document.addEventListener('DOMContentLoaded', buildOverlay);
  }

  // Flush on page unload
  window.addEventListener('beforeunload', () => {
    if (eventBuffer.length > 0) {
      // Use sendBeacon for reliable last-chance send
      navigator.sendBeacon(
        API_BASE + '/api/events',
        JSON.stringify({ session_id: SESSION_ID, events: eventBuffer })
      );
    }
  });
})();
