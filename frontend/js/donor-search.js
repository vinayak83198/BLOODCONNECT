/**
 * donor-search.js — behavior for donor-search.html.
 */
(function donorSearchPage() {
  const { api, auth, ApiError } = window.BloodConnect;

  document.addEventListener("DOMContentLoaded", () => {
    auth.requireSession();

    const user = auth.getUser();
    const form = document.getElementById("search-form");
    const resultsArea = document.getElementById("results-area");
    const banner = document.getElementById("banner");
    const submitBtn = document.getElementById("search-submit");

    function showBanner(message) {
      banner.textContent = message;
      banner.className = "banner is-visible banner--error";
    }
    function hideBanner() {
      banner.className = "banner";
    }

    function initials(name) {
      return name
        .split(" ")
        .filter(Boolean)
        .slice(0, 2)
        .map((p) => p[0].toUpperCase())
        .join("");
    }

    function renderLoading() {
      resultsArea.innerHTML = `
        <div class="result-list">
          ${[1, 2, 3]
            .map(
              () => `
            <div class="card donor-card">
              <div class="skeleton" style="width:220px;height:38px;"></div>
              <div class="skeleton" style="width:90px;height:28px;"></div>
            </div>`
            )
            .join("")}
        </div>`;
    }

    function renderEmpty(bloodGroup) {
      resultsArea.innerHTML = `
        <div class="empty-state">
          <h3>No matching donors right now</h3>
          <p>Nobody compatible with <strong>${bloodGroup}</strong> is available in this radius. Try a wider radius, or create a request so donors get notified as they become eligible.</p>
        </div>`;
    }

    function renderResults(results) {
      resultsArea.innerHTML = `
        <div class="result-list">
          ${results
            .map(
              (donor) => `
            <div class="card donor-card">
              <div class="donor-card__identity">
                <div class="donor-card__avatar" aria-hidden="true">${initials(donor.name)}</div>
                <div>
                  <div class="donor-card__name">${escapeHtml(donor.name)}</div>
                  <div class="donor-card__meta">${escapeHtml(donor.city)} · ${donor.distance_km} km away</div>
                </div>
              </div>
              <div class="donor-card__right">
                <span class="badge badge--teal">${donor.blood_group}</span>
                ${
                  donor.eligible
                    ? `<span class="badge badge--teal">Eligible</span>`
                    : `<span class="badge badge--amber">Eligible ${donor.next_eligible_date}</span>`
                }
                ${
                  donor.available
                    ? `<span class="badge badge--neutral">Available</span>`
                    : `<span class="badge badge--neutral">Unavailable</span>`
                }
              </div>
            </div>`
            )
            .join("")}
        </div>`;
    }

    function escapeHtml(str) {
      const div = document.createElement("div");
      div.textContent = str;
      return div.innerHTML;
    }

    async function runSearch(bloodGroup, radiusKm, onlyAvailable) {
      hideBanner();
      renderLoading();
      submitBtn.disabled = true;

      try {
        const results = await api.searchDonors({
          blood_group: bloodGroup,
          latitude: user.latitude,
          longitude: user.longitude,
          radius_km: radiusKm,
          only_available: onlyAvailable,
        });
        if (results.length === 0) {
          renderEmpty(bloodGroup);
        } else {
          renderResults(results);
        }
      } catch (err) {
        resultsArea.innerHTML = "";
        showBanner(err instanceof ApiError ? err.message : "Couldn't load donors. Please try again.");
      } finally {
        submitBtn.disabled = false;
      }
    }

    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const bloodGroup = document.getElementById("filter-blood-group").value;
      if (!bloodGroup) {
        showBanner("Choose a blood group to search for.");
        return;
      }
      const radiusKm = document.getElementById("filter-radius").value;
      const onlyAvailable = document.getElementById("filter-availability").value === "true";
      runSearch(bloodGroup, radiusKm, onlyAvailable);
    });

    // Pre-fill from the signed-in user's own blood group as a sensible default search.
    document.getElementById("filter-blood-group").value = user.blood_group || "";
  });
})();
