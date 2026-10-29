(() => {
  const { auth } = window.BloodConnect;

  const message = document.getElementById("admin-message");
  const content = document.getElementById("dashboard-content");
  const refreshButton = document.getElementById("refresh-btn");

  function showMessage(text, isError = false) {
    message.textContent = text;
    message.classList.toggle("admin-error", isError);
    message.hidden = false;
  }

  function setNumber(id, value) {
    document.getElementById(id).textContent =
      Number(value || 0).toLocaleString();
  }

  function renderList(id, data) {
    const list = document.getElementById(id);
    list.replaceChildren();

    const entries = Object.entries(data || {}).sort((a, b) => {
      return Number(b[1] || 0) - Number(a[1] || 0);
    });

    if (!entries.length) {
      const li = document.createElement("li");
      li.style.display = "block";
      li.textContent = "No data available yet";
      list.appendChild(li);
      return;
    }

    const max = Math.max(1, ...entries.map(([, count]) => Number(count) || 0));

    for (const [label, count] of entries) {
      const li = document.createElement("li");
      const name = document.createElement("span");
      const value = document.createElement("strong");
      const meter = document.createElement("div");
      const fill = document.createElement("span");

      name.textContent = label.replaceAll("_", " ");
      value.textContent = Number(count || 0).toLocaleString();

      meter.className = "admin-meter";
      meter.setAttribute("aria-label", `${label}: ${count}`);
      fill.style.width = `${Math.max(0, Math.min(100, (Number(count || 0) / max) * 100))}%`;

      meter.appendChild(fill);
      li.append(name, value, meter);
      list.appendChild(li);
    }
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }

  function renderRecentRequests(requests) {
    const tbody = document.getElementById("recent-requests");
    tbody.replaceChildren();

    if (!requests || !requests.length) {
      const row = tbody.insertRow();
      const cell = row.insertCell();
      cell.colSpan = 6;
      cell.className = "admin-empty";
      cell.textContent = "No blood requests have been recorded yet.";
      return;
    }

    for (const request of requests) {
      const row = tbody.insertRow();

      const recipientCell = row.insertCell();
      recipientCell.className = "admin-recipient";
      recipientCell.textContent = request.recipient_name || "—";

      const bloodCell = row.insertCell();
      const blood = document.createElement("span");
      blood.className = "admin-blood";
      blood.textContent = request.blood_group || "—";
      bloodCell.appendChild(blood);

      row.insertCell().textContent = request.hospital_name || "—";

      const urgencyCell = row.insertCell();
      const urgency = String(request.urgency || "—");
      urgencyCell.textContent = urgency;
      urgencyCell.className = "admin-urgency";
      if (["emergency", "critical", "high"].includes(urgency.toLowerCase())) {
        urgencyCell.classList.add("urgency-emergency");
      }

      const statusCell = row.insertCell();
      const status = String(request.status || "unknown");
      const badge = document.createElement("span");
      badge.className = `admin-status status-${status.toLowerCase().replaceAll(" ", "_")}`;
      badge.textContent = status.replaceAll("_", " ");
      statusCell.appendChild(badge);

      row.insertCell().textContent = formatDate(request.created_at);
    }
  }

  async function apiRequest(path) {
    const token = auth.getToken();
    const base = window.BLOODCONNECT_API_BASE_URL;

    const response = await fetch(`${base}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      const error = new Error(
        payload.detail || `Request failed (${response.status})`
      );
      error.status = response.status;
      throw error;
    }

    return payload;
  }

  async function loadDashboard() {
    refreshButton.disabled = true;
    showMessage("Refreshing BloodConnect statistics…");

    try {
      const data = await apiRequest("/api/admin/overview");

      setNumber("total-users", data.total_users);
      setNumber("total-donors", data.total_donors);
      setNumber("total-recipients", data.total_recipients);
      setNumber("available-donors", data.available_donors);
      setNumber("total-requests", data.total_requests);

      renderList("request-statuses", data.request_statuses);
      renderList("blood-groups", data.blood_group_distribution);
      renderRecentRequests(data.recent_requests);

      content.hidden = false;
      message.hidden = true;
    } catch (error) {
      if (error.status === 401) {
        auth.clearSession();
        window.location.href = "index.html";
        return;
      }

      if (error.status === 403) {
        showMessage(
          "Access denied. This account is not configured as a BloodConnect administrator.",
          true
        );
      } else {
        showMessage(error.message || "Unable to load dashboard data.", true);
      }
    } finally {
      refreshButton.disabled = false;
    }
  }

  async function init() {
    if (!auth.isLoggedIn()) {
      window.location.href = "index.html";
      return;
    }

    const user = auth.getUser();
    document.getElementById("admin-welcome").textContent =
      user ? `Signed in as ${user.name || user.email}` : "Signed in";

    try {
      await apiRequest("/api/admin/access");
      await loadDashboard();
    } catch (error) {
      if (error.status === 401) {
        auth.clearSession();
        window.location.href = "index.html";
        return;
      }

      if (error.status === 403) {
        showMessage(
          "Access denied. This account is not configured as a BloodConnect administrator.",
          true
        );
      } else {
        showMessage(error.message || "Unable to verify administrator access.", true);
      }
    }
  }

  refreshButton.addEventListener("click", loadDashboard);

  document.getElementById("logout-btn").addEventListener("click", () => {
    auth.clearSession();
    window.location.href = "index.html";
  });

  init();
})();
