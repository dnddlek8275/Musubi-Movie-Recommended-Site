import { expect, test } from '@playwright/test';

const movieDetail = {
  id: 196,
  movie_id: 196,
  tmdb_id: 969681,
  title: '스파이더맨: 브랜드 뉴 데이',
  overview: '테스트 줄거리',
  genres: ['액션'],
  reviews: [],
  rating_count: 0,
};

test('URL과 상세 응답의 내부 영화 ID가 다르면 화면을 차단한다', async ({ page }) => {
  await page.route('**/api/movies/296?**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ state: 'success', data: movieDetail }),
  }));

  await page.goto('/movies/296');

  await expect(page.getByText('영화 식별 정보가 일치하지 않습니다. 페이지를 새로고침해 주세요.'))
    .toBeVisible();
  await expect(page.getByRole('button', { name: '평가하기' })).toHaveCount(0);
});

test('리뷰 저장 요청에 검증된 내부 ID와 TMDB ID, 제목을 함께 보낸다', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.clear();
    localStorage.setItem('auth_user', JSON.stringify({ user_id: 4, nickname: 'zeusqoi' }));
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
    body: JSON.stringify({ state: 'success', data: movieDetail }),
  }));
  await page.route('**/api/user/movies-like', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ state: 'success', data: [] }),
  }));
  await page.route('**/api/movies/196/similar?**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ state: 'success', data: [] }),
  }));

  let requestBody;
  await page.route('**/api/movies/196/rating', async (route) => {
    requestBody = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        state: 'success',
        data: { my_rating: 5, my_comment: '뉴욕통온다..', rating_count: 1, reviews: [] },
      }),
    });
  });

  await page.goto('/movies/196');
  await page.getByRole('button', { name: '평가하기' }).click();
  await page.getByRole('button', { name: '4.5점 또는 5점 선택', exact: true }).press('Enter');
  await page.getByPlaceholder('이 영화에 대한 생각을 남겨주세요.').fill('뉴욕통온다..');
  await page.getByRole('button', { name: '평가 및 리뷰 등록' }).click();

  expect(requestBody).toEqual({
    score: 5,
    comment: '뉴욕통온다..',
    is_spoiler: false,
    expected_movie_id: 196,
    expected_tmdb_id: 969681,
    expected_title: '스파이더맨: 브랜드 뉴 데이',
  });
  await expect(page.getByText('스파이더맨: 브랜드 뉴 데이에 리뷰가 저장되었습니다.')).toHaveCount(0);
});
