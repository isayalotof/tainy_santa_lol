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

        if not is_drawn:
            builder.row(
                InlineKeyboardButton(text="🎲 Провести жеребьёвку", callback_data=f"draw_{room_id}")
            )
        else:
            builder.row(
                InlineKeyboardButton(text="♻️ Перепровести жеребьёвку", callback_data=f"redraw_{room_id}")
            )

    if is_drawn:
        builder.row(
            InlineKeyboardButton(text="🎁 Узнать кому дарить", callback_data=f"my_receiver_{room_id}")
        )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="my_rooms")
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
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {room['room_name']}",
                callback_data=f"room_{room['room_id']}"
            )
        )

    builder.row(
        InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")
    )

    return builder.as_markup()
