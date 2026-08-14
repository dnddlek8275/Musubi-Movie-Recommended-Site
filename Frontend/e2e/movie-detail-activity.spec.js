import { expect, test } from '@playwright/test';

const detail = {
  id: 196,
  movie_id: 196,
  tmdb_id: 969681,
  title: '스파이더맨: 브랜드 뉴 데이',
  overview: '테스트 줄거리',
  genres: ['액션'],
  cast: [],
  reviews: [{
    id: 31,
    user_id: 4,
    nickname: 'zeusqoi',
    score: 4,
    comment: '결말에 대한 이야기',
    is_spoiler: true,
    is_mine: false,
    updated_at: '2026-08-11T00:00:00Z',
  }],
  rating_count: 1,
  musubi_rating: 4,
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
  await page.route('**/api/movies/196?**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ state: 'success', data: detail }),
  }));
  await page.route('**/api/movies/196/similar?**', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ state: 'success', data: [{ movie_id: 197, title: '추천 영화', genres: ['액션'] }] }),
    });
  });
  await page.route('**/api/user/public/4/activity', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      state: 'success',
      data: {
        user: { id: 4, nickname: 'zeusqoi' },
        liked_movies: [{ movie_id: 197, title: '추천 영화', genres: ['액션'] }],
        reviews: [{ id: 32, score: 5, comment: '재미있어요', movie: { movie_id: 197, title: '추천 영화' } }],
      },
    }),
  }));
});

test('추천 로딩 스켈레톤을 표시하고 찜을 저장한다', async ({ page }) => {
  let wishlistRequested = false;
  await page.route('**/api/movies/196/wishlist', async (route) => {
    if (route.request().method() === 'POST') wishlistRequested = true;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ state: 'success', data: { movie_id: 196, wishlisted: true } }),
    });
  });

  await page.goto('/movies/196');
  await expect(page.locator('.movie-detail__similar-skeleton')).toHaveCount(6);
  const heart = page.locator('.movie-detail__heart');
  await expect(heart).toHaveCSS('font-size', '19px');
  await page.getByRole('button', { name: '좋아요' }).click();
  await expect(heart).toHaveClass(/is-liked/);
  await expect(heart).toHaveCSS('font-size', '25px');
  const wishlistButton = page.getByRole('button', { name: '찜하기' });
  await wishlistButton.click();
  // 활성화 후에도 문구와 버튼 외형은 유지하고 별만 노란색으로 바뀐다.
  await expect(wishlistButton).toBeVisible();
  await expect(wishlistButton).toHaveClass(/is-wishlisted/);
  await expect(wishlistButton.locator('.movie-detail__bookmark')).toHaveText('★');
  expect(wishlistRequested).toBe(true);
  await expect(page.getByText('추천 영화', { exact: true })).toBeVisible();
});

test('스포일러 평가를 저장하고 리뷰 카드에서 다른 회원 활동 페이지로 이동한다', async ({ page }) => {
  let ratingBody;
  await page.route('**/api/movies/196/rating', async (route) => {
    ratingBody = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ state: 'success', data: { my_rating: 5, my_comment: '스포일러 리뷰', my_is_spoiler: true, reviews: detail.reviews } }),
    });
  });

  await page.goto('/movies/196');
  await page.getByRole('button', { name: '평가하기' }).click();
  await page.getByRole('button', { name: '4.5점 또는 5점 선택', exact: true }).press('Enter');
  await page.getByPlaceholder('이 영화에 대한 생각을 남겨주세요.').fill('스포일러 리뷰');
  await page.getByLabel('스포일러가 포함된 리뷰예요').check();
  await page.getByRole('button', { name: '평가 및 리뷰 등록' }).click();
  expect(ratingBody.is_spoiler).toBe(true);

  await expect(page.getByText('zeusqoi', { exact: true })).toBeVisible();
  await expect(page.getByText('zeusqoi의 활동 보기', { exact: true })).toHaveCount(0);
  await page.locator('.movie-detail__review.is-member-link').click({ position: { x: 12, y: 12 } });
  await expect(page).toHaveURL(/\/users\/4\/activity$/);
  await expect(page.getByRole('heading', { name: 'zeusqoi' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '좋아요 누른 영화' })).toBeVisible();
  await expect(page.getByText('추천 영화', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('재미있어요', { exact: true })).toBeVisible();
});
