import { expect, test } from "@playwright/test";

test("register and open the configured edition", async ({ page }, testInfo) => {
  const turtleModule = process.env.E2E_TURTLE_MODULE !== "false";
  const email = `keeper-${testInfo.project.name}-${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("顯示名稱").fill("測試飼主");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("密碼").fill("safe-password-123");
  await page.getByRole("button", { name: /建立帳號/ }).click();
  await expect(page.getByRole("heading", { name: "今天想問什麼？" })).toBeVisible();

  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "開啟選單" }).click();
  }
  if (!turtleModule) {
    await expect(page.getByRole("link", { name: "組織知識庫" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Profile" })).toHaveCount(0);
    if (testInfo.project.name === "mobile") {
      await page.getByRole("link", { name: "AI 對話" }).click();
    }
    await expect(page.getByRole("textbox", { name: "訊息輸入" })).toBeVisible();
    return;
  }
  await page.getByRole("link", { name: "我的龜龜" }).click();
  await page.getByRole("button", { name: /新增龜龜/ }).first().click();
  await page.getByLabel("名稱").fill("龜小弟");
  await page.getByLabel("種類").fill("臺灣斑龜");
  await page.getByLabel("背甲長度（cm）").fill("10");
  await page.getByLabel("飼養環境").fill("室外水池，有曬背台與過濾器");
  await page.getByRole("button", { name: "儲存 Profile" }).click();
  await expect(page.getByRole("heading", { name: "龜小弟" })).toBeVisible();

  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "開啟選單" }).click();
  }
  await page.getByRole("link", { name: "AI 對話" }).click();
  await expect(page.getByText("先到「我的龜龜」建立 Profile")).not.toBeVisible();
});
