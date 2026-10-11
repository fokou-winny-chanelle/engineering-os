// Smoke + accessibility check for the home page. Add one test per critical journey; keep this suite small.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("home renders with no serious accessibility violations @smoke", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("body")).toBeVisible();
  // WCAG 2.0, 2.1 and 2.2 A/AA rules; without the 21/22 tags the 2.2 target-size rule never runs.
  const { violations } = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const serious = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(serious.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
});
