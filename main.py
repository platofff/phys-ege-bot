import asyncio
import signal
import sys
from datetime import datetime, timedelta
import shelve
import os
import random

from aiogram import Bot, Dispatcher, types

BOT_TOKEN = os.getenv('TOKEN')
db = shelve.open(os.path.join('db', 'db'), writeback=True)
tasks_set = set(db['tasks'].keys())
bot: Bot
solving_now = {}
solved_now = {}
invalid_now = {}
session_start = {}
last_active = {}
rows = {}
rows_record = []
basic_emoji = ['😏', '😌', '☺', '😇']
advanced_emoji = ['😮', '🤯', '😎', '🤓']
valid_emoji = ['💪', '👍', '🤗', '🤤', '🍆', '🤩', '😈', '✅', '🥳']
invalid_emoji = ['🚫', '😡', '😨', '🤫', '🤡', '💩', '❌']


def strfdelta(tdelta):
    fmt = "{hours}:{minutes:02d}:{seconds:02d}"
    d = {"days": tdelta.days}
    d["hours"], rem = divmod(tdelta.seconds, 3600)
    d["minutes"], d["seconds"] = divmod(rem, 60)
    return fmt.format(**d)


async def end_session_stats(tasks_count: int, session_len: timedelta, valid_percent: int, event: types.Message):
    await event.answer(
        f'{random.choice(valid_emoji)} Решено задач: <b>{tasks_count}</b> ({valid_percent}%)\n'
        f'Продолжительность сессии: <b>{strfdelta(session_len)}</b>\n'
        f'Не забывай возвращаться и тренироваться 🤓', parse_mode=types.ParseMode.HTML)


async def no_active_handler(event: types.Message):
    await asyncio.sleep(601)
    if (datetime.now() - last_active[event.from_user["id"]]).seconds > 600 and event.from_user["id"] in solved_now.keys():
        tasks_count, session_len, valid_percent = await end_session(event, True)
        await event.answer('Сессия завершена (не было активности в течение 10 минут). '
                           'Чтобы вернуться к последней задаче напиши <b>/задачи</b> снова',
                           parse_mode=types.ParseMode.HTML)
        await end_session_stats(tasks_count, session_len, valid_percent, event)
        solved_now.pop(event.from_user["id"], None)


async def task_handler(event: types.Message):
    if event.text.startswith('/'):
        session_start.update({event.from_user["id"]: datetime.now()})
        last_active.update({event.from_user["id"]: datetime.now()})
        asyncio.get_running_loop().create_task(no_active_handler(event))
        rows.update({event.from_user["id"]: 0})
        solved_now.update({event.from_user["id"]: 0})
        invalid_now.update({event.from_user["id"]: 0})
        await event.answer('Чтобы прекратить получать задачи введи <b>/стоп</b>', parse_mode=types.ParseMode.HTML)
    if not event.from_user['id'] in db['users'].keys():
        db['users'].update({event.from_user['id']: {'done_tasks': [],
                                                    'max_times_row': 0,
                                                    'max_session': 0,
                                                    'valid_solutions': 0}})
    if event.from_user["id"] in solving_now.keys():
        task = solving_now[event.from_user['id']]
    else:
        available_tasks = list(tasks_set - set(db['users'][event.from_user['id']]['done_tasks']))
        if not available_tasks:
            available_tasks.append(db['users'][event.from_user['id']]['done_tasks'].pop(0))
        task = random.choice(available_tasks)
    with open(os.path.join('tasks', f'{task}.png'), 'rb') as f:
        await bot.send_photo(chat_id=event.chat.id, photo=f)
    solving_now.update({event.from_user['id']: task})
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(types.KeyboardButton(text='/стоп'))
    if db['tasks'][task]['taskTypeId'] == 2:
        keyboard.add('1')
        keyboard.add('2')
        keyboard.add('3')
        keyboard.add('4')
    await event.answer(
        f"Уровень задачи: {db['tasks'][task]['levelName']} "
        f"{random.choice(basic_emoji) if db['tasks'][task]['levelName'].startswith('Базовый') else random.choice(advanced_emoji)}",
        reply_markup=keyboard)


async def end_session(event: types.Message, from_timeout=False):
    session = datetime.now() - session_start[event.from_user['id']]
    session_len = session.seconds
    if from_timeout:
        session_len -= 600
    try:
        if db['users'][event.from_user['id']]['max_session'] < solved_now[event.from_user['id']]:
            db['users'][event.from_user['id']]['max_session'] = solved_now[event.from_user['id']]
            msg = f'Новый рекорд по количеству задач, решённых за сессию {random.choice(valid_emoji)}\n'
        else:
            msg = ''
    except KeyError:
        msg = ''
    if session_len >= 2760:
        msg += f'Хорошая усидчивость! {random.choice(valid_emoji)}\n'
    if event.from_user['id'] in rows_record:
        rows_record.pop(rows_record.index(event.from_user['id']))
        msg += f'Новый рекорд: {db["users"][event.from_user["id"]]["max_times_row"]} ' \
               f'правильных ответов подряд! {random.choice(valid_emoji)}'
    if msg:
        await event.answer(msg)
    return solved_now[event.from_user['id']], session, \
           int(solved_now[event.from_user['id']] / (
                       solved_now[event.from_user['id']] + invalid_now[event.from_user['id']]) * 100)


async def solution_handler(event: types.Message):
    if event.text == '/стоп':
        await end_session_stats(*(await end_session(event)), event)
        solved_now.pop(event.from_user["id"], None)
    elif event.from_user['id'] in solving_now.keys() and not event.text.startswith('/'):
        last_active.update({event.from_user["id"]: datetime.now()})
        asyncio.get_running_loop().create_task(no_active_handler(event))
        if event.text == db['tasks'][solving_now[event.from_user['id']]]['answer']:
            solved_now[event.from_user['id']] += 1
            rows[event.from_user["id"]] += 1
            if rows[event.from_user["id"]] > db['users'][event.from_user["id"]]['max_times_row']:
                rows_record.append(event.from_user["id"])
                db['users'][event.from_user["id"]]['max_times_row'] = rows[event.from_user["id"]]
            db['users'][event.from_user['id']]['valid_solutions'] += 1
            db['users'][event.from_user['id']]['done_tasks'].append(solving_now[event.from_user['id']])
            await event.answer(f'{random.choice(valid_emoji)} Верно')
            if rows[event.from_user["id"]] % 5 == 0:
                await event.answer(f'{rows[event.from_user["id"]]} правильных подряд {random.choice(valid_emoji)}')
        else:
            rows[event.from_user["id"]] = 0
            invalid_now[event.from_user["id"]] += 1
            await event.answer(
                f"{random.choice(invalid_emoji)} Неверно. Правильный ответ: {db['tasks'][solving_now[event.from_user['id']]]['answer']}")
        solving_now.pop(event.from_user['id'], None)
        await task_handler(event)


async def start_handler(event: types.Message):
    await event.answer(
        f"Привет, {event.from_user.get_mention(as_html=True)} 👋! "
        f"Напиши мне <b>/задачи</b> чтобы начать готовиться к ЕГЭ по физике 🤓\n"
        f"Проверить свои достижения: <b>/статистика</b>",
        parse_mode=types.ParseMode.HTML)


async def stats_handler(event: types.Message):
    await event.answer(f'Решено задач: <b>{db["users"][event.from_user["id"]]["valid_solutions"]}</b>\n'
                       f'Максимум правильных ответов за сессию: <b>{db["users"][event.from_user["id"]]["max_session"]}</b>\n'
                       f'Максимум правильных ответов подряд: <b>{db["users"][event.from_user["id"]]["max_times_row"]}</b>',
                       parse_mode=types.ParseMode.HTML)


async def main():
    global bot
    bot = Bot(token=BOT_TOKEN)
    try:
        disp = Dispatcher(bot=bot)
        disp.register_message_handler(start_handler, commands={'start', 'restart', 'старт', 'начать'})
        disp.register_message_handler(task_handler, commands={'tasks', 'задачи'})
        disp.register_message_handler(stats_handler, commands={'stats', 'статистика'})
        disp.register_message_handler(solution_handler)
        await disp.start_polling()
    finally:
        await bot.close()
        db.close()


def signal_handler(sig, frame):
    db.close()
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    asyncio.run(main())
