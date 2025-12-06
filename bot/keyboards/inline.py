from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎄 Создать комнату", callback_data="create_room")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Мои комнаты", callback_data="my_rooms")
    )
    builder.row(
        InlineKeyboardButton(text="🔗 Присоединиться по ссылке", callback_data="join_room")
    )
    return builder.as_markup()


def get_room_menu_keyboard(room_id: int, is_admin: bool, is_drawn: bool) -> InlineKeyboardMarkup:
    """Room management keyboard"""
    builder = InlineKeyboardBuilder()

    if is_admin:
        builder.row(
            InlineKeyboardButton(text="👥 Участники", callback_data=f"members_{room_id}")
        )
        builder.row(
            InlineKeyboardButton(text="🔗 Пригласительная ссылка", callback_data=f"invite_{room_id}")
        )
        builder.row(
            InlineKeyboardButton(text="💰 Установить ценовой диапазон", callback_data=f"set_price_range_{room_id}")
        )
        builder.row(
            InlineKeyboardButton(text="⏰ Установить дедлайн", callback_data=f"set_deadline_{room_id}")
        )
        builder.row(
            InlineKeyboardButton(text="📅 Время и место вручения", callback_data=f"gift_info_{room_id}")
        )

        if not is_drawn:
            builder.row(
                InlineKeyboardButton(text="🎲 Провести жеребьёвку", callback_data=f"draw_{room_id}")
            )
        else:
            builder.row(
                InlineKeyboardButton(text="♻️ Перепровести жеребьёвку", callback_data=f"redraw_{room_id}")
            )
            builder.row(
                InlineKeyboardButton(text="👀 Посмотреть назначения", callback_data=f"view_assignments_{room_id}")
            )

    builder.row(
        InlineKeyboardButton(text="📋 Мой вишлист", callback_data=f"wishlist_{room_id}")
            )

    if is_drawn:
        builder.row(
            InlineKeyboardButton(text="🎁 Узнать кому дарить", callback_data=f"my_receiver_{room_id}")
        )

    builder.row(
        InlineKeyboardButton(text="🚪 Выйти из комнаты", callback_data=f"leave_room_{room_id}")
        )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="my_rooms")
    )

    return builder.as_markup()


def get_members_management_keyboard(room_id: int) -> InlineKeyboardMarkup:
    """Keyboard for managing room members"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🗑️ Удалить участника",
            callback_data=f"remove_member_{room_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="👤 Управление участием",
            callback_data=f"manage_participation_{room_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад в комнату",
            callback_data=f"room_{room_id}"
        )
    )
    return builder.as_markup()


def get_member_list_keyboard(
    room_id: int,
    members: list,
    action: str,
    page: int = 0,
    per_page: int = 10
) -> InlineKeyboardMarkup:
    """Keyboard for selecting a member with pagination"""
    builder = InlineKeyboardBuilder()
    
    total = len(members)
    start = page * per_page
    end = min(start + per_page, total)
    page_members = members[start:end]
    
    for member in page_members:
        name = member['first_name']
        if member.get('last_name'):
            name += f" {member['last_name']}"
        if len(name) > 30:
            name = name[:27] + "..."
        
        builder.row(
            InlineKeyboardButton(
                text=name,
                callback_data=f"{action}_{room_id}_{member['user_id']}"
            )
        )
    
    # Pagination controls
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=f"{action}_page_{room_id}_{page - 1}"
            )
        )
    if end < total:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Вперёд ▶️",
                callback_data=f"{action}_page_{room_id}_{page + 1}"
            )
        )
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"members_{room_id}"
        )
    )

    return builder.as_markup()


def get_confirm_draw_keyboard(room_id: int) -> InlineKeyboardMarkup:
    """Confirmation keyboard for draw"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, провести", callback_data=f"confirm_draw_{room_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"room_{room_id}")
    )
    return builder.as_markup()


def get_back_to_room_keyboard(room_id: int) -> InlineKeyboardMarkup:
    """Back to room keyboard"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад в комнату", callback_data=f"room_{room_id}")
    )
    return builder.as_markup()


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Back to main menu keyboard"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")
    )
    return builder.as_markup()


def get_rooms_list_keyboard(rooms: list) -> InlineKeyboardMarkup:
    """List of user's rooms"""
    builder = InlineKeyboardBuilder()

    for room in rooms:
        status = "✅" if room['is_drawn'] else "⏳"
        room_name = room['room_name']
        if len(room_name) > 30:
            room_name = room_name[:27] + "..."
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {room_name}",
                callback_data=f"room_{room['room_id']}"
            )
        )

    builder.row(
        InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")
    )

    return builder.as_markup()


def get_assignments_paginated_keyboard(
    room_id: int, 
    page: int = 0, 
    total_pages: int = 1
) -> InlineKeyboardMarkup:
    """Keyboard for paginated assignments view"""
    builder = InlineKeyboardBuilder()
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=f"view_assignments_{room_id}_{page - 1}"
            )
        )
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Вперёд ▶️",
                callback_data=f"view_assignments_{room_id}_{page + 1}"
            )
        )
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад в комнату",
            callback_data=f"room_{room_id}"
        )
    )
    
    return builder.as_markup()
