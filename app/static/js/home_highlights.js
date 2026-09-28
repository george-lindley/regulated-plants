// static/js/home_highlights.js
(function () {
    function formatDate(isoString) {
        if (!isoString) return '--';
        const date = new Date(isoString);
        if (Number.isNaN(date.getTime())) return '--';
        return date.toLocaleDateString(undefined, {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }

    function releaseDateText(release) {
        if (!release) return 'Date pending';
        const dateLabel = release.dateLabel || formatDate(release.generatedAt);
        if (!dateLabel || dateLabel === '--') return 'Date pending';
        return dateLabel;
    }

    function animateCount(element, value) {
        if (!element || typeof value !== 'number') return;

        const startValue = 0;
        const startTime = performance.now();
        const duration = 1200;

        function step(currentTime) {
            const progress = Math.min((currentTime - startTime) / duration, 1);
            const currentValue = Math.floor(startValue + (value - startValue) * progress);
            element.textContent = new Intl.NumberFormat().format(currentValue);

            if (progress < 1) requestAnimationFrame(step);
        }

        requestAnimationFrame(step);
    }

    function setClickableDataset(linkEl, regionValue) {
        if (!linkEl) return;

        if (regionValue) {
            // New, clean attribute name
            linkEl.dataset.region = regionValue;

            // Optional backward compatibility (harmless)
            linkEl.dataset.state = regionValue;

            linkEl.classList.remove('disabled');
        } else {
            linkEl.dataset.region = '';
            linkEl.dataset.state = '';
            linkEl.classList.add('disabled');
        }
    }

    function updateHighlights(data) {
        const jurisdictionsEl = document.getElementById('highlight-jurisdictions');
        const speciesEl = document.getElementById('highlight-species');
        const lastUpdatedEl = document.getElementById('highlight-last-updated');
        const lastUpdatedBadge = document.getElementById('highlight-last-updated-badge');
        const releaseVersionEl = document.getElementById('highlight-release-version');
        const releaseDateEl = document.getElementById('highlight-release-date');

        const latestCountryEl = document.getElementById('highlight-latest-country');
        const latestCountryLink = document.getElementById('highlight-latest-country-link');

        const topSpeciesLink = document.getElementById('highlight-top-species-link');
        const topSpeciesNameEl = document.getElementById('highlight-top-species-name');
        const topSpeciesCommonEl = document.getElementById('highlight-top-species-common');
        const topSpeciesCountEl = document.getElementById('highlight-top-species-count');

        const topJurisdictionNameEl = document.getElementById('highlight-top-jurisdiction-name');
        const topJurisdictionCountryEl = document.getElementById('highlight-top-jurisdiction-country');
        const topJurisdictionCountEl = document.getElementById('highlight-top-jurisdiction-count');
        const topJurisdictionLink = document.getElementById('highlight-top-jurisdiction-link');

        if (jurisdictionsEl && data.stats) animateCount(jurisdictionsEl, data.stats.jurisdictions);
        if (speciesEl && data.stats) animateCount(speciesEl, data.stats.species);

        const formattedDate = formatDate(data.lastUpdated);
        if (lastUpdatedEl) lastUpdatedEl.textContent = formattedDate;
        if (lastUpdatedBadge) {
            lastUpdatedBadge.textContent = `Database updated on: ${formattedDate}`;
        }

        const release = data.release || {};
        if (releaseVersionEl) releaseVersionEl.textContent = release.version || '--';
        if (releaseDateEl) releaseDateEl.textContent = releaseDateText(release);

        // Latest country card
        const latestCountry = data.latestCountry || {};
        if (latestCountryEl) {
            latestCountryEl.textContent = latestCountry.name || 'New regions on the way';
        }
        if (latestCountryLink) {
            // Backend provides latestCountry.stateName = latest_country_region (views.py)
            // If it's missing, we can’t highlight a specific region reliably.
            setClickableDataset(latestCountryLink, latestCountry.stateName || '');
        }

        // Top species card
        if (topSpeciesLink && topSpeciesNameEl && topSpeciesCountEl && topSpeciesCommonEl) {
            const topSpecies = data.topSpecies;
            if (topSpecies && topSpecies.name) {
                topSpeciesNameEl.textContent = topSpecies.name;
                topSpeciesCommonEl.textContent = topSpecies.common_name || '';
                topSpeciesLink.href = `/species?name=${encodeURIComponent(topSpecies.name)}`;
                topSpeciesLink.classList.remove('disabled');

                if (topSpecies.jurisdiction_count) {
                    animateCount(topSpeciesCountEl, topSpecies.jurisdiction_count);
                } else {
                    topSpeciesCountEl.textContent = '--';
                }
            } else {
                topSpeciesNameEl.textContent = 'Data pending';
                topSpeciesCommonEl.textContent = '';
                topSpeciesLink.href = '#';
                topSpeciesLink.classList.add('disabled');
                topSpeciesCountEl.textContent = '--';
            }
        }

        // Top jurisdiction card (this is a REGION in the new model)
        if (topJurisdictionNameEl && topJurisdictionLink && topJurisdictionCountryEl) {
            const tj = data.topJurisdiction;
            if (tj && tj.name) {
                topJurisdictionNameEl.textContent = tj.name;
                topJurisdictionCountryEl.textContent = tj.country || '';

                // We only highlight by region name right now (map.js matches on region text).
                // If you later pass both country+region through the event, we can make it exact.
                setClickableDataset(topJurisdictionLink, tj.name);
            } else {
                topJurisdictionNameEl.textContent = 'Data pending';
                topJurisdictionCountryEl.textContent = '';
                setClickableDataset(topJurisdictionLink, '');
            }
        }

        if (topJurisdictionCountEl) {
            const count = data.topJurisdiction && data.topJurisdiction.species_count
                ? data.topJurisdiction.species_count
                : 0;
            if (count) animateCount(topJurisdictionCountEl, count);
            else topJurisdictionCountEl.textContent = '--';
        }
    }

    function initHighlights() {
        const section = document.getElementById('home-highlights');
        if (!section) return;

        fetch('/api/home-highlights')
            .then(response => {
                if (!response.ok) throw new Error('Failed to load highlights');
                return response.json();
            })
            .then(updateHighlights)
            .catch(error => {
                console.error(error);
                const badge = document.getElementById('highlight-last-updated-badge');
                if (badge) badge.textContent = 'Database updated on: unavailable';
            });
    }

    function handleRegionClick(event) {
        const regionName = event.currentTarget.dataset.region || event.currentTarget.dataset.state;
        if (!regionName) return;

        event.preventDefault();

        // Keep event name as-is so map.js doesn’t need another change.
        window.dispatchEvent(
            new CustomEvent('highlight:showState', {
                detail: { state: regionName, scroll: true }
            })
        );
    }

    document.addEventListener('DOMContentLoaded', function () {
        const topJurisdictionLink = document.getElementById('highlight-top-jurisdiction-link');
        const latestCountryLink = document.getElementById('highlight-latest-country-link');

        if (topJurisdictionLink) topJurisdictionLink.addEventListener('click', handleRegionClick);
        if (latestCountryLink) latestCountryLink.addEventListener('click', handleRegionClick);

        initHighlights();
    });
})();
