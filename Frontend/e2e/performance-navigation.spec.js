import { expect, test } from '@playwright/test';

test('공통 메뉴 이동은 전체 문서를 다시 로드하지 않는다', async ({ page }) => {
  await page.goto('/home');
  await page.evaluate(() => { window.__musubiDocumentMarker = 'kept'; });

  await page.getByRole('link', { name: '박스오피스' }).click();

  await expect(page).toHaveURL('/recommendations');
  await expect.poll(() => page.evaluate(() => window.__musubiDocumentMarker)).toBe('kept');
  await expect(page.locator('.home3-cinema-nav')).toBeVisible();
});

test('브라우저 뒤로 가기도 SPA 상태에서 경로를 복원한다', async ({ page }) => {
  await page.goto('/home');
  await page.getByRole('link', { name: '박스오피스' }).click();
  await expect(page).toHaveURL('/recommendations');

  await page.goBack();

  await expect(page).toHaveURL('/home');
  await expect(page.locator('.home3-page')).toBeVisible();
});
