import logging
import asyncio
import csv
from datetime import datetime
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.filters import Command

# Bot configuration
BOT_TOKEN = "8146573794:AAGcGkQbjemK6JSSiEasV3dsljz0MO38kKg"
ADMIN_GROUP_ID = -1002592730994
CSV_FILE = "questions.csv"
REPORT_PASSWORD = "ask_me_question"  # Password for accessing reports

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# In-memory storage
pending_questions = {}  # {group_msg_id: {user_id, user_chat_id, module}}
waiting_replies = {}    # {admin_id: {user_id, user_chat_id, group_msg_id}}
user_states = {}        # {user_id: {'module': selected_module, 'waiting_password': bool}}

# Modules for the buttons
MODULES = ["HTML", "CSS", "Bootstrap", "WIX", "JavaScript", "Scratch"]

def save_to_csv(user_id, module, question):
    """Save question data to CSV file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow([user_id, module, question, timestamp])

def read_csv_data():
    """Read all data from CSV file"""
    try:
        with open(CSV_FILE, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            # Skip header
            next(reader)
            return list(reader)
    except FileNotFoundError:
        return []

@router.message(Command("start"))
async def send_welcome(message: types.Message):
    """Send welcome message with module selection buttons"""
    builder = ReplyKeyboardBuilder()
    for module in MODULES:
        builder.add(types.KeyboardButton(text=module))
    builder.adjust(2)  # 2 buttons per row
    
    await message.answer(
        "👋 Welcome to the support bot!\n\n"
        "Please select the module you need help with:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@router.message(Command("report"))
async def request_report_password(message: types.Message):
    """Ask for password to access reports"""
    user_id = message.from_user.id
    user_states[user_id] = {'waiting_password': True}
    await message.answer("🔒 Bazaga kirish uchun parolni kiriting:")

@router.message(F.text == REPORT_PASSWORD)
async def send_report(message: types.Message):
    """Send the report data if password is correct"""
    user_id = message.from_user.id
    
    # Check if user was waiting for password prompt
    if user_id in user_states and user_states[user_id].get('waiting_password'):
        data = read_csv_data()
        if not data:
            await message.answer("Malumot topilmadi.")
            return
            
        # Format the report
        report_text = "📊 Question Report:\n\n"
        for row in data:
            user_id, module, question, timestamp = row
            report_text += (
                f"🆔 User ID: {user_id}\n"
                f"📌 Module: {module}\n"
                f"🕒 Time: {timestamp}\n"
                f"❓ Question: {question}\n"
                f"{'-'*30}\n"
            )
        
        # Split long messages to avoid Telegram limits
        max_length = 4000
        for i in range(0, len(report_text), max_length):
            await message.answer(report_text[i:i+max_length])
        
        # Clear the waiting_password state
        user_states.pop(user_id, None)
    else:
        await message.answer("Please use /report command first to request access.")

@router.message(F.text.in_(MODULES))
async def handle_module_selection(message: types.Message):
    """Handle module selection and ask for question"""
    user_id = message.from_user.id
    module = message.text
    
    # Store user's selected module
    user_states[user_id] = {'module': module}
    
    await message.answer(
        f"📝 You've selected <b>{module}</b>. Please type your question now:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@router.callback_query(F.data.startswith("answer_"))
async def handle_answer_button(callback_query: types.CallbackQuery):
    try:
        admin_id = callback_query.from_user.id
        user_id, user_chat_id = map(int, callback_query.data.split("_")[1:])

        member = await bot.get_chat_member(callback_query.message.chat.id, admin_id)
        if member.status not in ['administrator', 'creator']:
            await callback_query.answer("Only admins can answer.")
            return

        waiting_replies[admin_id] = {
            "user_id": user_id,
            "user_chat_id": user_chat_id,
            "group_msg_id": callback_query.message.message_id
        }

        # Edit the original message to replace the button with a tick
        await callback_query.message.edit_reply_markup(
            reply_markup=InlineKeyboardBuilder()
            .button(text="✓ Answered", callback_data="answered")
            .adjust(1)
            .as_markup()
        )

        await bot.send_message(admin_id, "💬 Please reply to this message with your answer to the user:")
        await callback_query.answer("You can now reply to the user")

    except Exception as e:
        logger.error("❌ Error handling answer button: %s", e)
        await callback_query.answer("Error occurred.")

@router.callback_query(F.data == "answered")
async def handle_already_answered(callback_query: types.CallbackQuery):
    await callback_query.answer("This question has already been answered.", show_alert=True)

@router.message()
async def handle_all_messages(message: types.Message):
    if message.from_user.is_bot or not message.text:
        return

    admin_id = message.from_user.id
    context = waiting_replies.get(admin_id)

    # Admin reply
    if context and message.chat.type == 'private':
        try:
            await bot.send_message(
                chat_id=context["user_chat_id"],
                text=f"📬 Answer from support:\n\n{message.text}"
            )
            
            # Edit the original question message to mark it as resolved
            try:
                await bot.edit_message_reply_markup(
                    chat_id=ADMIN_GROUP_ID,
                    message_id=context["group_msg_id"],
                    reply_markup=None  # Remove buttons completely
                )
            except Exception as e:
                logger.error(f"Couldn't edit original message: {e}")

            await message.answer("✅ Answer was sent to the user.")
            
            # Clean up
            waiting_replies.pop(admin_id, None)
            pending_questions.pop(context["group_msg_id"], None)
            
        except Exception as e:
            logger.error("❌ Error sending answer: %s", e)
            await message.answer(f"❌ Failed to send answer: {e}")
        return

    # User question from private chat (non-command)
    if message.chat.type == 'private' and not message.text.startswith("/"):
        user_id = message.from_user.id
        user_state = user_states.get(user_id)
        
        if not user_state or 'module' not in user_state:
            await message.answer("Please select a module first using /start")
            return
            
        module = user_state['module']
        question_text = message.text

        try:
            builder = InlineKeyboardBuilder()
            builder.button(
                text="✉️ Answer",
                callback_data=f"answer_{user_id}_{message.chat.id}"
            )
            builder.adjust(1)

            sent = await bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=f"❓ Question about <b>{module}</b> from @{message.from_user.username or 'user'} (ID: {user_id}):\n\n{question_text}",
                reply_markup=builder.as_markup()
            )

            pending_questions[sent.message_id] = {
                "user_id": user_id,
                "user_chat_id": message.chat.id,
                "module": module
            }
            
            # Save to CSV
            save_to_csv(user_id, module, question_text)
            
            await message.answer("✅ Your question was sent to the support team!")
            
            # Clear user's state after question is sent
            user_states.pop(user_id, None)

        except Exception as e:
            logger.error("❌ Error forwarding question: %s", e)
            await message.answer("❌ Failed to send your question. Try again.")

# Add error handler
@dp.errors()
async def handle_errors(event, exception):
    logger.error(f"⚠️ Error occurred: {exception}")

# Initialize CSV file with headers if it doesn't exist
def init_csv():
    try:
        with open(CSV_FILE, 'x', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["user_id", "module", "question", "timestamp"])
    except FileExistsError:
        pass

# Main
async def main():
    init_csv()  # Initialize CSV file
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
