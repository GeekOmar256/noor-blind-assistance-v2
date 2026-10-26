const {chromium}=require('C:/Users/omars/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs');const assert=require('node:assert/strict');
(async()=>{
 const text=fs.readFileSync('LOCAL_ACCESS.txt','utf8');const password=text.match(/Initial password: (.*)/)[1];
 const browser=await chromium.launch({headless:true,channel:'msedge'});const page=await browser.newPage({viewport:{width:390,height:844}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('https://alzheimer-noor.web.app');await page.fill('#email','cargiver@gmail.com');await page.fill('#password',password);await page.locator('#login-form button').click();await page.locator('#app').waitFor({state:'visible',timeout:60000});
 const connection=await page.locator('#connection').textContent();if(process.env.EXPECTED_PI_STATUS)assert.equal(connection,process.env.EXPECTED_PI_STATUS);else assert(['Online','Offline'].includes(connection));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
 await page.locator('[data-nav="people"]').click();await page.locator('#person-form').waitFor({state:'visible'});
 await page.locator('[data-nav="voices"]').click();await page.locator('#voice-history').waitFor({state:'visible'});
 await page.locator('[data-nav="settings"]').click();await page.locator('#settings-form').waitFor({state:'visible'});
 assert.equal(await page.locator('#setting-face-model option[value="dlib"]').textContent(),'dlib');
 assert(await page.locator('#setting-scene').count());assert(await page.locator('#setting-face').count());
 assert.deepEqual(errors,[]);await browser.close();console.log('PASS: deployed site caregiver login, paired state, Pi status '+connection+', mobile layout, profiles/settings navigation, no JavaScript errors');
})().catch(e=>{console.error(e.message);process.exit(1)});
