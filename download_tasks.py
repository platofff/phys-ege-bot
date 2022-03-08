import json
import shelve
import sys
from urllib import request
from os import path
import tempfile
import asyncio
from pathlib import Path

from pyppeteer import launch

with open('styles.css') as f:
    css = f.read().replace('\n', '')

Path('db').mkdir(exist_ok=True)
Path('tasks').mkdir(exist_ok=True)

db = shelve.open(path.join('db', 'db'))
if 'tasks' not in db.keys():
    db['tasks'] = {}
if 'users' not in db.keys():
    db['users'] = {}

screenshots = len(sys.argv) == 1 or sys.argv[1] != 'no_screenshots'


async def main():
    tasks = {}
    if screenshots:
        browser = await launch()
        page = await browser.newPage()
        await page.emulate({'viewport': {'width': 768, 'height': 1024, 'deviceScaleFactor': 1.5}})
    for page_n in range(1, 182):
        while True:
            try:
                print(f'Processing page {page_n}...')
                data = {"subjectId": "3", "levelIds": [], "themeIds": [], "typeIds": [], "id": "", "favorites": 0,
                        "answerStatus": 0,
                        "themeSectionIds": [], "published": 0, "extId": "", "fipiCode": "", "docId": "", "isAdmin": False,
                        "loadDates": [], "isPublished": False, "pageSize": 10, "pageNumber": page_n}
                req = request.Request('http://os.fipi.ru/api/tasks', data=json.dumps(data).encode())
                req.add_header('Content-Type', 'application/json;charset=utf-8')
                req.add_header('sessionId', '6f48920e-c3f2-54f0-1a30-2e36f8e46cb4')

                with request.urlopen(req) as resp:
                    data = json.load(resp)

                for i in range(len(data['tasks'])):
                    if 22588 <= data["tasks"][i]["id"] <= 22589:
                        continue
                    tmp = path.join(tempfile.gettempdir(), f'{data["tasks"][i]["id"]}.html')
                    with open(tmp, 'w') as f:
                        f.write(data['tasks'][i]['html'].encode().decode('cp1251', 'backslashreplace')
                                .replace('<script src="/', '<script src="http://os.fipi.ru/')
                                .replace(r'Р\x98', '&#1048;').replace('<link href="/', '<link href="http://os.fipi.ru/'))
                    if data["tasks"][i]['answer'] == '':
                        continue
                    if screenshots:
                        await page.goto(f'file://{tmp}')
                        await page.evaluate('''() => {
                            const style = document.createElement('style')
                            document.head.appendChild(style)
                            style.type = 'text/css'
                            style.appendChild(document.createTextNode("''' + css + '''"))
                            for (const img of document.getElementsByTagName('img')) {
                                img.setAttribute('src', 'http://os.fipi.ru' + img.getAttribute('src'))
                            }
                            for (const el of document.querySelectorAll('div.answers>div.answer')) {
                                const number = Number(el.getAttribute('number'))
                                if (!number) {
                                    continue
                                }
                                let target = el.querySelector('.answer-item-text').children[0]
                                if (target.nodeName !== "P") {
                                    target = target.children[0]
                                }
                                const n = document.createElement('SPAN')
                                n.classList.add('v-number')
                                n.innerText = number + ') '
                                target.insertBefore(n, target.firstChild)
                            }
                        }''')
                        await page.waitForSelector('html')
                        await asyncio.sleep(1)
                        element = await page.querySelector('html')
                        await element.screenshot({'path': path.join('tasks', f'{data["tasks"][i]["id"]}.png')})
                    tasks.update({data["tasks"][i]["id"]: {'answer': data['tasks'][i]['answer'].replace(', ', ''),
                                                           'levelName': data['tasks'][i]['levelName'].strip(),
                                                           'taskTypeId': data['tasks'][i]['taskTypeId']}})
                break
            except Exception as e:
                e = str(e)
                if 'nodeName' in e:
                    continue
                print(e, 'page', page_n)
    tasks.update(db['tasks'])
    db['tasks'] = tasks
    if screenshots:
        await browser.close()

asyncio.new_event_loop().run_until_complete(main())
db.close()
