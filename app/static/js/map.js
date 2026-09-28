// static/js/map.js
document.addEventListener('DOMContentLoaded', function () {
    /******************************
     * BASIC CONFIG
     ******************************/
    const GEOJSON_PATH = '/static/data/geographic/';
    const MAP_CONFIG = window.MAP_CONFIG || {};
    const EU_MEMBERS = new Set([
        "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia",
        "Denmark", "Estonia", "Finland", "France", "Germany", "Greece",
        "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg",
        "Malta", "Netherlands", "Poland", "Portugal", "Romania", "Slovakia",
        "Slovenia", "Spain", "Sweden"
    ]);
    const EU_LABEL = "European Union";
    const COUNTRY_NAME_ALIASES = {
        "federal republic of germany": "Germany",
        "the federal republic of germany": "Germany",
        "deutschland": "Germany",
        "kingdom of saudi arabia": "Saudi Arabia",
        "united states of america": "United States"
    };

    // Region counts lookup keyed by stable geo_region_id.
    // Legacy key fallback (`country::region`) is kept for backward compatibility.
    let regionWeedData = {};
    let regionWeedDataByLegacyKey = {};
    let geojsonLayer = null;

    // Current selection
    let currentSelected = null; // { country, region }
    let pendingScrollToTable = false;

    // Toggle state management (new model)
    // Default ON for all three (as you want: "show all regulations that exist")
    const toggleState = {
        region: true,
        national: true,
        international: true
    };
    const SAMPLE_PLANT_LIMIT = 5;
    const ANONYMOUS_USER_COOKIE = 'anonymous_user_id';
    const AHA_ACTIVATED_COOKIE = 'aha_activated';
    const COOKIE_MAX_AGE_DAYS = 730;
    let activationInFlight = false;

    /******************************
     * UTILITY FUNCTIONS
     ******************************/

    // Simple hash so we can pick a colour ramp based on country name
    function hashString(str) {
        let hash = 0;
        if (!str) return 0;
        for (let i = 0; i < str.length; i++) {
            hash = (hash << 5) - hash + str.charCodeAt(i);
            hash |= 0; // convert to 32-bit int
        }
        return Math.abs(hash);
    }

    function normalizeLabel(value) {
        return String(value || '').trim().replace(/\s+/g, ' ');
    }

    function canonicalCountryName(value) {
        const normalized = normalizeLabel(value);
        if (!normalized) return '';
        return COUNTRY_NAME_ALIASES[normalized.toLowerCase()] || normalized;
    }

    function canonicalRegionName(value) {
        return normalizeLabel(value).replace(/\s*&\s*/g, ' & ');
    }

    // Get a colour config (thresholds + scheme) for a given country name
    function getCountryConfig(countryName) {
        const isEU = EU_MEMBERS.has(countryName);
        const cacheKey = isEU ? 'EU' : (countryName || 'default');

        MAP_CONFIG._countryCache = MAP_CONFIG._countryCache || {};
        if (MAP_CONFIG._countryCache[cacheKey]) return MAP_CONFIG._countryCache[cacheKey];

        if (isEU) {
            const thresholds = MAP_CONFIG.euThresholds || MAP_CONFIG.defaultThresholds || [0, 1, 2, 3, 4, 5];
            const scheme = MAP_CONFIG.euColorRamp || ["#e9f2ff", "#d3e5ff", "#b7d4ff", "#97c1ff", "#74a9ff", "#4f90f0", "#2c74d4"];
            const config = { thresholds, scheme };
            MAP_CONFIG._countryCache[cacheKey] = config;
            return config;
        }

        const ramps = MAP_CONFIG.defaultColorRamps || [];
        const thresholds = MAP_CONFIG.defaultThresholds || [0, 1, 2, 3, 4, 5];

        let scheme;
        if (!ramps.length) {
            scheme = ['#f0f0f0', '#f0f0f0', '#f0f0f0', '#f0f0f0', '#f0f0f0', '#f0f0f0', '#f0f0f0'];
        } else {
            const idx = hashString(cacheKey) % ramps.length;
            scheme = ramps[idx];
        }

        const config = { thresholds, scheme };
        MAP_CONFIG._countryCache[cacheKey] = config;
        return config;
    }

    function getColor(value, countryName) {
        const countryConfig = getCountryConfig(countryName);
        const thresholds = countryConfig.thresholds;
        const scheme = countryConfig.scheme;

        if (value > thresholds[5]) return scheme[6];
        if (value > thresholds[4]) return scheme[5];
        if (value > thresholds[3]) return scheme[4];
        if (value > thresholds[2]) return scheme[3];
        if (value > thresholds[1]) return scheme[2];
        if (value > thresholds[0]) return scheme[1];
        return scheme[0];
    }

    function slugify(value) {
        return String(value || '')
            .trim()
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-+|-+$/g, '');
    }

    function geojsonSlugFromFilename(filename) {
        return String(filename || '')
            .replace(/\.geojson$/i, '')
            .trim()
            .toLowerCase();
    }

    function geojsonUrl(filename) {
        const geojsonPath = MAP_CONFIG.geojsonPath || GEOJSON_PATH;
        const url = geojsonPath + filename;
        const dataVersion = String(MAP_CONFIG.dataVersion || '').trim();
        if (!dataVersion) return url;
        const separator = url.includes('?') ? '&' : '?';
        return `${url}${separator}v=${encodeURIComponent(dataVersion)}`;
    }

    function buildGeoRegionId(geojsonSlug, region) {
        return `geo:${geojsonSlug}:${slugify(canonicalRegionName(region))}`;
    }

    function inferCountryFromFilename(filename) {
        // e.g. "united_states.geojson" -> "United States"
        const base = filename.replace(/\.geojson$/i, '');
        return canonicalCountryName(base
            .replace(/[_-]+/g, ' ')
            .replace(/\b\w/g, c => c.toUpperCase())
            .trim());
    }

    function extractRegionName(feature) {
        const props = feature && feature.properties ? feature.properties : {};
        const country = extractCountryName(feature);
        let sawCountryLevelName = false;
        // Prefer canonical `region`; fall back to source-specific names.
        const possibleNameProps = ['region', 'REGION', 'STATE_NAME', 'state', 'STATE', 'name', 'NAME', 'shapeName'];
        for (const prop of possibleNameProps) {
            if (props[prop]) {
                const v = canonicalRegionName(props[prop]);
                if (!v) continue;
                if (country) {
                    const canonicalName = canonicalCountryName(v);
                    if (canonicalName && canonicalName.toLowerCase() === country.toLowerCase()) {
                        // Some files expose official long-form names for the
                        // whole country. Collapse those to country-level labels.
                        sawCountryLevelName = true;
                        continue;
                    }
                }
                if (sawCountryLevelName) {
                    // If we've already identified a country-level name, ignore
                    // fallback labels (for example verbose `shapeName` values).
                    continue;
                }
                return v;
            }
        }
        if (sawCountryLevelName && country) return country;
        return country || null;
    }

    function extractCountryName(feature) {
        const props = feature && feature.properties ? feature.properties : {};
        if (props.country) {
            const v = canonicalCountryName(props.country);
            if (v) return v;
        }
        return '';
    }

    function extractGeoRegionId(feature) {
        const props = feature && feature.properties ? feature.properties : {};
        if (props.geo_region_id) {
            return String(props.geo_region_id).trim();
        }
        const geojsonSlug = props.geojson_slug ? String(props.geojson_slug).trim() : '';
        const region = extractRegionName(feature);
        if (!geojsonSlug || !region) return '';
        return buildGeoRegionId(geojsonSlug, region);
    }

    function regionKey(country, region) {
        return `${canonicalCountryName(country)}::${canonicalRegionName(region)}`;
    }

    function getRegionData(geoRegionId, country, region) {
        if (geoRegionId && regionWeedData[geoRegionId]) {
            return regionWeedData[geoRegionId];
        }

        const exact = regionWeedDataByLegacyKey[regionKey(country, region)];
        if (exact) return exact;

        const countryFallback = regionWeedDataByLegacyKey[regionKey(country, country)];
        if (countryFallback) {
            return {
                count: countryFallback.count || 0,
                country: canonicalCountryName(country),
                region: canonicalRegionName(region),
                count_source_level: 'national',
                jurisdiction_match: 'country_overlay',
            };
        }

        return {
            count: 0,
            country,
            region,
            count_source_level: 'none',
            jurisdiction_match: 'none',
        };
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function primaryCommonName(value) {
        const raw = String(value || '').trim();
        if (!raw) return '';
        return raw.split(',').map(part => part.trim()).find(Boolean) || raw;
    }

    function getCookie(name) {
        const encodedName = encodeURIComponent(name);
        const cookieParts = document.cookie ? document.cookie.split('; ') : [];
        for (const part of cookieParts) {
            const [rawKey, rawValue = ''] = part.split('=');
            if (rawKey === encodedName) {
                return decodeURIComponent(rawValue);
            }
        }
        return null;
    }

    function setCookie(name, value, maxAgeDays) {
        const expires = new Date(Date.now() + maxAgeDays * 24 * 60 * 60 * 1000).toUTCString();
        const secure = window.location.protocol === 'https:' ? '; Secure' : '';
        document.cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value)}; Expires=${expires}; Path=/; SameSite=Lax${secure}`;
    }

    function generateAnonymousId() {
        if (window.crypto && typeof window.crypto.randomUUID === 'function') {
            return window.crypto.randomUUID();
        }
        return `anon-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }

    function ensureAnonymousId() {
        let anonymousId = getCookie(ANONYMOUS_USER_COOKIE);
        if (!anonymousId) {
            anonymousId = generateAnonymousId();
            setCookie(ANONYMOUS_USER_COOKIE, anonymousId, COOKIE_MAX_AGE_DAYS);
        }
        return anonymousId;
    }

    function metricsEnabled() {
        return (
            MAP_CONFIG.oozrMetricsEnabled === true
            && typeof window.analyticsConsentGranted === 'function'
            && window.analyticsConsentGranted()
        );
    }

    function oozrBaseUrl() {
        return String(MAP_CONFIG.oozrBaseUrl || '').trim().replace(/\/$/, '');
    }

    function oozrProjectSlug() {
        const configured = String(MAP_CONFIG.oozrProjectSlug || '').trim();
        return configured || 'regulatedplants';
    }

    async function sendAhaActivationIfNeeded(weedsCount) {
        if (!metricsEnabled()) return;
        if (!Number.isFinite(weedsCount) || weedsCount <= 0) return;
        if (getCookie(AHA_ACTIVATED_COOKIE) === '1') return;
        if (activationInFlight) return;

        const baseUrl = oozrBaseUrl();
        if (!baseUrl) return;

        activationInFlight = true;
        try {
            const response = await fetch(`${baseUrl}/api/activate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project: oozrProjectSlug(),
                    anonymous_id: ensureAnonymousId(),
                    timestamp: new Date().toISOString()
                })
            });

            if (response.ok) {
                setCookie(AHA_ACTIVATED_COOKIE, '1', COOKIE_MAX_AGE_DAYS);
            }
        } catch (error) {
            console.error('Error sending activation event:', error);
        } finally {
            activationInFlight = false;
        }
    }

    function buildRegionLookup(list) {
        const byId = {};
        const byLegacyKey = {};
        if (!Array.isArray(list)) return { byId, byLegacyKey };

        for (const row of list) {
            if (!row || !row.country || !row.region) continue;
            const country = canonicalCountryName(row.country);
            const region = canonicalRegionName(row.region);
            if (!country || !region) continue;

            const payload = {
                count: row.count || 0,
                country,
                region,
                geo_region_id: row.geo_region_id || null,
                count_source_level: row.count_source_level || 'none',
                jurisdiction_match: row.jurisdiction_match || 'none',
                regulation_status: row.regulation_status || 'unknown',
                jurisdiction_uid: row.jurisdiction_uid || null,
                canonical_display_name: row.canonical_display_name || region,
                geojson_slug: row.geojson_slug || null,
            };

            if (payload.geo_region_id) {
                byId[payload.geo_region_id] = payload;
            }
            byLegacyKey[regionKey(country, region)] = payload;
        }
        return { byId, byLegacyKey };
    }

    function displayCountryLabel(country) {
        if (!country) return "";
        return EU_MEMBERS.has(country) ? EU_LABEL : country;
    }

    function formatLocation(region, country) {
        const displayCountry = displayCountryLabel(country);
        if (!region) return displayCountry || "Unknown";

        // Avoid duplication when region == country (e.g., New Zealand)
        if (region === displayCountry) return displayCountry || region;

        // EU: use group label as country part
        if (EU_MEMBERS.has(country)) return `${region}, ${EU_LABEL}`;

        return displayCountry ? `${region}, ${displayCountry}` : region;
    }

    // ✅ Correct querystring builder (prevents your `...?region=X?includeY=...` bug forever)
    function buildQueryParams() {
        const params = new URLSearchParams();
        params.set('includeRegion', toggleState.region ? 'true' : 'false');
        params.set('includeNational', toggleState.national ? 'true' : 'false');
        params.set('includeInternational', toggleState.international ? 'true' : 'false');
        return params.toString();
    }

    function researcherLoginUrl() {
        const next = `${window.location.pathname}${window.location.search}`;
        return `/auth/signup?next=${encodeURIComponent(next || '/')}`;
    }

    function enterpriseAccessUrl() {
        return MAP_CONFIG.enterpriseAccessUrl || '/api';
    }

    function allTogglesOff() {
        return (!toggleState.region && !toggleState.national && !toggleState.international);
    }

    function validateToggles() {
        const errorElement = document.getElementById('toggleError');
        if (!errorElement) return;

        if (allTogglesOff()) {
            errorElement.classList.remove('d-none');

            const tableElement = document.getElementById('state-species');
            if (tableElement) tableElement.classList.add('d-none');

            currentSelected = null;

            // Close and unbind all tooltips
            if (geojsonLayer) {
                geojsonLayer.eachLayer(function (layer) {
                    layer.closeTooltip();
                    layer.unbindTooltip();
                });
            }
        } else {
            errorElement.classList.add('d-none');
        }
    }

    /******************************
     * API: COUNTS + MAP COLORING
     ******************************/

    function refreshMapColors() {
        if (allTogglesOff()) {
            if (geojsonLayer) geojsonLayer.setStyle(styleFeature);
            return;
        }

        fetch(`/api/region-weed-counts?${buildQueryParams()}`)
            .then(r => r.json())
            .then(list => {
                const lookup = buildRegionLookup(list);
                regionWeedData = lookup.byId;
                regionWeedDataByLegacyKey = lookup.byLegacyKey;
                if (geojsonLayer) geojsonLayer.setStyle(styleFeature);
            })
            .catch(err => console.error('Error refreshing map colors:', err));
    }

    function refreshTableData() {
        if (!currentSelected) return;
        loadRegionDetails(currentSelected.geoRegionId, currentSelected.country, currentSelected.region);
    }

    /******************************
     * TABLE RENDERING
     ******************************/

    function buildScopeText() {
        const parts = [];
        if (toggleState.region) parts.push('Regional');
        if (toggleState.national) parts.push('National');
        if (toggleState.international) parts.push('International');
        return parts.length ? parts.join(' + ') : 'No layers selected';
    }

    function updateTable(country, region, weeds, hasAnyData, options = {}) {
        const scopeText = buildScopeText();
        const allWeeds = Array.isArray(weeds) ? weeds : [];
        const totalCount = Number.isFinite(options.totalCount) ? options.totalCount : allWeeds.length;
        const isSample = Boolean(options.isSample);
        const authenticated = Boolean(options.authenticated);
        const showFullControls = authenticated && allWeeds.length > SAMPLE_PLANT_LIMIT;

        // Title
        const titleLocation = formatLocation(region, country);
        const title = `Regulated plants in ${titleLocation}`;
        const titleEl = document.getElementById('state-title');
        if (titleEl) titleEl.textContent = title;

        const warningEl = document.getElementById('state-warning');
        if (warningEl) {
            const shouldShowSampleWarning = Boolean(hasAnyData) && isSample && allWeeds.length > 0;
            if (shouldShowSampleWarning) {
                warningEl.innerHTML = `<strong>Research access sample.</strong> Showing ${allWeeds.length.toLocaleString()} of ${totalCount.toLocaleString()} regulated plants. <a href="${researcherLoginUrl()}">Request research access</a> to view the full website list. Enterprise teams should use <a href="${enterpriseAccessUrl()}">enterprise access</a> for automated compliance checks.`;
                warningEl.classList.remove('d-none');
            } else {
                warningEl.innerHTML = '';
                warningEl.classList.add('d-none');
            }
        }

        const subtitleEl = document.getElementById('state-subtitle');
        if (subtitleEl) {
            const countText = totalCount > 0 ? `Plants: ${totalCount.toLocaleString()}` : '';
            subtitleEl.textContent = [scopeText ? `Filters: ${scopeText}` : '', countText].filter(Boolean).join(' · ');
        }

        const table = document.getElementById('species-table');
        if (!table) return;

        const hasDataAnyLevel = !!hasAnyData;
        const isEUCountry = EU_MEMBERS.has(country);
        let emptyMessage = 'No plants are available for the selected filters. Please change the level of regulation using the toggles.';
        if (!hasDataAnyLevel && !isEUCountry) {
            emptyMessage = 'No published species specific regulations have been found for this country.';
        }

        if ($.fn.DataTable.isDataTable(table)) {
            $(table).DataTable().destroy();
            $(table).empty();
            $(table).html('<thead><tr><th>Scientific Name</th><th>Common Name</th><th>Family</th><th>Source</th></tr></thead>');
        }

        $(table).DataTable({
            data: allWeeds,
            columns: [
                {
                    data: 'canonical_name',
                    title: 'Scientific Name',
                    width: '27%',
                    render: function (data, type, row) {
                        if (type !== 'display') return data || '';
                        if (type === 'display' && data) {
                            const speciesUrl = row.species_id
                                ? `/species?species_id=${encodeURIComponent(row.species_id)}`
                                : `/species?name=${encodeURIComponent(data)}`;
                            return `<a href="${speciesUrl}" class="species-link" target="_blank"><em>${escapeHtml(data)}</em></a>`;
                        }
                        return 'Unknown';
                    }
                },
                {
                    data: 'common_name',
                    title: 'Common Name',
                    width: '23%',
                    render: function (data, type, row) {
                        const displayCommonName = primaryCommonName(data);
                        if (type !== 'display') return data || '';
                        if (!displayCommonName || String(data).includes('No English common names available')) {
                            return `(${escapeHtml(row.canonical_name || 'Unknown')})`;
                        }
                        return escapeHtml(displayCommonName);
                    }
                },
                {
                    data: 'family_name',
                    title: 'Family',
                    width: '15%',
                    render: function (data) {
                        return escapeHtml(data || 'Unknown');
                    }
                },
                {
                    data: 'source_authority',
                    title: 'Source',
                    width: '35%',
                    render: function (data, type, row) {
                        const sourceAuthority = data || row.level || 'Unknown';
                        if (type !== 'display') return sourceAuthority;
                        return `<span>${escapeHtml(sourceAuthority)}</span>`;
                    }
                }
            ],
            paging: showFullControls && allWeeds.length > 25,
            searching: showFullControls,
            info: showFullControls,
            lengthChange: showFullControls && allWeeds.length > 25,
            pageLength: 25,
            order: [[0, 'asc']],
            autoWidth: false,
            width: '100%',
            language: {
                emptyTable: emptyMessage
            },
            initComplete: function () {
                const element = document.getElementById('state-species');
                if (element) {
                    element.classList.remove('d-none');
                    element.classList.add('updated');
                    setTimeout(() => element.classList.remove('updated'), 1000);


                    if (pendingScrollToTable || (window.L && L.Browser && L.Browser.mobile)) {
                        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                        pendingScrollToTable = false;
                    }
                }
            }
        });
    }

    function loadRegionDetails(geoRegionId, country, region) {
        if (!geoRegionId) return;

        const url =
            `/api/region?geo_region_id=${encodeURIComponent(geoRegionId)}&${buildQueryParams()}`;

        fetch(url)
            .then(r => r.json())
            .then(result => {
                const weeds = Array.isArray(result) ? result : (result.weeds || []);
                const hasAnyData = Array.isArray(result) ? weeds.length > 0 : !!result.has_any_data;
                const resolvedGeo = result.geo_region || {};
                const resolvedCountry = resolvedGeo.country || country;
                const resolvedRegion = resolvedGeo.region || region;
                updateTable(resolvedCountry, resolvedRegion, weeds, hasAnyData, {
                    authenticated: !Array.isArray(result) && !!result.authenticated,
                    isSample: !Array.isArray(result) && !!result.is_sample,
                    sampleLimit: !Array.isArray(result) ? result.sample_limit : SAMPLE_PLANT_LIMIT,
                    totalCount: !Array.isArray(result) && Number.isFinite(result.total_count)
                        ? result.total_count
                        : weeds.length
                });
                sendAhaActivationIfNeeded(weeds.length);
            })
            .catch(err => {
                console.error('Error fetching region data:', err);
                const titleEl = document.getElementById('state-title');
                if (titleEl) titleEl.textContent = `Error loading data for ${formatLocation(region, country)}`;
                const warningEl = document.getElementById('state-warning');
                if (warningEl) {
                    warningEl.innerHTML = '';
                    warningEl.classList.add('d-none');
                }
                const subtitleEl = document.getElementById('state-subtitle');
                if (subtitleEl) subtitleEl.textContent = '';
            });
    }

    /******************************
     * STYLE FUNCTION
     ******************************/
    function styleFeature(feature) {
        if (allTogglesOff()) {
            return {
                fillColor: '#ffffff',
                weight: 1,
                opacity: 1,
                color: '#cccccc',
                fillOpacity: 0.3
            };
        }

        const region = extractRegionName(feature);
        const country = extractCountryName(feature);
        const geoRegionId = extractGeoRegionId(feature);

        if (!region || !country) {
            return {
                fillColor: '#cccccc',
                weight: 1,
                opacity: 1,
                color: 'white',
                fillOpacity: 0.5
            };
        }

        const data = getRegionData(geoRegionId, country, region);
        const weedCount = data.count || 0;
        const locationLabel = formatLocation(region, country);

        return {
            fillColor: getColor(weedCount, country),
            weight: 1,
            opacity: 1,
            color: 'white',
            fillOpacity: 0.7
        };
    }

    /******************************
     * MAP INITIALIZATION
     ******************************/
    const map = L.map('map', {
        dragging: !L.Browser.mobile,
        tap: !L.Browser.mobile,
        worldCopyJump: false,
        maxBoundsViscosity: 1.0,
        attributionControl: true,
        zoomControl: true
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    /******************************
     * DATA LOADING
     ******************************/
    fetch(`/api/region-weed-counts?${buildQueryParams()}`)
        .then(r => r.json())
        .then(list => {
            const lookup = buildRegionLookup(list);
            regionWeedData = lookup.byId;
            regionWeedDataByLegacyKey = lookup.byLegacyKey;
            return fetch('/api/geojson-files');
        })
        .then(r => {
            if (!r.ok) throw new Error('Failed to load GeoJSON file list');
            return r.json();
        })
        .then(geojsonFiles => {
            const geoJsonPromises = geojsonFiles.map(filename =>
                fetch(geojsonUrl(filename))
                    .then(response => {
                        if (!response.ok) throw new Error(`Failed to load ${filename}`);
                        return response.json();
                    })
                    .then(geojson => {
                        // Force canonical country from filename so GeoJSON long-form
                        // aliases do not break API key matching.
                        const geojsonSlug = geojsonSlugFromFilename(filename);
                        const inferredCountry = inferCountryFromFilename(filename);
                        if (geojson && Array.isArray(geojson.features)) {
                            geojson.features.forEach(f => {
                                f.properties = f.properties || {};
                                f.properties.country = inferredCountry;
                                f.properties.geojson_slug = geojsonSlug;
                                const inferredRegion = extractRegionName(f);
                                if (inferredRegion) {
                                    f.properties.geo_region_id = buildGeoRegionId(geojsonSlug, inferredRegion);
                                }
                            });
                        }
                        return geojson;
                    })
                    .catch(error => {
                        console.error(`Error loading ${filename}:`, error);
                        return { type: 'FeatureCollection', features: [] };
                    })
            );

            return Promise.all(geoJsonPromises);
        })
        .then(results => {
            const combinedFeatures = [];
            results.forEach(result => {
                if (result.features && Array.isArray(result.features)) {
                    combinedFeatures.push(...result.features);
                }
            });

            const combinedGeoJSON = {
                type: 'FeatureCollection',
                features: combinedFeatures
            };

            /******************************
             * MAP INTERACTION
             ******************************/
            let previouslyClickedLayer = null;

            geojsonLayer = L.geoJson(combinedGeoJSON, {
                style: styleFeature,
                onEachFeature: function (feature, layer) {
                    const region = extractRegionName(feature);
                    const country = extractCountryName(feature);
                    const geoRegionId = extractGeoRegionId(feature);
                    if (!region || !country) return;

                    const key = regionKey(country, region);

                    // Click
                    layer.on('click', function () {
                        if (allTogglesOff()) return;

                        if (previouslyClickedLayer) geojsonLayer.resetStyle(previouslyClickedLayer);
                        previouslyClickedLayer = layer;

                        currentSelected = { geoRegionId, country, region };
                        pendingScrollToTable = true;
                        loadRegionDetails(geoRegionId, country, region);
                    });

                    // Hover
                    layer.on('mouseover', function () {
                        if (allTogglesOff()) {
                            layer.closeTooltip();
                            layer.unbindTooltip();
                            return;
                        }

                        layer.setStyle({ weight: 2, fillOpacity: 0.9 });

                        const data = getRegionData(geoRegionId, country, region);
                        const weedCount = data.count || 0;
                        const locationLabel = formatLocation(region, country);
                        const safeLocationLabel = escapeHtml(locationLabel);

                        const tooltipContent = `
                            <strong>${safeLocationLabel}</strong><br>
                            Regulated Plants: ${weedCount}
                        `;

                        layer
                            .bindTooltip(tooltipContent, {
                                sticky: true,
                                direction: 'top',
                                opacity: 0.9
                            })
                            .openTooltip();
                    });

                    layer.on('mouseout', function () {
                        if (allTogglesOff()) return;

                        geojsonLayer.resetStyle(layer);
                        if (layer === previouslyClickedLayer) {
                            layer.setStyle({ weight: 2, fillOpacity: 0.9 });
                        }
                    });

                    // For highlight event matching (region name)
                    layer.featureRegionName = region;
                    layer.featureRegionNameLower = region.toLowerCase();
                    layer.featureCountryName = country;
                    layer.featureKey = key;
                    layer.featureGeoRegionId = geoRegionId;
                }
            }).addTo(map);

            // Bounds
            const northAmericaAndAustraliaBounds = [
                [-45, -170],
                [70, 155]
            ];

            map.fitBounds(northAmericaAndAustraliaBounds, {
                padding: [20, 20],
                maxZoom: 3
            });

            map.setMaxBounds([
                [-90, -190],
                [90, 190]
            ]);

            map.options.worldCopyJump = false;
            map.setMinZoom(map.getZoom());
        })
        .catch(error => {
            console.error('Error loading map data:', error);
            const mapElement = document.getElementById('map');
            if (mapElement) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'map-error-message';
                errorDiv.innerHTML = '<strong>Error:</strong> Failed to load map data.';
                mapElement.appendChild(errorDiv);
            }
        });

    /******************************
     * HIGHLIGHT EVENT (home_highlights.js)
     ******************************/
    window.addEventListener('highlight:showState', function (event) {
        // We keep the same event name so home_highlights.js doesn't need changes.
        // It passes "state", but in the new model that is actually "region".
        const targetRegion = event.detail && event.detail.state;
        if (!targetRegion) return;

        const normalizedTarget = targetRegion.toLowerCase();
        if (event.detail && event.detail.scroll) pendingScrollToTable = true;

        if (allTogglesOff()) {
            validateToggles();
            return;
        }

        let matchedLayer = null;

        if (geojsonLayer) {
            geojsonLayer.eachLayer(function (layer) {
                if (layer.featureRegionNameLower && layer.featureRegionNameLower === normalizedTarget) {
                    matchedLayer = layer;
                }
            });
        }

        if (matchedLayer) {
            matchedLayer.fire('click');
        } else {
            console.warn('No matching region found for highlight:', targetRegion);
        }
    });

    /******************************
     * TOGGLE EVENT LISTENERS
     ******************************/
    const nationalToggle = document.getElementById('nationalToggle');
    const regionToggle = document.getElementById('regionToggle');
    const internationalToggle = document.getElementById('internationalToggle');

    if (nationalToggle) {
        nationalToggle.addEventListener('change', function () {
            toggleState.national = this.checked;
            validateToggles();
            refreshMapColors();
            if (currentSelected && !allTogglesOff()) refreshTableData();
        });
    }

    if (regionToggle) {
        regionToggle.addEventListener('change', function () {
            toggleState.region = this.checked;
            validateToggles();
            refreshMapColors();
            if (currentSelected && !allTogglesOff()) refreshTableData();
        });
    }

    if (internationalToggle) {
        internationalToggle.addEventListener('change', function () {
            toggleState.international = this.checked;
            validateToggles();
            refreshMapColors();
            if (currentSelected && !allTogglesOff()) refreshTableData();
        });
    }

    // Initial validation
    validateToggles();
});
