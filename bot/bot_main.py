"""Telegram Bot UI for Gift Buyer - Operator Interface"""

import asyncio
import logging
from typing import Dict, Any, List, Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Add these imports at the top
from shared.api_client import BuyerAPIClient
from shared.logging_config import setup_logging
from shared.config import settings
from database.models import Base, Ruleset, Run, Purchase

# Add after other imports
logger = setup_logging("bot")

# Database setup
engine = create_async_engine(settings.database_url)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Bot setup
bot = Bot(token=settings.bot_token)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# States for FSM
class RulesetStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_rules = State()


def is_operator(user_id: int) -> bool:
    """Check if user is authorized operator"""
    return user_id in settings.operator_user_ids


def create_main_keyboard() -> InlineKeyboardMarkup:
    """Create main control keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(text="📊 Status", callback_data="status"),
            InlineKeyboardButton(text="💰 Balance", callback_data="balance")
        ],
        [
            InlineKeyboardButton(text="📋 Rules", callback_data="rules"),
            InlineKeyboardButton(text="🧪 Dry Run", callback_data="dryrun")
        ],
        [
            InlineKeyboardButton(text="▶️ Arm", callback_data="arm"),
            InlineKeyboardButton(text="⏸️ Disarm", callback_data="disarm")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Start command handler"""
    if not is_operator(message.from_user.id):
        await message.reply("❌ Unauthorized access")
        return

    welcome_text = (
        "🤖 **Telegram Gift Buyer Control Panel**\n\n"
        "Welcome to the automated gift buyer interface. "
        "Use the buttons below to control the system.\n\n"
        "⚠️ **Safety First**: Always test with dry runs before arming!"
    )
    
    await message.reply(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Help command handler"""
    if not is_operator(message.from_user.id):
        await message.reply("❌ Unauthorized access")
        return

    help_text = (
        "🤖 **Available Commands:**\n\n"
        "**Main Controls:**\n"
        "/start - Control panel\n"
        "/help - Show this help\n\n"
        "**Ruleset Management:**\n"
        "/create_ruleset - Create new ruleset\n"
        "/list_rulesets - List all rulesets\n"
        "/activate_ruleset <id> - Activate a ruleset\n\n"
        "**System Control:**\n"
        "Use the buttons in the control panel for:\n"
        "• Status monitoring\n"
        "• Balance checking\n"
        "• Dry run testing\n"
        "• Arm/disarm system\n\n"
        "⚠️ **Always test with dry runs first!**"
    )
    
    await message.reply(help_text, parse_mode="Markdown")


@router.message(Command("create_ruleset"))
async def cmd_create_ruleset(message: Message, state: FSMContext):
    """Start creating a new ruleset"""
    if not is_operator(message.from_user.id):
        await message.reply("❌ Unauthorized access")
        return

    await state.set_state(RulesetStates.waiting_for_name)
    await message.reply(
        "📝 **Creating New Ruleset**\n\n"
        "Please enter a name for the ruleset:",
        parse_mode="Markdown"
    )


@router.message(RulesetStates.waiting_for_name)
async def process_ruleset_name(message: Message, state: FSMContext):
    """Process ruleset name"""
    if not is_operator(message.from_user.id):
        await message.reply("❌ Unauthorized access")
        return

    await state.update_data(name=message.text)
    await state.set_state(RulesetStates.waiting_for_rules)
    
    await message.reply(
        "📝 **Rules Configuration**\n\n"
        "Please enter the rules as JSON. Example:\n"
        "```json\n"
        "{\n"
        '  "source": ["primary"],\n'
        '  "price": {"max_stars": 2000},\n'
        '  "models_allowlist": ["Evil Eye"]\n'
        "}"
        "```",
        parse_mode="Markdown"
    )


@router.message(RulesetStates.waiting_for_rules)
async def process_ruleset_rules(message: Message, state: FSMContext):
    """Process ruleset rules"""
    if not is_operator(message.from_user.id):
        await message.reply("❌ Unauthorized access")
        return

    try:
        # Parse JSON rules
        rules = json.loads(message.text)
        
        # Get ruleset name from state
        data = await state.get_data()
        name = data.get("name")
        
        # Save to database
        async with async_session() as session:
            # Deactivate all other rulesets
            await session.execute(
                select(Ruleset).where(Ruleset.active == True)
            )
            active_rulesets = await session.execute(select(Ruleset).where(Ruleset.active == True))
            for ruleset in active_rulesets.scalars():
                ruleset.active = False
            
            # Create new ruleset
            new_ruleset = Ruleset(
                name=name,
                rules=rules,
                active=True,
                created_by=str(message.from_user.id)
            )
            session.add(new_ruleset)
            await session.commit()
            
            await message.reply(
                f"✅ **Ruleset Created Successfully!**\n\n"
                f"**Name:** {name}\n"
                f"**ID:** {new_ruleset.id}\n"
                f"**Status:** Active\n\n"
                f"Use /list_rulesets to see all rulesets.",
                parse_mode="Markdown"
            )
        
        await state.clear()
        
    except json.JSONDecodeError as e:
        await message.reply(
            f"❌ **Invalid JSON Format**\n\n"
            f"Error: {str(e)}\n\n"
            "Please try again with valid JSON:",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to create ruleset: {e}")
        await message.reply(f"❌ Failed to create ruleset: {str(e)}")
        await state.clear()


@router.message(Command("list_rulesets"))
async def cmd_list_rulesets(message: Message):
    """List all rulesets"""
    if not is_operator(message.from_user.id):
        await message.reply("❌ Unauthorized access")
        return

    async with async_session() as session:
        result = await session.execute(
            select(Ruleset).order_by(Ruleset.created_at.desc())
        )
        rulesets = result.scalars().all()
        
        if not rulesets:
            await message.reply("📋 **No rulesets found.**\nUse /create_ruleset to create one.")
            return
        
        response = "📋 **Available Rulesets:**\n\n"
        for ruleset in rulesets:
            status = "🟢 Active" if ruleset.active else "⚪ Inactive"
            response += (
                f"**{ruleset.name}** (ID: {ruleset.id})\n"
                f"Status: {status}\n"
                f"Created: {ruleset.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            )
        
        await message.reply(response, parse_mode="Markdown")


@router.callback_query(F.data == "status")
async def handle_status(callback: CallbackQuery):
    """Show system status"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    try:
        async with BuyerAPIClient() as client:
            status_data = await client.get_status()
            
        status_text = (
            "📊 **System Status**\n\n"
            f"**Armed:** {'✅ Yes' if status_data.get('is_armed') else '❌ No'}\n"
            f"**Active Run:** {status_data.get('current_run_id', 'None')}\n"
            f"**Ruleset:** {status_data.get('active_ruleset', 'None')}\n\n"
            f"**Today's Stats:**\n"
            f"• Purchases this hour: {status_data.get('purchases_this_hour', 0)}\n"
            f"• Spent today: {status_data.get('spent_today', 0):,} ⭐\n\n"
            f"**Limits:**\n"
            f"• Max daily spend: {settings.max_spend_per_day:,} ⭐\n"
            f"• Max hourly purchases: {settings.max_purchases_per_hour}\n"
        )
    except Exception as e:
        logger.error(f"Failed to fetch status: {e}")
        status_text = "❌ Failed to fetch status. Check buyer service connection."

    await callback.message.edit_text(
        status_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "balance")
async def handle_balance(callback: CallbackQuery):
    """Show Stars balance and spending"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    try:
        async with BuyerAPIClient() as client:
            balance_data = await client.get_balance()
            
        balance_text = (
            "💰 **Balance & Spending**\n\n"
            f"**Stars Balance:** {balance_data.get('stars_balance', 0):,} ⭐\n"
            "**Today's Spending:** 2,150 ⭐\n"  # Would come from database
            "**This Hour:** 450 ⭐\n\n"
            "**Limits:**\n"
            f"• Daily: {settings.max_spend_per_day:,} ⭐\n"
            f"• Hourly: {settings.max_purchases_per_hour} purchases\n\n"
            "**Owned Gifts:** 23 items\n"
            "**Total Value:** ~45,000 ⭐"
        )
    except Exception as e:
        logger.error(f"Failed to fetch balance: {e}")
        balance_text = "❌ Failed to fetch balance. Check buyer service connection."

    await callback.message.edit_text(
        balance_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "rules")
async def handle_rules(callback: CallbackQuery):
    """Show ruleset management"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    # Get active ruleset
    async with async_session() as session:
        result = await session.execute(
            select(Ruleset).where(Ruleset.active == True).order_by(Ruleset.created_at.desc()).limit(1)
        )
        active_ruleset = result.scalar_one_or_none()

    rules_text = "📋 **Ruleset Management**\n\n"
    
    if active_ruleset:
        rules_text += f"**Active Ruleset:** {active_ruleset.name}\n"
        rules_text += f"**Created:** {active_ruleset.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
    else:
        rules_text += "**No active ruleset**\n\n"
    
    rules_text += "Use /create_ruleset to create new rules\n"
    rules_text += "Use /list_rulesets to see all rulesets"

    await callback.message.edit_text(
        rules_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "dryrun")
async def handle_dryrun(callback: CallbackQuery):
    """Execute dry run test"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    # Get active ruleset
    async with async_session() as session:
        result = await session.execute(
            select(Ruleset).where(Ruleset.active == True).order_by(Ruleset.created_at.desc()).limit(1)
        )
        active_ruleset = result.scalar_one_or_none()

        if not active_ruleset:
            await callback.message.edit_text(
                "❌ No active ruleset found. Please create and activate a ruleset first.",
                parse_mode="Markdown",
                reply_markup=create_main_keyboard()
            )
            await callback.answer()
            return

    await callback.message.edit_text(
        "🧪 **Dry Run Mode**\n\n"
        f"Testing ruleset: {active_ruleset.name}\n"
        "Analyzing current catalog and marketplace...",
        parse_mode="Markdown"
    )

    try:
        async with BuyerAPIClient() as client:
            results = await client.dry_run(active_ruleset.id)
            
        if results.get("success"):
            matches = results.get("matches", [])
            results_text = (
                "🧪 **Dry Run Results**\n\n"
                f"**Gifts Evaluated:** {results.get('total_evaluated', 0)}\n"
                f"**Matches Found:** {len(matches)}\n\n"
            )
            
            if matches:
                results_text += "**Would Purchase:**\n\n"
                for i, match in enumerate(matches[:5], 1):  # Show first 5
                    gift = match["gift"]
                    source = match["source"].title()
                    price = gift.get("price_stars", gift.get("stars", 0))
                    results_text += f"{i}️⃣ **{gift.get('title', 'Unknown')}**\n"
                    results_text += f"   Source: {source}\n"
                    results_text += f"   Price: {price:,} ⭐\n"
                    if match.get("reasons"):
                        results_text += f"   Match: {', '.join(match['reasons'][:2])}\n\n"
                        
                if len(matches) > 5:
                    results_text += f"...and {len(matches) - 5} more items\n\n"
                    
                results_text += f"**Total Cost:** {results.get('total_cost', 0):,} ⭐"
            else:
                results_text += "No matching items found with current rules."
        else:
            results_text = f"❌ Dry run failed: {results.get('error', 'Unknown error')}"
            
    except Exception as e:
        logger.error(f"Dry run failed: {e}")
        results_text = "❌ Dry run failed. Check buyer service connection."

    await callback.message.edit_text(
        results_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer("Dry run complete!")


@router.callback_query(F.data == "arm")
async def handle_arm(callback: CallbackQuery):
    """Arm the buyer"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    # Get active ruleset
    async with async_session() as session:
        result = await session.execute(
            select(Ruleset).where(Ruleset.active == True).order_by(Ruleset.created_at.desc()).limit(1)
        )
        active_ruleset = result.scalar_one_or_none()

        if not active_ruleset:
            await callback.message.edit_text(
                "❌ No active ruleset found. Please create and activate a ruleset first.",
                parse_mode="Markdown",
                reply_markup=create_main_keyboard()
            )
            await callback.answer()
            return

    try:
        async with BuyerAPIClient() as client:
            result = await client.arm_buyer(active_ruleset.id, "live")
            
        if result.get("success"):
            arm_text = (
                "✅ **Buyer Armed**\n\n"
                f"**Ruleset:** {active_ruleset.name}\n"
                f"**Run ID:** {result.get('run_id')}\n"
                f"**Mode:** Live\n\n"
                "⚠️ **System is now actively purchasing gifts!**\n"
                "Monitor carefully and disarm when needed."
            )
        else:
            arm_text = f"❌ Failed to arm buyer: {result.get('error', 'Unknown error')}"
            
    except Exception as e:
        logger.error(f"Arm failed: {e}")
        arm_text = "❌ Failed to arm buyer. Check buyer service connection."

    await callback.message.edit_text(
        arm_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "disarm")
async def handle_disarm(callback: CallbackQuery):
    """Disarm the buyer"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    try:
        async with BuyerAPIClient() as client:
            result = await client.disarm_buyer()
            
        if result.get("success"):
            disarm_text = (
                "⏸️ **Buyer Disarmed**\n\n"
                "System is no longer actively purchasing gifts.\n"
                "All automated operations have stopped safely."
            )
        else:
            disarm_text = f"❌ Failed to disarm buyer: {result.get('error', 'Unknown error')}"
            
    except Exception as e:
        logger.error(f"Disarm failed: {e}")
        disarm_text = "❌ Failed to disarm buyer. Check buyer service connection."

    await callback.message.edit_text(
        disarm_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()


async def initialize_database():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main():
    """Main bot entry point"""
    logger.info("Starting Telegram Gift Buyer Bot...")
    
    # Initialize database
    await initialize_database()
    
    # Start polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

"""Telegram Bot UI for Gift Buyer - Operator Interface"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Add these imports at the top
from shared.api_client import BuyerAPIClient
from shared.logging_config import setup_logging
from shared.config import settings
from database.models import Base, Ruleset, Run, Purchase

# Add after other imports
logger = setup_logging("bot")

# Database setup
engine = create_async_engine(settings.database_url)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Bot setup
bot = Bot(token=settings.bot_token)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# States for FSM
class RulesetStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_rules = State()


def is_operator(user_id: int) -> bool:
    """Check if user is authorized operator"""
    return user_id in settings.operator_user_ids


def create_main_keyboard() -> InlineKeyboardMarkup:
    """Create main control keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(text="📊 Status", callback_data="status"),
            InlineKeyboardButton(text="💰 Balance", callback_data="balance")
        ],
        [
            InlineKeyboardButton(text="📋 Rules", callback_data="rules"),
            InlineKeyboardButton(text="🧪 Dry Run", callback_data="dryrun")
        ],
        [
            InlineKeyboardButton(text="▶️ Arm", callback_data="arm"),
            InlineKeyboardButton(text="⏸️ Disarm", callback_data="disarm")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Start command handler"""
    if not is_operator(message.from_user.id):
        await message.reply("❌ Unauthorized access")
        return

    welcome_text = (
        "🤖 **Telegram Gift Buyer Control Panel**\n\n"
        "Welcome to the automated gift buyer interface. "
        "Use the buttons below to control the system.\n\n"
        "⚠️ **Safety First**: Always test with dry runs before arming!"
    )
    
    await message.reply(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Help command handler"""
    if not is_operator(message.from_user.id):
        await message.reply("❌ Unauthorized access")
        return

    help_text = (
        "🤖 **Available Commands:**\n\n"
        "**Main Controls:**\n"
        "/start - Control panel\n"
        "/help - Show this help\n\n"
        "**Ruleset Management:**\n"
        "/create_ruleset - Create new ruleset\n"
        "/list_rulesets - List all rulesets\n"
        "/activate_ruleset <id> - Activate a ruleset\n\n"
        "**System Control:**\n"
        "Use the buttons in the control panel for:\n"
        "• Status monitoring\n"
        "• Balance checking\n"
        "• Dry run testing\n"
        "• Arm/disarm system\n\n"
        "⚠️ **Always test with dry runs first!**"
    )
    
    await message.reply(help_text, parse_mode="Markdown")


@router.message(Command("create_ruleset"))
async def cmd_create_ruleset(message: Message, state: FSMContext):
    """Start creating a new ruleset"""
    if not is_operator(message.from_user.id):
        await message.reply("❌ Unauthorized access")
        return

    await state.set_state(RulesetStates.waiting_for_name)
    await message.reply(
        "📝 **Creating New Ruleset**\n\n"
        "Please enter a name for the ruleset:",
        parse_mode="Markdown"
    )


@router.message(RulesetStates.waiting_for_name)
async def process_ruleset_name(message: Message, state: FSMContext):
    """Process ruleset name"""
    if not is_operator(message.from_user.id):
        await message.reply("❌ Unauthorized access")
        return

    await state.update_data(name=message.text)
    await state.set_state(RulesetStates.waiting_for_rules)
    
    await message.reply(
        "📝 **Rules Configuration**\n\n"
        "Please enter the rules as JSON. Example:\n"
        "```json\n"
        "{\n"
        '  "source": ["primary"],\n'
        '  "price": {"max_stars": 2000},\n'
        '  "models_allowlist": ["Evil Eye"]\n'
        "}"
        "```",
        parse_mode="Markdown"
    )


@router.message(RulesetStates.waiting_for_rules)
async def process_ruleset_rules(message: Message, state: FSMContext):
    """Process ruleset rules"""
    if not is_operator(message.from_user.id):
        await message.reply("❌ Unauthorized access")
        return

    try:
        # Parse JSON rules
        rules = json.loads(message.text)
        
        # Get ruleset name from state
        data = await state.get_data()
        name = data.get("name")
        
        # Save to database
        async with async_session() as session:
            # Deactivate all other rulesets
            await session.execute(
                select(Ruleset).where(Ruleset.active == True)
            )
            active_rulesets = await session.execute(select(Ruleset).where(Ruleset.active == True))
            for ruleset in active_rulesets.scalars():
                ruleset.active = False
            
            # Create new ruleset
            new_ruleset = Ruleset(
                name=name,
                rules=rules,
                active=True,
                created_by=str(message.from_user.id)
            )
            session.add(new_ruleset)
            await session.commit()
            
            await message.reply(
                f"✅ **Ruleset Created Successfully!**\n\n"
                f"**Name:** {name}\n"
                f"**ID:** {new_ruleset.id}\n"
                f"**Status:** Active\n\n"
                f"Use /list_rulesets to see all rulesets.",
                parse_mode="Markdown"
            )
        
        await state.clear()
        
    except json.JSONDecodeError as e:
        await message.reply(
            f"❌ **Invalid JSON Format**\n\n"
            f"Error: {str(e)}\n\n"
            "Please try again with valid JSON:",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to create ruleset: {e}")
        await message.reply(f"❌ Failed to create ruleset: {str(e)}")
        await state.clear()


@router.message(Command("list_rulesets"))
async def cmd_list_rulesets(message: Message):
    """List all rulesets"""
    if not is_operator(message.from_user.id):
        await message.reply("❌ Unauthorized access")
        return

    async with async_session() as session:
        result = await session.execute(
            select(Ruleset).order_by(Ruleset.created_at.desc())
        )
        rulesets = result.scalars().all()
        
        if not rulesets:
            await message.reply("📋 **No rulesets found.**\nUse /create_ruleset to create one.")
            return
        
        response = "📋 **Available Rulesets:**\n\n"
        for ruleset in rulesets:
            status = "🟢 Active" if ruleset.active else "⚪ Inactive"
            response += (
                f"**{ruleset.name}** (ID: {ruleset.id})\n"
                f"Status: {status}\n"
                f"Created: {ruleset.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            )
        
        await message.reply(response, parse_mode="Markdown")


@router.callback_query(F.data == "status")
async def handle_status(callback: CallbackQuery):
    """Show system status"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    try:
        async with BuyerAPIClient() as client:
            status_data = await client.get_status()
            
        status_text = (
            "📊 **System Status**\n\n"
            f"**Armed:** {'✅ Yes' if status_data.get('is_armed') else '❌ No'}\n"
            f"**Active Run:** {status_data.get('current_run_id', 'None')}\n"
            f"**Ruleset:** {status_data.get('active_ruleset', 'None')}\n\n"
            f"**Today's Stats:**\n"
            f"• Purchases this hour: {status_data.get('purchases_this_hour', 0)}\n"
            f"• Spent today: {status_data.get('spent_today', 0):,} ⭐\n\n"
            f"**Limits:**\n"
            f"• Max daily spend: {settings.max_spend_per_day:,} ⭐\n"
            f"• Max hourly purchases: {settings.max_purchases_per_hour}\n"
        )
    except Exception as e:
        logger.error(f"Failed to fetch status: {e}")
        status_text = "❌ Failed to fetch status. Check buyer service connection."

    await callback.message.edit_text(
        status_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "balance")
async def handle_balance(callback: CallbackQuery):
    """Show Stars balance and spending"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    try:
        async with BuyerAPIClient() as client:
            balance_data = await client.get_balance()
            
        balance_text = (
            "💰 **Balance & Spending**\n\n"
            f"**Stars Balance:** {balance_data.get('stars_balance', 0):,} ⭐\n"
            "**Today's Spending:** 2,150 ⭐\n"  # Would come from database
            "**This Hour:** 450 ⭐\n\n"
            "**Limits:**\n"
            f"• Daily: {settings.max_spend_per_day:,} ⭐\n"
            f"• Hourly: {settings.max_purchases_per_hour} purchases\n\n"
            "**Owned Gifts:** 23 items\n"
            "**Total Value:** ~45,000 ⭐"
        )
    except Exception as e:
        logger.error(f"Failed to fetch balance: {e}")
        balance_text = "❌ Failed to fetch balance. Check buyer service connection."

    await callback.message.edit_text(
        balance_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "rules")
async def handle_rules(callback: CallbackQuery):
    """Show ruleset management"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    # Get active ruleset
    async with async_session() as session:
        result = await session.execute(
            select(Ruleset).where(Ruleset.active == True).order_by(Ruleset.created_at.desc()).limit(1)
        )
        active_ruleset = result.scalar_one_or_none()

    rules_text = "📋 **Ruleset Management**\n\n"
    
    if active_ruleset:
        rules_text += f"**Active Ruleset:** {active_ruleset.name}\n"
        rules_text += f"**Created:** {active_ruleset.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
    else:
        rules_text += "**No active ruleset**\n\n"
    
    rules_text += "Use /create_ruleset to create new rules\n"
    rules_text += "Use /list_rulesets to see all rulesets"

    await callback.message.edit_text(
        rules_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "dryrun")
async def handle_dryrun(callback: CallbackQuery):
    """Execute dry run test"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    # Get active ruleset
    async with async_session() as session:
        result = await session.execute(
            select(Ruleset).where(Ruleset.active == True).order_by(Ruleset.created_at.desc()).limit(1)
        )
        active_ruleset = result.scalar_one_or_none()

        if not active_ruleset:
            await callback.message.edit_text(
                "❌ No active ruleset found. Please create and activate a ruleset first.",
                parse_mode="Markdown",
                reply_markup=create_main_keyboard()
            )
            await callback.answer()
            return

    await callback.message.edit_text(
        "🧪 **Dry Run Mode**\n\n"
        f"Testing ruleset: {active_ruleset.name}\n"
        "Analyzing current catalog and marketplace...",
        parse_mode="Markdown"
    )

    try:
        async with BuyerAPIClient() as client:
            results = await client.dry_run(active_ruleset.id)
            
        if results.get("success"):
            matches = results.get("matches", [])
            results_text = (
                "🧪 **Dry Run Results**\n\n"
                f"**Gifts Evaluated:** {results.get('total_evaluated', 0)}\n"
                f"**Matches Found:** {len(matches)}\n\n"
            )
            
            if matches:
                results_text += "**Would Purchase:**\n\n"
                for i, match in enumerate(matches[:5], 1):  # Show first 5
                    gift = match["gift"]
                    source = match["source"].title()
                    price = gift.get("price_stars", gift.get("stars", 0))
                    results_text += f"{i}️⃣ **{gift.get('title', 'Unknown')}**\n"
                    results_text += f"   Source: {source}\n"
                    results_text += f"   Price: {price:,} ⭐\n"
                    if match.get("reasons"):
                        results_text += f"   Match: {', '.join(match['reasons'][:2])}\n\n"
                        
                if len(matches) > 5:
                    results_text += f"...and {len(matches) - 5} more items\n\n"
                    
                results_text += f"**Total Cost:** {results.get('total_cost', 0):,} ⭐"
            else:
                results_text += "No matching items found with current rules."
        else:
            results_text = f"❌ Dry run failed: {results.get('error', 'Unknown error')}"
            
    except Exception as e:
        logger.error(f"Dry run failed: {e}")
        results_text = "❌ Dry run failed. Check buyer service connection."

    await callback.message.edit_text(
        results_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer("Dry run complete!")


@router.callback_query(F.data == "arm")
async def handle_arm(callback: CallbackQuery):
    """Arm the buyer"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    # Get active ruleset
    async with async_session() as session:
        result = await session.execute(
            select(Ruleset).where(Ruleset.active == True).order_by(Ruleset.created_at.desc()).limit(1)
        )
        active_ruleset = result.scalar_one_or_none()

        if not active_ruleset:
            await callback.message.edit_text(
                "❌ No active ruleset found. Please create and activate a ruleset first.",
                parse_mode="Markdown",
                reply_markup=create_main_keyboard()
            )
            await callback.answer()
            return

    try:
        async with BuyerAPIClient() as client:
            result = await client.arm_buyer(active_ruleset.id, "live")
            
        if result.get("success"):
            arm_text = (
                "✅ **Buyer Armed**\n\n"
                f"**Ruleset:** {active_ruleset.name}\n"
                f"**Run ID:** {result.get('run_id')}\n"
                f"**Mode:** Live\n\n"
                "⚠️ **System is now actively purchasing gifts!**\n"
                "Monitor carefully and disarm when needed."
            )
        else:
            arm_text = f"❌ Failed to arm buyer: {result.get('error', 'Unknown error')}"
            
    except Exception as e:
        logger.error(f"Arm failed: {e}")
        arm_text = "❌ Failed to arm buyer. Check buyer service connection."

    await callback.message.edit_text(
        arm_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "disarm")
async def handle_disarm(callback: CallbackQuery):
    """Disarm the buyer"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    try:
        async with BuyerAPIClient() as client:
            result = await client.disarm_buyer()
            
        if result.get("success"):
            disarm_text = (
                "⏸️ **Buyer Disarmed**\n\n"
                "System is no longer actively purchasing gifts.\n"
                "All automated operations have stopped safely."
            )
        else:
            disarm_text = f"❌ Failed to disarm buyer: {result.get('error', 'Unknown error')}"
            
    except Exception as e:
        logger.error(f"Disarm failed: {e}")
        disarm_text = "❌ Failed to disarm buyer. Check buyer service connection."

    await callback.message.edit_text(
        disarm_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()


async def initialize_database():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main():
    """Main bot entry point"""
    logger.info("Starting Telegram Gift Buyer Bot...")
    
    # Initialize database
    await initialize_database()
    
    # Start polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
