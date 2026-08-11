import { expect, test } from '@playwright/test';

for (const viewport of [
  { width: 1920, height: 1080 },
  { width: 1366, height: 768 },
  { width: 1280, height: 720 },
  { width: 390, height: 844 },
]) {
  test(`로그인 화면이 ${viewport.width}x${viewport.height}에서 가로로 잘리지 않는다`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.goto('/?scene=4');
    await expect(page.locator('.intro-entry')).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
}

test('Windows 대표 해상도에서 온보딩 하단 동작이 화면 안에 남는다', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto('/onboarding?mode=guest');
  const start = page.getByRole('button', { name: /무와 취향 찾기/ });
  await expect(start).toBeVisible({ timeout: 10_000 });
  await expect(start).toBeInViewport();
});

for (const path of ['/home', '/chat/group', '/recommendations']) {
  test(`${path} 공개 화면이 1366x768에서 문서 가로 넘침을 만들지 않는다`, async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto(path);
    await page.waitForTimeout(500);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
}
