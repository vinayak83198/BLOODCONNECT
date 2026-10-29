/**
 * request-form.js — behavior for request-form.html.
 */
(function requestFormPage() {
  const { api, auth, ApiError } = window.BloodConnect;

  document.addEventListener("DOMContentLoaded", () => {
    auth.requireSession();

    const form = document.getElementById("request-form");
    const banner = document.getElementById("banner");
    const submitBtn = document.getElementById("request-submit");

    function showBanner(message, kind = "error") {
      banner.textContent = message;
      banner.className = `banner is-visible banner--${kind}`;
    }
    function hideBanner() {
      banner.className = "banner";
    }
    function setFieldError(fieldId, hasError) {
      document.getElementById(fieldId).classList.toggle("has-error", hasError);
    }
    function setLoading(isLoading) {
      submitBtn.disabled = isLoading;
      const label = submitBtn.querySelector(".btn-label");
      if (!submitBtn.dataset.originalLabel) submitBtn.dataset.originalLabel = label.textContent;
      label.textContent = isLoading ? "Sending…" : submitBtn.dataset.originalLabel;
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      hideBanner();

      const bloodGroup = document.getElementById("blood-group").value;
      const units = parseInt(document.getElementById("units").value, 10);
      const hospital = document.getElementById("hospital").value.trim();
      const urgency = document.getElementById("urgency").value;
      const radius = parseFloat(document.getElementById("radius").value);
      const notes = document.getElementById("notes").value.trim();

      let hasError = false;
      const check = (fieldId, condition) => {
        setFieldError(fieldId, !condition);
        if (!condition) hasError = true;
      };
      check("blood-group-field", bloodGroup !== "");
      check("units-field", Number.isInteger(units) && units >= 1 && units <= 20);
      check("hospital-field", hospital.length >= 2);
      if (hasError) return;

      setLoading(true);
      try {
        await api.createRequest({
          blood_group: bloodGroup,
          units_needed: units,
          hospital_name: hospital,
          urgency,
          radius_km: radius,
          notes: notes || null,
        });
        showBanner("Request sent. Compatible donors nearby will be matched automatically.", "success");
        form.reset();
        document.getElementById("units").value = 1;
        setTimeout(() => {
          window.location.href = "my-requests.html";
        }, 900);
      } catch (err) {
        showBanner(err instanceof ApiError ? err.message : "Couldn't send the request. Please try again.");
      } finally {
        setLoading(false);
      }
    });
  });
})();
