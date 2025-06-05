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
BOT_TOKEN = "7383119117:AAFnL4h4B6eF0tzJRLRkWDUVkRf7rdrg1QM"
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
javob_kutayotganlar = {}
foydalanuvchi_holati = {}
MODULLAR = ["HTML", "CSS", "Bootstrap", "WIX", "JavaScript", "Scratch"]

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

def csvdan_oqish():
    try:
        if not os.path.exists(CSV_FILE):
            return []
        with open(CSV_FILE, 'r', encoding='utf-8') as fayl:
            reader = csv.reader(fayl)
            next(reader)
            return list(reader)
    except Exception as e:
        logger.error(f"CSVdan o'qishda xato: {e}")
        return []

async def forward_to_admin_group(content, modul, foydalanuvchi_id, username):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✉️ Javob berish",
        callback_data=f"javob_{foydalanuvchi_id}_{content.chat.id}"
    )
    builder.adjust(1)

    caption = f"❓ Savol ({modul}) @{username or 'foydalanuvchi'} (ID: {foydalanuvchi_id})"
    content_text = content.text if content.content_type == ContentType.TEXT else content.caption or ""

    if content.content_type == ContentType.TEXT:
        sent = await bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=f"{caption}:\n\n{content_text}",
            reply_markup=builder.as_markup()
        )
    elif content.content_type == ContentType.PHOTO:
        sent = await bot.send_photo(
            chat_id=ADMIN_GROUP_ID,
            photo=content.photo[-1].file_id,
            caption=f"{caption}:\n\n{content_text}",
            reply_markup=builder.as_markup()
        )
    elif content.content_type == ContentType.VIDEO:
        sent = await bot.send_video(
            chat_id=ADMIN_GROUP_ID,
            video=content.video.file_id,
            caption=f"{caption}:\n\n{content_text}",
            reply_markup=builder.as_markup()
        )
    elif content.content_type == ContentType.VOICE:
        sent = await bot.send_voice(
            chat_id=ADMIN_GROUP_ID,
            voice=content.voice.file_id,
            caption=caption,
            reply_markup=builder.as_markup()
        )
    elif content.content_type == ContentType.DOCUMENT:
        sent = await bot.send_document(
            chat_id=ADMIN_GROUP_ID,
            document=content.document.file_id,
            caption=caption,
            reply_markup=builder.as_markup()
        )
    else:
        return None

    # Store the question information
    kutilayotgan_savollar[sent.message_id] = {
        "foydalanuvchi_id": foydalanuvchi_id,
        "foydalanuvchi_chat_id": content.chat.id,
        "modul": modul,
        "content_type": content.content_type,
        "original_content": content_text
    }

    return sent

@router.message(Command("start"))
async def boshlash(message: types.Message):
    builder = ReplyKeyboardBuilder()
    for modul in MODULLAR:
        builder.add(types.KeyboardButton(text=modul))
    builder.adjust(2)

    await message.answer(
        "👋 Qo'llab-quvvatlash botiga xush kelibsiz!\n\n"
        "Iltimos, yordam kerak bo'lgan modulni tanlang:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@router.message(Command("hisobot"))
async def hisobot_paroli(message: types.Message):
    foydalanuvchi_id = message.from_user.id
    foydalanuvchi_holati[foydalanuvchi_id] = {'parol_kutilyapti': True}
    await message.answer("🔐 Iltimos, hisobotni ko'rish uchun parolni kiriting:")

@router.message(F.text == HISOBOT_PAROLI)
async def hisobot_yuborish(message: types.Message):
    foydalanuvchi_id = message.from_user.id

    if foydalanuvchi_id in foydalanuvchi_holati and foydalanuvchi_holati[foydalanuvchi_id].get('parol_kutilyapti'):
        ma_lumotlar = csvdan_oqish()
        if not ma_lumotlar:
            await message.answer("❌ Hisobotda ma'lumot mavjud emas.")
            return

        hisobot_matni = "📊 Savollar hisoboti:\n\n"
        for qator in ma_lumotlar:
            foydalanuvchi_id, modul, savol, content_type, sana_vaqt = qator
            hisobot_matni += (
                f"🆔 Foydalanuvchi ID: {foydalanuvchi_id}\n"
                f"📌 Modul: {modul}\n"
                f"📄 Kontent turi: {content_type}\n"
                f"🕒 Vaqt: {sana_vaqt}\n"
                f"❓ Savol: {savol}\n"
                f"{'-'*30}\n"
            )

        await message.answer(hisobot_matni)
        foydalanuvchi_holati.pop(foydalanuvchi_id, None)
    else:
        await message.answer("Iltimos, avval /hisobot buyrug'ini yuboring.")

@router.message(F.text.in_(MODULLAR))
async def modul_tanlash(message: types.Message):
    foydalanuvchi_id = message.from_user.id
    modul = message.text
    foydalanuvchi_holati[foydalanuvchi_id] = {'modul': modul}

    await message.answer(
        f"📝 Siz <b>{modul}</b> modulini tanladingiz. Iltimos, savolingizni yuboring:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@router.message(F.content_type.in_({
    ContentType.TEXT,
    ContentType.PHOTO,
    ContentType.VIDEO,
    ContentType.VOICE,
    ContentType.DOCUMENT
}))
async def foydalanuvchi_savoli(message: types.Message):
    if message.chat.type != 'private' or message.from_user.is_bot:
        return

    if message.from_user.id in javob_kutayotganlar:
        return

    foydalanuvchi_id = message.from_user.id
    foydalanuvchi_holati_ = foydalanuvchi_holati.get(foydalanuvchi_id)

    if not foydalanuvchi_holati_ or 'modul' not in foydalanuvchi_holati_:
        await message.answer("Iltimos, avval /start buyrug'i orqali modulni tanlang")
        return

    modul = foydalanuvchi_holati_['modul']
    username = message.from_user.username

    try:
        sent = await forward_to_admin_group(message, modul, foydalanuvchi_id, username)
        if not sent:
            await message.answer("❌ Faqat matn, rasm, video, ovozli xabar yoki fayllar qabul qilinadi")
            return

        content_text = message.text if message.content_type == ContentType.TEXT else message.caption or ""
        csvga_yozish(foydalanuvchi_id, modul, content_text, message.content_type)
        await message.answer("✅ Savolingiz support jamoasiga yuborildi!")
        foydalanuvchi_holati.pop(foydalanuvchi_id, None)

    except Exception as e:
        logger.error(f"Savol yuborishda xato: {e}")
        await message.answer("❌ Savolingizni yuborishda xato yuz berdi. Iltimos, qayta urinib ko'ring.")

@router.callback_query(F.data.startswith("javob_"))
async def javob_berish_tugmasi(callback_query: types.CallbackQuery):
    try:
        admin_id = callback_query.from_user.id
        parts = callback_query.data.split("_")
        foydalanuvchi_id = int(parts[1])
        foydalanuvchi_chat_id = int(parts[2])
        
        # Check if admin
        a_zo = await bot.get_chat_member(callback_query.message.chat.id, admin_id)
        if a_zo.status not in ['administrator', 'creator']:
            await callback_query.answer("Faqat adminlar javob berishi mumkin.")
            return

        # Get the original question info
        original_question = kutilayotgan_savollar.get(callback_query.message.message_id, {})
        
        # Store all necessary information
        javob_kutayotganlar[admin_id] = {
            "foydalanuvchi_id": foydalanuvchi_id,
            "foydalanuvchi_chat_id": foydalanuvchi_chat_id,
            "original_message_id": callback_query.message.message_id,
            "original_chat_id": callback_query.message.chat.id,
            "modul": original_question.get("modul", ""),
            "original_question": original_question.get("original_content", "")
        }

        admin = await bot.get_chat(admin_id)
        admin_ismi = admin.first_name
        if admin.last_name:
            admin_ismi += " " + admin.last_name

        # Update the button to show who is answering
        await callback_query.message.edit_reply_markup(
            reply_markup=InlineKeyboardBuilder()
            .button(text=f"✓ Javob berildi || {admin_ismi}", callback_data="javob_berildi")
            .adjust(1)
            .as_markup()
        )

        # Send the original question to admin for context
        await bot.send_message(
            admin_id,
            f"💬 Foydalanuvchining savoli ({original_question.get('modul', '')}):\n\n"
            f"{original_question.get('original_content', '')}\n\n"
            "Iltimos, javobingizni yuboring (matn, rasm, video, ovozli xabar yoki fayl):"
        )
        
        await callback_query.answer("Endi foydalanuvchiga javob yozishingiz mumkin")

    except Exception as e:
        logger.error(f"Javob tugmasida xato: {e}")
        await callback_query.answer("Xato yuz berdi.")

@router.message(F.content_type.in_({
    ContentType.TEXT,
    ContentType.PHOTO,
    ContentType.VIDEO,
    ContentType.VOICE,
    ContentType.DOCUMENT
}))
async def admin_javobi(message: types.Message):
    if message.chat.type != 'private' or message.from_user.is_bot:
        return

    admin_id = message.from_user.id
    context = javob_kutayotganlar.get(admin_id)
    if not context:
        return

    try:
        caption_prefix = f"📬 Supportdan javob ({context.get('modul', '')}):\n\n"
        
        # Include the original question in the reply
        original_question = f"\n\n💬 Sizning savolingiz:\n{context.get('original_question', '')}"

        # Send the reply to the student
        if message.content_type == ContentType.TEXT:
            await bot.send_message(
                chat_id=context["foydalanuvchi_chat_id"],
                text=f"{caption_prefix}{message.text}{original_question}"
            )
        elif message.content_type == ContentType.PHOTO:
            await bot.send_photo(
                chat_id=context["foydalanuvchi_chat_id"],
                photo=message.photo[-1].file_id,
                caption=f"{caption_prefix}{message.caption or ''}{original_question}"
            )
        elif message.content_type == ContentType.VIDEO:
            await bot.send_video(
                chat_id=context["foydalanuvchi_chat_id"],
                video=message.video.file_id,
                caption=f"{caption_prefix}{message.caption or ''}{original_question}"
            )
        elif message.content_type == ContentType.VOICE:
            await bot.send_voice(
                chat_id=context["foydalanuvchi_chat_id"],
                voice=message.voice.file_id,
                caption=f"{caption_prefix.strip()}{original_question}"
            )
        elif message.content_type == ContentType.DOCUMENT:
            await bot.send_document(
                chat_id=context["foydalanuvchi_chat_id"],
                document=message.document.file_id,
                caption=f"{caption_prefix.strip()}{original_question}"
            )

        # Update the original message in group
        try:
            await bot.edit_message_reply_markup(
                chat_id=context["original_chat_id"],
                message_id=context["original_message_id"],
                reply_markup=None
            )
        except Exception as e:
            logger.error(f"Original xabarni tahrirlashda xato: {e}")

        # Clean up
        await message.answer("✅ Javob foydalanuvchiga yuborildi!")
        javob_kutayotganlar.pop(admin_id, None)
        kutilayotgan_savollar.pop(context["original_message_id"], None)

    except Exception as e:
        logger.error(f"Javob yuborishda xato: {e}")
        await message.answer(f"❌ Javob yuborishda xato: {e}")

async def asosiy():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(asosiy())
