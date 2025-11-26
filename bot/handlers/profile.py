from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

from bot.database import Database
from bot.keyboards.inline import (
    get_main_menu_keyboard,
    get_profile_keyboard,
    get_profile_edit_keyboard,
    get_back_to_profile_keyboard
)

router = Router()
logger = logging.getLogger(__name__)


class ProfileEdit(StatesGroup):
    waiting_for_bio = State()
    waiting_for_photo = State()
    waiting_for_wishlist = State()


def format_user_name(user: dict) -> str:
    """Format user name from user dict"""
    name = user.get('first_name', 'Пользователь')
    if user.get('last_name'):
        name += f" {user['last_name']}"
    if user.get('username'):
        name += f" (@{user['username']})"
    return name


def format_profile_text(user: dict) -> str:
    """Format profile information for display"""
    name = format_user_name(user)

    text = f"👤 Профиль: {name}\n\n"

    if user.get('bio'):
        text += f"📝 О себе:\n{user['bio']}\n\n"
    else:
        text += "📝 О себе: не указано\n\n"

    if user.get('photo_file_id'):
        text += "📸 Фото: добавлено\n\n"
    else:
        text += "📸 Фото: не добавлено\n\n"

    if user.get('wishlist'):
        text += f"🎁 Список желаний:\n{user['wishlist']}\n"
    else:
        text += "🎁 Список желаний: не указан\n"

    return text


@router.callback_query(F.data == "my_profile")
async def show_my_profile(callback: CallbackQuery, db: Database):
    """Show user profile"""
    user = db.get_user_profile(callback.from_user.id)

    if not user:
        await callback.answer("❌ Профиль не найден", show_alert=True)
        return

    text = format_profile_text(user)

    # If user has photo, send it with caption
    if user.get('photo_file_id'):
        try:
            await callback.message.delete()
            await callback.bot.send_photo(
                callback.from_user.id,
                photo=user['photo_file_id'],
                caption=text,
                reply_markup=get_profile_keyboard()
            )
        except Exception as e:
            logger.error(f"Error sending profile photo: {e}")
            await callback.message.edit_text(
                text,
                reply_markup=get_profile_keyboard()
            )
    else:
        await callback.message.edit_text(
            text,
            reply_markup=get_profile_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "edit_profile")
async def show_edit_profile_menu(callback: CallbackQuery):
    """Show profile edit menu"""
    text = (
        "✏️ Редактирование профиля\n\n"
        "Выбери, что хочешь изменить:"
    )

    # Check if message has photo
    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=get_profile_edit_keyboard())
    else:
        await callback.message.edit_text(text, reply_markup=get_profile_edit_keyboard())

    await callback.answer()


@router.callback_query(F.data == "edit_bio")
async def start_edit_bio(callback: CallbackQuery, state: FSMContext):
    """Start bio editing"""
    text = (
        "📝 Расскажи о себе\n\n"
        "Напиши немного информации о себе, своих интересах и хобби.\n"
        "Это поможет тайному санте выбрать подарок получше!\n\n"
        "Максимум 500 символов."
    )

    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=get_back_to_profile_keyboard())
    else:
        await callback.message.edit_text(text, reply_markup=get_back_to_profile_keyboard())

    await state.set_state(ProfileEdit.waiting_for_bio)
    await callback.answer()


@router.message(ProfileEdit.waiting_for_bio)
async def process_bio(message: Message, state: FSMContext, db: Database):
    """Process bio text"""
    bio = message.text.strip()

    if len(bio) > 500:
        await message.answer(
            "❌ Текст слишком длинный! Максимум 500 символов.\n"
            "Попробуй сократить:",
            reply_markup=get_back_to_profile_keyboard()
        )
        return

    if len(bio) < 10:
        await message.answer(
            "❌ Текст слишком короткий! Минимум 10 символов.\n"
            "Попробуй добавить больше информации:",
            reply_markup=get_back_to_profile_keyboard()
        )
        return

    try:
        db.update_user_bio(message.from_user.id, bio)

        await message.answer(
            "✅ Информация о себе обновлена!",
            reply_markup=get_profile_keyboard()
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Error updating bio: {e}")
        await message.answer(
            "❌ Произошла ошибка. Попробуй позже.",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


@router.callback_query(F.data == "edit_photo")
async def start_edit_photo(callback: CallbackQuery, state: FSMContext):
    """Start photo editing"""
    text = (
        "📸 Добавь фото\n\n"
        "Отправь свою фотографию.\n"
        "Это поможет участникам узнать тебя лучше!\n\n"
        "Отправь фото или нажми 'Назад' для отмены."
    )

    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=get_back_to_profile_keyboard())
    else:
        await callback.message.edit_text(text, reply_markup=get_back_to_profile_keyboard())

    await state.set_state(ProfileEdit.waiting_for_photo)
    await callback.answer()


@router.message(ProfileEdit.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext, db: Database):
    """Process photo"""
    # Get the largest photo
    photo: PhotoSize = message.photo[-1]

    try:
        db.update_user_photo(message.from_user.id, photo.file_id)

        await message.answer(
            "✅ Фото обновлено!",
            reply_markup=get_profile_keyboard()
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Error updating photo: {e}")
        await message.answer(
            "❌ Произошла ошибка. Попробуй позже.",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


@router.message(ProfileEdit.waiting_for_photo)
async def process_invalid_photo(message: Message):
    """Handle invalid photo input"""
    await message.answer(
        "❌ Пожалуйста, отправь фотографию или нажми 'Назад' для отмены.",
        reply_markup=get_back_to_profile_keyboard()
    )


@router.callback_query(F.data == "edit_wishlist")
async def start_edit_wishlist(callback: CallbackQuery, state: FSMContext):
    """Start wishlist editing"""
    text = (
        "🎁 Список желаний\n\n"
        "Напиши, какие подарки ты хотел бы получить.\n"
        "Укажи диапазон цен, интересы, пожелания.\n\n"
        "Например:\n"
        "• Книги по психологии (500-1000₽)\n"
        "• Настольные игры\n"
        "• Хенд-мейд подарки\n\n"
        "Максимум 500 символов."
    )

    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=get_back_to_profile_keyboard())
    else:
        await callback.message.edit_text(text, reply_markup=get_back_to_profile_keyboard())

    await state.set_state(ProfileEdit.waiting_for_wishlist)
    await callback.answer()


@router.message(ProfileEdit.waiting_for_wishlist)
async def process_wishlist(message: Message, state: FSMContext, db: Database):
    """Process wishlist text"""
    wishlist = message.text.strip()

    if len(wishlist) > 500:
        await message.answer(
            "❌ Текст слишком длинный! Максимум 500 символов.\n"
            "Попробуй сократить:",
            reply_markup=get_back_to_profile_keyboard()
        )
        return

    if len(wishlist) < 10:
        await message.answer(
            "❌ Текст слишком короткий! Минимум 10 символов.\n"
            "Добавь больше информации о желаемых подарках:",
            reply_markup=get_back_to_profile_keyboard()
        )
        return

    try:
        db.update_user_wishlist(message.from_user.id, wishlist)

        await message.answer(
            "✅ Список желаний обновлен!",
            reply_markup=get_profile_keyboard()
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Error updating wishlist: {e}")
        await message.answer(
            "❌ Произошла ошибка. Попробуй позже.",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


@router.callback_query(F.data.startswith("view_profile_"))
async def view_user_profile(callback: CallbackQuery, db: Database):
    """View another user's profile"""
    user_id = int(callback.data.split("_")[2])

    user = db.get_user_profile(user_id)

    if not user:
        await callback.answer("❌ Профиль не найден", show_alert=True)
        return

    text = format_profile_text(user)

    # If user has photo, send it
    if user.get('photo_file_id'):
        try:
            await callback.message.delete()
            await callback.bot.send_photo(
                callback.from_user.id,
                photo=user['photo_file_id'],
                caption=text,
                reply_markup=get_main_menu_keyboard()
            )
        except Exception as e:
            logger.error(f"Error sending profile photo: {e}")
            await callback.message.edit_text(
                text,
                reply_markup=get_main_menu_keyboard()
            )
    else:
        await callback.message.edit_text(
            text,
            reply_markup=get_main_menu_keyboard()
        )

    await callback.answer()
