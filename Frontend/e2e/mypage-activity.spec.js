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
  await page.route('**/api/user/chatai-recommended-movies?**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      state: 'success',
      data: [{
        movie_id: 4451,
        tmdb_id: 933260,
        title: '서브스턴스',
        genres: ['공포'],
        poster_path: '/substance.jpg',
      }],
    }),
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

test('영화 활동의 채팅 추천 영화를 상세 페이지로 연결한다', async ({ page }) => {
  await page.goto('/mypage?tab=activity');

  const recommendedSection = page.locator('#chat-recommended-movies');
  await expect(recommendedSection).toContainText('서브스턴스');
  await expect(recommendedSection.getByRole('link', { name: '서브스턴스 상세 보기' }))
    .toHaveAttribute('href', '/movies/4451');
  await expect(recommendedSection.getByRole('link', { name: '서브스턴스', exact: true }))
    .toHaveAttribute('href', '/movies/4451');
});

test('직접 선택한 취향을 장르, 배우, 키워드 순서로 수정한다', async ({ page }) => {
  let savedPreferences = null;
  await page.route('**/api/user/preferences', async (route) => {
    if (route.request().method() === 'PATCH') {
      savedPreferences = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ state: 'success', data: savedPreferences }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        state: 'success',
        data: {
          explicit_preferences: { genres: ['드라마'], actors: [], keywords: [] },
          learned_preferences: { genres: [], actors: [], keywords: [] },
          combined_preferences: { genres: ['드라마'], actors: [], keywords: [] },
        },
      }),
    });
  });
  await page.route('**/api/movies/preference-options', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      state: 'success',
      data: { genres: ['드라마', 'SF'], keywords: ['우정', '복수'] },
    }),
  }));
  await page.route('**/api/movies/actors?**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      state: 'success',
      data: [{ actor_id: 1, actor_name: '황정민', profile_path: '' }],
    }),
  }));

  await page.goto('/mypage?tab=taste');
  await page.locator('.mypage-taste-editor.is-direct').getByRole('button', { name: '수정하기' }).click();

  const dialog = page.getByRole('dialog', { name: '직접 선택한 취향 수정' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('heading', { name: '좋아하는 장르를 골라주세요' })).toBeVisible();
  await expect(dialog.getByRole('button', { name: /배우/ })).toBeDisabled();
  await dialog.getByRole('button', { name: 'SF', exact: true }).click();
  await dialog.getByRole('button', { name: '다음' }).click();

  await expect(dialog.getByRole('heading', { name: '좋아하는 배우를 선택해 주세요' })).toBeVisible();
  await dialog.locator('.mypage-taste-modal__choices.is-actors > button', { hasText: '황정민' }).click();
  await dialog.getByRole('button', { name: '다음' }).click();

  await expect(dialog.getByRole('heading', { name: '끌리는 이야기 키워드를 골라주세요' })).toBeVisible();
  await dialog.getByRole('button', { name: '#우정', exact: true }).click();
  await dialog.getByRole('button', { name: '취향 저장' }).click();

  await expect(dialog).toBeHidden();
  expect(savedPreferences).toEqual({
    genres: ['드라마', 'SF'],
    actors: ['황정민'],
    keywords: ['우정'],
    onboarding_completed: true,
  });
  await expect(page.locator('.mypage-taste-editor.is-direct')).toContainText('황정민');
  await expect(page.locator('.mypage-taste-editor.is-direct')).toContainText('우정');
});
