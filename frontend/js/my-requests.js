/**
 * my-requests.js — behavior for my-requests.html.
 */
(function myRequestsPage() {
  const { api, auth, ApiError } = window.BloodConnect;

  const STATUS_LABEL = {
    open: { text: "Open", cls: "badge--teal" },
    matched: { text: "Matched", cls: "badge--amber" },
    fulfilled: { text: "Fulfilled", cls: "badge--neutral" },
    cancelled: { text: "Cancelled", cls: "badge--neutral" },
  };

  const URGENCY_LABEL = {
    standard: { text: "Standard", cls: "badge--neutral" },
    urgent: { text: "Urgent", cls: "badge--amber" },
    critical: { text: "Critical", cls: "badge--coral" },
  };

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
  }

  function formatWhen(isoString) {
    const d = new Date(isoString);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    auth.requireSession();

    const banner = document.getElementById("banner");
    const outgoingPanel = document.getElementById("outgoing-panel");
    const incomingPanel = document.getElementById("incoming-panel");
    const tabOutgoing = document.getElementById("tab-outgoing");
    const tabIncoming = document.getElementById("tab-incoming");

    function showBanner(message) {
      banner.textContent = message;
      banner.className = "banner is-visible banner--error";
    }
    function hideBanner() {
      banner.className = "banner";
    }

    function switchTab(which) {
      const isOutgoing = which === "outgoing";
      tabOutgoing.classList.toggle("is-active", isOutgoing);
      tabIncoming.classList.toggle("is-active", !isOutgoing);
      tabOutgoing.setAttribute("aria-selected", String(isOutgoing));
      tabIncoming.setAttribute("aria-selected", String(!isOutgoing));
      outgoingPanel.style.display = isOutgoing ? "" : "none";
      incomingPanel.style.display = isOutgoing ? "none" : "";
    }
    tabOutgoing.addEventListener("click", () => switchTab("outgoing"));
    tabIncoming.addEventListener("click", () => switchTab("incoming"));

    function renderSkeleton(container) {
      container.innerHTML = [1, 2].map(() => `<div class="card request-card skeleton" style="height:96px;"></div>`).join("");
    }

    function renderOutgoing(list) {
      if (list.length === 0) {
        outgoingPanel.innerHTML = `
          <div class="empty-state">
            <h3>No requests yet</h3>
            <p>When you need blood, create a request and compatible nearby donors will be matched automatically.</p>
            <a class="btn btn--primary" href="request-form.html" style="margin-top:14px;">New request</a>
          </div>`;
        return;
      }

      outgoingPanel.innerHTML = list
        .map((r) => {
          const status = STATUS_LABEL[r.status] || STATUS_LABEL.open;
          const urgency = URGENCY_LABEL[r.urgency] || URGENCY_LABEL.standard;
          return `
          <div class="card request-card">
            <div class="request-card__top">
              <div>
                <div class="request-card__title">${escapeHtml(r.blood_group)} · ${r.units_needed} unit${r.units_needed > 1 ? "s" : ""} · ${escapeHtml(r.hospital_name)}</div>
                <div class="request-card__meta">Sent ${formatWhen(r.created_at)}</div>
              </div>
              <div style="display:flex; gap:8px;">
                <span class="badge ${urgency.cls}">${urgency.text}</span>
                <span class="badge ${status.cls}">${status.text}</span>
              </div>
            </div>
            ${r.notes ? `<div class="request-card__notes">${escapeHtml(r.notes)}</div>` : ""}
            <div class="request-card__footer">
              <div>
                ${
                  r.accepted_by_name
                    ? `<span class="contact-reveal">Accepted by ${escapeHtml(r.accepted_by_name)} · ${escapeHtml(r.accepted_by_phone)}</span>`
                    : r.status === "open"
                      ? `<span style="color:var(--text-muted); font-size:0.86rem;">Waiting for a donor to accept</span>`
                      : `<span style="color:var(--text-muted); font-size:0.86rem;">Request status: ${escapeHtml(status.text)}</span>`
                }
              </div>
              ${
                r.status === "matched"
                  ? `<button class="btn btn--ghost btn--sm" data-fulfill="${r.request_id}">Mark fulfilled</button>`
                  : ""
              }
            </div>
          </div>`;
        })
        .join("");

      outgoingPanel.querySelectorAll("[data-fulfill]").forEach((btn) => {
        btn.addEventListener("click", () => handleFulfill(btn.getAttribute("data-fulfill"), btn));
      });
    }

    function renderIncoming(list) {
      if (list.length === 0) {
        incomingPanel.innerHTML = `
          <div class="empty-state">
            <h3>No matches right now</h3>
            <p>You'll see open requests here when they're compatible with your blood group, inside your area, and you're inside the eligibility window.</p>
          </div>`;
        return;
      }

      incomingPanel.innerHTML = list
        .map((r) => {
          const urgency = URGENCY_LABEL[r.urgency] || URGENCY_LABEL.standard;
          return `
          <div class="card request-card">
            <div class="request-card__top">
              <div>
                <div class="request-card__title">${escapeHtml(r.blood_group)} needed · ${r.units_needed} unit${r.units_needed > 1 ? "s" : ""}</div>
                <div class="request-card__meta">${escapeHtml(r.hospital_name)} · ${r.distance_km} km away · ${formatWhen(r.created_at)}</div>
              </div>
              <span class="badge ${urgency.cls}">${urgency.text}</span>
            </div>
            ${r.notes ? `<div class="request-card__notes">${escapeHtml(r.notes)}</div>` : ""}
            <div class="request-card__footer">
              <span style="color:var(--text-muted); font-size:0.86rem;">Requested by ${escapeHtml(r.recipient_name)}</span>
              <button class="btn btn--primary btn--sm" data-accept="${r.request_id}">Accept &amp; share contact</button>
            </div>
          </div>`;
        })
        .join("");

      incomingPanel.querySelectorAll("[data-accept]").forEach((btn) => {
        btn.addEventListener("click", () => handleAccept(btn.getAttribute("data-accept"), btn));
      });
    }

    async function handleAccept(requestId, btn) {
  btn.disabled = true;
  const original = btn.textContent;
  btn.textContent = "Accepting…";

  try {
    const matched = await api.acceptRequest(requestId);

    await loadIncoming();
    await loadOutgoing();

    if (matched && matched.status === "matched") {
      const contactCard = document.createElement("div");
      contactCard.className = "card request-card";
      contactCard.innerHTML = `
        <h3>Request accepted successfully</h3>
        <p><strong>Recipient:</strong> ${escapeHtml(matched.recipient_name)}</p>
        <p><strong>Phone:</strong> ${escapeHtml(matched.recipient_phone || "Not available")}</p>
        <p><strong>Hospital:</strong> ${escapeHtml(matched.hospital_name)}</p>
        <p><strong>Blood group:</strong> ${escapeHtml(matched.blood_group)}</p>
      `;
      incomingPanel.prepend(contactCard);
    }
  } catch (err) {
    showBanner(
      err instanceof ApiError
        ? err.message
        : "Couldn't accept this request."
    );
    btn.disabled = false;
    btn.textContent = original;
  }
}
    async function handleFulfill(requestId, btn) {
      btn.disabled = true;
      const original = btn.textContent;
      btn.textContent = "Updating…";
      try {
        await api.fulfillRequest(requestId);
        await loadOutgoing();
      } catch (err) {
        showBanner(err instanceof ApiError ? err.message : "Couldn't update this request.");
        btn.disabled = false;
        btn.textContent = original;
      }
    }

    async function loadOutgoing() {
      renderSkeleton(outgoingPanel);
      try {
        const list = await api.myRequests();
        renderOutgoing(list);
      } catch (err) {
        outgoingPanel.innerHTML = "";
        showBanner(err instanceof ApiError ? err.message : "Couldn't load your requests.");
      }
    }

    async function loadIncoming() {
      renderSkeleton(incomingPanel);
      try {
        const list = await api.incomingRequests();
        renderIncoming(list);
      } catch (err) {
        incomingPanel.innerHTML = "";
        showBanner(err instanceof ApiError ? err.message : "Couldn't load matching requests.");
      }
    }

    hideBanner();
    loadOutgoing();
    loadIncoming();
  });
})();
