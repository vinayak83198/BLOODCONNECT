/**
 * auth-page.js — behavior for index.html (login + signup).
 */
(function authPage() {
  const { api, auth, ApiError } = window.BloodConnect;

  document.addEventListener("DOMContentLoaded", () => {
    // If already signed in, skip straight to the app.
    if (auth.isLoggedIn()) {
      window.location.href = "donor-search.html";
      return;
    }

    const banner = document.getElementById("banner");
    const tabLogin = document.getElementById("tab-login");
    const tabSignup = document.getElementById("tab-signup");
    const panelLogin = document.getElementById("panel-login");
    const panelSignup = document.getElementById("panel-signup");

    function showTab(which) {
      const isLogin = which === "login";
      tabLogin.classList.toggle("is-active", isLogin);
      tabSignup.classList.toggle("is-active", !isLogin);
      tabLogin.setAttribute("aria-selected", String(isLogin));
      tabSignup.setAttribute("aria-selected", String(!isLogin));
      panelLogin.classList.toggle("is-active", isLogin);
      panelSignup.classList.toggle("is-active", !isLogin);
      hideBanner();
    }

    tabLogin.addEventListener("click", () => showTab("login"));
    tabSignup.addEventListener("click", () => showTab("signup"));

    const resendLink = document.getElementById("resend-verification-link");
    resendLink.addEventListener("click", async (event) => {
      event.preventDefault();
      const email = document.getElementById("login-email").value.trim();
      if (!/\S+@\S+\.\S+/.test(email)) {
        showBanner("Enter your email in the Email field first, then click Resend verification email.");
        return;
      }
      try {
        const result = await api.resendVerification(email);
        showBanner(result.message, "success");
      } catch (err) {
        showBanner(err instanceof ApiError ? err.message : "Could not send the verification email.");
      }
    });

    const telegramShare = document.getElementById("telegram-share-btn");
    telegramShare.addEventListener("click", () => {
      const projectUrl = new URL("index.html", window.location.href);
      projectUrl.search = "";
      projectUrl.hash = "";
      const shareUrl = "https://t.me/share/url?url=" + encodeURIComponent(projectUrl.href) +
        "&text=" + encodeURIComponent("Join BloodConnect — connect with blood donors and manage emergency blood requests.");
      window.open(shareUrl, "_blank", "noopener,noreferrer");
    });

    function showBanner(message, kind = "error") {
      banner.textContent = message;
      banner.className = `banner is-visible banner--${kind}`;
    }
    function hideBanner() {
      banner.className = "banner";
    }

    function setFieldError(fieldId, hasError) {
      const field = document.getElementById(fieldId);
      if (field) field.classList.toggle("has-error", hasError);
    }

    function setLoading(button, isLoading, labelWhenLoading) {
      button.disabled = isLoading;
      const label = button.querySelector(".btn-label");
      if (!button.dataset.originalLabel) {
        button.dataset.originalLabel = label.textContent;
      }
      label.textContent = isLoading ? labelWhenLoading : button.dataset.originalLabel;
    }

    // ---- Login + email OTP -----------------------------------------
    const loginForm = document.getElementById("login-form");
    const loginOtpForm = document.getElementById("login-otp-form");
    const loginOtpInput = document.getElementById("login-otp");
    let pendingOtpEmail = "";

    document.getElementById("login-otp-back").addEventListener("click", () => {
      loginOtpForm.hidden = true;
      loginForm.hidden = false;
      loginOtpInput.value = "";
      hideBanner();
    });

    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      hideBanner();

      const email = document.getElementById("login-email").value.trim();
      const password = document.getElementById("login-password").value;
      const emailValid = /\S+@\S+\.\S+/.test(email);
      setFieldError("login-email-field", !emailValid);
      setFieldError("login-password-field", password.length === 0);
      if (!emailValid || password.length === 0) return;

      const submitBtn = document.getElementById("login-submit");
      setLoading(submitBtn, true, "Sending OTP…");
      try {
        const result = await api.login({ email, password });
        pendingOtpEmail = email.toLowerCase();
        document.getElementById("login-otp-message").textContent = result.message || `Enter the 6-digit OTP sent to ${pendingOtpEmail}.`;
        loginForm.hidden = true;
        loginOtpForm.hidden = false;
        loginOtpInput.focus();
        showBanner(result.message || "OTP sent to your email.", "success");
      } catch (err) {
        showBanner(err instanceof ApiError ? err.message : "Login failed. Please try again.");
      } finally {
        setLoading(submitBtn, false);
      }
    });

    loginOtpForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      hideBanner();
      const otp = loginOtpInput.value.trim();
      setFieldError("login-otp-field", !/^\d{6}$/.test(otp));
      if (!/^\d{6}$/.test(otp) || !pendingOtpEmail) return;
      const submitBtn = document.getElementById("login-otp-submit");
      setLoading(submitBtn, true, "Verifying…");
      try {
        const result = await api.verifyLoginOtp(pendingOtpEmail, otp);
        auth.setSession(result.access_token, result.user);
        window.location.href = "donor-search.html";
      } catch (err) {
        showBanner(err instanceof ApiError ? err.message : "OTP verification failed. Please try again.");
      } finally {
        setLoading(submitBtn, false);
      }
    });

    // ---- Signup ------------------------------------------------------
    const signupForm = document.getElementById("signup-form");
    const termsCheckbox = document.getElementById("signup-terms");
    const useLocationBtn = document.getElementById("use-location-btn");
    const locationStatus = document.getElementById("location-status");
    const latInput = document.getElementById("signup-lat");
    const lngInput = document.getElementById("signup-lng");

    // Clear the Terms error as soon as the user accepts the terms.
    termsCheckbox.addEventListener("change", () => {
      setFieldError("signup-terms-field", !termsCheckbox.checked);
      if (termsCheckbox.checked && banner.textContent.includes("Terms & Conditions")) {
        hideBanner();
      }
    });

    useLocationBtn.addEventListener("click", () => {
      if (!navigator.geolocation) {
        locationStatus.textContent = "Geolocation isn't supported in this browser — enter your city manually.";
        return;
      }
      locationStatus.textContent = "Locating…";
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          latInput.value = pos.coords.latitude;
          lngInput.value = pos.coords.longitude;
          locationStatus.textContent = `Location set (±${Math.round(pos.coords.accuracy)}m accuracy).`;
        },
        () => {
          locationStatus.textContent = "Couldn't get your location — you can still sign up and update it later.";
        }
      );
    });

    signupForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      hideBanner();

      const name = document.getElementById("signup-name").value.trim();
      const phone = document.getElementById("signup-phone").value.trim();
      const email = document.getElementById("signup-email").value.trim();
      const password = document.getElementById("signup-password").value;
      const role = document.getElementById("signup-role").value;
      const bloodGroup = document.getElementById("signup-blood").value;
      const city = document.getElementById("signup-city").value.trim();
      const latitude = latInput.value;
      const longitude = lngInput.value;
      const acceptedTerms = termsCheckbox.checked;

      let hasError = false;
      const check = (fieldId, condition) => {
        setFieldError(fieldId, !condition);
        if (!condition) hasError = true;
      };

      check("signup-name-field", name.length >= 2);
      check("signup-phone-field", phone.length >= 7);
      check("signup-email-field", /\S+@\S+\.\S+/.test(email));
      check("signup-password-field", password.length >= 8);
      check("signup-blood-field", bloodGroup !== "");
      check("signup-city-field", city.length >= 2);
      check("signup-terms-field", acceptedTerms);

      if (hasError) {
        if (!acceptedTerms) {
          showBanner("Please tick the Terms & Conditions checkbox before creating an account.");
          termsCheckbox.focus();
        }
        return;
      }

      // Default to a central-city fallback if the user skipped geolocation,
      // so the account is still usable for search/matching demos.
      const finalLat = latitude ? parseFloat(latitude) : 22.7196;
      const finalLng = longitude ? parseFloat(longitude) : 75.8577;

      const submitBtn = document.getElementById("signup-submit");
      setLoading(submitBtn, true, "Creating account…");
      try {
        const result = await api.signup({
          name,
          phone,
          email,
          password,
          role,
          blood_group: bloodGroup,
          city,
          latitude: finalLat,
          longitude: finalLng,
          accepted_terms: acceptedTerms,
        });
        showBanner(result.message || "Account created. Check your email to verify your address before logging in.", "success");
        signupForm.reset();
        locationStatus.textContent = "Needed to match nearby donors and requests.";
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          showBanner("An account with this email already exists. Try logging in instead.");
        } else if (err instanceof ApiError) {
          showBanner(err.message);
        } else {
          showBanner("Sign up failed. Please try again.");
        }
      } finally {
        setLoading(submitBtn, false);
      }
    });
  });
})();
