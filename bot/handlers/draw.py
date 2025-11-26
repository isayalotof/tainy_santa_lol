from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
import logging

from bot.database import Database
from bot.keyboards.inline import (
    get_room_menu_keyboard,
    get_confirm_draw_keyboard,
    get_back_to_room_keyboard,
    get_receiver_profile_keyboard
)
from bot.utils.draw_algorithm import secret_santa_draw, validate_draw

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("draw_"))
async def start_draw(callback: CallbackQuery, db: Database):
    """Start draw confirmation"""
    room_id = int(callback.data.split("_")[1])

    room = db.get_room_by_id(room_id)
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return

    # Check if user is admin
    if room['admin_id'] != callback.from_user.id:
        await callback.answer("❌ Только администратор может провести жеребьёвку", show_alert=True)
        return

    # Check member count
    member_count = db.get_room_member_count(room_id)
    if member_count < 2:
        await callback.answer(
            "❌ Для жеребьёвки нужно минимум 2 участника",
            show_alert=True
        )
        return

    await callback.message.edit_text(
        f"🎲 Провести жеребьёвку для комнаты '{room['room_name']}'?\n\n"
        f"👥 Участников: {member_count}\n\n"
        f"⚠️ После жеребьёвки каждый участник получит уведомление о том, кому он дарит подарок.",
        reply_markup=get_confirm_draw_keyboard(room_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("redraw_"))
async def start_redraw(callback: CallbackQuery, db: Database):
    """Start redraw confirmation"""
    room_id = int(callback.data.split("_")[1])

    room = db.get_room_by_id(room_id)
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return

    # Check if user is admin
    if room['admin_id'] != callback.from_user.id:
        await callback.answer("❌ Только администратор может провести жеребьёвку", show_alert=True)
        return

    # Check member count
    member_count = db.get_room_member_count(room_id)
    if member_count < 2:
        await callback.answer(
            "❌ Для жеребьёвки нужно минимум 2 участника",
            show_alert=True
        )
        return

    await callback.message.edit_text(
        f"♻️ Перепровести жеребьёвку для комнаты '{room['room_name']}'?\n\n"
        f"👥 Участников: {member_count}\n\n"
        f"⚠️ Предыдущие назначения будут удалены!\n"
        f"Каждый участник получит новое уведомление.",
        reply_markup=get_confirm_draw_keyboard(room_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_draw_"))
async def confirm_draw(callback: CallbackQuery, db: Database, bot: Bot):
    """Perform Secret Santa draw"""
    room_id = int(callback.data.split("_")[2])

    room = db.get_room_by_id(room_id)
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return

    # Check if user is admin
    if room['admin_id'] != callback.from_user.id:
        await callback.answer("❌ Только администратор может провести жеребьёвку", show_alert=True)
        return

    try:
        # Get all room members
        members = db.get_room_members(room_id)
        member_ids = [member['user_id'] for member in members]

        if len(member_ids) < 2:
            await callback.answer("❌ Недостаточно участников", show_alert=True)
            return

        # Delete old assignments if redraw
        if room['is_drawn']:
            db.delete_room_assignments(room_id)

        # Generate Secret Santa assignments
        assignments = secret_santa_draw(member_ids)

        # Validate assignments
        if not validate_draw(assignments):
            raise ValueError("Generated invalid Secret Santa assignment")

        # Save assignments to database
        for giver_id, receiver_id in assignments.items():
            db.create_assignment(room_id, giver_id, receiver_id)

        # Mark room as drawn
        db.update_room_drawn(room_id, True)

        # Notify all participants
        success_count = 0
        fail_count = 0

        for giver_id, receiver_id in assignments.items():
            # Get receiver info with profile
            receiver = db.get_user_profile(receiver_id)
            if not receiver:
                continue

            receiver_name = receiver['first_name']
            if receiver['last_name']:
                receiver_name += f" {receiver['last_name']}"
            if receiver['username']:
                receiver_name += f" (@{receiver['username']})"

            # Build notification message
            msg_text = (
                f"🎁 Результаты жеребьёвки в комнате '{room['room_name']}'!\n\n"
                f"Ты даришь подарок:\n"
                f"👤 {receiver_name}\n\n"
            )

            # Add profile info
            if receiver.get('bio'):
                msg_text += f"📝 О получателе:\n{receiver['bio'][:150]}...\n\n" if len(receiver['bio']) > 150 else f"📝 О получателе:\n{receiver['bio']}\n\n"

            if receiver.get('wishlist'):
                msg_text += f"🎁 Список желаний:\n{receiver['wishlist'][:150]}...\n\n" if len(receiver['wishlist']) > 150 else f"🎁 Список желаний:\n{receiver['wishlist']}\n\n"

            if not receiver.get('bio') and not receiver.get('wishlist'):
                msg_text += "ℹ️ Получатель ещё не заполнил профиль.\n\n"

            msg_text += "🤫 Никому не говори!\n\n💡 Посмотреть подробный профиль получателя можно в разделе комнаты."

            try:
                # Send photo if receiver has one, otherwise send text message
                if receiver.get('photo_file_id'):
                    await bot.send_photo(
                        giver_id,
                        photo=receiver['photo_file_id'],
                        caption=msg_text
                    )
                else:
                    await bot.send_message(giver_id, msg_text)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to notify user {giver_id}: {e}")
                fail_count += 1

        # Notify admin about results
        result_text = (
            f"✅ Жеребьёвка проведена!\n\n"
            f"👥 Участников: {len(member_ids)}\n"
            f"✅ Уведомлено: {success_count}\n"
        )

        if fail_count > 0:
            result_text += f"❌ Не удалось уведомить: {fail_count}\n"

        result_text += "\n💡 Все участники получили уведомления о своих получателях."

        await callback.message.edit_text(
            result_text,
            reply_markup=get_room_menu_keyboard(room_id, is_admin=True, is_drawn=True)
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error during draw: {e}")
        await callback.answer(
            "❌ Произошла ошибка при проведении жеребьёвки",
            show_alert=True
        )


@router.callback_query(F.data.startswith("my_receiver_"))
async def show_my_receiver(callback: CallbackQuery, db: Database):
    """Show user's Secret Santa receiver"""
    room_id = int(callback.data.split("_")[2])

    room = db.get_room_by_id(room_id)
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return

    # Check if user is member
    if not db.is_user_in_room(room_id, callback.from_user.id):
        await callback.answer("❌ Ты не состоишь в этой комнате", show_alert=True)
        return

    # Check if draw was done
    if not room['is_drawn']:
        await callback.answer("❌ Жеребьёвка ещё не проведена", show_alert=True)
        return

    # Get assignment
    assignment = db.get_assignment(room_id, callback.from_user.id)
    if not assignment:
        await callback.answer("❌ Назначение не найдено", show_alert=True)
        return

    receiver_id = assignment['receiver_id']
    receiver_name = assignment['first_name']
    if assignment['last_name']:
        receiver_name += f" {assignment['last_name']}"
    if assignment['username']:
        receiver_name += f" (@{assignment['username']})"

    # Get receiver profile
    receiver_profile = db.get_user_profile(receiver_id)

    text = (
        f"🎁 Комната '{room['room_name']}'\n\n"
        f"Ты даришь подарок:\n"
        f"👤 {receiver_name}\n\n"
    )

    # Add profile info if available
    if receiver_profile:
        if receiver_profile.get('bio'):
            text += f"📝 О получателе:\n{receiver_profile['bio'][:200]}...\n\n" if len(receiver_profile['bio']) > 200 else f"📝 О получателе:\n{receiver_profile['bio']}\n\n"

        if receiver_profile.get('wishlist'):
            text += f"🎁 Список желаний:\n{receiver_profile['wishlist'][:200]}...\n\n" if len(receiver_profile['wishlist']) > 200 else f"🎁 Список желаний:\n{receiver_profile['wishlist']}\n\n"

        if not receiver_profile.get('bio') and not receiver_profile.get('wishlist'):
            text += "ℹ️ Получатель ещё не заполнил профиль.\n\n"

    text += "🤫 Никому не говори!"

    await callback.message.edit_text(
        text,
        reply_markup=get_receiver_profile_keyboard(room_id, receiver_id)
    )
    await callback.answer()
