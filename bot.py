import logging
import os
import csv
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.filters import Command

# Bot konfiguratsiyasi
BOT_TOKEN = "7383119117:AAFES5Jx0kmYcMClOAsb099VI8ZzeWi4PjU"
ADMIN_GROUP_ID = -1002592730994
CSV_FILE = "savollar.csv"
HISOBOT_PAROLI = "menga_savol_ber"  # Hisobot uchun parol

# Log yozish
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Botni ishga tushirish
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Xotira saqlash
kutilayotgan_savollar = {}  # {gruppa_xabari_id: {foydalanuvchi_id, chat_id, modul}}
javob_kutayotganlar = {}    # {admin_id: {foydalanuvchi_id, chat_id, gruppa_xabari_id}}
foydalanuvchi_holati = {}   # {foydalanuvchi_id: {'modul': tanlangan_modul}}

# Modullar
MODULLAR = ["HTML", "CSS", "Bootstrap", "WIX", "JavaScript", "Scratch"]

def csvga_yozish(foydalanuvchi_id, modul, savol):
    """Savollarni CSV fayliga yozish"""
    sana_vaqt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        # Agar fayl yo'q bo'lsa, yaratib olish
        if not os.path.exists(CSV_FILE):
            with open(CSV_FILE, 'w', newline='', encoding='utf-8') as fayl:
                yozuvchi = csv.writer(fayl)
                yozuvchi.writerow(["foydalanuvchi_id", "modul", "savol", "sana_vaqt"])
        
        # Ma'lumotlarni qo'shish
        with open(CSV_FILE, 'a', newline='', encoding='utf-8') as fayl:
            yozuvchi = csv.writer(fayl)
            yozuvchi.writerow([foydalanuvchi_id, modul, savol, sana_vaqt])
    except Exception as e:
        logger.error(f"CSVga yozishda xato: {e}")

def csvdan_oqish():
    """CSV faylidan ma'lumotlarni o'qish"""
    try:
        with open(CSV_FILE, 'r', newline='', encoding='utf-8') as fayl:
            oquvchi = csv.reader(fayl)
            next(oquvchi)  # Sarlavhani o'tkazib yuborish
            return list(oquvchi)
    except FileNotFoundError:
        return []

@router.message(Command("start"))
async def boshlash(message: types.Message):
    """Boshlash xabari va modul tanlash tugmalari"""
    builder = ReplyKeyboardBuilder()
    for modul in MODULLAR:
        builder.add(types.KeyboardButton(text=modul))
    builder.adjust(2)  # Har qatorda 2 ta tugma
    
    await message.answer(
        "👋 Qo'llab-quvvatlash botiga xush kelibsiz!\n\n"
        "Iltimos, yordam kerak bo'lgan modulni tanlang:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@router.message(Command("hisobot"))
async def hisobot_paroli(message: types.Message):
    """Hisobot uchun parol so'rash"""
    foydalanuvchi_id = message.from_user.id
    foydalanuvchi_holati[foydalanuvchi_id] = {'parol_kutilyapti': True}
    await message.answer("🔒 Iltimos, hisobotni ko'rish uchun parolni kiriting:")

@router.message(F.text == HISOBOT_PAROLI)
async def hisobot_yuborish(message: types.Message):
    """To'g'ri parol kiritilganda hisobotni yuborish"""
    foydalanuvchi_id = message.from_user.id
    
    if foydalanuvchi_id in foydalanuvchi_holati and foydalanuvchi_holati[foydalanuvchi_id].get('parol_kutilyapti'):
        ma_lumotlar = csvdan_oqish()
        if not ma_lumotlar:
            await message.answer("❌ Hisobotda ma'lumot mavjud emas.")
            return
            
        hisobot_matni = "📊 Savollar hisoboti:\n\n"
        for qator in ma_lumotlar:
            foydalanuvchi_id, modul, savol, sana_vaqt = qator
            hisobot_matni += (
                f"🆔 Foydalanuvchi ID: {foydalanuvchi_id}\n"
                f"📌 Modul: {modul}\n"
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
    """Modul tanlashni qayta ishlash"""
    foydalanuvchi_id = message.from_user.id
    modul = message.text
    
    foydalanuvchi_holati[foydalanuvchi_id] = {'modul': modul}
    
    await message.answer(
        f"📝 Siz <b>{modul}</b> modulini tanladingiz. Iltimos, savolingizni yozing:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@router.callback_query(F.data.startswith("javob_"))
async def javob_berish_tugmasi(callback_query: types.CallbackQuery):
    try:
        admin_id = callback_query.from_user.id
        foydalanuvchi_id, foydalanuvchi_chat_id = map(int, callback_query.data.split("_")[1:])

        # Adminlikni tekshirish
        a_zo = await bot.get_chat_member(callback_query.message.chat.id, admin_id)
        if a_zo.status not in ['administrator', 'creator']:
            await callback_query.answer("Faqat adminlar javob berishi mumkin.")
            return

        javob_kutayotganlar[admin_id] = {
            "foydalanuvchi_id": foydalanuvchi_id,
            "foydalanuvchi_chat_id": foydalanuvchi_chat_id,
            "gruppa_xabari_id": callback_query.message.message_id
        }

        # Original xabarni tahrirlash
        await callback_query.message.edit_reply_markup(
            reply_markup=InlineKeyboardBuilder()
            .button(text="✓ Javob berildi", callback_data="javob_berildi")
            .adjust(1)
            .as_markup()
        )

        await bot.send_message(admin_id, "💬 Iltimos, foydalanuvchiga javobingizni shu xabar orqali yuboring:")
        await callback_query.answer("Endi foydalanuvchiga javob yozishingiz mumkin")

    except Exception as e:
        logger.error(f"Javob tugmasida xato: {e}")
        await callback_query.answer("Xato yuz berdi.")

@router.message()
async def barcha_xabarlar(message: types.Message):
    if message.from_user.is_bot or not message.text:
        return

    admin_id = message.from_user.id
    kontekst = javob_kutayotganlar.get(admin_id)

    # Admin javobi
    if kontekst and message.chat.type == 'private':
        try:
            await bot.send_message(
                chat_id=kontekst["foydalanuvchi_chat_id"],
                text=f"📬 Supportdan javob:\n\n{message.text}"
            )
            
            # Original savolni tahrirlash
            try:
                await bot.edit_message_reply_markup(
                    chat_id=ADMIN_GROUP_ID,
                    message_id=kontekst["gruppa_xabari_id"],
                    reply_markup=None
                )
            except Exception as e:
                logger.error(f"Original xabarni tahrirlashda xato: {e}")

            await message.answer("✅ Javob foydalanuvchiga yuborildi!")
            
            # Tozalash
            javob_kutayotganlar.pop(admin_id, None)
            kutilayotgan_savollar.pop(kontekst["gruppa_xabari_id"], None)
            
        except Exception as e:
            logger.error(f"Javob yuborishda xato: {e}")
            await message.answer(f"❌ Javob yuborishda xato: {e}")
        return

    # Foydalanuvchi savoli
    if message.chat.type == 'private' and not message.text.startswith("/"):
        foydalanuvchi_id = message.from_user.id
        foydalanuvchi_holati_ = foydalanuvchi_holati.get(foydalanuvchi_id)
        
        if not foydalanuvchi_holati_ or 'modul' not in foydalanuvchi_holati_:
            await message.answer("Iltimos, avval /start buyrug'i orqali modulni tanlang")
            return
            
        modul = foydalanuvchi_holati_['modul']
        savol_matni = message.text

        try:
            builder = InlineKeyboardBuilder()
            builder.button(
                text="✉️ Javob berish",
                callback_data=f"javob_{foydalanuvchi_id}_{message.chat.id}"
            )
            builder.adjust(1)

            yuborilgan = await bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=f"❓ Savol ({modul}) @{message.from_user.username or 'foydalanuvchi'} (ID: {foydalanuvchi_id}):\n\n{savol_matni}",
                reply_markup=builder.as_markup()
            )

            kutilayotgan_savollar[yuborilgan.message_id] = {
                "foydalanuvchi_id": foydalanuvchi_id,
                "foydalanuvchi_chat_id": message.chat.id,
                "modul": modul
            }
            
            csvga_yozish(foydalanuvchi_id, modul, savol_matni)
            
            await message.answer("✅ Savolingiz support jamoasiga yuborildi!")
            
            foydalanuvchi_holati.pop(foydalanuvchi_id, None)

        except Exception as e:
            logger.error(f"Savol yuborishda xato: {e}")
            await message.answer("❌ Savolingizni yuborishda xato yuz berdi. Iltimos, qayta urinib ko'ring.")

# Xatolikni qayta ishlash
@dp.errors()
async def xatolikni_qayta_ishlash(event, exception):
    logger.error(f"⚠️ Xato yuz berdi: {exception}")

# Asosiy funksiya
async def asosiy():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(asosiy())
