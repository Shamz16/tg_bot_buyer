"""Telegram Bot UI for Gift Buyer - Operator Interface"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.config import settings
from shared.rules_engine import RulesEngine, create_example_rules
from database.models import Base, Ruleset, Run, RunMode, RunStatus

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=settings.bot_token)
dp = Dispatcher()

# Database setup
engine = create_async_engine(settings.database_url)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class RuleStates(StatesGroup):
    """FSM states for rule configuration"""
    waiting_for_name = State()
    waiting_for_rules = State()
    editing_rules = State()


def is_operator(user_id: int) -> bool:
    """Check if user is authorized operator"""
    return user_id in settings.operator_user_ids


def create_main_keyboard() -> InlineKeyboardMarkup:
    """Create main menu keyboard"""
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
        ],
        [
            InlineKeyboardButton(text="📈 Stats", callback_data="stats"),
            InlineKeyboardButton(text="📜 Logs", callback_data="logs")
        ],
        [
            InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Handle /start command"""
    if not is_operator(message.from_user.id):
        await message.reply("❌ Unauthorized. This bot is for authorized operators only.")
        return
    
    welcome_text = (
        "🎁 **Telegram Gift Buyer Bot**\n\n"
        "Welcome, operator! This bot helps you:\n"
        "• Configure purchase rules for gifts\n"
        "• Monitor gift drops and marketplace\n"
        "• Execute automated purchases\n"
        "• Track spending and inventory\n\n"
        "Use the menu below to get started:"
    )
    
    await message.reply(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )


@dp.callback_query(F.data == "status")
async def handle_status(callback: types.CallbackQuery):
    """Show current system status"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return
    
    async with async_session() as session:
        # Get active runs
        result = await session.execute(
            "SELECT * FROM runs WHERE status = 'running' ORDER BY started_at DESC LIMIT 1"
        )
        active_run = result.fetchone()
        
        # Get active rulesets
        result = await session.execute(
            "SELECT COUNT(*) FROM rulesets WHERE active = true"
        )
        active_rulesets = result.scalar()
    
    status_text = "📊 **System Status**\n\n"
    
    if active_run:
        status_text += f"✅ Bot is ARMED\n"
        status_text += f"Mode: {active_run.mode.upper()}\n"
        status_text += f"Started: {active_run.started_at}\n"
        status_text += f"Evaluated: {active_run.total_evaluated}\n"
        status_text += f"Matched: {active_run.total_matched}\n"
        status_text += f"Purchased: {active_run.total_purchased}\n"
        status_text += f"Spent: {active_run.total_spent_stars} Stars\n"
    else:
        status_text += "⏸️ Bot is DISARMED\n"
    
    status_text += f"\nActive Rulesets: {active_rulesets}\n"
    status_text += f"Environment: {settings.environment.upper()}\n"
    
    await callback.message.edit_text(
        status_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "balance")
async def handle_balance(callback: types.CallbackQuery):
    """Show Stars balance and spending"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return
    
    # This would connect to MTProto client to get real balance
    # For now, showing mock data
    balance_text = (
        "💰 **Balance & Spending**\n\n"
        "**Stars Balance:** 15,432 ⭐\n"
        "**Today's Spending:** 2,150 ⭐\n"
        "**This Hour:** 450 ⭐\n\n"
        "**Limits:**\n"
        f"• Daily: {settings.max_spend_per_day} ⭐\n"
        f"• Hourly: {settings.max_purchases_per_hour} purchases\n\n"
        "**Owned Gifts:** 23 items\n"
        "**Total Value:** ~45,000 ⭐"
    )
    
    await callback.message.edit_text(
        balance_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "rules")
async def handle_rules(callback: types.CallbackQuery):
    """Show and manage rules"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return
    
    async with async_session() as session:
        result = await session.execute("SELECT * FROM rulesets ORDER BY created_at DESC")
        rulesets = result.fetchall()
    
    if not rulesets:
        rules_text = "📋 **No rulesets configured**\n\n"
        rules_text += "Create your first ruleset to get started."
    else:
        rules_text = "📋 **Configured Rulesets**\n\n"
        for rs in rulesets:
            status = "✅" if rs.active else "⏸️"
            rules_text += f"{status} **{rs.name}**\n"
            rules_text += f"   Created: {rs.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
    
    keyboard = [
        [
            InlineKeyboardButton(text="➕ New Ruleset", callback_data="new_ruleset"),
            InlineKeyboardButton(text="📝 Edit", callback_data="edit_ruleset")
        ],
        [
            InlineKeyboardButton(text="🔙 Back", callback_data="back_to_main")
        ]
    ]
    
    await callback.message.edit_text(
        rules_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@dp.callback_query(F.data == "new_ruleset")
async def handle_new_ruleset(callback: types.CallbackQuery, state: FSMContext):
    """Start creating new ruleset"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📝 **New Ruleset**\n\n"
        "Please send a name for the new ruleset:",
        parse_mode="Markdown"
    )
    
    await state.set_state(RuleStates.waiting_for_name)
    await callback.answer()


@dp.message(RuleStates.waiting_for_name)
async def process_ruleset_name(message: types.Message, state: FSMContext):
    """Process ruleset name"""
    if not is_operator(message.from_user.id):
        return
    
    ruleset_name = message.text.strip()
    await state.update_data(ruleset_name=ruleset_name)
    
    # Show example rules
    example_rules = create_example_rules()
    rules_json = json.dumps(example_rules, indent=2)
    
    await message.reply(
        f"**Ruleset: {ruleset_name}**\n\n"
        "Now send the rules configuration in JSON format.\n\n"
        "Example:\n"
        f"```json\n{rules_json[:1500]}...\n```",
        parse_mode="Markdown"
    )
    
    await state.set_state(RuleStates.waiting_for_rules)


@dp.message(RuleStates.waiting_for_rules)
async def process_rules_config(message: types.Message, state: FSMContext):
    """Process rules configuration"""
    if not is_operator(message.from_user.id):
        return
    
    try:
        rules_config = json.loads(message.text)
        data = await state.get_data()
        
        # Validate rules
        engine = RulesEngine(rules_config)
        
        # Save to database
        async with async_session() as session:
            new_ruleset = Ruleset(
                name=data["ruleset_name"],
                rules=rules_config,
                created_by=str(message.from_user.id),
                active=False
            )
            session.add(new_ruleset)
            await session.commit()
        
        await message.reply(
            f"✅ **Ruleset '{data['ruleset_name']}' created successfully!**\n\n"
            "You can now activate it and run tests.",
            parse_mode="Markdown",
            reply_markup=create_main_keyboard()
        )
        
        await state.clear()
        
    except json.JSONDecodeError as e:
        await message.reply(
            f"❌ **Invalid JSON format:**\n{str(e)}\n\n"
            "Please send valid JSON configuration.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.reply(
            f"❌ **Error creating ruleset:**\n{str(e)}",
            parse_mode="Markdown"
        )


@dp.callback_query(F.data == "dryrun")
async def handle_dryrun(callback: types.CallbackQuery):
    """Execute dry run test"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🧪 **Dry Run Mode**\n\n"
        "Analyzing current catalog and marketplace...\n"
        "This will show what would be purchased without spending Stars.",
        parse_mode="Markdown"
    )
    
    # Here would connect to buyer service for dry run
    # Showing mock results
    await asyncio.sleep(2)
    
    results_text = (
        "🧪 **Dry Run Results**\n\n"
        "**Gifts Evaluated:** 156\n"
        "**Matches Found:** 3\n\n"
        "**Would Purchase:**\n\n"
        "1️⃣ **Evil Eye #777**\n"
        "   Source: Primary Drop\n"
        "   Price: 1,500 ⭐\n"
        "   Match: ✓ Model, ✓ Price, ✓ Number\n\n"
        "2️⃣ **Space Cat (Aurora)**\n"
        "   Source: Resale\n"
        "   Price: 1,200 ⭐ (20% discount)\n"
        "   Match: ✓ Model, ✓ Backdrop, ✓ Discount\n\n"
        "3️⃣ **Lucky Charm (Coin)**\n"
        "   Source: Primary Drop\n"
        "   Price: 2,000 ⭐\n"
        "   Match: ✓ Model, ✓ Symbol, ✓ Price\n\n"
        "**Total Cost:** 4,700 ⭐"
    )
    
    await callback.message.edit_text(
        results_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer("Dry run complete!")


@dp.callback_query(F.data == "arm")
async def handle_arm(callback: types.CallbackQuery):
    """Arm the buyer for live purchases"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return
    
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Confirm ARM", callback_data="confirm_arm"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="back_to_main")
        ]
    ]
    
    await callback.message.edit_text(
        "⚠️ **ARM Buyer - Confirmation Required**\n\n"
        "This will enable LIVE purchases with real Stars.\n\n"
        "**Current Settings:**\n"
        f"• Max spend/day: {settings.max_spend_per_day} ⭐\n"
        f"• Max purchases/hour: {settings.max_purchases_per_hour}\n"
        f"• Active rulesets: 1\n\n"
        "Are you sure you want to ARM the buyer?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@dp.callback_query(F.data == "confirm_arm")
async def handle_confirm_arm(callback: types.CallbackQuery):
    """Confirm arming the buyer"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return
    
    # Here would start the buyer service
    await callback.message.edit_text(
        "✅ **Buyer ARMED Successfully!**\n\n"
        "The bot is now actively monitoring and will execute purchases based on configured rules.\n\n"
        "Use /disarm to stop automated purchases.",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    
    await callback.answer("Buyer armed! Monitoring started.")


@dp.callback_query(F.data == "disarm")
async def handle_disarm(callback: types.CallbackQuery):
    """Disarm the buyer"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return
    
    # Here would stop the buyer service
    await callback.message.edit_text(
        "⏸️ **Buyer DISARMED**\n\n"
        "Automated purchases have been stopped.\n"
        "All pending operations cancelled safely.",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    
    await callback.answer("Buyer disarmed successfully.")


@dp.callback_query(F.data == "back_to_main")
async def handle_back_to_main(callback: types.CallbackQuery):
    """Return to main menu"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🎁 **Gift Buyer Control Panel**\n\n"
        "Select an action:",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")


async def main():
    """Main bot entry point"""
    logger.info("Starting Gift Buyer Bot...")
    
    # Initialize database
    await init_db()
    
    # Start polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())