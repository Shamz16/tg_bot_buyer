# Telegram Gift Buyer Bot

## Overview
Automated Telegram gift buyer that discovers collectible gifts and marketplace listings, evaluates them against configurable rules, and automatically purchases qualifying items with strict safety limits.

## Architecture

### Components
1. **Bot UI** (`bot/`) - Telegram Bot API interface for operators
2. **Buyer Service** (`buyer/`) - MTProto client for discovery and purchasing
3. **Rules Engine** (`shared/`) - Configurable evaluation logic
4. **Database** (`database/`) - PostgreSQL for persistence

## Quick Start

### 1. Setup Environment
```bash
# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your credentials:
# - BOT_TOKEN from @BotFather
# - API_ID and API_HASH from https://my.telegram.org
# - PHONE_NUMBER for MTProto session
# - OPERATOR_USER_IDS (comma-separated Telegram user IDs)
```

### 2. Initialize Database
```bash
# Using PostgreSQL (recommended)
createdb tg_gifts

# Or use SQLite by changing DATABASE_URL in .env:
# DATABASE_URL=sqlite+aiosqlite:///./tg_gifts.db
```

### 3. Start Services
```bash
# Run both bot and buyer services
python start.py

# Or run separately:
python bot/bot_main.py      # Bot UI only
python buyer/buyer_service.py  # Buyer service only
```

## Bot Commands

### Operator Commands
- `/start` - Main control panel
- **📊 Status** - System status and active runs
- **💰 Balance** - Stars balance and spending
- **📋 Rules** - Manage rulesets
- **🧪 Dry Run** - Test rules without spending
- **▶️ Arm** - Enable live purchases
- **⏸️ Disarm** - Stop automated purchases

## Rules Configuration

### Example Ruleset
```json
{
  "source": ["primary", "resale"],
  "price": {
    "max_stars": 2500,
    "min_stars": 100
  },
  "rarity": {
    "symbols_allowlist": ["Coin", "Crown"],
    "backdrop_allowlist": ["Aurora", "Nebula"],
    "numbers_allowlist": [1, 7, 77, 777]
  },
  "models_allowlist": ["Evil Eye", "Space Cat"],
  "sale_window": {
    "utc_start": "2025-09-08T17:59:50Z",
    "utc_end": "2025-09-08T18:10:00Z"
  },
  "resale": {
    "max_price_stars": 1800,
    "min_discount_pct": 10
  },
  "safety": {
    "max_purchases_per_hour": 3,
    "max_spend_per_day": 6000,
    "cooldown_ms_between_purchases": 800
  }
}
```

### Rule Fields
- **source**: Allow primary drops, resale, or both
- **price**: Min/max Stars price range
- **rarity**: Filter by backdrop, symbol, number attributes
- **models**: Allowlist or blocklist specific models
- **sale_window**: Time window for primary drops
- **resale**: Resale-specific price and discount rules
- **safety**: Rate limits and spend caps

## Safety Features

### Spend Limits
- Daily spend cap (configurable)
- Hourly purchase limit
- Per-purchase cooldown

### Pre-flight Checks
- Re-fetch gift before purchase
- Verify price hasn't changed
- Check availability status

### Audit Trail
- All operations logged to database
- Purchase receipts with transaction IDs
- Evaluation reasons for dry runs

## Database Schema

### Core Tables
- `rulesets` - Rule configurations
- `runs` - Execution sessions
- `purchases` - Purchase records
- `op_events` - Operation event log
- `inventory` - Owned gifts tracking
- `audit_log` - User action audit

## Development

### Project Structure
```
tg-gift-buyer/
├── bot/           # Telegram Bot UI
├── buyer/         # MTProto buyer service
├── shared/        # Shared utilities
├── database/      # Database models
├── sessions/      # Telethon sessions
├── logs/          # Log files
└── tests/         # Test suite
```

### Testing
```bash
# Run dry run test
python -c "from bot.bot_main import *; asyncio.run(dry_run(1))"

# Test rules engine
python -c "from shared.rules_engine import *; print(create_example_rules())"
```

## Security Notes

1. **Session Protection**: Telethon sessions are encrypted and stored in `sessions/`
2. **API Credentials**: Never commit `.env` file
3. **Operator Access**: Only whitelisted user IDs can control the bot
4. **Spend Caps**: Always configure reasonable limits

## Monitoring

### Metrics
- Gifts evaluated per minute
- Matches found per hour
- Success/failure rate
- Spend tracking

### Logs
- Structured logging to `logs/` directory
- Separate files for bot and buyer
- Configurable log levels

## Deployment

### Production Checklist
1. ✅ Set `ENVIRONMENT=production` in `.env`
2. ✅ Configure proper database (PostgreSQL)
3. ✅ Set conservative safety limits
4. ✅ Enable monitoring/alerting
5. ✅ Backup Telethon sessions
6. ✅ Test with dry runs first

### Using PM2
```bash
# Install PM2
npm install -g pm2

# Start services
pm2 start bot/bot_main.py --name tg-bot --interpreter python3
pm2 start buyer/buyer_service.py --name tg-buyer --interpreter python3

# Monitor
pm2 logs
pm2 monit
```

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify API_ID and API_HASH
   - Check phone number format (+country code)
   - Delete session file and re-authenticate

2. **Database Connection**
   - Check DATABASE_URL format
   - Ensure PostgreSQL is running
   - Verify credentials

3. **Purchase Failures**
   - Check Stars balance
   - Verify gift availability
   - Review safety limits

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review dry run results
3. Verify rule configuration
4. Check database audit log

## License
Private - Not for distribution

## Disclaimer
This bot uses official Telegram APIs only. Ensure compliance with Telegram Terms of Service. Use at your own risk.