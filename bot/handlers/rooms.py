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
    get_back_to_menu_keyboard,
    get_members_management_keyboard,
    get_member_list_keyboard,
    get_assignments_paginated_keyboard
)

router = Router()
logger = logging.getLogger(__name__)


class RoomCreation(StatesGroup):
    waiting_for_name = State()


class RoomJoin(StatesGroup):
    waiting_for_code = State()


class PriceRange(StatesGroup):
    waiting_for_price_range = State()


class Deadline(StatesGroup):
    waiting_for_deadline = State()


class GiftTime(StatesGroup):
    waiting_for_gift_time = State()


class GiftLocation(StatesGroup):
    waiting_for_gift_location = State()


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
    participant_count = db.get_participant_count(room_id)
    is_admin = room['admin_id'] == callback.from_user.id

    status = "✅ Проведена" if room['is_drawn'] else "⏳ Не проведена"

    text = (
        f"🎄 {room['room_name']}\n\n"
        f"👥 Всего в комнате: {member_count}\n"
        f"✅ Участвует в жеребьёвке: {participant_count}\n"
        f"🎲 Жеребьёвка: {status}\n"
    )

    if room.get('price_range'):
        text += f"💰 Ценовой диапазон: {room['price_range']}\n"

    if room.get('deadline'):
        text += f"⏰ Дедлайн жеребьёвки: {room['deadline']}\n"

    if room.get('gift_time'):
        text += f"📅 Время вручения: {room['gift_time']}\n"

    if room.get('gift_location'):
        text += f"📍 Место вручения: {room['gift_location']}\n"

    if is_admin:
        text += f"\n👑 Ты администратор этой комнаты"

    await callback.message.edit_text(
        text,
        reply_markup=get_room_menu_keyboard(room_id, is_admin, room['is_drawn'])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("members_"))
async def show_room_members(callback: CallbackQuery, db: Database):
    """Show room members with pagination"""
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
    total = len(members)
    
    # Show first page (first 10 members in text, all in management)
    per_page = 10
    page_members = members[:per_page]

    text = f"👥 Участники комнаты '{room['room_name']}':\n\n"
    
    if total > per_page:
        text += f"Показано {len(page_members)} из {total} участников\n\n"

    for i, member in enumerate(page_members, 1):
        name = member['first_name']
        if member['last_name']:
            name += f" {member['last_name']}"
        if member['username']:
            name += f" (@{member['username']})"

        admin_mark = " 👑" if member['user_id'] == room['admin_id'] else ""
        participation = " ✅" if member.get('is_participating', True) else " ❌"
        text += f"{i}. {name}{admin_mark}{participation}\n"
    
    if total > per_page:
        text += f"\n... и ещё {total - per_page} участников\n"

    text += "\n✅ - участвует в жеребьёвке\n❌ - не участвует"

    await callback.message.edit_text(
        text,
        reply_markup=get_members_management_keyboard(room_id)
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


@router.callback_query(F.data.startswith("set_price_range_"))
async def start_set_price_range(callback: CallbackQuery, state: FSMContext, db: Database):
    """Start price range setting process"""
    room_id = int(callback.data.split("_")[3])

    room = db.get_room_by_id(room_id)
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return

    # Check if user is admin
    if room['admin_id'] != callback.from_user.id:
        await callback.answer("❌ Только администратор может установить ценовой диапазон", show_alert=True)
        return

    current_range = room.get('price_range', 'не установлен')
    
    await callback.message.edit_text(
        f"💰 Установка ценового диапазона для комнаты '{room['room_name']}'\n\n"
        f"Текущий диапазон: {current_range}\n\n"
        f"Введи ценовой диапазон (например: до 700 рублей, 500-1000 рублей, до 1000₽):",
        reply_markup=get_back_to_room_keyboard(room_id)
    )
    
    await state.update_data(room_id=room_id)
    await state.set_state(PriceRange.waiting_for_price_range)
    await callback.answer()


@router.message(PriceRange.waiting_for_price_range)
async def process_price_range(message: Message, state: FSMContext, db: Database):
    """Process price range and save it"""
    data = await state.get_data()
    room_id = data.get('room_id')
    
    if not room_id:
        await message.answer("❌ Ошибка. Попробуй снова.", reply_markup=get_main_menu_keyboard())
        await state.clear()
        return

    room = db.get_room_by_id(room_id)
    if not room:
        await message.answer("❌ Комната не найдена", reply_markup=get_main_menu_keyboard())
        await state.clear()
        return

    # Check if user is admin
    if room['admin_id'] != message.from_user.id:
        await message.answer("❌ Только администратор может установить ценовой диапазон", reply_markup=get_main_menu_keyboard())
        await state.clear()
        return

    price_range = message.text.strip()

    if len(price_range) > 100:
        await message.answer("❌ Ценовой диапазон слишком длинный (макс. 100 символов). Попробуй ещё раз:")
        return

    try:
        db.update_room_price_range(room_id, price_range)
        
        # Refresh room data
        room = db.get_room_by_id(room_id)
        member_count = db.get_room_member_count(room_id)
        is_admin = True
        status = "✅ Проведена" if room['is_drawn'] else "⏳ Не проведена"
        
        text = (
            f"✅ Ценовой диапазон установлен!\n\n"
            f"🎄 {room['room_name']}\n\n"
            f"👥 Участников: {member_count}\n"
            f"🎲 Жеребьёвка: {status}\n"
            f"💰 Ценовой диапазон: {price_range}\n\n"
            f"👑 Ты администратор этой комнаты"
        )

        await message.answer(
            text,
            reply_markup=get_room_menu_keyboard(room_id, is_admin, room['is_drawn'])
        )

        await state.clear()

    except Exception as e:
        logger.error(f"Error setting price range: {e}")
        await message.answer(
            "❌ Произошла ошибка при установке ценового диапазона. Попробуй позже.",
            reply_markup=get_room_menu_keyboard(room_id, True, room['is_drawn'])
        )
        await state.clear()


@router.callback_query(F.data.startswith("leave_room_"))
async def leave_room(callback: CallbackQuery, db: Database):
    """Leave room"""
    room_id = int(callback.data.split("_")[2])
    
    room = db.get_room_by_id(room_id)
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return
    
    # Check if user is member
    if not db.is_user_in_room(room_id, callback.from_user.id):
        await callback.answer("❌ Ты не состоишь в этой комнате", show_alert=True)
        return
    
    # Check if user is admin
    if room['admin_id'] == callback.from_user.id:
        await callback.answer(
            "❌ Администратор не может покинуть комнату. Удалите комнату или передайте права администратора.",
            show_alert=True
        )
        return
    
    try:
        db.remove_member_from_room(room_id, callback.from_user.id)
        
        await callback.message.edit_text(
            f"✅ Ты покинул комнату '{room['room_name']}'",
            reply_markup=get_main_menu_keyboard()
        )
        await callback.answer("✅ Ты покинул комнату")
        
    except Exception as e:
        logger.error(f"Error leaving room: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("remove_member_"))
async def start_remove_member(callback: CallbackQuery, db: Database):
    """Start removing member process"""
    room_id = int(callback.data.split("_")[2])
    
    room = db.get_room_by_id(room_id)
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return
    
    # Check if user is admin
    if room['admin_id'] != callback.from_user.id:
        await callback.answer("❌ Только администратор может удалять участников", show_alert=True)
        return
    
    members = db.get_room_members(room_id)
    # Filter out admin
    members = [m for m in members if m['user_id'] != room['admin_id']]
    
    if not members:
        await callback.answer("❌ Нет участников для удаления", show_alert=True)
        return
    
    total = len(members)
    page = 0
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    page_info = f" (стр. {page + 1}/{total_pages})" if total > per_page else ""
    
    await callback.message.edit_text(
        f"🗑️ Удаление участника из комнаты '{room['room_name']}'{page_info}\n\n"
        f"Выбери участника для удаления:",
        reply_markup=get_member_list_keyboard(room_id, members, "remove_user", page, per_page)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("remove_user_page_"))
async def remove_member_page(callback: CallbackQuery, db: Database):
    """Handle pagination for remove member"""
    # Parse: remove_user_page_{room_id}_{page}
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("❌ Ошибка формата", show_alert=True)
        return
    
    try:
        room_id = int(parts[3])
        page = int(parts[4])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка формата", show_alert=True)
        return
    
    room = db.get_room_by_id(room_id)
    if not room or room['admin_id'] != callback.from_user.id:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    members = db.get_room_members(room_id)
    members = [m for m in members if m['user_id'] != room['admin_id']]
    
    total = len(members)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    
    if page < 0 or page >= total_pages:
        await callback.answer("❌ Неверная страница", show_alert=True)
        return
    
    page_info = f" (стр. {page + 1}/{total_pages})" if total > per_page else ""
    
    await callback.message.edit_text(
        f"🗑️ Удаление участника из комнаты '{room['room_name']}'{page_info}\n\n"
        f"Выбери участника для удаления:",
        reply_markup=get_member_list_keyboard(room_id, members, "remove_user", page, per_page)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("remove_user_"))
async def confirm_remove_member(callback: CallbackQuery, db: Database):
    """Remove member from room"""
    # Parse: remove_user_{room_id}_{user_id}
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("❌ Ошибка формата", show_alert=True)
        return
    
    room_id = int(parts[2])
    user_id = int(parts[3])
    
    # Get room and verify admin access
    target_room = db.get_room_by_id(room_id)
    if not target_room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return
    
    if target_room['admin_id'] != callback.from_user.id:
        await callback.answer("❌ Только администратор может удалять участников", show_alert=True)
        return
    
    if user_id == target_room['admin_id']:
        await callback.answer("❌ Нельзя удалить администратора", show_alert=True)
        return
    
    try:
        user = db.get_user(user_id)
        user_name = user['first_name'] if user else "Пользователь"
        
        db.remove_member_from_room(target_room['room_id'], user_id)
        
        members = db.get_room_members(target_room['room_id'])
        
        text = f"✅ Участник {user_name} удалён из комнаты '{target_room['room_name']}'\n\n"
        text += f"👥 Участники комнаты:\n\n"
        
        # Show only first 10 members to avoid long messages
        display_members = members[:10]
        for i, member in enumerate(display_members, 1):
            name = member['first_name']
            if member.get('last_name'):
                name += f" {member['last_name']}"
            if member.get('username'):
                name += f" (@{member['username']})"
            
            admin_mark = " 👑" if member['user_id'] == target_room['admin_id'] else ""
            participation = " ✅" if member.get('is_participating', True) else " ❌"
            text += f"{i}. {name}{admin_mark}{participation}\n"
        
        if len(members) > 10:
            text += f"\n... и ещё {len(members) - 10} участников\n"
        
        text += "\n✅ - участвует в жеребьёвке\n❌ - не участвует"
        
        # Check message length
        if len(text) > 4096:
            text = text[:4000] + "\n\n... (список обрезан)"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_members_management_keyboard(target_room['room_id'])
        )
        await callback.answer(f"✅ {user_name} удалён")
        
    except Exception as e:
        logger.error(f"Error removing member: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("manage_participation_"))
async def start_manage_participation(callback: CallbackQuery, db: Database):
    """Start managing participation"""
    room_id = int(callback.data.split("_")[2])
    
    room = db.get_room_by_id(room_id)
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return
    
    # Check if user is admin
    if room['admin_id'] != callback.from_user.id:
        await callback.answer("❌ Только администратор может управлять участием", show_alert=True)
        return
    
    members = db.get_room_members(room_id)
    total = len(members)
    page = 0
    per_page = 10
    page_info = f" (стр. {page + 1}/{(total + per_page - 1) // per_page})" if total > per_page else ""
    
    await callback.message.edit_text(
        f"👤 Управление участием в комнате '{room['room_name']}'{page_info}\n\n"
        f"Выбери участника для изменения статуса участия:",
        reply_markup=get_member_list_keyboard(room_id, members, "toggle_participation", page, per_page)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_participation_page_"))
async def toggle_participation_page(callback: CallbackQuery, db: Database):
    """Handle pagination for toggle participation"""
    # Parse: toggle_participation_page_{room_id}_{page}
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("❌ Ошибка формата", show_alert=True)
        return
    
    try:
        room_id = int(parts[3])
        page = int(parts[4])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка формата", show_alert=True)
        return
    
    room = db.get_room_by_id(room_id)
    if not room or room['admin_id'] != callback.from_user.id:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    members = db.get_room_members(room_id)
    total = len(members)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    
    if page < 0 or page >= total_pages:
        await callback.answer("❌ Неверная страница", show_alert=True)
        return
    
    page_info = f" (стр. {page + 1}/{total_pages})" if total > per_page else ""
    
    await callback.message.edit_text(
        f"👤 Управление участием в комнате '{room['room_name']}'{page_info}\n\n"
        f"Выбери участника для изменения статуса участия:",
        reply_markup=get_member_list_keyboard(room_id, members, "toggle_participation", page, per_page)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_participation_"))
async def toggle_participation(callback: CallbackQuery, db: Database):
    """Toggle participation status"""
    # Parse: toggle_participation_{room_id}_{user_id}
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("❌ Ошибка формата", show_alert=True)
        return
    
    room_id = int(parts[2])
    user_id = int(parts[3])
    
    # Get room and verify admin access
    target_room = db.get_room_by_id(room_id)
    if not target_room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return
    
    if target_room['admin_id'] != callback.from_user.id:
        await callback.answer("❌ Только администратор может управлять участием", show_alert=True)
        return
    
    # Get current participation status
    members = db.get_room_members(target_room['room_id'])
    member = next((m for m in members if m['user_id'] == user_id), None)
    
    if not member:
        await callback.answer("❌ Участник не найден", show_alert=True)
        return
    
    current_status = member.get('is_participating', True)
    new_status = not current_status
    
    try:
        db.set_participation(target_room['room_id'], user_id, new_status)
        
        user = db.get_user(user_id)
        user_name = user['first_name'] if user else "Пользователь"
        status_text = "участвует" if new_status else "не участвует"
        
        # Refresh members list
        members = db.get_room_members(target_room['room_id'])
        
        text = f"✅ Статус участия изменён!\n\n"
        text += f"{user_name} теперь {status_text} в жеребьёвке.\n\n"
        text += f"👥 Участники комнаты '{target_room['room_name']}':\n\n"
        
        # Show only first 10 members to avoid long messages
        display_members = members[:10]
        for i, m in enumerate(display_members, 1):
            name = m['first_name']
            if m.get('last_name'):
                name += f" {m['last_name']}"
            if m.get('username'):
                name += f" (@{m['username']})"
            
            admin_mark = " 👑" if m['user_id'] == target_room['admin_id'] else ""
            participation = " ✅" if m.get('is_participating', True) else " ❌"
            text += f"{i}. {name}{admin_mark}{participation}\n"
        
        if len(members) > 10:
            text += f"\n... и ещё {len(members) - 10} участников\n"
        
        text += "\n✅ - участвует в жеребьёвке\n❌ - не участвует"
        
        # Check message length
        if len(text) > 4096:
            text = text[:4000] + "\n\n... (список обрезан)"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_members_management_keyboard(target_room['room_id'])
        )
        await callback.answer(f"✅ Статус изменён")
        
    except Exception as e:
        logger.error(f"Error toggling participation: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("set_deadline_"))
async def start_set_deadline(callback: CallbackQuery, state: FSMContext, db: Database):
    """Start deadline setting process"""
    room_id = int(callback.data.split("_")[2])

    room = db.get_room_by_id(room_id)
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return

    if room['admin_id'] != callback.from_user.id:
        await callback.answer("❌ Только администратор может установить дедлайн", show_alert=True)
        return

    current_deadline = room.get('deadline', 'не установлен')

    await callback.message.edit_text(
        f"⏰ Установка дедлайна для жеребьёвки\n\n"
        f"Комната: '{room['room_name']}'\n"
        f"Текущий дедлайн: {current_deadline}\n\n"
        f"Введи дедлайн (например: до 25 декабря, 25.12.2024 18:00):",
        reply_markup=get_back_to_room_keyboard(room_id)
    )

    await state.update_data(room_id=room_id)
    await state.set_state(Deadline.waiting_for_deadline)
    await callback.answer()


@router.message(Deadline.waiting_for_deadline)
async def process_deadline(message: Message, state: FSMContext, db: Database):
    """Process deadline and save it"""
    data = await state.get_data()
    room_id = data.get('room_id')

    if not room_id:
        await message.answer("❌ Ошибка", reply_markup=get_main_menu_keyboard())
        await state.clear()
        return

    room = db.get_room_by_id(room_id)
    if not room or room['admin_id'] != message.from_user.id:
        await message.answer("❌ Ошибка доступа", reply_markup=get_main_menu_keyboard())
        await state.clear()
        return

    deadline_text = message.text.strip()
    if len(deadline_text) > 255:
        await message.answer("❌ Слишком длинный текст (макс. 255 символов)")
        return

    try:
        db.update_room_deadline(room_id, deadline_text)
        room = db.get_room_by_id(room_id)
        member_count = db.get_room_member_count(room_id)
        participant_count = db.get_participant_count(room_id)
        status = "✅ Проведена" if room['is_drawn'] else "⏳ Не проведена"

        text = (
            f"✅ Дедлайн установлен!\n\n"
            f"🎄 {room['room_name']}\n\n"
            f"👥 Всего в комнате: {member_count}\n"
            f"✅ Участвует: {participant_count}\n"
            f"🎲 Жеребьёвка: {status}\n"
        )

        if room.get('price_range'):
            text += f"💰 Ценовой диапазон: {room['price_range']}\n"
        if room.get('deadline'):
            text += f"⏰ Дедлайн: {room['deadline']}\n"
        if room.get('gift_time'):
            text += f"📅 Время вручения: {room['gift_time']}\n"
        if room.get('gift_location'):
            text += f"📍 Место вручения: {room['gift_location']}\n"

        text += "\n👑 Ты администратор"

        await message.answer(
            text,
            reply_markup=get_room_menu_keyboard(room_id, True, room['is_drawn'])
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Error setting deadline: {e}")
        await message.answer("❌ Ошибка при установке дедлайна")
        await state.clear()


@router.callback_query(F.data.startswith("gift_info_"))
async def show_gift_info_menu(callback: CallbackQuery, db: Database):
    """Show gift info management menu"""
    room_id = int(callback.data.split("_")[2])

    room = db.get_room_by_id(room_id)
    if not room or room['admin_id'] != callback.from_user.id:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    current_time = room.get('gift_time', 'не установлено')
    current_location = room.get('gift_location', 'не установлено')

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📅 Установить время",
            callback_data=f"set_gift_time_{room_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📍 Установить место",
            callback_data=f"set_gift_location_{room_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"room_{room_id}"
        )
    )

    await callback.message.edit_text(
        f"📅 Управление информацией о вручении\n\n"
        f"Комната: '{room['room_name']}'\n\n"
        f"📅 Время: {current_time}\n"
        f"📍 Место: {current_location}\n\n"
        f"Выбери, что изменить:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_gift_time_"))
async def start_set_gift_time(callback: CallbackQuery, state: FSMContext, db: Database):
    """Start gift time setting"""
    room_id = int(callback.data.split("_")[3])

    room = db.get_room_by_id(room_id)
    if not room or room['admin_id'] != callback.from_user.id:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    current_time = room.get('gift_time', 'не установлено')

    await callback.message.edit_text(
        f"📅 Установка времени вручения\n\n"
        f"Комната: '{room['room_name']}'\n"
        f"Текущее время: {current_time}\n\n"
        f"Введи время вручения (например: 25 декабря в 18:00):",
        reply_markup=get_back_to_room_keyboard(room_id)
    )

    await state.update_data(room_id=room_id)
    await state.set_state(GiftTime.waiting_for_gift_time)
    await callback.answer()


@router.message(GiftTime.waiting_for_gift_time)
async def process_gift_time(message: Message, state: FSMContext, db: Database):
    """Process gift time"""
    data = await state.get_data()
    room_id = data.get('room_id')

    if not room_id:
        await message.answer("❌ Ошибка", reply_markup=get_main_menu_keyboard())
        await state.clear()
        return

    room = db.get_room_by_id(room_id)
    if not room or room['admin_id'] != message.from_user.id:
        await message.answer("❌ Ошибка доступа", reply_markup=get_main_menu_keyboard())
        await state.clear()
        return

    gift_time = message.text.strip()
    if len(gift_time) > 255:
        await message.answer("❌ Слишком длинный текст (макс. 255 символов)")
        return

    try:
        db.update_room_gift_time(room_id, gift_time)
        room = db.get_room_by_id(room_id)
        member_count = db.get_room_member_count(room_id)
        participant_count = db.get_participant_count(room_id)
        status = "✅ Проведена" if room['is_drawn'] else "⏳ Не проведена"

        text = (
            f"✅ Время вручения установлено!\n\n"
            f"🎄 {room['room_name']}\n\n"
            f"👥 Всего в комнате: {member_count}\n"
            f"✅ Участвует: {participant_count}\n"
            f"🎲 Жеребьёвка: {status}\n"
        )

        if room.get('price_range'):
            text += f"💰 Ценовой диапазон: {room['price_range']}\n"
        if room.get('deadline'):
            text += f"⏰ Дедлайн: {room['deadline']}\n"
        if room.get('gift_time'):
            text += f"📅 Время вручения: {room['gift_time']}\n"
        if room.get('gift_location'):
            text += f"📍 Место вручения: {room['gift_location']}\n"

        text += "\n👑 Ты администратор"

        await message.answer(
            text,
            reply_markup=get_room_menu_keyboard(room_id, True, room['is_drawn'])
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Error setting gift time: {e}")
        await message.answer("❌ Ошибка при установке времени")
        await state.clear()


@router.callback_query(F.data.startswith("set_gift_location_"))
async def start_set_gift_location(callback: CallbackQuery, state: FSMContext, db: Database):
    """Start gift location setting"""
    room_id = int(callback.data.split("_")[3])

    room = db.get_room_by_id(room_id)
    if not room or room['admin_id'] != callback.from_user.id:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    current_location = room.get('gift_location', 'не установлено')

    await callback.message.edit_text(
        f"📍 Установка места вручения\n\n"
        f"Комната: '{room['room_name']}'\n"
        f"Текущее место: {current_location}\n\n"
        f"Введи место вручения (например: Офис, комната 205):",
        reply_markup=get_back_to_room_keyboard(room_id)
    )

    await state.update_data(room_id=room_id)
    await state.set_state(GiftLocation.waiting_for_gift_location)
    await callback.answer()


@router.message(GiftLocation.waiting_for_gift_location)
async def process_gift_location(message: Message, state: FSMContext, db: Database):
    """Process gift location"""
    data = await state.get_data()
    room_id = data.get('room_id')

    if not room_id:
        await message.answer("❌ Ошибка", reply_markup=get_main_menu_keyboard())
        await state.clear()
        return

    room = db.get_room_by_id(room_id)
    if not room or room['admin_id'] != message.from_user.id:
        await message.answer("❌ Ошибка доступа", reply_markup=get_main_menu_keyboard())
        await state.clear()
        return

    gift_location = message.text.strip()
    if len(gift_location) > 255:
        await message.answer("❌ Слишком длинный текст (макс. 255 символов)")
        return

    try:
        db.update_room_gift_location(room_id, gift_location)
        room = db.get_room_by_id(room_id)
        member_count = db.get_room_member_count(room_id)
        participant_count = db.get_participant_count(room_id)
        status = "✅ Проведена" if room['is_drawn'] else "⏳ Не проведена"

        text = (
            f"✅ Место вручения установлено!\n\n"
            f"🎄 {room['room_name']}\n\n"
            f"👥 Всего в комнате: {member_count}\n"
            f"✅ Участвует: {participant_count}\n"
            f"🎲 Жеребьёвка: {status}\n"
        )

        if room.get('price_range'):
            text += f"💰 Ценовой диапазон: {room['price_range']}\n"
        if room.get('deadline'):
            text += f"⏰ Дедлайн: {room['deadline']}\n"
        if room.get('gift_time'):
            text += f"📅 Время вручения: {room['gift_time']}\n"
        if room.get('gift_location'):
            text += f"📍 Место вручения: {room['gift_location']}\n"

        text += "\n👑 Ты администратор"

        await message.answer(
            text,
            reply_markup=get_room_menu_keyboard(room_id, True, room['is_drawn'])
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Error setting gift location: {e}")
        await message.answer("❌ Ошибка при установке места")
        await state.clear()


@router.callback_query(F.data.startswith("view_assignments_"))
async def view_assignments(callback: CallbackQuery, db: Database):
    """Show all Secret Santa assignments for admin with pagination"""
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Ошибка формата", show_alert=True)
        return
    
    try:
        room_id = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка формата", show_alert=True)
        return
    
    room = db.get_room_by_id(room_id)
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return
    
    # Check if user is admin
    if room['admin_id'] != callback.from_user.id:
        await callback.answer("❌ Только администратор может просматривать назначения", show_alert=True)
        return
    
    # Check if draw was done
    if not room['is_drawn']:
        await callback.answer("❌ Жеребьёвка ещё не проведена", show_alert=True)
        return
    
    # Get all assignments with user info
    assignments = db.get_room_assignments_with_users(room_id)
    
    if not assignments:
        await callback.answer("❌ Назначения не найдены", show_alert=True)
        return
    
    # Pagination
    per_page = 10
    total = len(assignments)
    total_pages = (total + per_page - 1) // per_page
    
    if page < 0 or page >= total_pages:
        await callback.answer("❌ Неверная страница", show_alert=True)
        return
    
    start = page * per_page
    end = min(start + per_page, total)
    page_assignments = assignments[start:end]
    
    text = f"👀 Назначения в комнате '{room['room_name']}'\n\n"
    if total > per_page:
        text += f"Страница {page + 1} из {total_pages}\n\n"
    text += "🎁 Кто кому дарит подарки:\n\n"
    
    for i, assignment in enumerate(page_assignments, start=start + 1):
        # Format giver name
        giver_name = assignment['giver_first_name']
        if assignment.get('giver_last_name'):
            giver_name += f" {assignment['giver_last_name']}"
        if assignment.get('giver_username'):
            giver_name += f" (@{assignment['giver_username']})"
        
        # Format receiver name
        receiver_name = assignment['receiver_first_name']
        if assignment.get('receiver_last_name'):
            receiver_name += f" {assignment['receiver_last_name']}"
        if assignment.get('receiver_username'):
            receiver_name += f" (@{assignment['receiver_username']})"
        
        text += f"{i}. {giver_name}\n"
        text += f"   → {receiver_name}\n\n"
    
    text += "🤫 Эта информация видна только администратору!"
    
    # Check message length (Telegram limit is 4096)
    if len(text) > 4096:
        # Truncate if too long
        text = text[:4000] + "\n\n... (сообщение обрезано)"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_assignments_paginated_keyboard(room_id, page, total_pages)
    )
    await callback.answer()


