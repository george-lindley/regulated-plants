(function () {
  function text(value) {
    if (value === null || value === undefined || value === "") {
      return "Not provided";
    }
    return String(value);
  }

  function makeElement(tag, className, value) {
    const element = document.createElement(tag);
    if (className) {
      element.className = className;
    }
    if (value !== undefined) {
      element.textContent = value;
    }
    return element;
  }

  function addFact(container, label, value) {
    if (value === null || value === undefined || value === "") {
      return;
    }
    const item = makeElement("div", "api-demo-fact");
    item.appendChild(makeElement("span", "api-demo-fact-label", label));
    item.appendChild(makeElement("span", "api-demo-fact-value", text(value)));
    container.appendChild(item);
  }

  function jurisdictionName(jurisdiction) {
    if (!jurisdiction) {
      return "";
    }
    const named = jurisdiction.name || jurisdiction.jurisdiction_name;
    if (named) {
      return named;
    }
    const place = [jurisdiction.region, jurisdiction.country].filter(Boolean).join(", ");
    return place || jurisdiction.iso_subdivision_code || jurisdiction.jurisdiction_uid || "";
  }

  function statusLabel(status, regulated) {
    if (status === "regulated" || regulated === true) {
      return "Regulated record found";
    }
    if (status === "not_regulated_in_dataset" || regulated === false) {
      return "No regulation record found";
    }
    if (status === "plant_match_required") {
      return "Plant match required";
    }
    if (status === "jurisdiction_match_required") {
      return "Jurisdiction match required";
    }
    return status || "API response";
  }

  function badgeClass(status, regulated) {
    if (status === "regulated" || regulated === true) {
      return "regulated";
    }
    if (status === "not_regulated_in_dataset" || regulated === false) {
      return "clear";
    }
    return "notice";
  }

  function renderSuggestions(container, suggestions) {
    if (!Array.isArray(suggestions) || suggestions.length === 0) {
      return;
    }

    container.appendChild(makeElement("h3", "api-demo-result-title", "Suggested plant matches"));
    const list = makeElement("div", "api-demo-list");
    suggestions.slice(0, 5).forEach((item) => {
      const row = makeElement("div", "api-demo-list-item");
      const name = item.canonical_name || item.scientific_name || item.name || "Unknown plant";
      const details = [];
      if (item.species_id) {
        details.push(item.species_id);
      }
      if (item.match_type) {
        details.push(item.match_type);
      }
      if (item.confidence) {
        details.push(item.confidence);
      }
      row.appendChild(makeElement("strong", "", name));
      if (details.length) {
        row.appendChild(makeElement("div", "api-demo-message", details.join(" - ")));
      }
      list.appendChild(row);
    });
    container.appendChild(list);
  }

  function renderRegulations(container, regulations) {
    if (!Array.isArray(regulations) || regulations.length === 0) {
      return;
    }

    container.appendChild(makeElement("h3", "api-demo-result-title", "Regulation details"));
    const list = makeElement("div", "api-demo-list");
    regulations.slice(0, 3).forEach((item) => {
      const row = makeElement("div", "api-demo-list-item");
      const facts = makeElement("div", "api-demo-facts");
      addFact(facts, "Classification", item.classification_raw || item.regulation_type || "Recorded regulation");
      addFact(facts, "Authority", item.authority_name || item.authority_type);
      addFact(facts, "Jurisdiction", jurisdictionName(item));
      if (item.source_url) {
        const source = makeElement("div", "api-demo-fact");
        source.appendChild(makeElement("span", "api-demo-fact-label", "Source"));
        const link = makeElement("a", "api-demo-fact-value", item.source_url);
        link.href = item.source_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        source.appendChild(link);
        facts.appendChild(source);
      }
      row.appendChild(facts);
      list.appendChild(row);
    });
    container.appendChild(list);
  }

  function renderResponse(root, data) {
    const result = root.querySelector("[data-demo-result]");
    const rawDetails = root.querySelector("[data-demo-raw-details]");
    const raw = root.querySelector("[data-demo-raw]");
    result.textContent = "";

    const header = makeElement("div", "api-demo-result-header");
    const titleBlock = makeElement("div", "");
    titleBlock.appendChild(makeElement("h3", "api-demo-result-title", statusLabel(data.status, data.regulated)));
    titleBlock.appendChild(makeElement("p", "api-demo-message", data.message || data.error || "The API returned a response."));
    header.appendChild(titleBlock);
    header.appendChild(makeElement("span", "api-demo-badge " + badgeClass(data.status, data.regulated), data.status || "error"));
    result.appendChild(header);

    const facts = makeElement("div", "api-demo-facts");
    if (data.matched_plant) {
      addFact(facts, "Matched plant", data.matched_plant.canonical_name || data.matched_plant.scientific_name);
      addFact(facts, "Species ID", data.matched_plant.species_id);
    }
    if (data.plant_match) {
      addFact(facts, "Plant match", [data.plant_match.match_type, data.plant_match.confidence].filter(Boolean).join(", "));
    }
    if (data.jurisdiction) {
      addFact(facts, "Jurisdiction", jurisdictionName(data.jurisdiction));
      addFact(facts, "Jurisdiction ID", data.jurisdiction.jurisdiction_uid);
    }
    if (data.release) {
      addFact(facts, "Release", data.release.version || data.release.generated_at);
    }
    if (facts.childElementCount > 0) {
      result.appendChild(facts);
    }

    renderSuggestions(result, data.suggestions);
    renderRegulations(result, data.regulations);

    raw.textContent = JSON.stringify(data, null, 2);
    rawDetails.hidden = false;
    result.hidden = false;
  }

  function setStatus(root, message) {
    const status = root.querySelector("[data-demo-status]");
    if (status) {
      status.textContent = message || "";
    }
  }

  function setBusy(root, isBusy) {
    const button = root.querySelector("[data-demo-submit]");
    if (button) {
      button.disabled = isBusy;
      button.textContent = isBusy ? "Checking..." : "Run compliance check";
    }
  }

  function payloadFromForm(root) {
    return {
      plant_query: root.querySelector("[data-demo-plant]").value.trim(),
      ship_to: {
        country: root.querySelector("[data-demo-country]").value.trim(),
        region: root.querySelector("[data-demo-region]").value.trim()
      }
    };
  }

  async function runDemo(root) {
    const endpoint = root.dataset.endpoint;
    const csrfToken = root.dataset.csrfToken;
    setBusy(root, true);
    setStatus(root, "Calling the v1 API...");

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken
        },
        body: JSON.stringify(payloadFromForm(root))
      });
      const data = await response.json();
      renderResponse(root, data);
      setStatus(root, response.ok ? "API response received." : "API returned an error.");
    } catch (error) {
      renderResponse(root, { status: "request_failed", error: "The API demo request could not be completed." });
      setStatus(root, "Request failed.");
    } finally {
      setBusy(root, false);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    const root = document.querySelector("[data-api-demo]");
    if (!root) {
      return;
    }

    root.querySelector("[data-demo-form]").addEventListener("submit", function (event) {
      event.preventDefault();
      runDemo(root);
    });

    root.querySelectorAll("[data-example-plant]").forEach((button) => {
      button.addEventListener("click", function () {
        root.querySelector("[data-demo-plant]").value = button.dataset.examplePlant || "";
        root.querySelector("[data-demo-country]").value = button.dataset.exampleCountry || "";
        root.querySelector("[data-demo-region]").value = button.dataset.exampleRegion || "";
        runDemo(root);
      });
    });
  });
})();
