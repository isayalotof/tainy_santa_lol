from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

from bot.database import Database
from bot.keyboards.inline import get_main_menu_keyboard, get_room_menu_keyboard

router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: Database):
    """Handle /start command (with or without deep link)"""
    await state.clear()

    user = message.from_user
    # Database is handled in main.py middleware

    # Check if there's a deep link parameter (invite code)
    args = message.text.split()
    if len(args) > 1:
        invite_code = args[1]

        # Try to join room with invite code
        room = db.get_room_by_invite_code(invite_code)
        if room:
            # Check if already a member
            if db.is_user_in_room(room['room_id'], user.id):
                await message.answer(
                    f"ℹ️ Ты уже состоишь в комнате '{room['room_name']}'!",
                    reply_markup=get_room_menu_keyboard(room['room_id'], room['admin_id'] == user.id, room['is_drawn'])
                )
                return

            # Add user to room
            try:
                db.add_member_to_room(room['room_id'], user.id)

                await message.answer(
                    f"✅ Ты присоединился к комнате '{room['room_name']}'!",
                    reply_markup=get_room_menu_keyboard(room['room_id'], False, room['is_drawn'])
                )
                return

            except Exception as e:
                logger.error(f"Error joining room via deep link: {e}")
                await message.answer(
                    "❌ Произошла ошибка при присоединении к комнате. Попробуй позже.",
                    reply_markup=get_main_menu_keyboard()
                )
                return

    # Regular start message
    welcome_text = (
        f"🎅 Привет, {user.first_name}!\n\n"
        "Добро пожаловать в бота для игры в Тайного Санту! 🎄\n\n"
        "Здесь ты можешь:\n"
        "• Создать комнату для игры\n"
        "• Пригласить друзей по ссылке\n"
        "• Провести жеребьёвку\n"
        "• Узнать, кому ты даришь подарок\n\n"
        "Выбери действие:"
    )

    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard())


@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery, state: FSMContext):
    """Show main menu"""
    await state.clear()

    welcome_text = (
        "🎅 Главное меню\n\n"
        "Выбери действие:"
    )

    # Check if message has photo (can't edit text of photo messages)
    if callback.message.photo:
        # Delete old message and send new one
        await callback.message.delete()
        await callback.message.answer(welcome_text, reply_markup=get_main_menu_keyboard())
    else:
        # Edit existing text message
        await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard())

    await callback.answer()
