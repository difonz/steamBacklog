const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({
    headless: false,      // Set to true for final recording
    slowMo: 100            // Slow down actions for visibility (optional)
  });

  const context = await browser.newContext({
    recordVideo: {
      dir: 'videos/',
      size: { width: 1280, height: 720 }
    }
  });

  const page = await context.newPage();
  const baseURL = 'https://steambacklog.onrender.com';

  // 1. Go to homepage and navigate to Register
  await page.goto(baseURL);
  await page.waitForTimeout(3000);
  await page.click('text=Register');

  // 2. Register new user
  await page.waitForSelector('input[name="email"]', { timeout: 15000 });
  await page.fill('input[name="email"]', 'demoUser2@email.com');
  await page.fill('input[name="password"]', 'demoPass123');
  await page.click('button:has-text("Register")');
  await page.waitForTimeout(2000);

  // 3. Go to Login
  await page.goto(`${baseURL}/login/`);
  await page.waitForSelector('input[name="email"]', { timeout: 10000 });
  await page.fill('input[name="email"]', 'demoUser2@email.com');
  await page.fill('input[name="password"]', 'demoPass123');
  await page.click('button:has-text("Login")');
  await page.waitForTimeout(3000);

  // 4. Add Steam profile and view games
  await page.waitForSelector('input[placeholder^="https://steamcommunity"]', { timeout: 15000 });
  await page.fill('input[placeholder^="https://steamcommunity"]', 'https://steamcommunity.com/id/abyssfonz');

  await page.click('text=Save Steam ID'); 
  await page.click('text=View My Games', {timeout: 0}); 
  await page.waitForURL('**/games/' ,{timeout: 0});
  await page.waitForSelector('text=My Game Library', { timeout: 100000 });

  // 5. Sort by Completion %
  await page.click('text=Achievement Completion %',{timeout:0});
  await page.waitForTimeout(10000);
  await page.click('text=Achievement Completion %',{timeout:0});

  // 6. Update statuses of 2 games
  const row3 = (await page.$$('tr'))[5];
  if (row3) {
    const select1 = await row3.$('select');
    const save1 = await row3.$('text=Save');
    if (select1 && save1) {
        await select1.selectOption({ label: 'In Progress' });
        await save1.click();
        await page.waitForTimeout(1000);
    } else {
        console.warn('Row 3 select or save not found.');
  }
}

// Safely set 5th row to "Completed"
  const row4 = (await page.$$('tr'))[6];
  if (row4) {
    const select2 = await row4.$('select');
    const save2 = await row4.$('text=Save');
    if (select2 && save2) {
        await select2.selectOption({ label: 'Completed' });
        await save2.click();
        await page.waitForTimeout(1000);
    } else {
        console.warn('Row 4 select or save not found.');
  }
}
  // 7. Scroll for polish
  await page.mouse.wheel(0, 600);
  await page.waitForTimeout(1500);
  await page.click('text=Logout')
  await page.waitForTimeout(3000);
  const videoPath = await page.video().path();
  console.log('🎬 Video saved at:', videoPath);
  await page.close();
  await browser.close();

})();
