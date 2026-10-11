// Style Dictionary 5 build for the DTCG tokens in design/tokens/ (eos scaffold design-tokens).
// Run: node design/build-tokens.mjs   (package.json script "tokens"; needs style-dictionary@5.6.1 as a dev dependency)
// Outputs (generated; do not edit by hand, edit the .tokens.json files):
//   design/build/tokens.css   Tailwind v4 @theme block (light) + .dark overrides; import it from your global CSS
//   design/build/tokens.js    ES module for React Native / JS charts
//   design/build/tokens.dart  Flutter class
// Style Dictionary 5.6 reads DTCG colour and dimension objects but not yet every 2025.10 type ("does not have
// full support yet"), so the transforms below turn duration objects and cubicBezier arrays into CSS and Dart.
import StyleDictionary from "style-dictionary";

StyleDictionary.registerTransform({
  name: "eos/duration/css",
  type: "value",
  transitive: true,
  filter: (t) => (t.$type ?? t.type) === "duration" && typeof (t.$value ?? t.value) === "object",
  transform: (t) => {
    const v = t.$value ?? t.value;
    return `${v.value}${v.unit}`;
  },
});

StyleDictionary.registerTransform({
  name: "eos/cubicBezier/css",
  type: "value",
  transitive: true,
  filter: (t) => (t.$type ?? t.type) === "cubicBezier" && Array.isArray(t.$value ?? t.value),
  transform: (t) => `cubic-bezier(${(t.$value ?? t.value).join(", ")})`,
});

// Flutter: Style Dictionary's flutter group treats DTCG px dimensions as rem (2px became 32.00 in 5.6.1), so
// these transforms convert explicitly: px stays, rem x 16 (logical pixels), duration -> Duration, fonts -> first family.
const v = (t) => t.$value ?? t.value;
StyleDictionary.registerTransform({
  name: "eos/dimension/dart",
  type: "value",
  filter: (t) => (t.$type ?? t.type) === "dimension" && typeof v(t) === "object",
  transform: (t) => (v(t).unit === "rem" ? v(t).value * 16 : v(t).value).toFixed(2),
});
StyleDictionary.registerTransform({
  name: "eos/duration/dart",
  type: "value",
  filter: (t) => (t.$type ?? t.type) === "duration" && typeof v(t) === "object",
  transform: (t) => `Duration(milliseconds: ${Math.round(v(t).unit === "s" ? v(t).value * 1000 : v(t).value)})`,
});
StyleDictionary.registerTransform({
  name: "eos/fontFamily/dart",
  type: "value",
  filter: (t) => (t.$type ?? t.type) === "fontFamily",
  transform: (t) => `'${[].concat(v(t))[0]}'`,
});
const dart = ["attribute/cti", "name/camel", "color/hex8flutter", "eos/dimension/dart", "eos/duration/dart", "eos/fontFamily/dart"];
const dartTypes = ["color", "dimension", "number", "fontWeight", "duration", "fontFamily"];

const css = [...StyleDictionary.hooks.transformGroups.css, "eos/duration/css", "eos/cubicBezier/css"];
const base = ["design/tokens/base.tokens.json"];
const dark = "design/tokens/dark.tokens.json";

const configs = [
  {
    source: base,
    platforms: {
      css: {
        transforms: css,
        buildPath: "design/build/",
        files: [{ destination: "tokens.css", format: "css/variables", options: { selector: "@theme", outputReferences: true } }],
      },
      js: {
        transforms: [...StyleDictionary.hooks.transformGroups.js, "eos/duration/css", "eos/cubicBezier/css"],
        buildPath: "design/build/",
        files: [{ destination: "tokens.js", format: "javascript/es6" }],
      },
      flutter: {
        transforms: dart,
        buildPath: "design/build/",
        files: [
          {
            destination: "tokens.dart",
            format: "flutter/class.dart",
            filter: (t) => dartTypes.includes(t.$type ?? t.type),
            options: { className: "AppTokens" },
          },
        ],
      },
    },
  },
  {
    // dark theme: only the semantic colours it overrides, under .dark (base tokens included for aliases)
    include: base,
    source: [dark],
    platforms: {
      css: {
        transforms: css,
        buildPath: "design/build/",
        files: [
          {
            destination: "tokens.dark.css",
            format: "css/variables",
            filter: (t) => t.filePath.endsWith("dark.tokens.json"),
            options: { selector: ".dark" },
          },
        ],
      },
    },
  },
];

for (const config of configs) {
  await new StyleDictionary(config).buildAllPlatforms();
}
