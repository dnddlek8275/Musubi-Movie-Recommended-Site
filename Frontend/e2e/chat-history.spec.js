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

test('일반 대화 입력창 기록에는 일반 대화만 표시한다', async ({ page }) => {
  await page.goto('/home');
  await page.getByRole('button', { name: '채팅 메뉴 열기' }).click();
  await page.getByRole('button', { name: '대화 기록', exact: true }).click();

  await expect(page.getByText('무무와 나눈 영화 이야기', { exact: true })).toBeVisible();
  await expect(page.getByText('아이언맨', { exact: true })).toHaveCount(0);
});

test('캐릭터 대화 입력창 기록에는 캐릭터 대화만 표시한다', async ({ page }) => {
  await page.goto('/chat/group');
  await page.getByRole('button', { name: '채팅 메뉴 열기' }).click();
  await page.getByRole('button', { name: '대화 기록', exact: true }).click();

  await expect(page.getByText('아이언맨', { exact: true })).toBeVisible();
  await expect(page.getByText('무무와 나눈 영화 이야기', { exact: true })).toHaveCount(0);
});

test('일반 대화는 기록 선택 때만 열리고 새로고침하면 비활성 상태로 돌아간다', async ({ page }) => {
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
  });
  await page.route('**/api/movies/resolve?**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ state: 'success', data: { movie_id: 51646, tmdb_id: 933260, title: '서브스턴스' } }),
  }));
  await page.route('**/api/chat/rooms/11/messages', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      state: 'success',
      data: [{
        role: 'assistant',
        character: '무무',
        content: '이 영화를 추천해요.',
        recommended_movies: [{ tmdb_id: '933260', title: '서브스턴스', poster_url: '/substance.jpg' }],
      }],
    }),
  }));

  await page.goto('/home?room=11');
  await expect(page.getByText('이 영화를 추천해요.')).toBeVisible();
  await expect(page).toHaveURL('/home');
  const messageList = page.locator('.home-variant-chat__messages');
  const cursor = await messageList.evaluate((element) => getComputedStyle(element).cursor);
  expect(['pointer', 'grab', 'grabbing']).not.toContain(cursor);

  const movieButton = page.getByRole('button', { name: '서브스턴스 상세 페이지 보기' });
  await expect(movieButton).toHaveCSS('width', '132px');
  await page.reload();
  await expect(page.getByText('이 영화를 추천해요.')).toHaveCount(0);
  await expect(page.locator('.home3-chat-stage')).not.toHaveClass(/is-chatting/);

  await page.goto('/home?room=11');
  await expect(page.getByText('이 영화를 추천해요.')).toBeVisible();
  await page.locator('nav[aria-label="주요 이동 메뉴"]').getByRole('link', { name: '박스오피스' }).click();
  await expect(page).toHaveURL('/recommendations');
  await page.locator('nav[aria-label="주요 이동 메뉴"]').getByRole('link', { name: '홈' }).click();
  await expect(page).toHaveURL('/home');
  await expect(page.getByText('이 영화를 추천해요.')).toHaveCount(0);
  await expect(page.locator('.home3-chat-stage')).not.toHaveClass(/is-chatting/);
});

test('캐릭터 대화는 기록 선택 때만 열리고 새로고침하면 비활성 상태로 돌아간다', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('cineverse.groupchat.conversations', JSON.stringify({
      sessionId: 'e2e-session',
      conversations: [{
        id: 'saved-character-22',
        roomId: '22',
        title: '아이언맨',
        members: [{ id: 1, name: '아이언맨' }],
        createdAt: '2026-08-11T03:00:00Z',
        messages: [{ id: 'character-1', role: 'assistant', character: '아이언맨', content: '준비됐어.' }],
      }],
    }));
  });
  await page.route('**/api/chat/rooms/22/messages', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      state: 'success',
      data: [{ role: 'assistant', character: '아이언맨', content: '준비됐어.' }],
    }),
  }));

  await page.goto('/chat/group?room=22&members=%EC%95%84%EC%9D%B4%EC%96%B8%EB%A7%A8');
  await expect(page).toHaveURL('/chat/group');
  await expect(page.getByText('준비됐어.')).toBeVisible();

  await page.reload();
  await expect(page.getByText('준비됐어.')).toHaveCount(0);
  await expect(page.locator('.group-chat-home-stage')).not.toHaveClass(/is-chatting/);

  await page.goto('/chat/group?room=22&members=%EC%95%84%EC%9D%B4%EC%96%B8%EB%A7%A8');
  await expect(page.getByText('준비됐어.')).toBeVisible();
  await page.locator('nav[aria-label="주요 이동 메뉴"]').getByRole('link', { name: '홈' }).click();
  await expect(page).toHaveURL('/home');
  await page.locator('nav[aria-label="주요 이동 메뉴"]').getByRole('link', { name: '캐릭터와 대화' }).click();
  await expect(page).toHaveURL('/chat/group');
  await expect(page.getByText('준비됐어.')).toHaveCount(0);
  await expect(page.locator('.group-chat-home-stage')).not.toHaveClass(/is-chatting/);
});
