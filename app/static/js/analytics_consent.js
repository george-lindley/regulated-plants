// Optional analytics consent for Google Analytics and site metrics.
(function () {
    const CONSENT_COOKIE = 'rp_analytics_consent';
    const CONSENT_ACCEPTED = 'accepted';
    const CONSENT_REJECTED = 'rejected';
    const COOKIE_MAX_AGE_DAYS = 180;
    const config = window.ANALYTICS_CONFIG || {};
    const measurementId = String(config.googleAnalyticsId || '').trim();

    function getCookie(name) {
        const encodedName = encodeURIComponent(name);
        const cookieParts = document.cookie ? document.cookie.split('; ') : [];
        for (const part of cookieParts) {
            const [rawKey, rawValue = ''] = part.split('=');
            if (rawKey === encodedName) return decodeURIComponent(rawValue);
        }
        return '';
    }

    function setCookie(name, value, maxAgeDays) {
        const expires = new Date(Date.now() + maxAgeDays * 24 * 60 * 60 * 1000).toUTCString();
        const secure = window.location.protocol === 'https:' ? '; Secure' : '';
        document.cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value)}; Expires=${expires}; Path=/; SameSite=Lax${secure}`;
    }

    function deleteCookie(name) {
        document.cookie = `${encodeURIComponent(name)}=; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Path=/; SameSite=Lax`;
    }

    function consentValue() {
        return getCookie(CONSENT_COOKIE);
    }

    function hasAcceptedAnalytics() {
        return consentValue() === CONSENT_ACCEPTED;
    }

    function loadGoogleAnalytics() {
        if (!measurementId || window.__googleAnalyticsLoaded) return;

        window.__googleAnalyticsLoaded = true;
        window.dataLayer = window.dataLayer || [];
        window.gtag = window.gtag || function () {
            window.dataLayer.push(arguments);
        };
        window.gtag('js', new Date());
        window.gtag('config', measurementId);

        const script = document.createElement('script');
        script.async = true;
        script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
        document.head.appendChild(script);
    }

    function clearAnalyticsCookies() {
        deleteCookie('_ga');
        deleteCookie('_gid');
        deleteCookie('_gat');
        deleteCookie(`_ga_${measurementId.replace(/^G-/, '')}`);
        deleteCookie('anonymous_user_id');
        deleteCookie('aha_activated');
    }

    function hideBanner() {
        const banner = document.querySelector('[data-cookie-banner]');
        if (banner) banner.hidden = true;
    }

    function showBannerIfNeeded() {
        const banner = document.querySelector('[data-cookie-banner]');
        if (!banner) return;
        banner.hidden = Boolean(consentValue());
    }

    window.analyticsConsentGranted = hasAcceptedAnalytics;

    document.addEventListener('DOMContentLoaded', function () {
        const acceptButton = document.querySelector('[data-analytics-accept]');
        const rejectButton = document.querySelector('[data-analytics-reject]');

        if (hasAcceptedAnalytics()) {
            loadGoogleAnalytics();
        } else {
            showBannerIfNeeded();
        }

        if (acceptButton) {
            acceptButton.addEventListener('click', function () {
                setCookie(CONSENT_COOKIE, CONSENT_ACCEPTED, COOKIE_MAX_AGE_DAYS);
                hideBanner();
                loadGoogleAnalytics();
            });
        }

        if (rejectButton) {
            rejectButton.addEventListener('click', function () {
                setCookie(CONSENT_COOKIE, CONSENT_REJECTED, COOKIE_MAX_AGE_DAYS);
                clearAnalyticsCookies();
                hideBanner();
            });
        }
    });
})();
