import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Твій токен
TOKEN = '8968199767:AAF3r4WKngDsnDeKOoH-HzQ7S3VigxNls5c'
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Бази даних в пам'яті
users = set()
admins_usernames = {"fyto3"}  # Головний адмін

# Стан поточного голосування
active_vote = {
    "in_progress": False,
    "topic": "",
    "duration": 25,
    "votes": {"yes": [], "no": [], "abstain": []},
    "voted_users": set(),
    "messages_to_update": {}
}

# Стан для адмінів, які створюють голосування
admin_states = {}

def is_admin(username: str) -> bool:
    if not username: return False
    return username.lower() in admins_usernames

def get_main_keyboard(is_adm: bool):
    kb = [
        [
            InlineKeyboardButton(text="👍 За", callback_data="vote_yes"), 
            InlineKeyboardButton(text="👎 Проти", callback_data="vote_no")
        ],
        [
            InlineKeyboardButton(text="➖ Утриматися", callback_data="vote_abstain")
        ],
        [
            InlineKeyboardButton(text="👤 Мій профіль", callback_data="profile")
        ]
    ]
    if is_adm:
        kb.append([InlineKeyboardButton(text="📢 Надіслати голосування", callback_data="start_vote")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    users.add(message.from_user.id)
    is_adm = is_admin(message.from_user.username)
    await message.answer("Вітаю! Це бот для голосування. Використовуй кнопки нижче:", reply_markup=get_main_keyboard(is_adm))

@dp.callback_query(F.data == "profile")
async def profile_handler(callback: types.CallbackQuery):
    user = callback.from_user
    is_adm = is_admin(user.username)
    status = "Адміністратор" if is_adm else "Учасник"
    text = f"👤 **Ваш профіль:**\n\n📌 Ім'я: {user.first_name}\n🔗 Юзернейм: @{user.username or 'немає'}\n🆔 ID: {user.id}\n🛡️ Статус: {status}"
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.message(Command("give"))
async def give_command_handler(message: types.Message):
    if not is_admin(message.from_user.username):
        await message.answer("❌ У вас немає прав.")
        return
    
    args = message.text.split()
    if len(args) >= 3 and args[1].lower() == "admin":
        target = args[2].replace("@", "").strip().lower()
        admins_usernames.add(target)
        await message.answer(f"✅ Користувачу @{target} успішно видано повні права адміністратора!")
    else:
        await message.answer("⚠️ Використовуйте формат: `/give admin @username`", parse_mode="Markdown")

@dp.message(Command("give_admin"))
async def give_admin_legacy(message: types.Message):
    if not is_admin(message.from_user.username):
        await message.answer("❌ У вас немає прав.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Вкажіть юзернейм. Приклад: `/give admin @username`", parse_mode="Markdown")
        return
    
    target = args[1].replace("@", "").strip().lower()
    admins_usernames.add(target)
    await message.answer(f"✅ Користувачу @{target} успішно видано повні права адміністратора!")

@dp.callback_query(F.data == "start_vote")
async def start_vote_prompt(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.username):
        await callback.answer("❌ Доступ заборонено", show_alert=True)
        return
    
    admin_states[callback.from_user.id] = {"step": "topic"}
    await callback.message.answer("✍️ Напишіть **тему голосування** у наступному повідомленні:")
    await callback.answer()

@dp.message(F.text)
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    
    if user_id in admin_states:
        state = admin_states[user_id]
        
        if state["step"] == "topic":
            state["topic"] = message.text
            state["step"] = "duration"
            await message.answer("⏱️ Тепер введіть **тривалість голосування в секундах** (наприклад: `25` або `60`):")
            return
            
        elif state["step"] == "duration":
            text_val = message.text.strip()
            if not text_val.isdigit():
                await message.answer("⚠️ Будь ласка, введіть число (секунди). Спробуйте ще раз:")
                return
                
            duration = int(text_val)
            topic = state["topic"]
            del admin_states[user_id]
            
            if active_vote["in_progress"]:
                await message.answer("⚠️ Попереднє голосування ще триває!")
                return
            
            active_vote["in_progress"] = True
            active_vote["topic"] = topic
            active_vote["duration"] = duration
            active_vote["votes"] = {"yes": [], "no": [], "abstain": []}
            active_vote["voted_users"] = set()
            active_vote["messages_to_update"] = {}
            
            await message.answer(f"🚀 Голосування запущено на {duration} сек! Розсилаю {len(users)} користувачам...")
            
            vote_kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="👍 За", callback_data="vote_yes"), 
                    InlineKeyboardButton(text="👎 Проти", callback_data="vote_no")
                ],
                [
                    InlineKeyboardButton(text="➖ Утриматися", callback_data="vote_abstain")
                ]
            ])
            
            for uid in users:
                try:
                    msg = await bot.send_message(
                        uid, 
                        f"📢 **НОВЕ ГОЛОСУВАННЯ!**\n\n{topic}\n\n⏱️ Залишилося часу: **{duration} сек.**", 
                        reply_markup=vote_kb, 
                        parse_mode="Markdown"
                    )
                    active_vote["messages_to_update"][uid] = msg.message_id
                except Exception:
                    pass
            
            asyncio.create_task(run_vote_timer(user_id))
    else:
        pass

async def run_vote_timer(admin_id: int):
    seconds_left = active_vote["duration"]
    vote_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👍 За", callback_data="vote_yes"), 
            InlineKeyboardButton(text="👎 Проти", callback_data="vote_no")
        ],
        [
            InlineKeyboardButton(text="➖ Утриматися", callback_data="vote_abstain")
        ]
    ])
    
    while seconds_left > 0 and active_vote["in_progress"]:
        await asyncio.sleep(1)
        seconds_left -= 1
        
        if seconds_left <= 0:
            break
            
        for uid, msg_id in list(active_vote["messages_to_update"].items()):
            try:
                await bot.edit_message_text(
                    chat_id=uid,
                    message_id=msg_id,
                    text=f"📢 **НОВЕ ГОЛОСУВАННЯ!**\n\n{active_vote['topic']}\n\n⏱️ Залишилося часу: **{seconds_left} сек.**",
                    reply_markup=vote_kb,
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    active_vote["in_progress"] = False
    
    # Підрахунок кількості голосів для загального звіту
    yes_count = len(active_vote["votes"]["yes"])
    no_count = len(active_vote["votes"]["no"])
    abstain_count = len(active_vote["votes"]["abstain"])

    # Учасникам відправляємо загальну статистику без імен
    public_results = (
        f"📢 **ГОЛОСУВАННЯ ЗАВЕРШЕНО!**\n\n"
        f"📌 Тема: *{active_vote['topic']}*\n\n"
        f"📊 **Підсумки:**\n"
        f"👍 За: **{yes_count}**\n"
        f"👎 Проти: **{no_count}**\n"
        f"➖ Утрималися: **{abstain_count}**"
    )

    for uid, msg_id in list(active_vote["messages_to_update"].items()):
        try:
            await bot.edit_message_text(
                chat_id=uid,
                message_id=msg_id,
                text=public_results,
                reply_markup=None,
                parse_mode="Markdown"
            )
        except Exception:
            pass

    # Адміну відправляємо детальний звіт із іменами
    yes_list = active_vote["votes"]["yes"]
    no_list = active_vote["votes"]["no"]
    abstain_list = active_vote["votes"]["abstain"]
    
    def format_users(lst):
        if not lst: return "Нікого"
        return "\n".join([f"• {u['name']} (@{u['username']})" for u in lst])
    
    admin_res_text = (
        f"📊 **ПОВНИЙ ЗВІТ ДЛЯ АДМІНІСТРАТОРА**\n"
        f"📌 Тема: *{active_vote['topic']}*\n\n"
        f"👍 За: **{yes_count}**\n{format_users(yes_list)}\n\n"
        f"👎 Проти: **{no_count}**\n{format_users(no_list)}\n\n"
        f"➖ Утрималися: **{abstain_count}**\n{format_users(abstain_list)}"
    )
    
    try:
        await bot.send_message(admin_id, admin_res_text, parse_mode="Markdown")
    except:
        pass

@dp.callback_query(F.data.in_({"vote_yes", "vote_no", "vote_abstain"}))
async def handle_vote(callback: types.CallbackQuery):
    if not active_vote["in_progress"]:
        await callback.answer("❌ Голосування зараз не активне або вже завершилося.", show_alert=True)
        return
    
    user_id = callback.from_user.id
    if user_id in active_vote["voted_users"]:
        await callback.answer("⚠️ Ви вже проголосували!", show_alert=True)
        return
    
    active_vote["voted_users"].add(user_id)
    
    u_data = {
        "name": callback.from_user.first_name,
        "username": callback.from_user.username or "немає"
    }
    
    if callback.data == "vote_yes":
        active_vote["votes"]["yes"].append(u_data)
        await callback.answer("✅ Ваш голос «За» зараховано!", show_alert=True)
    elif callback.data == "vote_no":
        active_vote["votes"]["no"].append(u_data)
        await callback.answer("✅ Ваш голос «Проти» зараховано!", show_alert=True)
    elif callback.data == "vote_abstain":
        active_vote["votes"]["abstain"].append(u_data)
        await callback.answer("✅ Ваш голос зараховано (утримався).", show_alert=True)

async def main():
    print("Бот запущений...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
