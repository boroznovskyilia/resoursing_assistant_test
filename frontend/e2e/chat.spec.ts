import { test, expect } from "@playwright/test";

test("real local API renders facts, SQL and persisted history", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Message", { exact: true })).toBeEnabled();
  await page.screenshot({ path: "test-results/welcome.png", fullPage: true });
  await page.getByLabel("Message", { exact: true }).fill("count");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(
    page.getByRole("cell", { name: "400", exact: true }),
  ).toBeVisible();
  await page.getByText("Executed SQL · People count").click();
  await expect(page.locator("pre")).toContainText("SELECT COUNT(*)");
  await page.reload();
  await expect(
    page.getByRole("cell", { name: "400", exact: true }),
  ).toBeVisible();
});

test("pending proposal permits a question then confirms canonical card", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "New conversation" }).click();
  await page.getByLabel("Message", { exact: true }).fill("book");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(
    page.getByRole("button", { name: "Confirm soft booking" }),
  ).toBeVisible();
  await page.getByLabel("Message", { exact: true }).fill("count");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(
    page.getByRole("cell", { name: "400", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Confirm soft booking" }).click();
  await expect(
    page.getByRole("button", { name: "Confirm soft booking" }),
  ).toHaveCount(0);
  await expect(page.getByText(/Saved booking #/).first()).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Confirm soft booking" }),
  ).toHaveCount(0);
});

test("lost message response retries same identity without duplicate turn", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "New conversation" }).click();
  let lost = false;
  await page.route("**/threads/*/messages", async (route) => {
    if (!lost) {
      lost = true;
      await route.fetch();
      await route.abort("failed");
    } else await route.continue();
  });
  await page.getByLabel("Message", { exact: true }).fill("count");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(
    page.getByRole("button", { name: "Retry same request" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Retry same request" }).click();
  await expect(
    page.getByRole("button", { name: "Retry same request" }),
  ).toHaveCount(0);
  await expect(page.locator(".message.user")).toHaveCount(1);
});

test("small viewport, reject and literal untrusted markup", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "New conversation" }).click();
  await page.getByLabel("Message", { exact: true }).fill("book");
  await page.getByRole("button", { name: "Send message" }).click();
  await page.getByRole("button", { name: "Reject", exact: true }).click();
  await expect(page.locator(".booking.rejected").first()).toBeVisible();
  await page
    .getByLabel("Message", { exact: true })
    .fill("<script>window.pwned=1</script>");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(
    page.getByRole("cell", { name: "400", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => Reflect.get(window, "pwned")),
  ).toBeUndefined();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
});

test("terminal failure offers a new attempt with a new request ID", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "New conversation" }).click();
  const ids: string[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/messages"))
      ids.push(request.postDataJSON().request_id);
  });
  await page.getByLabel("Message", { exact: true }).fill("fail");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(
    page.getByRole("button", { name: "Try as a new request" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Try as a new request" }).click();
  await expect(page.locator(".message.user")).toHaveCount(2);
  expect(ids.length).toBe(2);
  expect(ids[0]).not.toBe(ids[1]);
});
