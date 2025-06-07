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
BOT_TOKEN = "8146573794:AAGhXSp3JCwYn2cqd9IOykfmLz0KR4WMd74"
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

# Media types to handle
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
    """Save questions to CSV file with error handling"""
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
    """Forward media with proper context to admin group"""
    try:
        content_type = media_message.content_type
        media_method = getattr(bot, f"send_{SUPPORTED_MEDIA[content_type]}")
        
        # Send context message first
        text_message = await bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=context_text
        )
        
        # Forward media as reply
        media_file = getattr(media_message, SUPPORTED_MEDIA[content_type])[-1]
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
    """Enhanced start command with persistent buttons"""
    builder = ReplyKeyboardBuilder()
    for module in MODULES:
        builder.add(types.KeyboardButton(text=module))
    builder.adjust(2)
    
    await message.answer(
        "👋 Welcome to the Support Bot!\n\n"
        "Please select the module you need help with:",
        reply_markup=builder.as_markup(
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )

@router.message(F.text.in_(MODULES))
async def handle_module_selection(message: types.Message):
    """Module selection with state management"""
    user_id = message.from_user.id
    selected_module = message.text
    
    user_states[user_id] = {
        'module': selected_module,
        'awaiting_question': True
    }
    
    await message.answer(
        f"📝 You've selected <b>{selected_module}</b>.\n"
        "Please send your question or file:",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode=ParseMode.HTML
    )

@router.message(F.content_type.in_({ContentType.TEXT} | set(SUPPORTED_MEDIA.keys())))
async def handle_user_input(message: types.Message):
    """Unified handler for all user questions"""
    user_id = message.from_user.id
    user_state = user_states.get(user_id, {})
    
    if not user_state.get('awaiting_question'):
        await message.answer("Please select a module first using /start")
        return
    
    module = user_state['module']
    username = message.from_user.username or f"user_{user_id}"
    
    try:
        # Prepare response button
        builder = InlineKeyboardBuilder()
        builder.button(
            text="✉️ Respond",
            callback_data=f"respond_{user_id}_{message.chat.id}"
        )
        
        if message.content_type == ContentType.TEXT:
            # Handle text questions
            question_text = message.text
            admin_message = await bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=f"❓ {module} question from @{username} (ID: {user_id}):\n\n{question_text}",
                reply_markup=builder.as_markup()
            )
        else:
            # Handle media questions
            caption = message.caption or f"[{message.content_type.upper()}]"
            admin_message = await forward_to_admin(
                message,
                f"❓ {module} question from @{username} (ID: {user_id}):\n\n{caption}"
            )
            await admin_message.edit_reply_markup(reply_markup=builder.as_markup())
        
        # Store question reference
        pending_questions[admin_message.message_id] = {
            'user_id': user_id,
            'chat_id': message.chat.id,
            'module': module
        }
        
        # Log to CSV
        question_content = message.text if message.content_type == ContentType.TEXT else caption
        await write_to_csv(user_id, module, question_content, message.content_type)
        
        await message.answer(
            "✅ Your question has been forwarded to support team!",
            reply_markup=types.ReplyKeyboardRemove()
        )
        
        # Clear user state
        user_states.pop(user_id, None)
        
    except Exception as e:
        logger.error(f"Question handling error: {e}")
        await message.answer("❌ Failed to process your question. Please try again.")

@router.callback_query(F.data.startswith("respond_"))
async def handle_response_request(callback: types.CallbackQuery):
    """Admin response initiation"""
    try:
        admin_id = callback.from_user.id
        user_id, chat_id = map(int, callback.data.split("_")[1:3])
        
        # Verify admin status
        chat_member = await bot.get_chat_member(callback.message.chat.id, admin_id)
        if chat_member.status not in ['administrator', 'creator']:
            await callback.answer("Only admins can respond")
            return
        
        # Update message to show admin is responding
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
            'group_msg_id': callback.message.message_id
        }
        
        await callback.answer()
        await bot.send_message(
            admin_id,
            "💬 Please send your response (text/media/voice):"
        )
        
    except Exception as e:
        logger.error(f"Response init error: {e}")
        await callback.answer("Failed to initiate response")

@router.message(F.chat.type == 'private')
async def handle_admin_response(message: types.Message):
    """Process admin responses"""
    if message.from_user.id not in awaiting_responses:
        return
        
    context = awaiting_responses[message.from_user.id]
    
    try:
        # Forward response to user
        if message.content_type == ContentType.TEXT:
            await bot.send_message(
                chat_id=context['chat_id'],
                text=f"📨 Support response:\n\n{message.text}"
            )
        elif message.content_type in SUPPORTED_MEDIA:
            media_method = getattr(bot, f"send_{SUPPORTED_MEDIA[message.content_type]}")
            media_file = getattr(message, SUPPORTED_MEDIA[message.content_type])[-1]
            
            await media_method(
                chat_id=context['chat_id'],
                **{SUPPORTED_MEDIA[message.content_type]: media_file.file_id},
                caption=f"📨 Support response:\n\n{message.caption}" if message.caption else None
            )
        
        # Clean up
        await bot.edit_message_reply_markup(
            chat_id=ADMIN_GROUP_ID,
            message_id=context['group_msg_id'],
            reply_markup=None
        )
        
        await message.answer("✅ Response delivered!")
        pending_questions.pop(context['group_msg_id'], None)
        awaiting_responses.pop(message.from_user.id, None)
        
    except Exception as e:
        logger.error(f"Response delivery error: {e}")
        await message.answer(f"❌ Delivery failed: {str(e)}")

async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
