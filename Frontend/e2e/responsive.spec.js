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

for (const viewport of [
  { width: 1512, height: 982, expectedColumns: 3 },
  { width: 1366, height: 768, expectedColumns: 2 },
  { width: 1210, height: 768, expectedColumns: 2 },
  { width: 900, height: 700, expectedColumns: 1 },
]) {
  test(`/home 핵심 카드가 ${viewport.width}px 폭에서 겹치지 않고 ${viewport.expectedColumns}열로 보인다`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.goto('/home');
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));

    const middleGrid = page.locator('.index-middle-grid');
    await expect(middleGrid).toBeVisible({ timeout: 10_000 });

    const layout = await middleGrid.evaluate((element) => {
      const shell = document.querySelector('.app-shell').getBoundingClientRect();
      const viewportWidth = document.documentElement.clientWidth;
      const children = Array.from(element.children).map((child) => {
        const rect = child.getBoundingClientRect();
        return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, width: rect.width };
      });
      const rows = new Set(children.map(({ left }) => Math.round(left)));

      return {
        viewportWidth,
        shellWidth: shell.width,
        children,
        columns: rows.size,
      };
    });

    expect(layout.shellWidth).toBeLessThanOrEqual(layout.viewportWidth + 1);
    expect(layout.columns).toBe(viewport.expectedColumns);
    for (const child of layout.children) {
      expect(child.width).toBeGreaterThan(0);
      expect(child.left).toBeGreaterThanOrEqual(-1);
      expect(child.right).toBeLessThanOrEqual(layout.viewportWidth + 1);
    }
    for (let i = 0; i < layout.children.length; i += 1) {
      for (let j = i + 1; j < layout.children.length; j += 1) {
        const a = layout.children[i];
        const b = layout.children[j];
        const overlapsHorizontally = a.left < b.right && b.left < a.right;
        const overlapsVertically = a.top < b.bottom && b.top < a.bottom;
        expect(overlapsHorizontally && overlapsVertically).toBe(false);
      }
    }
  });
}

test('추천 페이지에서도 공통 상단 메뉴 레이아웃이 유지된다', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto('/recommendations');

  const navigation = page.locator('.home3-cinema-nav');
  await expect(navigation).toBeVisible();
  await expect(navigation).toHaveCSS('display', 'grid');
  await expect(navigation.getByRole('navigation', { name: '주요 이동 메뉴' })).toBeVisible();
});
