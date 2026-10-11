// Screenshots for the design critique loop (eos scaffold design-tokens). Not a pass/fail test: it captures
// each key page at phone and desktop widths, light and dark, with reduced motion, so a human or an agent can
// score them against docs/design/critiques/<date>-<screen>.md (`eos new critique "<screen>"`).
// Run: CRITIQUE=1 CRITIQUE_PATHS="/,/fr/compte" npx playwright test e2e/design-critique.spec.ts
// Output: design-critique/<page>-<width>-<scheme>.png (gitignore it; attach the before/after pair to the PR).
import { test } from "@playwright/test";

const paths = (process.env.CRITIQUE_PATHS ?? "/").split(",").map((p) => p.trim()).filter(Boolean);
const widths = [
  { name: "phone", width: 360, height: 800 }, // narrow phone; also try 320 px (WCAG 1.4.10 reflow)
  { name: "desktop", width: 1280, height: 800 },
];

test.describe("design critique screenshots", () => {
  test.skip(!process.env.CRITIQUE, "set CRITIQUE=1 to capture screenshots");
  for (const path of paths) {
    for (const vp of widths) {
      for (const scheme of ["light", "dark"] as const) {
        test(`${path} ${vp.name} ${scheme}`, async ({ page }) => {
          await page.setViewportSize({ width: vp.width, height: vp.height });
          await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
          await page.goto(path);
          await page.waitForLoadState("networkidle");
          const slug = path === "/" ? "home" : path.replace(/^\/|\/$/g, "").replace(/\//g, "_");
          await page.screenshot({ path: `design-critique/${slug}-${vp.name}-${scheme}.png`, fullPage: true });
        });
      }
    }
  }
});
