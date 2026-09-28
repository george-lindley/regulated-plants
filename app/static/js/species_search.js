// static/js/species_search.js
document.addEventListener('DOMContentLoaded', function () {
    /******************************
     * URL PARAMS
     ******************************/
    function getUrlParameter(name) {
        name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
        const regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
        const results = regex.exec(location.search);
        return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
    }

    function getPrimaryCommonName(value) {
        const raw = String(value || '').trim();
        if (!raw) return '';
        return raw.split(',').map(part => part.trim()).find(Boolean) || raw;
    }

    /******************************
     * SELECT2 SEARCH
     ******************************/
    $('#weedSearch').select2({
        placeholder: 'Start typing a common or scientific name...',
        minimumInputLength: 2,
        ajax: {
            url: '/species/api/search',
            dataType: 'json',
            delay: 250,
            data: function (params) {
                return { q: params.term };
            },
            processResults: function (data) {
                return {
                    results: data.map(weed => {
                        let displayCommonName = getPrimaryCommonName(weed.common_name);
                        if (!displayCommonName || displayCommonName.includes('No English common names available')) {
                            displayCommonName = null;
                        }

                        return {
                            id: weed.species_id || weed.usage_key,
                            text: displayCommonName
                                ? `${displayCommonName} (${weed.canonical_name})`
                                : `(${weed.canonical_name})`,
                            common_name: displayCommonName || weed.canonical_name,
                            canonical_name: weed.canonical_name,
                            family_name: weed.family_name,
                            synonyms: weed.synonyms,
                            species_id: weed.species_id,
                            usage_key: weed.usage_key,
                            lifeform_final: weed.lifeform_final,
                            lifespan_final: weed.lifespan_final,
                            habitat_final: weed.habitat_final,
                            woodiness_final: weed.woodiness_final
                        };
                    })
                };
            },
            cache: true
        },
        templateResult: function (weed) {
            if (!weed.id) return weed.text;

            let commonName = getPrimaryCommonName(weed.common_name);
            if (commonName.includes('No English common names available')) commonName = '';

            const canonicalName = weed.canonical_name || '';
            const container = $('<div>');

            if (commonName) {
                $('<div>')
                    .addClass('common-name')
                    .text(commonName)
                    .appendTo(container);
            }

            $('<div>')
                .addClass(`canonical-name ${commonName ? 'text-muted small' : ''}`.trim())
                .text(commonName ? canonicalName : `(${canonicalName})`)
                .appendTo(container);

            return container;
        }
    });

    $('#weedSearch').on('select2:select', function (e) {
        const selectedWeed = e.params.data;
        displayWeedDetails(selectedWeed);
    });

    $('#weedSearch').on('select2:clear', function () {
        document.getElementById('results').classList.add('d-none');
    });

    /******************************
     * DETAILS RENDER
     ******************************/
    function displayCountryName(country) {
        if (!country) return country;
        const normalized = String(country).trim();
        if (normalized.toUpperCase() === 'EU') return 'European Union';
        return normalized;
    }

    function formatTraitValue(value) {
        const raw = String(value || '').trim();
        if (!raw) return 'Not Available';

        // Preserve short all-caps codes (e.g., "W").
        if (raw === raw.toUpperCase() && raw.length <= 4) return raw;

        return raw
            .toLowerCase()
            .replace(/(^|[\s\-\/,(])([a-z])/g, (_, prefix, letter) => `${prefix}${letter.toUpperCase()}`);
    }

    /******************************
     * PHOTO GALLERY (GBIF)
     ******************************/
    // Guards against a slow gallery response landing after the user has already
    // moved on to a different species.
    let galleryRequestToken = 0;

    function openPhotoModal(photo, speciesName) {
        const modalElement = document.getElementById('speciesPhotoModal');
        if (!modalElement || typeof bootstrap === 'undefined') return;

        document.getElementById('speciesPhotoModalLabel').textContent = speciesName || 'Photograph';

        const image = document.getElementById('speciesPhotoModalImage');
        image.src = photo.full_url;
        image.alt = speciesName ? `Photograph of ${speciesName}` : 'Species photograph';

        const credit = document.getElementById('speciesPhotoModalCredit');
        credit.textContent = '';
        credit.appendChild(document.createTextNode(`${photo.creator} — `));

        const licenceLink = document.createElement('a');
        licenceLink.href = photo.licence_url;
        licenceLink.target = '_blank';
        licenceLink.rel = 'noopener';
        licenceLink.textContent = photo.licence;
        credit.appendChild(licenceLink);

        credit.appendChild(document.createTextNode(' — '));

        const occurrenceLink = document.createElement('a');
        occurrenceLink.href = photo.occurrence_url;
        occurrenceLink.target = '_blank';
        occurrenceLink.rel = 'noopener';
        occurrenceLink.textContent = 'view occurrence on GBIF';
        credit.appendChild(occurrenceLink);

        bootstrap.Modal.getOrCreateInstance(modalElement).show();
    }

    function buildPhotoTile(photo, speciesName) {
        const tile = document.createElement('button');
        tile.type = 'button';
        tile.className = 'species-photo';
        tile.setAttribute('role', 'listitem');

        const image = document.createElement('img');
        image.src = photo.thumbnail_url;
        image.alt = speciesName ? `Photograph of ${speciesName}` : 'Species photograph';
        image.loading = 'lazy';
        image.decoding = 'async';
        // GBIF's image cache occasionally cannot resolve a source image; drop the
        // tile rather than leaving a broken frame in the grid.
        image.addEventListener('error', function () {
            tile.remove();
        });
        tile.appendChild(image);

        const caption = document.createElement('span');
        caption.className = 'species-photo-caption';
        caption.appendChild(document.createTextNode(`${photo.creator} `));

        const licence = document.createElement('span');
        licence.className = 'licence';
        licence.textContent = photo.licence;
        caption.appendChild(licence);
        tile.appendChild(caption);

        tile.addEventListener('click', function () {
            openPhotoModal(photo, speciesName);
        });

        return tile;
    }

    function renderGallery(usageKey, speciesName) {
        const gallery = document.getElementById('speciesGallery');
        const grid = document.getElementById('speciesGalleryGrid');
        if (!gallery || !grid) return;

        gallery.classList.add('d-none');
        grid.innerHTML = '';

        if (!usageKey) return;

        const token = ++galleryRequestToken;

        fetch(`/species/api/photos/by-key/${encodeURIComponent(usageKey)}`)
            .then(response => (response.ok ? response.json() : { photos: [] }))
            .then(data => {
                if (token !== galleryRequestToken) return;

                const photos = Array.isArray(data.photos) ? data.photos : [];
                if (photos.length === 0) return;

                photos.forEach(photo => grid.appendChild(buildPhotoTile(photo, speciesName)));
                grid.classList.toggle('is-featured', photos.length === 5);
                gallery.classList.remove('d-none');
            })
            .catch(error => {
                // A missing gallery is cosmetic; never let it surface as an error.
                console.warn('Species photos unavailable:', error);
            });
    }

    function formatJurisdictionCount(count) {
        const number = Number(count || 0);
        return `${number.toLocaleString()} ${number === 1 ? 'jurisdiction' : 'jurisdictions'}`;
    }

    function renderAnonymousRegulationSummary(statesList, jurisdictionCount) {
        const loginUrl = statesList.dataset.researcherLoginUrl || '/auth/signup';
        const apiRequestUrl = statesList.dataset.apiRequestUrl || '/api';

        if (!jurisdictionCount) {
            statesList.innerHTML = `
                <div class="list-group-item">
                    <p class="mb-1">No regulations found for this species.</p>
                </div>
            `;
            return;
        }

        statesList.innerHTML = `
            <div class="list-group-item species-access-summary">
                <h5 class="mb-2">Regulated in ${formatJurisdictionCount(jurisdictionCount)}</h5>
                <p class="mb-0">
                    Detailed website jurisdiction lists are available through Research Access.
                    <a href="${loginUrl}">Request research access</a>. Enterprise teams can
                    <a href="${apiRequestUrl}">request enterprise access</a> for automated compliance checks.
                </p>
            </div>
        `;
    }

    function normalizeRegulationResponse(response) {
        if (!response || typeof response !== 'object') {
            return {
                authenticated: true,
                jurisdiction_count: 0,
                regulations_by_country: {}
            };
        }

        if (
            Object.prototype.hasOwnProperty.call(response, 'regulations_by_country') ||
            Object.prototype.hasOwnProperty.call(response, 'authenticated') ||
            Object.prototype.hasOwnProperty.call(response, 'jurisdiction_count')
        ) {
            return {
                authenticated: Boolean(response.authenticated),
                jurisdiction_count: Number(response.jurisdiction_count || 0),
                regulations_by_country: response.regulations_by_country || {}
            };
        }

        // Backward compatibility for older local servers that returned only the grouped map.
        const count = Object.values(response).reduce((total, jurisdictions) => {
            return total + (Array.isArray(jurisdictions) ? jurisdictions.length : 0);
        }, 0);

        return {
            authenticated: true,
            jurisdiction_count: count,
            regulations_by_country: response
        };
    }

    function displayWeedDetails(selectedWeed) {
        let displayName = getPrimaryCommonName(selectedWeed.common_name);
        if (!displayName || displayName.includes('No English common names available')) {
            displayName = `(${selectedWeed.canonical_name || 'Unknown'})`;
        }

        document.getElementById('weedTitle').textContent = displayName;
        document.getElementById('weedCanonicalName').textContent = selectedWeed.canonical_name;
        document.getElementById('weedFamily').textContent = selectedWeed.family_name || 'Not available';
        document.getElementById('weedLifeform').textContent = formatTraitValue(selectedWeed.lifeform_final);
        document.getElementById('weedLifespan').textContent = formatTraitValue(selectedWeed.lifespan_final);
        document.getElementById('weedHabitat').textContent = formatTraitValue(selectedWeed.habitat_final);
        document.getElementById('weedWoodiness').textContent = formatTraitValue(selectedWeed.woodiness_final);

        // Synonyms (first 3)
        const synonymsSection = document.getElementById('synonymsSection');
        const weedSynonyms = document.getElementById('weedSynonyms');

        if (selectedWeed.synonyms && selectedWeed.synonyms.trim() !== '') {
            const allSynonyms = selectedWeed.synonyms.split(',');
            const truncatedSynonyms = allSynonyms.length > 3
                ? allSynonyms.slice(0, 3).join(', ')
                : selectedWeed.synonyms;

            weedSynonyms.textContent = truncatedSynonyms;
            synonymsSection.classList.remove('d-none');
        } else {
            synonymsSection.classList.add('d-none');
        }

        // GBIF link
        const gbifLink = document.getElementById('gbifLink');
        gbifLink.href = `https://www.gbif.org/species/${selectedWeed.usage_key}`;

        // Photos are fetched independently so a slow or failing GBIF call never
        // delays the regulation summary, which is the page's real payload.
        renderGallery(selectedWeed.usage_key, selectedWeed.canonical_name);

        // Fetch regulation jurisdictions by stable species_id. GBIF is not unique.
        const speciesLookupId = selectedWeed.species_id || selectedWeed.id;
        const statesUrl = speciesLookupId
            ? `/species/api/weed-states/by-species-id/${encodeURIComponent(speciesLookupId)}`
            : `/species/api/weed-states/by-key/${selectedWeed.usage_key}`;

        fetch(statesUrl)
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(regulationResponse => {
                const normalizedResponse = normalizeRegulationResponse(regulationResponse);
                const regulationsByCountry = normalizedResponse.regulations_by_country;
                const statesList = document.getElementById('statesList');
                statesList.innerHTML = '';

                if (!normalizedResponse.authenticated) {
                    renderAnonymousRegulationSummary(statesList, normalizedResponse.jurisdiction_count);
                    document.getElementById('results').classList.remove('d-none');
                    return;
                }

                if (!regulationsByCountry || Object.keys(regulationsByCountry).length === 0) {
                    statesList.innerHTML = `
                        <div class="list-group-item">
                            <p class="mb-1">No regulations found for this species.</p>
                        </div>
                    `;
                    document.getElementById('results').classList.remove('d-none');
                    return;
                }

                // Expected shape:
                // { "United States": ["National Level", "California", ...],
                //   "European Union": ["International Level", ...],
                //   "New Zealand": ["National Level"] }
                for (const [countryKey, jurisdictions] of Object.entries(regulationsByCountry)) {
                    const country = displayCountryName(countryKey);
                    const list = Array.isArray(jurisdictions) ? jurisdictions : [];

                    const hasNational = list.includes('National Level');
                    const hasInternational = list.includes('International Level');

                    // Everything else is treated as a regional jurisdiction name
                    const regional = list.filter(x =>
                        x !== 'National Level' &&
                        x !== 'International Level'
                    );

                    const countryElement = document.createElement('div');
                    countryElement.className = 'list-group-item';

                    const countryHeader = document.createElement('h5');
                    countryHeader.className = 'mb-2';
                    countryHeader.textContent = country;
                    countryElement.appendChild(countryHeader);

                    if (hasInternational) {
                        const intlInfo = document.createElement('p');
                        intlInfo.className = 'mb-1';
                        intlInfo.innerHTML = '<strong>International Level:</strong> Regulated at international level';
                        countryElement.appendChild(intlInfo);
                    }

                    if (hasNational) {
                        const nationalInfo = document.createElement('p');
                        nationalInfo.className = 'mb-1';
                        nationalInfo.innerHTML = '<strong>National Level:</strong> Regulated nationwide';
                        countryElement.appendChild(nationalInfo);
                    }

                    if (regional.length > 0) {
                        const regionsRow = document.createElement('p');
                        regionsRow.className = 'mb-0';

                        const label = regional.length === 1 ? 'Region' : 'Regions';
                        const labelElement = document.createElement('strong');
                        labelElement.textContent = `${label}:`;
                        regionsRow.appendChild(labelElement);
                        regionsRow.appendChild(document.createTextNode(` ${regional.join(', ')}`));

                        countryElement.appendChild(regionsRow);
                    }

                    // If it’s only international/national and no region list, keep it clean (no extra line)
                    statesList.appendChild(countryElement);
                }

                document.getElementById('results').classList.remove('d-none');
            })
            .catch(error => {
                console.error('Error fetching weed jurisdictions:', error);
                const statesList = document.getElementById('statesList');
                statesList.innerHTML = `
                    <div class="list-group-item text-danger">
                        <p class="mb-1">Error loading data. Please try again.</p>
                    </div>
                `;
                document.getElementById('results').classList.remove('d-none');
            });
    }

    function selectAndDisplayWeed(weedData) {
        if (!weedData) return;

        let displayCommonName = getPrimaryCommonName(weedData.common_name);
        if (!displayCommonName || displayCommonName.includes('No English common names available')) {
            displayCommonName = null;
        }

        const formattedData = {
            id: weedData.species_id || weedData.usage_key,
            text: displayCommonName
                ? `${displayCommonName} (${weedData.canonical_name})`
                : `(${weedData.canonical_name})`,
            common_name: displayCommonName || weedData.canonical_name,
            canonical_name: weedData.canonical_name,
            family_name: weedData.family_name,
            synonyms: weedData.synonyms,
            species_id: weedData.species_id,
            usage_key: weedData.usage_key,
            lifeform_final: weedData.lifeform_final,
            lifespan_final: weedData.lifespan_final,
            habitat_final: weedData.habitat_final,
            woodiness_final: weedData.woodiness_final
        };

        const newOption = new Option(formattedData.text, formattedData.id, true, true);
        $('#weedSearch').append(newOption).trigger('change');

        displayWeedDetails(formattedData);
    }

    /******************************
     * AUTOLOAD BY URL ?species_id= or ?name=
     ******************************/
    const speciesId = getUrlParameter('species_id');
    const plantName = getUrlParameter('name');
    if (speciesId) {
        fetch(`/species/api/by-species-id/${encodeURIComponent(speciesId)}`)
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(selectAndDisplayWeed)
            .catch(error => {
                console.error('Error fetching plant data:', error);
            });
    } else if (plantName) {
        fetch(`/species/api/search?q=${encodeURIComponent(plantName)}`)
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(results => {
                const exactMatch = results.find(weed =>
                    weed.canonical_name.toLowerCase() === plantName.toLowerCase()
                );

                const weedData = exactMatch || results[0];
                selectAndDisplayWeed(weedData);
            })
            .catch(error => {
                console.error('Error fetching plant data:', error);
            });
    }
});
