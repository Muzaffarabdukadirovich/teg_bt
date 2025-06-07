import logging
import os
import csv
import asyncio
import aiofiles
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
CSV_FILE = "questions.csv"
REPORT_PASSWORD = "menga_savol_ber"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Bot initialization
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Memory storage
pending_questions = {}  # {group_message_id: {user_id, chat_id, module}}
awaiting_responses = {}  # {admin_id: {user_id, chat_id, group_message_id}}
user_states = {}        # {user_id: {'module': selected_module}}

# Modules
MODULES = ["HTML", "CSS", "Bootstrap", "WIX", "JavaScript", "Scratch"]

# Supported media types
SUPPORTED_MEDIA = {
    ContentType.PHOTO: "photo",
    ContentType.VIDEO: "video",
    ContentType.DOCUMENT: "document",
    ContentType.AUDIO: "audio",
    ContentType.VOICE: "voice",
    ContentType.ANIMATION: "animation",
    ContentType.STICKER: "sticker"
}

async def write_to_csv(user_id: int, module: str, question: str, content_type: str = "text"):
    """Save questions to CSV file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        file_exists = os.path.exists(CSV_FILE)
        async with aiofiles.open(CSV_FILE, mode='a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                await writer.writerow(["user_id", "module", "question", "content_type", "timestamp"])
            await writer.writerow([user_id, module, question, content_type, timestamp])
    except Exception as e:
        logger.error(f"CSV write error: {e}")
        raise

async def forward_to_admin(media_message: types.Message, context_text: str):
    """Forward media with context to admin group"""
    try:
        content_type = media_message.content_type
        media_method = getattr(bot, f"send_{SUPPORTED_MEDIA[content_type]}")
        media_file = getattr(media_message, SUPPORTED_MEDIA[content_type])[-1]
        
        # Send context message
        text_message = await bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=context_text
        )
        
        # Forward media
        await media_method(
            chat_id=ADMIN_GROUP_ID,
            **{SUPPORTED_MEDIA[content_type]: media_file.file_id},
            reply_to_message_id=text_message.message_id
        )
        
        return text_message
    except Exception as e:
        logger.error(f"Media forwarding error: {e}")
        raise

@router.message(Command("start"))
async def start_command(message: types.Message):
    """Start command with module selection"""
    builder = ReplyKeyboardBuilder()
    for module in MODULES:
        builder.add(types.KeyboardButton(text=module))
    builder.adjust(2)
    
    await message.answer(
        "👋Modulni tanlang:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@router.message(F.text.in_(MODULES))
async def handle_module_selection(message: types.Message):
    """Store selected module"""
    user_id = message.from_user.id
    user_states[user_id] = {
        'module': message.text,
        'awaiting_question': True
    }
    await message.answer(
        f"📝 Siz tanladingiz <b>{message.text}</b>. Savolingizni yuboring (matn shaklida):",
        reply_markup=types.ReplyKeyboardRemove()
    )

@router.message(F.chat.type == "private", ~F.from_user.id.in_(awaiting_responses.keys()))
async def handle_user_question(message: types.Message):
    """Process user questions with media support"""
    user_id = message.from_user.id
    user_state = user_states.get(user_id, {})
    
    if not user_state.get('awaiting_question'):
        await message.answer("Agarda savol bermoqchi bo'lsangiz,  /start tugmasini bosing.")
        return
    
    module = user_state['module']
    username = message.from_user.username or f"user_{user_id}"
    
    try:
        builder = InlineKeyboardBuilder()
        builder.button(
            text="✉️ Respond",
            callback_data=f"respond_{user_id}_{message.chat.id}"
        )
        
        if message.content_type == ContentType.TEXT:
            # Text question
            admin_message = await bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=f"❓ {module} question from @{username} (ID: {user_id}):\n\n{message.text}",
                reply_markup=builder.as_markup()
            )
            question_text = message.text
        else:
            # Media question
            caption = message.caption or f"[{message.content_type.upper()}]"
            admin_message = await forward_to_admin(
                message,
                f"❓ {module} question from @{username} (ID: {user_id}):\n\n{caption}"
            )
            await admin_message.edit_reply_markup(reply_markup=builder.as_markup())
            question_text = caption
        
        # Store question reference
        pending_questions[admin_message.message_id] = {
            'user_id': user_id,
            'chat_id': message.chat.id,
            'module': module
        }
        
        # Log to CSV
        await write_to_csv(user_id, module, question_text, message.content_type)
        
        await message.answer("✅Sizning savolingiz yuborildi!")
        user_states.pop(user_id, None)
        
    except Exception as e:
        logger.error(f"Question handling error: {e}")
        await message.answer("❌ Savolingizni yuborishda xatolik bor, matn shaklida yuboring.")

@router.callback_query(F.data.startswith("respond_"))
async def handle_response_request(callback: types.CallbackQuery):
    """Prepare admin to respond"""
    try:
        admin_id = callback.from_user.id
        user_id, chat_id = map(int, callback.data.split("_")[1:3])
        group_msg_id = callback.message.message_id
        
        # Verify admin
        chat_member = await bot.get_chat_member(ADMIN_GROUP_ID, admin_id)
        if chat_member.status not in ['administrator', 'creator']:
            await callback.answer("Only admins can respond")
            return
        
        # Update message to show responding admin
        admin_name = callback.from_user.first_name
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardBuilder()
            .button(text=f"🔄 Responding: {admin_name}", callback_data="handled")
            .as_markup()
        )
        
        # Store response context
        awaiting_responses[admin_id] = {
            'user_id': user_id,
            'chat_id': chat_id,
            'group_msg_id': group_msg_id
        }
        
        await callback.answer()
        await bot.send_message(
            admin_id,
            "💬 Ushbu foydalanuvchiga javobingizni yuboring:"
        )
        
    except Exception as e:
        logger.error(f"Response init error: {e}")
        await callback.answer("Failed to initiate response")

@router.message(F.from_user.id.in_(awaiting_responses.keys()))
async def handle_admin_response(message: types.Message):
    """Process admin responses with full media support"""
    admin_id = message.from_user.id
    context = awaiting_responses.get(admin_id)
    if not context:
        return

    try:
        response_header = "📨 Support response:\n\n"
        
        if message.content_type == ContentType.TEXT:
            await bot.send_message(
                chat_id=context['chat_id'],
                text=response_header + message.text
            )
        elif message.content_type in SUPPORTED_MEDIA:
            media_type = SUPPORTED_MEDIA[message.content_type]
            media_file = getattr(message, media_type)[-1]
            caption = response_header + (message.caption or "")
            
            await getattr(bot, f"send_{media_type}")(
                chat_id=context['chat_id'],
                **{media_type: media_file.file_id},
                caption=caption if caption.strip() else None
            )
        else:
            await message.answer("❌ Noto'g'ri tipdagi fayl yuborilmoqda ")
            return

        # Clean up
        try:
            await bot.edit_message_reply_markup(
                chat_id=ADMIN_GROUP_ID,
                message_id=context['group_msg_id'],
                reply_markup=None
            )
            pending_questions.pop(context['group_msg_id'], None)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

        await message.answer("✅ Response delivered!")
        awaiting_responses.pop(admin_id, None)

    except Exception as e:
        logger.error(f"Response delivery failed: {str(e)}")
        await message.answer(f"❌ Delivery failed: {str(e)}")

async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
