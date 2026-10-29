(() => {
  const { api, auth } = window.BloodConnect;

  const message = document.getElementById("admin-message");
  const content = document.getElementById("dashboard-content");
  const refreshButton = document.getElementById("refresh-btn");

  function showMessage(text, isError = false) {
    message.textContent = text;
    message.classList.toggle("admin-error", isError);
    message.hidden = false;
  }

  function setNumber(id, value) {
    document.getElementById(id).textContent = Number(value || 0).toLocaleString();
  }

  function renderList(id, data) {
    const list = document.getElementById(id);
    list.replaceChildren();

    const entries = Object.entries(data || {});
    if (!entries.length) {
      const li = document.createElement("li");
      li.textContent = "No data yet";
      list.appendChild(li);
      return;
    }

    for (const [label, count] of entries) {
      const li = document.createElement("li");
      const name = document.createElement("span");
      const value = document.createElement("strong");
      name.textContent = label.replaceAll("_", " ");
      value.textContent = Number(count || 0).toLocaleString();
      li.append(name, value);
      list.appendChild(li);
    }
  }

  function renderRecentRequests(requests) {
    const tbody = document.getElementById("recent-requests");
    tbody.replaceChildren();

    if (!requests || !requests.length) {
      const row = tbody.insertRow();
      const cell = row.insertCell();
      cell.colSpan = 5;
      cell.textContent = "No requests yet";
      return;
    }

    for (const request of requests) {
      const row = tbody.insertRow();
      [
        request.recipient_name,
        request.blood_group,
        request.hospital_name,
        request.urgency,
        request.status,
      ].forEach((value) => {
        const cell = row.insertCell();
        cell.textContent = value || "—";
        if (value === request.status) cell.className = "admin-status";
      });
    }
  }

  async function loadDashboard() {
    refreshButton.disabled = true;
    showMessage("Loading dashboard data…");

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
      if (error.status === 403) {
        showMessage("Access denied. This account is not configured as a BloodConnect administrator.", true);
      } else if (error.status === 401) {
        showMessage("Your session has expired. Please log in again.", true);
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
      if (error.status === 403) {
        showMessage("Access denied. This account is not configured as a BloodConnect administrator.", true);
      } else if (error.status === 401) {
        auth.clearSession();
        window.location.href = "index.html";
      } else {
        showMessage(error.message || "Unable to verify administrator access.", true);
      }
    }
  }

  function apiRequest(path) {
    const token = auth.getToken();
    return fetch(`${window.BLOODCONNECT_API_BASE_URL}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(async (response) => {
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const error = new Error(payload.detail || `Request failed (${response.status})`);
        error.status = response.status;
        throw error;
      }
      return payload;
    });
  }

  refreshButton.addEventListener("click", loadDashboard);
  document.getElementById("logout-btn").addEventListener("click", () => {
    auth.clearSession();
    window.location.href = "index.html";
  });

  init();
})();
