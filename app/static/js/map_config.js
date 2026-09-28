// static/js/map_config.js
window.MAP_CONFIG = window.MAP_CONFIG || {};

MAP_CONFIG.geojsonPath = MAP_CONFIG.geojsonPath || "/static/data/geographic/";

// Global thresholds (used for every country)
MAP_CONFIG.defaultThresholds = [0, 100, 150, 200, 250, 300];

// Choropleth ramps for countries that DO have regulations
// (all ocean-safe: no strong blues)
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
  ["#fde7f0","#f9c4dd","#f29ec8","#e976b0","#d24c94","#b73178","#8f225b"],
  // 6. Teal
  ["#e0f7f4","#b3ebe4","#80dfd3","#4dd2c1","#26c6b7","#00b8a9","#008f82"],
  // 7. Smoky blue-grey
  ["#edf3fa","#d6e0f2","#bccbe7","#9ab0d7","#7a95c6","#5c7aac","#445d86"]
];

// Dark grey for regions with NO regulation at all (count === 0)
MAP_CONFIG.noDataColor = "#555555";

// Single-hue ramp for EU (light → saturated blue)
MAP_CONFIG.euColorRamp = ["#e9f2ff", "#d3e5ff", "#b7d4ff", "#97c1ff", "#74a9ff", "#4f90f0", "#2c74d4"];
