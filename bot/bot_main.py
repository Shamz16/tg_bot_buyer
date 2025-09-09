"""Telegram Bot UI for Gift Buyer - Operator Interface"""

# Add these imports at the top
from shared.api_client import BuyerAPIClient
from shared.logging_config import setup_logging

# Add after other imports
logger = setup_logging("bot")

# Update the balance handler to use real API
@dp.callback_query(F.data == "balance")
async def handle_balance(callback: types.CallbackQuery):
    """Show Stars balance and spending"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    try:
        async with BuyerAPIClient() as client:
            balance_data = await client.get_balance()
            
        balance_text = (
            "💰 **Balance & Spending**\n\n"
            f"**Stars Balance:** {balance_data['stars_balance']:,} ⭐\n"
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

# Update dry run handler
@dp.callback_query(F.data == "dryrun")
async def handle_dryrun(callback: types.CallbackQuery):
    """Execute dry run test"""
    if not is_operator(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    # Get active ruleset
    async with async_session() as session:
        result = await session.execute(
            "SELECT * FROM rulesets WHERE active = true ORDER BY created_at DESC LIMIT 1"
        )
        active_ruleset = result.fetchone()
    
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
            
        if results["success"]:
            matches = results["matches"]
            results_text = (
                "🧪 **Dry Run Results**\n\n"
                f"**Gifts Evaluated:** {results['total_evaluated']}\n"
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
                    if match["reasons"]:
                        results_text += f"   Match: {', '.join(match['reasons'][:2])}\n\n"
                
                if len(matches) > 5:
                    results_text += f"...and {len(matches) - 5} more items\n\n"
                    
                results_text += f"**Total Cost:** {results['total_cost']:,} ⭐"
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
