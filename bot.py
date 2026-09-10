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
    "votes": {"yes": [], "no": []},
    "voted_users": set()
}

waiting_for_topic = set()

def is_admin(username: str) -> bool:
    if not username: return False
    return username.lower() in admins_usernames

def get_main_keyboard(is_adm: bool):
    kb = [
        [InlineKeyboardButton(text="👍 За", callback_data="vote_yes"), 
         InlineKeyboardButton(text="👎 Проти", callback_data="vote_no")],
        [InlineKeyboardButton(text="👤 Мій профіль", callback_data="profile")]
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

@dp.message(Command("give_admin"))
async def give_admin(message: types.Message):
    if not is_admin(message.from_user.username):
        await message.answer("❌ У вас немає прав.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Вкажіть юзернейм. Приклад: /give_admin @username")
        return
    
    target = args[1].replace("@", "").strip().lower()
    admins_usernames.add(target)
    await message.answer(f"✅ Користувачу @{target} надано права адміністратора!")

@dp.callback_query(F.data == "start_vote")
async def start_vote_prompt(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.username):
        await callback.answer("❌ Доступ заборонено", show_alert=True)
        return
    
    waiting_for_topic.add(callback.from_user.id)
    await callback.message.answer("✍️ Напишіть тему голосування у наступному повідомленні:")
    await callback.answer()

@dp.message(F.text)
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    if user_id in waiting_for_topic:
        waiting_for_topic.remove(user_id)
        
        if active_vote["in_progress"]:
            await message.answer("⚠️ Попереднє голосування ще триває!")
            return
        
        topic = message.text
        active_vote["in_progress"] = True
        active_vote["topic"] = topic
        active_vote["votes"] = {"yes": [], "no": []}
        active_vote["voted_users"] = set()
        
        await message.answer(f"🚀 Голосування розпочато! Розсилаю {len(users)} користувачам...")
        
        vote_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👍 За", callback_data="vote_yes"), 
             InlineKeyboardButton(text="👎 Проти", callback_data="vote_no")]
        ])
        
        for uid in users:
            try:
                await bot.send_message(
                    uid, 
                    f"📢 **НОВЕ ГОЛОСУВАННЯ!**\n\n{topic}\n\n⏱️ У вас є **25 секунд**!", 
                    reply_markup=vote_kb, 
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        
        # Запуск таймера на 25 секунд
        asyncio.create_task(vote_timer(user_id))
    else:
        pass 

async def vote_timer(admin_id: int):
    await asyncio.sleep(25)
    active_vote["in_progress"] = False
    
    yes_list = active_vote["votes"]["yes"]
    no_list = active_vote["votes"]["no"]
    
    def format_users(lst):
        if not lst: return "Нікого"
        return "\n".join([f"• {u['name']} (@{u['username']})" for u in lst])
    
    res_text = (
        f"📊 **РЕЗУЛЬТАТИ ГОЛОСУВАННЯ**\n"
        f"📌 Тема: *{active_vote['topic']}*\n\n"
        f"👍 За: **{len(yes_list)}**\n{format_users(yes_list)}\n\n"
        f"👎 Проти: **{len(no_list)}**\n{format_users(no_list)}"
    )
    
    try:
        await bot.send_message(admin_id, res_text, parse_mode="Markdown")
    except:
        pass

@dp.callback_query(F.data.in_({"vote_yes", "vote_no"}))
async def handle_vote(callback: types.CallbackQuery):
    if not active_vote["in_progress"]:
        await callback.answer("❌ Голосування зараз не активне.", show_alert=True)
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
    else:
        active_vote["votes"]["no"].append(u_data)
        await callback.answer("✅ Ваш голос «Проти» зараховано!", show_alert=True)

async def main():
    print("Бот запущений...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
