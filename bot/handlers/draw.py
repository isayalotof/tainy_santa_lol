from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
import logging
import asyncio

from bot.database import Database
from bot.keyboards.inline import (
    get_room_menu_keyboard,
    get_confirm_draw_keyboard,
    get_back_to_room_keyboard
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

    # Check participant count
    participant_count = db.get_participant_count(room_id)
    if participant_count < 2:
        await callback.answer(
            "❌ Для жеребьёвки нужно минимум 2 участника",
            show_alert=True
        )
        return

    await callback.message.edit_text(
        f"🎲 Провести жеребьёвку для комнаты '{room['room_name']}'?\n\n"
        f"👥 Участников: {participant_count}\n\n"
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

    # Check participant count
    participant_count = db.get_participant_count(room_id)
    if participant_count < 2:
        await callback.answer(
            "❌ Для жеребьёвки нужно минимум 2 участника",
            show_alert=True
        )
        return

    await callback.message.edit_text(
        f"♻️ Перепровести жеребьёвку для комнаты '{room['room_name']}'?\n\n"
        f"👥 Участников: {participant_count}\n\n"
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
        # Get only participating members
        members = db.get_room_participants(room_id)
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

        # Notify all participants (parallel)
        async def send_notification(giver_id: int, receiver_id: int):
            """Send notification to a single user"""
            try:
                # Get receiver info
                receiver = db.get_user(receiver_id)
                if not receiver:
                    return False

                receiver_name = receiver['first_name']
                if receiver['last_name']:
                    receiver_name += f" {receiver['last_name']}"
                if receiver['username']:
                    receiver_name += f" (@{receiver['username']})"

                message_text = (
                    f"🎁 Результаты жеребьёвки в комнате '{room['room_name']}'!\n\n"
                    f"Ты даришь подарок:\n"
                    f"👤 {receiver_name}\n\n"
                )
                
                if room.get('price_range'):
                    message_text += f"💰 Ценовой диапазон: {room['price_range']}\n\n"
                
                # Get receiver's wishlist
                wishlist_items = db.get_wishlist_items(room_id, receiver_id)
                
                if wishlist_items:
                    message_text += "📋 Вишлист получателя:\n\n"
                    for i, item in enumerate(wishlist_items, 1):
                        message_text += f"{i}. {item['item_name']}"
                        if item['item_url']:
                            message_text += f"\n   🔗 {item['item_url']}"
                        message_text += "\n"
                    message_text += "\n"
                else:
                    message_text += "📋 Вишлист получателя пуст\n\n"
                
                if room.get('deadline'):
                    message_text += f"⏰ Дедлайн жеребьёвки: {room['deadline']}\n\n"
                
                if room.get('gift_time') or room.get('gift_location'):
                    message_text += "📅 Информация о вручении:\n"
                    if room.get('gift_time'):
                        message_text += f"   📅 Время: {room['gift_time']}\n"
                    if room.get('gift_location'):
                        message_text += f"   📍 Место: {room['gift_location']}\n"
                    message_text += "\n"
                
                message_text += f"🤫 Никому не говори!"
                
                # Check message length (Telegram limit is 4096)
                if len(message_text) > 4096:
                    # Truncate wishlist if too long
                    base_length = len(message_text) - len("📋 Вишлист получателя:\n\n") - len("\n\n")
                    if wishlist_items:
                        available = 4096 - base_length - 100  # Safety margin
                        wishlist_text = "📋 Вишлист получателя:\n\n"
                        for i, item in enumerate(wishlist_items, 1):
                            item_text = f"{i}. {item['item_name']}"
                            if item['item_url']:
                                item_text += f"\n   🔗 {item['item_url']}"
                            item_text += "\n"
                            if len(wishlist_text) + len(item_text) > available:
                                wishlist_text += f"... и ещё {len(wishlist_items) - i + 1} пунктов\n"
                                break
                            wishlist_text += item_text
                        wishlist_text += "\n"
                        # Rebuild message
                        message_text = (
                            f"🎁 Результаты жеребьёвки в комнате '{room['room_name']}'!\n\n"
                            f"Ты даришь подарок:\n"
                            f"👤 {receiver_name}\n\n"
                        )
                        if room.get('price_range'):
                            message_text += f"💰 Ценовой диапазон: {room['price_range']}\n\n"
                        message_text += wishlist_text
                        if room.get('deadline'):
                            message_text += f"⏰ Дедлайн жеребьёвки: {room['deadline']}\n\n"
                        if room.get('gift_time') or room.get('gift_location'):
                            message_text += "📅 Информация о вручении:\n"
                            if room.get('gift_time'):
                                message_text += f"   📅 Время: {room['gift_time']}\n"
                            if room.get('gift_location'):
                                message_text += f"   📍 Место: {room['gift_location']}\n"
                            message_text += "\n"
                        message_text += f"🤫 Никому не говори!"
                
                await bot.send_message(
                    giver_id, 
                    message_text,
                    disable_web_page_preview=False
                )
                return True
            except Exception as e:
                logger.error(f"Failed to notify user {giver_id}: {e}")
                return False

        # Send notifications in parallel (batch of 10 at a time to avoid rate limits)
        all_results = []
        tasks = []
        for giver_id, receiver_id in assignments.items():
            tasks.append(send_notification(giver_id, receiver_id))
            # Process in batches of 10
            if len(tasks) >= 10:
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                all_results.extend(batch_results)
                tasks = []
                # Small delay between batches to avoid rate limits
                await asyncio.sleep(0.1)
        
        # Process remaining tasks
        if tasks:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            all_results.extend(batch_results)
        
        success_count = sum(1 for r in all_results if r is True)
        fail_count = len(all_results) - success_count

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

    receiver_name = assignment['first_name']
    if assignment['last_name']:
        receiver_name += f" {assignment['last_name']}"
    if assignment['username']:
        receiver_name += f" (@{assignment['username']})"

    text = (
        f"🎁 Комната '{room['room_name']}'\n\n"
        f"Ты даришь подарок:\n"
        f"👤 {receiver_name}\n\n"
    )
    
    if room.get('price_range'):
        text += f"💰 Ценовой диапазон: {room['price_range']}\n\n"
    
    # Get receiver's wishlist
    receiver_id = assignment['user_id']
    wishlist_items = db.get_wishlist_items(room_id, receiver_id)
    
    if wishlist_items:
        text += "📋 Вишлист получателя:\n\n"
        for i, item in enumerate(wishlist_items, 1):
            text += f"{i}. {item['item_name']}"
            if item['item_url']:
                text += f"\n   🔗 {item['item_url']}"
            text += "\n"
        text += "\n"
    else:
        text += "📋 Вишлист получателя пуст\n\n"
    
    if room.get('deadline'):
        text += f"⏰ Дедлайн жеребьёвки: {room['deadline']}\n\n"
    
    if room.get('gift_time') or room.get('gift_location'):
        text += "📅 Информация о вручении:\n"
        if room.get('gift_time'):
            text += f"   📅 Время: {room['gift_time']}\n"
        if room.get('gift_location'):
            text += f"   📍 Место: {room['gift_location']}\n"
        text += "\n"
    
    text += f"🤫 Никому не говори!"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_to_room_keyboard(room_id),
        disable_web_page_preview=False
    )
    await callback.answer()
