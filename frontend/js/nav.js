/**
 * nav.js — wires the topbar that's markup-duplicated across pages:
 * fills in the signed-in user's name, handles the mobile menu toggle,
 * and wires logout. Include after api.js.
 */
(function initNav() {
  const { auth, api } = window.BloodConnect;
  document.addEventListener("DOMContentLoaded", () => {
    const user = auth.getUser();
    const nav = document.querySelector(".topbar__nav");

    // Show Dashboard only when the backend confirms admin access.
    if (nav && auth.isLoggedIn()) {
      api.adminAccess().then(() => {
        if (nav.querySelector("[data-admin-link]")) return;

        const link = document.createElement("a");
        link.className = "topbar__link";
        link.href = "admin.html";
        link.textContent = "Dashboard";
        link.dataset.adminLink = "true";
        nav.appendChild(link);
      }).catch(() => {
        // Regular users should not see the admin link.
      });
    }

    const nameEl = document.querySelector("[data-nav-username]");
    if (nameEl && user) {
      nameEl.textContent = user.name;
    }

    const toggle = document.querySelector("[data-nav-toggle]");
    const topbar = document.querySelector(".topbar");
    if (toggle && topbar) {
      toggle.addEventListener("click", () => {
        const isOpen = topbar.classList.toggle("is-open");
        toggle.setAttribute("aria-expanded", String(isOpen));
      });
    }

    // Telegram is connected once per account. If it is not connected yet,
    // show a one-time onboarding prompt instead of a permanent nav button.
    if (user && auth.isLoggedIn()) {
      const promptKey = `bloodconnect_telegram_prompt_${user.user_id || user.email || "account"}`;
      if (!sessionStorage.getItem(promptKey)) {
        window.BloodConnect.api.telegramStatus().then(async (status) => {
          if (status && status.linked) return;

          const result = await window.BloodConnect.api.createTelegramLink();
          if (!result || !result.link) return;

          sessionStorage.setItem(promptKey, "shown");
          const overlay = document.createElement("div");
          overlay.setAttribute("role", "dialog");
          overlay.setAttribute("aria-modal", "true");
          overlay.setAttribute("aria-labelledby", "telegram-alert-title");
          overlay.style.cssText = "position:fixed;inset:0;z-index:9999;background:rgba(10,20,30,.62);display:flex;align-items:center;justify-content:center;padding:20px;";

          const card = document.createElement("div");
          card.style.cssText = "width:min(440px,100%);background:var(--surface,#fff);color:var(--text,#17212b);border-radius:16px;padding:26px;box-shadow:0 20px 60px rgba(0,0,0,.25);";
          const title = document.createElement("h2");
          title.id = "telegram-alert-title";
          title.textContent = "Enable Telegram blood alerts";
          title.style.marginTop = "0";
          const description = document.createElement("p");
          description.textContent = "Connect Telegram once to receive compatible blood-request alerts and updates when a donor accepts your request. Telegram requires you to press START to authorize messages.";
          const connect = document.createElement("a");
          connect.href = result.link;
          connect.target = "_blank";
          connect.rel = "noopener noreferrer";
          connect.className = "btn btn--primary";
          connect.textContent = "Continue to Telegram";
          connect.style.cssText = "display:inline-flex;align-items:center;justify-content:center;text-decoration:none;margin:8px 8px 0 0;";
          const later = document.createElement("button");
          later.type = "button";
          later.className = "btn btn--ghost";
          later.textContent = "Not now";
          later.style.marginTop = "8px";
          later.addEventListener("click", () => overlay.remove());
          const note = document.createElement("p");
          note.textContent = "You can continue using BloodConnect without linking Telegram, but Telegram alerts will remain off until you connect.";
          note.style.cssText = "font-size:.9em;opacity:.8;margin-bottom:0;";
          card.append(title, description, connect, later, note);
          overlay.appendChild(card);
          document.body.appendChild(overlay);
        }).catch((err) => {
          console.warn("Could not check Telegram connection status:", err.message || err);
        });
      }
    }

    const logoutBtn = document.querySelector("[data-nav-logout]");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", () => {
        auth.clearSession();
        window.location.href = "index.html";
      });
    }
  });
})();
