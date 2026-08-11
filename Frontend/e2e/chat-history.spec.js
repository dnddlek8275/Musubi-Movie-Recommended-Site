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
