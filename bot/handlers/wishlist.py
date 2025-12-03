from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

from bot.database import Database

router = Router()
logger = logging.getLogger(__name__)


class WishlistItem(StatesGroup):
    waiting_for_item_name = State()
    waiting_for_item_url = State()


def get_wishlist_keyboard(
    room_id: int, items: list, editing_item_id: int = None
) -> InlineKeyboardMarkup:
    """Keyboard for wishlist management"""
    builder = InlineKeyboardBuilder()
    
    for item in items:
        item_text = f"📦 {item['item_name']}"
        if item['item_url']:
            item_text += " 🔗"
        builder.row(
            InlineKeyboardButton(
                text=item_text,
                callback_data=f"wishlist_item_{item['id']}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="➕ Добавить пункт",
            callback_data=f"wishlist_add_{room_id}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад в комнату",
            callback_data=f"room_{room_id}"
        )
    )
    
    return builder.as_markup()


def get_wishlist_item_keyboard(room_id: int, item_id: int) -> InlineKeyboardMarkup:
    """Keyboard for individual wishlist item"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🔗 Добавить/изменить ссылку",
            callback_data=f"wishlist_url_{item_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Удалить пункт",
            callback_data=f"wishlist_delete_{item_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад к вишлисту",
            callback_data=f"wishlist_{room_id}"
        )
    )
    
    return builder.as_markup()


@router.callback_query(
    F.data.startswith("wishlist_") &
    ~F.data.startswith("wishlist_add_") &
    ~F.data.startswith("wishlist_item_") &
    ~F.data.startswith("wishlist_url_") &
    ~F.data.startswith("wishlist_delete_")
)
async def show_wishlist(callback: CallbackQuery, db: Database):
    """Show user's wishlist for a room"""
    # Extract room_id from "wishlist_{room_id}"
    parts = callback.data.split("_")
    if len(parts) < 2:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    room_id = int(parts[1])
    
    room = db.get_room_by_id(room_id)
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return
    
    # Check if user is member
    if not db.is_user_in_room(room_id, callback.from_user.id):
        await callback.answer("❌ Ты не состоишь в этой комнате", show_alert=True)
        return
    
    items = db.get_wishlist_items(room_id, callback.from_user.id)
    
    if not items:
        text = (
            f"📋 Мой вишлист для комнаты '{room['room_name']}'\n\n"
            f"Твой список желаний пуст.\n"
            f"Добавь пункты, чтобы твой Тайный Санта знал, что тебе подарить!"
        )
    else:
        text = f"📋 Мой вишлист для комнаты '{room['room_name']}'\n\n"
        text += "Твой список желаний:\n\n"
        for i, item in enumerate(items, 1):
            text += f"{i}. {item['item_name']}"
            if item['item_url']:
                text += " 🔗"
            text += "\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_wishlist_keyboard(room_id, items)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wishlist_add_"))
async def start_add_wishlist_item(callback: CallbackQuery, state: FSMContext):
    """Start adding wishlist item"""
    room_id = int(callback.data.split("_")[2])
    
    await callback.message.edit_text(
        "➕ Добавление пункта в вишлист\n\n"
        "Введи название подарка:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Отмена", callback_data=f"wishlist_{room_id}")
        ]])
    )
    
    await state.update_data(room_id=room_id)
    await state.set_state(WishlistItem.waiting_for_item_name)
    await callback.answer()


@router.message(WishlistItem.waiting_for_item_name)
async def process_item_name(message: Message, state: FSMContext, db: Database):
    """Process item name and ask for URL"""
    data = await state.get_data()
    room_id = data.get('room_id')
    
    if not room_id:
        await message.answer("❌ Ошибка. Попробуй снова.")
        await state.clear()
        return
    
    room = db.get_room_by_id(room_id)
    if not room:
        await message.answer("❌ Комната не найдена")
        await state.clear()
        return
    
    item_name = message.text.strip()
    
    if len(item_name) < 2:
        await message.answer("❌ Название должно быть не короче 2 символов. Попробуй ещё раз:")
        return
    
    if len(item_name) > 255:
        await message.answer("❌ Название слишком длинное (макс. 255 символов). Попробуй ещё раз:")
        return
    
    await state.update_data(item_name=item_name)
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏭️ Пропустить", callback_data="wishlist_skip_url")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"wishlist_{room_id}")
    )
    
    await message.answer(
        f"✅ Название: {item_name}\n\n"
        f"Теперь можешь добавить ссылку на подарок (Wildberries, Ozon и т.д.)\n"
        f"Или нажми 'Пропустить', если ссылки нет:",
        reply_markup=builder.as_markup()
    )
    
    await state.set_state(WishlistItem.waiting_for_item_url)


@router.callback_query(F.data == "wishlist_skip_url")
async def skip_url(callback: CallbackQuery, state: FSMContext, db: Database):
    """Skip URL and save item"""
    data = await state.get_data()
    room_id = data.get('room_id')
    item_name = data.get('item_name')
    
    if not room_id or not item_name:
        await callback.answer("❌ Ошибка", show_alert=True)
        await state.clear()
        return
    
    try:
        db.add_wishlist_item(room_id, callback.from_user.id, item_name)
        
        room = db.get_room_by_id(room_id)
        items = db.get_wishlist_items(room_id, callback.from_user.id)
        
        text = f"✅ Пункт добавлен!\n\n📋 Мой вишлист для комнаты '{room['room_name']}'\n\n"
        if items:
            text += "Твой список желаний:\n\n"
            for i, item in enumerate(items, 1):
                text += f"{i}. {item['item_name']}"
                if item['item_url']:
                    text += " 🔗"
                text += "\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_wishlist_keyboard(room_id, items)
        )
        await callback.answer()
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error adding wishlist item: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
        await state.clear()


@router.message(WishlistItem.waiting_for_item_url)
async def process_item_url(message: Message, state: FSMContext, db: Database):
    """Process item URL and save item"""
    data = await state.get_data()
    room_id = data.get('room_id')
    item_name = data.get('item_name')
    item_id = data.get('item_id')  # For editing existing item
    
    item_url = message.text.strip()
    
    # Basic URL validation
    if not (item_url.startswith('http://') or item_url.startswith('https://')):
        await message.answer(
            "❌ Ссылка должна начинаться с http:// или https://\n"
            "Попробуй ещё раз:"
        )
        return
    
    if len(item_url) > 500:
        await message.answer("❌ Ссылка слишком длинная (макс. 500 символов). Попробуй ещё раз:")
        return
    
    try:
        if item_id:
            # Editing existing item
            db.update_wishlist_item(item_id, item_url=item_url)
            item = db.get_wishlist_item(item_id)
            if not item:
                await message.answer("❌ Пункт не найден")
                await state.clear()
                return
            
            room_id = item['room_id']
            
            text = f"✅ Ссылка обновлена!\n\n📦 {item['item_name']}\n\n"
            text += f"🔗 Ссылка: {item_url}"
            
            await message.answer(
                text,
                reply_markup=get_wishlist_item_keyboard(room_id, item_id)
            )
        else:
            # Adding new item
            if not room_id or not item_name:
                await message.answer("❌ Ошибка. Попробуй снова.")
                await state.clear()
                return
            
            db.add_wishlist_item(room_id, message.from_user.id, item_name, item_url)
            
            room = db.get_room_by_id(room_id)
            items = db.get_wishlist_items(room_id, message.from_user.id)
            
            text = f"✅ Пункт добавлен!\n\n📋 Мой вишлист для комнаты '{room['room_name']}'\n\n"
            if items:
                text += "Твой список желаний:\n\n"
                for i, item in enumerate(items, 1):
                    text += f"{i}. {item['item_name']}"
                    if item['item_url']:
                        text += " 🔗"
                    text += "\n"
            
            await message.answer(
                text,
                reply_markup=get_wishlist_keyboard(room_id, items)
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error processing wishlist item URL: {e}")
        await message.answer("❌ Произошла ошибка. Попробуй позже.")
        await state.clear()


@router.callback_query(F.data.startswith("wishlist_item_"))
async def show_wishlist_item(callback: CallbackQuery, db: Database):
    """Show individual wishlist item"""
    item_id = int(callback.data.split("_")[2])
    
    item = db.get_wishlist_item(item_id)
    if not item:
        await callback.answer("❌ Пункт не найден", show_alert=True)
        return
    
    # Check if user owns this item
    if item['user_id'] != callback.from_user.id:
        await callback.answer("❌ Это не твой пункт", show_alert=True)
        return
    
    room = db.get_room_by_id(item['room_id'])
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return
    
    text = f"📦 {item['item_name']}\n\n"
    
    if item['item_url']:
        text += f"🔗 Ссылка: {item['item_url']}"
    else:
        text += "🔗 Ссылка не добавлена"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_wishlist_item_keyboard(item['room_id'], item_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wishlist_url_"))
async def start_add_url(callback: CallbackQuery, state: FSMContext, db: Database):
    """Start adding/editing URL for wishlist item"""
    item_id = int(callback.data.split("_")[2])
    
    item = db.get_wishlist_item(item_id)
    if not item:
        await callback.answer("❌ Пункт не найден", show_alert=True)
        return
    
    # Check if user owns this item
    if item['user_id'] != callback.from_user.id:
        await callback.answer("❌ Это не твой пункт", show_alert=True)
        return
    
    current_url = item['item_url'] or "не добавлена"
    
    await callback.message.edit_text(
        f"🔗 Добавление/изменение ссылки для '{item['item_name']}'\n\n"
        f"Текущая ссылка: {current_url}\n\n"
        f"Введи новую ссылку (http:// или https://):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Отмена", callback_data=f"wishlist_item_{item_id}")
        ]])
    )
    
    await state.update_data(item_id=item_id)
    await state.set_state(WishlistItem.waiting_for_item_url)
    await callback.answer()


@router.callback_query(F.data.startswith("wishlist_delete_"))
async def delete_wishlist_item(callback: CallbackQuery, db: Database):
    """Delete wishlist item"""
    item_id = int(callback.data.split("_")[2])
    
    item = db.get_wishlist_item(item_id)
    if not item:
        await callback.answer("❌ Пункт не найден", show_alert=True)
        return
    
    # Check if user owns this item
    if item['user_id'] != callback.from_user.id:
        await callback.answer("❌ Это не твой пункт", show_alert=True)
        return
    
    room_id = item['room_id']
    
    try:
        db.delete_wishlist_item(item_id)
        
        room = db.get_room_by_id(room_id)
        items = db.get_wishlist_items(room_id, callback.from_user.id)
        
        text = f"✅ Пункт удалён!\n\n📋 Мой вишлист для комнаты '{room['room_name']}'\n\n"
        if items:
            text += "Твой список желаний:\n\n"
            for i, item in enumerate(items, 1):
                text += f"{i}. {item['item_name']}"
                if item['item_url']:
                    text += " 🔗"
                text += "\n"
        else:
            text += "Твой список желаний пуст.\nДобавь пункты, чтобы твой Тайный Санта знал, что тебе подарить!"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_wishlist_keyboard(room_id, items)
        )
        await callback.answer("✅ Пункт удалён")
        
    except Exception as e:
        logger.error(f"Error deleting wishlist item: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

