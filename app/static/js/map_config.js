// static/js/map_config.js
window.MAP_CONFIG = window.MAP_CONFIG || {};

MAP_CONFIG.geojsonPath = MAP_CONFIG.geojsonPath || "/static/data/geographic/";

// Global thresholds (used for every country)
MAP_CONFIG.defaultThresholds = [0, 100, 150, 200, 250, 300];

// Choropleth ramps for countries that DO have regulations. No blues, teals or
// blue-greys: those read as sea, which made Japan (teal) and South Africa
// (blue-grey) look empty.
MAP_CONFIG.defaultColorRamps = [
  // 1. Warm yellow-green
  ["#f4fae1","#e4f2b8","#d1e98d","#bddf63","#a7d33c","#8bb71f","#6d8f0f"],
  // 2. Purple
  ["#f3e8fd","#dec6fa","#c3a4f2","#a381e8","#845edc","#6a41c9","#4f29a3"],
  // 3. Earth / Brown
  ["#f8f1e6","#e8d8bf","#d6bf99","#c4a673","#b28c4d","#9f7333","#7d5926"],
  // 4. Orange
  ["#fff0e0","#ffd9b3","#ffbf80","#ffa64d","#ff8c1a","#e67300","#b35900"],
  // 5. Rose / Magenta
  ["#fde7f0","#f9c4dd","#f29ec8","#e976b0","#d24c94","#b73178","#8f225b"]
];

// Any region with at least one regulated species starts at this step of its ramp,
// so a country with a short list (Japan: 17) is clearly coloured, not near-white.
MAP_CONFIG.minRegulatedShade = 2;

// Covered region showing 0 species under the current level toggles.
MAP_CONFIG.zeroCountColor = "#dee2e6";

// Countries reviewed and found to have no published list (no_published_list from
// /api/region-weed-counts, e.g. Malaysia, UAE) are hatched; uncovered countries are not drawn.
MAP_CONFIG.noListHatch = { line: "#868e96", background: "#f8f9fa" };

// Single-hue ramp for EU, towards EU-flag blue (#003399). Kept blue as the bloc's
// colour, but deeper than the old pastel ramp so even the lightest regulated
// step (index minRegulatedShade) is clearly not sea.
MAP_CONFIG.euColorRamp = ["#dfe5f5", "#bccaeb", "#8fa5dc", "#6b86cd", "#4a68bd", "#2a4ca8", "#003399"];
