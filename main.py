import asyncio
import json
import os
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import aiohttp

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TON_WALLET = os.getenv("TON_WALLET")
TONCENTER_API_KEY = os.getenv("TONCENTER_API_KEY")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

PAID_USERS_FILE = "paid_users.json"
user_coefficients = {}
user_ids = {}

RANDOM_COUNT = 20
MAX_COEFFICIENTS = 25

def load_paid_users():
    if os.path.exists(PAID_USERS_FILE):
        with open(PAID_USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_paid_users(data):
    with open(PAID_USERS_FILE, "w") as f:
        json.dump(data, f)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = str(message.from_user.id)
    comment = f"user_{user_id}"
    user_coefficients.pop(user_id, None)

    await message.answer(
        f"👋 Hello, {message.from_user.full_name}!\n\n"
        f"💸 To start the game, please pay at least <b>3 TON</b>.\n\n"
        f"📥 TON Wallet Address:\n<code>{TON_WALLET}</code>\n\n"
        f"📝 Comment (required):\n<code>{comment}</code>\n\n"
        f"✅ After payment, type /check to continue.",
        disable_web_page_preview=True
    )

@dp.message(Command("check"))
async def check_payment(message: Message):
    user_id = str(message.from_user.id)
    paid_users = load_paid_users()

    if user_id in paid_users:
        if user_id in user_coefficients and len(user_coefficients[user_id]) >= MAX_COEFFICIENTS:
            paid_users.pop(user_id)
            save_paid_users(paid_users)
            return await message.answer("🔄 Your limit has ended. Please make another payment to continue.")
        return await ask_for_id(message)

    url = f"https://toncenter.com/api/v2/getTransactions?address={TON_WALLET}&limit=5&api_key={TONCENTER_API_KEY}"

    headers = {"Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return await message.answer("❌ TonCenter API did not respond.")
            data = await resp.json()

    for tx in data.get("result", []):
        in_msg = tx.get("in_msg", {})
        comment = in_msg.get("message", "") or ""
        sender = in_msg.get("source", "")
        value = int(in_msg.get("value", 0)) / 1e9

        print("=== TX DEBUG ===")
        print("Comment:", comment)
        print("Sender:", sender)
        print("Value:", value)
        print("---")

        if f"user_{user_id}" in comment and value >= 3.0:
            paid_users[user_id] = sender
            save_paid_users(paid_users)
            return await ask_for_id(message)

    await message.answer(
        "❌ Payment not found. Please make sure the comment is correct and the amount is <b>at least 3 TON</b>. "
        "Try /check again in 1-2 minutes."
    )


async def ask_for_id(message: Message):
    await message.answer(
        "✅ Payment received successfully!\n\n"
        "🎰 Register using the link below:\n"
        "🔗 <b><a href='https://1wfzws.life/casino/list?open=register&p=4lyi'>Click here to register</a></b>\n\n"
        "🆔 After registering, send your casino ID here.",
        disable_web_page_preview=True
    )

@dp.message(F.text.regexp(r"^\d{4,}$"))
async def receive_user_id(message: Message):
    user_id = str(message.from_user.id)
    paid_users = load_paid_users()

    if user_id not in paid_users:
        return await message.answer("❌ You need to make a payment first. Use /start to begin.")

    casino_id = message.text.strip()
    user_ids[user_id] = casino_id

    await message.answer(
        f"✅ ID received: <code>{casino_id}</code>\n\n"
        f"🎮 You can now start receiving coefficients.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Next", callback_data="continue")],
            [InlineKeyboardButton(text="🔴 Stop", callback_data="stop")]
        ])
    )

@dp.callback_query(F.data == "continue")
async def on_continue(callback: CallbackQuery):
    user_id = str(callback.from_user.id)

    if user_id not in user_coefficients:
        user_coefficients[user_id] = []

    used = user_coefficients[user_id]

    if len(used) >= MAX_COEFFICIENTS:
        paid_users = load_paid_users()
        paid_users.pop(user_id, None)
        save_paid_users(paid_users)

        await callback.message.answer(
            "✅ Your limit has ended. Please make another payment to continue.\nUse /start to begin again."
        )
        return await callback.answer()

    coefficient = round(random.uniform(1.00, 11.00), 2)
    used.append(coefficient)

    img = Image.new("RGB", (400, 200), color=(20, 20, 20))
    draw = ImageDraw.Draw(img)
    font_path = r"C:\Windows\Fonts\arial.ttf"
    font = ImageFont.truetype(font_path, 72)
    text = f"{coefficient}x"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((400 - text_width) / 2, (200 - text_height) / 2)
    draw.text(position, text, font=font, fill=(255, 255, 0))

    image_path = f"coefficient_{user_id}.png"
    img.save(image_path)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Next", callback_data="continue")],
        [InlineKeyboardButton(text="🔴 Stop", callback_data="stop")]
    ])

    await callback.message.answer_photo(
        types.FSInputFile(image_path),
        caption=f"🎲 Coefficient: <b>{coefficient}x</b>",
        reply_markup=keyboard
    )
    os.remove(image_path)
    await callback.answer()

@dp.callback_query(F.data == "stop")
async def on_stop(callback: CallbackQuery):
    await callback.message.answer("⛔ Game stopped. Use /start to play again.")
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
