from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import secrets
import logging

from bot.database import Database
from bot.keyboards.inline import (
    get_main_menu_keyboard,
    get_room_menu_keyboard,
    get_rooms_list_keyboard,
    get_back_to_room_keyboard,
    get_back_to_menu_keyboard
)

router = Router()
logger = logging.getLogger(__name__)


class RoomCreation(StatesGroup):
    waiting_for_name = State()


class RoomJoin(StatesGroup):
    waiting_for_code = State()


def generate_invite_code() -> str:
    """Generate unique invite code"""
    return secrets.token_urlsafe(8)


@router.callback_query(F.data == "create_room")
async def start_room_creation(callback: CallbackQuery, state: FSMContext):
    """Start room creation process"""
    await callback.message.edit_text(
        "🎄 Создание новой комнаты\n\n"
        "Введи название комнаты:",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state(RoomCreation.waiting_for_name)
    await callback.answer()


@router.message(RoomCreation.waiting_for_name)
async def process_room_name(message: Message, state: FSMContext, db: Database, bot: Bot):
    """Process room name and create room"""
    room_name = message.text.strip()

    if len(room_name) < 3:
        await message.answer("❌ Название должно быть не короче 3 символов. Попробуй ещё раз:")
        return

    if len(room_name) > 100:
        await message.answer("❌ Название слишком длинное (макс. 100 символов). Попробуй ещё раз:")
        return

    # Generate unique invite code
    invite_code = generate_invite_code()

    # Create room
    try:
        room_id = db.create_room(room_name, message.from_user.id, invite_code)
        db.add_member_to_room(room_id, message.from_user.id)

        # Get bot username for invite link
        bot_user = await bot.get_me()
        invite_link = f"https://t.me/{bot_user.username}?start={invite_code}"

        await message.answer(
            f"✅ Комната создана!\n\n"
            f"📝 Название: {room_name}\n"
            f"🔗 Пригласительная ссылка:\n"
            f"<code>{invite_link}</code>\n\n"
            f"Отправь эту ссылку друзьям, чтобы они присоединились!",
            parse_mode="HTML",
            reply_markup=get_room_menu_keyboard(room_id, is_admin=True, is_drawn=False)
        )

        await state.clear()

    except Exception as e:
        logger.error(f"Error creating room: {e}")
        await message.answer(
            "❌ Произошла ошибка при создании комнаты. Попробуй позже.",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


@router.callback_query(F.data == "my_rooms")
async def show_my_rooms(callback: CallbackQuery, db: Database):
    """Show user's rooms"""
    rooms = db.get_user_rooms(callback.from_user.id)

    if not rooms:
        await callback.message.edit_text(
            "📋 У тебя пока нет комнат.\n\n"
            "Создай новую или присоединись по ссылке!",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await callback.message.edit_text(
            "📋 Твои комнаты:\n\n"
            "✅ - жеребьёвка проведена\n"
            "⏳ - ожидание жеребьёвки",
            reply_markup=get_rooms_list_keyboard(rooms)
        )

    await callback.answer()


@router.callback_query(F.data.startswith("room_"))
async def show_room_details(callback: CallbackQuery, db: Database):
    """Show room details"""
    room_id = int(callback.data.split("_")[1])

    room = db.get_room_by_id(room_id)
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return

    # Check if user is member
    if not db.is_user_in_room(room_id, callback.from_user.id):
        await callback.answer("❌ Ты не состоишь в этой комнате", show_alert=True)
        return

    member_count = db.get_room_member_count(room_id)
    is_admin = room['admin_id'] == callback.from_user.id

    status = "✅ Проведена" if room['is_drawn'] else "⏳ Не проведена"

    text = (
        f"🎄 {room['room_name']}\n\n"
        f"👥 Участников: {member_count}\n"
        f"🎲 Жеребьёвка: {status}\n"
    )

    if is_admin:
        text += f"\n👑 Ты администратор этой комнаты"

    await callback.message.edit_text(
        text,
        reply_markup=get_room_menu_keyboard(room_id, is_admin, room['is_drawn'])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("members_"))
async def show_room_members(callback: CallbackQuery, db: Database):
    """Show room members"""
    room_id = int(callback.data.split("_")[1])

    room = db.get_room_by_id(room_id)
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return

    # Check if user is admin
    if room['admin_id'] != callback.from_user.id:
        await callback.answer("❌ Только администратор может видеть список участников", show_alert=True)
        return

    members = db.get_room_members(room_id)

    text = f"👥 Участники комнаты '{room['room_name']}':\n\n"

    for i, member in enumerate(members, 1):
        name = member['first_name']
        if member['last_name']:
            name += f" {member['last_name']}"
        if member['username']:
            name += f" (@{member['username']})"

        admin_mark = " 👑" if member['user_id'] == room['admin_id'] else ""
        text += f"{i}. {name}{admin_mark}\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_to_room_keyboard(room_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("invite_"))
async def show_invite_link(callback: CallbackQuery, db: Database, bot: Bot):
    """Show invite link"""
    room_id = int(callback.data.split("_")[1])

    room = db.get_room_by_id(room_id)
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return

    # Check if user is admin
    if room['admin_id'] != callback.from_user.id:
        await callback.answer("❌ Только администратор может получить пригласительную ссылку", show_alert=True)
        return

    bot_user = await bot.get_me()
    invite_link = f"https://t.me/{bot_user.username}?start={room['invite_code']}"

    await callback.message.edit_text(
        f"🔗 Пригласительная ссылка для комнаты '{room['room_name']}':\n\n"
        f"<code>{invite_link}</code>\n\n"
        f"Отправь эту ссылку друзьям!",
        parse_mode="HTML",
        reply_markup=get_back_to_room_keyboard(room_id)
    )
    await callback.answer()


@router.callback_query(F.data == "join_room")
async def start_room_join(callback: CallbackQuery, state: FSMContext):
    """Start room join process"""
    await callback.message.edit_text(
        "🔗 Присоединение к комнате\n\n"
        "Введи код приглашения или перейди по пригласительной ссылке:",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state(RoomJoin.waiting_for_code)
    await callback.answer()


@router.message(RoomJoin.waiting_for_code)
async def process_invite_code(message: Message, state: FSMContext, db: Database):
    """Process invite code and join room"""
    invite_code = message.text.strip()

    room = db.get_room_by_invite_code(invite_code)
    if not room:
        await message.answer(
            "❌ Комната с таким кодом не найдена.\n"
            "Проверь правильность кода и попробуй ещё раз:",
            reply_markup=get_back_to_menu_keyboard()
        )
        return

    # Check if already a member
    if db.is_user_in_room(room['room_id'], message.from_user.id):
        await message.answer(
            f"ℹ️ Ты уже состоишь в комнате '{room['room_name']}'!",
            reply_markup=get_room_menu_keyboard(room['room_id'], False, room['is_drawn'])
        )
        await state.clear()
        return

    # Add user to room
    try:
        db.add_member_to_room(room['room_id'], message.from_user.id)

        await message.answer(
            f"✅ Ты присоединился к комнате '{room['room_name']}'!",
            reply_markup=get_room_menu_keyboard(room['room_id'], False, room['is_drawn'])
        )

        await state.clear()

    except Exception as e:
        logger.error(f"Error joining room: {e}")
        await message.answer(
            "❌ Произошла ошибка при присоединении к комнате. Попробуй позже.",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


