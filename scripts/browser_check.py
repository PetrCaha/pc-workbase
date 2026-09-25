"""Optional browser QA. Run against a local demo; never a customer deployment.
Requires playwright as a development-only dependency.
"""
from pathlib import Path
import json, os
from playwright.sync_api import sync_playwright
BASE=os.environ.get('WORKBASE_TEST_URL','http://127.0.0.1:8765')
OUT=Path(__file__).resolve().parent.parent/'artifacts'
OUT.mkdir(exist_ok=True)
results=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    for width in (1440,768,390,320):
        for language in ('cs','en'):
            context=browser.new_context(viewport={'width':width,'height':1000 if width>760 else 844},locale=language)
            page=context.new_page()
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(BASE+'/login/')
            page.locator(f'.language-switch button[value="{language}"]').click()
            page.wait_for_load_state('networkidle')
            if width in (1440,390):page.screenshot(path=str(OUT/f'login-{language}-{width}.png'),full_page=True)
            page.locator('.entry-card button').click()
            page.wait_for_url(BASE+'/')
            paths=['/','/zakaznici/','/zakaznici/1/','/zakazky/?view=all','/zakazky/1/','/zakazky/1/faktury/1/','/zakazky/nova/','/zakaznici/novy/','/zakazky/1/faktury/nova/','/uzivatele/']
            for index,path in enumerate(paths):
                response=page.goto(BASE+path)
                page.wait_for_load_state('networkidle')
                assert response.status==200,(path,response.status)
                overflow=page.evaluate('document.documentElement.scrollWidth > window.innerWidth + 1')
                offenders=page.evaluate('''() => [...document.querySelectorAll('main *')].filter(e=>e.getBoundingClientRect().right>innerWidth+2).slice(0,8).map(e=>({tag:e.tagName,cls:e.className,text:e.textContent.slice(0,60)}))''') if overflow else []
                results.append({'width':width,'language':language,'path':path,'overflow':overflow,'offenders':offenders})
                if width in (1440,390) and index in (0,3,4,6):page.screenshot(path=str(OUT/f'page-{index}-{language}-{width}.png'),full_page=True)
            # Native browser validation, navigation and signed-cookie session work together.
            page.goto(BASE+'/zakaznici/novy/')
            page.locator('#id_name').fill('Only a fictional test')
            page.locator('.form button[type=submit], .form button:not([type])').last.click()
            page.wait_for_selector('#form-result')
            assert page.locator('#id_name').input_value()=='Only a fictional test'
            page.goto(BASE+'/zakazky/?view=all')
            page.locator('.preview-button').first.click()
            page.locator(".quick-row:not([hidden]) .quick-grid").wait_for()
            assert page.locator('.preview-button').first.get_attribute('aria-expanded')=='true'
            page.goto(BASE+'/zakazky/nova/')
            page.locator('#id_customer').select_option('1')
            page.locator("#id_contact option[value=\"1\"]").wait_for(state="attached")
            assert not errors,errors
            context.close()
    browser.close()
(OUT/'browser-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
failures=[row for row in results if row['overflow']]
print(json.dumps({'pages':len(results),'overflow_failures':failures},ensure_ascii=False,indent=2))
raise SystemExit(bool(failures))
