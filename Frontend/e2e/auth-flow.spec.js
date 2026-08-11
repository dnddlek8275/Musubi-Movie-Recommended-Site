import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.clear();
    sessionStorage.clear();
    localStorage.setItem('cineverse-theme', 'dark');
  });
});

test('로그인 필수값과 아이디 저장 흐름이 유지된다', async ({ page }) => {
  await page.route('**/api/auth/login', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        state: 'success',
        data: {
          access_token: 'e2e-token',
          token_type: 'bearer',
          email: 'member@example.com',
          nickname: '테스트회원',
          onboarding_completed: false,
        },
      }),
    });
  });

  await page.goto('/?scene=4');
  await page.getByRole('button', { name: '로그인', exact: true }).click();
  await expect(page.getByRole('status')).toHaveText('이메일과 비밀번호를 모두 입력해 주세요.');

  await page.getByPlaceholder('이메일').fill('member@example.com');
  await page.getByPlaceholder('비밀번호').fill('Password1!');
  await page.getByLabel('아이디 저장').check();
  await page.getByRole('button', { name: '로그인', exact: true }).click();

  await expect.poll(() => page.evaluate(() => localStorage.getItem('musubi.savedLoginEmail')))
    .toBe('member@example.com');
  await expect(page).toHaveURL(/\/onboarding/);
});

test('비밀번호 재설정 성공 후 재전송 버튼으로 바뀐다', async ({ page }) => {
  await page.route('**/api/auth/password-reset/request', async (route) => {
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        state: 'success',
        message: '이메일로 비밀번호 재설정 링크가 발송되었습니다.',
      }),
    });
  });

  await page.goto('/?auth=password-reset');
  await page.getByPlaceholder('이메일').fill('member@example.com');
  await page.getByRole('button', { name: '전송', exact: true }).click();

  await expect(page.getByRole('status')).toHaveText('이메일로 비밀번호 재설정 링크가 발송되었습니다.');
  await expect(page.getByRole('button', { name: '재전송', exact: true })).toBeVisible();
});

test('미가입 이메일 안내가 그대로 노출된다', async ({ page }) => {
  await page.route('**/api/auth/password-reset/request', async (route) => {
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ state: 'failure', message: '가입된 이메일이 아닙니다.' }),
    });
  });

  await page.goto('/?auth=password-reset');
  await page.getByPlaceholder('이메일').fill('missing@example.com');
  await page.getByRole('button', { name: '전송', exact: true }).click();
  await expect(page.getByRole('status')).toHaveText('가입된 이메일이 아닙니다.');
  await expect(page.getByRole('button', { name: '전송', exact: true })).toBeVisible();
});
