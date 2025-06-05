import logging
import os
import csv
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.enums import ParseMode, ContentType
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.filters import Command

# Bot configuration
BOT_TOKEN = "8017630610:AAHWozLydRjRwLQf7jPBgrvf-FSLYEzQ1B0"
ADMIN_GROUP_ID = -1002459383963
CSV_FILE = "savollar.csv"
HISOBOT_PAROLI = "menga_savol_ber"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

kutilayotgan_savollar = {}
foydalanuvchi_holati = {}
MODULLAR = ["HTML", "CSS", "Bootstrap", "WIX", "JavaScript", "Scratch"]

# To store which message admin is replying to
admin_reply_context = {}

def csvga_yozish(foydalanuvchi_id, modul, savol, content_type="text"):
    sana_vaqt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        if not os.path.exists(CSV_FILE):
            with open(CSV_FILE, 'w', newline='', encoding='utf-8') as fayl:
                yozuvchi = csv.writer(fayl)
                yozuvchi.writerow(["foydalanuvchi_id", "modul", "savol", "content_type", "sana_vaqt"])

        with open(CSV_FILE, 'a', newline='', encoding='utf-8') as fayl:
            yozuvchi = csv.writer(fayl)
            yozuvchi.writerow([foydalanuvchi_id, modul, savol, content_type, sana_vaqt])
    except Exception as e:
        logger.error(f"CSVga yozishda xato: {e}")

@router.callback_query(F.data.startswith("javob_"))
async def javob_berish_tugmasi(callback_query: types.CallbackQuery):
    try:
        admin_id = callback_query.from_user.id
        parts = callback_query.data.split("_")

        if len(parts) < 3:
            await callback_query.answer("Noto'g'ri formatdagi javob so'rovi")
            return

        foydalanuvchi_id = int(parts[1])
        foydalanuvchi_chat_id = int(parts[2])

        admin = await bot.get_chat(admin_id)
        admin_ismi = admin.full_name

        # Save admin context
        admin_reply_context[admin_id] = {
            "user_id": foydalanuvchi_id,
            "chat_id": foydalanuvchi_chat_id
        }

        await callback_query.message.edit_reply_markup(
            reply_markup=InlineKeyboardBuilder()
            .button(text=f"✓ Javob yozilmoqda... {admin_ismi}", callback_data="javob_berildi")
            .adjust(1)
            .as_markup()
        )

        await callback_query.answer("Endi guruhda javob yozishingiz mumkin.")
    except Exception as e:
        logger.error(f"Javob tugmasida xato: {e}")
        await callback_query.answer("Xato yuz berdi")

@router.message(F.chat.id == ADMIN_GROUP_ID)
async def admin_group_response_handler(message: types.Message):
    admin_id = message.from_user.id
    if admin_id not in admin_reply_context:
        return  # No expected context to send reply

    context = admin_reply_context.pop(admin_id)
    user_chat_id = context["chat_id"]

    try:
        if message.content_type == ContentType.TEXT:
            await bot.send_message(
                chat_id=user_chat_id,
                text=f"""📬 Admin javobi:

{message.text}"""
            )
        elif message.content_type == ContentType.PHOTO:
            await bot.send_photo(
                chat_id=user_chat_id,
                photo=message.photo[-1].file_id,
                caption=message.caption or "📬 Admin javobi"
            )
        elif message.content_type == ContentType.VIDEO:
            await bot.send_video(
                chat_id=user_chat_id,
                video=message.video.file_id,
                caption=message.caption or "📬 Admin javobi"
            )
        elif message.content_type == ContentType.DOCUMENT:
            await bot.send_document(
                chat_id=user_chat_id,
                document=message.document.file_id,
                caption=message.caption or "📬 Admin javobi"
            )
        elif message.content_type == ContentType.VOICE:
            await bot.send_voice(
                chat_id=user_chat_id,
                voice=message.voice.file_id,
                caption="📬 Admin javobi"
            )

        await message.reply("✅ Javob yuborildi")
    except Exception as e:
        logger.error(f"Foydalanuvchiga javob yuborishda xato: {e}")
        await message.reply("❌ Xabarni yuborishda xato yuz berdi")

async def asosiy():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(asosiy())
