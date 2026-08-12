import { expect, test } from '@playwright/test';

const rooms = [
  {
    room_id: 11,
    room_type: 'general',
    title: '무무와 나눈 영화 이야기',
    characters: [],
    created_at: '2026-08-11T01:00:00Z',
    updated_at: '2026-08-11T02:00:00Z',
  },
  {
    room_id: 22,
    room_type: 'character',
    title: null,
    characters: ['아이언맨'],
    created_at: '2026-08-11T03:00:00Z',
    updated_at: '2026-08-11T04:00:00Z',
  },
];

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.clear();
    localStorage.setItem('auth_user', JSON.stringify({ user_id: 3, nickname: '영화러버' }));
    localStorage.setItem('access_token', 'e2e-token');
    localStorage.setItem('cineverse.authSession', 'e2e-session');
  });

  await page.route('**/api/**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ state: 'success', data: [] }),
  }));
  await page.route('**/api/chat/rooms', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ state: 'success', data: rooms }),
  }));
  await page.route('**/api/chat/characters', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ state: 'success', data: [] }),
  }));
});

test('일반 대화 입력창 기록에서 캐릭터 대화도 확인하고 이동한다', async ({ page }) => {
  await page.goto('/home');
  await page.getByRole('button', { name: '채팅 메뉴 열기' }).click();
  await page.getByRole('button', { name: '대화 기록', exact: true }).click();

  await expect(page.getByText('무무와 나눈 영화 이야기', { exact: true })).toBeVisible();
  await expect(page.getByText('아이언맨', { exact: true })).toBeVisible();

  await page.getByText('아이언맨', { exact: true }).click();
  await expect(page).toHaveURL(/\/chat\/group\?room=22&members=/);
});

test('캐릭터 대화 입력창 기록에서 일반 대화도 확인하고 이동한다', async ({ page }) => {
  await page.goto('/chat/group');
  await page.getByRole('button', { name: '채팅 메뉴 열기' }).click();
  await page.getByRole('button', { name: '대화 기록', exact: true }).click();

  await expect(page.getByText('아이언맨', { exact: true })).toBeVisible();
  await expect(page.getByText('무무와 나눈 영화 이야기', { exact: true })).toBeVisible();

  await page.getByText('무무와 나눈 영화 이야기', { exact: true }).click();
  await expect(page).toHaveURL('/home?room=11');
});

test('홈 복귀 시 활성 대화를 복원하고 TMDB 추천 카드를 상세 페이지로 연결한다', async ({ page }) => {
  await page.addInitScript(() => {
    const conversation = {
      id: 'saved-general-11',
      roomId: '11',
      title: '저장된 추천 대화',
      createdAt: '2026-08-11T01:00:00Z',
      updatedAt: '2026-08-11T02:00:00Z',
      messages: [{
        id: 'assistant-1',
        role: 'assistant',
        character: '무무',
        content: '이 영화를 추천해요.',
        movies: [{ tmdb_id: '933260', title: '서브스턴스', poster_url: '/substance.jpg' }],
      }],
    };
    localStorage.setItem('cineverse.autochat.conversations', JSON.stringify([conversation]));
    localStorage.setItem('cineverse.autochat.activeConversation', conversation.id);
  });
  await page.route('**/api/movies/resolve?**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ state: 'success', data: { movie_id: 51646, tmdb_id: 933260, title: '서브스턴스' } }),
  }));

  await page.goto('/home');
  await expect(page.getByText('이 영화를 추천해요.')).toBeVisible();
  const messageList = page.locator('.home-variant-chat__messages');
  const cursor = await messageList.evaluate((element) => getComputedStyle(element).cursor);
  expect(['pointer', 'grab', 'grabbing']).not.toContain(cursor);

  const movieButton = page.getByRole('button', { name: '서브스턴스 상세 페이지 보기' });
  await expect(movieButton).toHaveCSS('width', '132px');
  await movieButton.click();
  await expect(page).toHaveURL('/movies/51646');

  await page.goto('/home');
  await expect(page.getByText('이 영화를 추천해요.')).toBeVisible();
});
