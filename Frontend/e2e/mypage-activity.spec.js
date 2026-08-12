import { expect, test } from '@playwright/test';

const movie = {
  movie_id: 196,
  title: '스파이더맨: 브랜드 뉴 데이',
  genres: ['액션'],
  poster_path: '/poster.jpg',
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.clear();
    localStorage.setItem('auth_user', JSON.stringify({ user_id: 3, nickname: '영화러버' }));
    localStorage.setItem('access_token', 'e2e-token');
  });
  await page.route('**/api/**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ state: 'success', data: [] }),
  }));
  await page.route('**/api/user/reviews', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      state: 'success',
      data: [
        { id: 7, score: 4, comment: '다시 보고 싶은 영화', updated_at: '2026-08-11T00:00:00Z', movie },
        { id: 8, score: 5, comment: null, updated_at: '2026-08-10T00:00:00Z', movie: { ...movie, movie_id: 197, title: '별점만 남긴 영화' } },
      ],
    }),
  }));
  await page.route('**/api/user/recently-viewed?**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ state: 'success', data: [movie] }),
  }));
});

test('아카이브 리뷰 수에서 내 활동으로 이동하고 영화 상세 링크를 제공한다', async ({ page }) => {
  await page.goto('/mypage');

  await page.getByRole('button', { name: '2 리뷰' }).click();
  await expect(page.getByRole('heading', { name: '내 활동' })).toBeVisible();
  const review = page.getByRole('link', { name: /스파이더맨: 브랜드 뉴 데이/ });
  await expect(review).toContainText('다시 보고 싶은 영화');
  await expect(review).toHaveAttribute('href', '/movies/196');
  const ratingOnly = page.getByText('별점만 남긴 평가입니다.');
  await expect(ratingOnly).toBeVisible();
  await expect(ratingOnly).toHaveClass(/is-rating-only/);
  const reviewColumns = await page.locator('.mypage-review-list').evaluate((element) => (
    getComputedStyle(element).gridTemplateColumns.split(' ').filter(Boolean).length
  ));
  expect(reviewColumns).toBe(2);
});

test('아카이브 최근 본 영화에서 영화 활동으로 이동하고 찜 섹션을 표시한다', async ({ page }) => {
  await page.goto('/mypage');

  await page.getByRole('button', { name: '1 최근 본 영화' }).click();
  await expect(page.evaluate(() => window.scrollY)).resolves.toBe(0);
  await expect(page.getByRole('heading', { name: '나의 영화 활동' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '찜한 영화' })).toBeVisible();
  await expect(page.getByText('아직 찜한 영화가 없습니다.')).toBeVisible();
  await expect(page.locator('#recent-movies')).toContainText('스파이더맨: 브랜드 뉴 데이');
});
