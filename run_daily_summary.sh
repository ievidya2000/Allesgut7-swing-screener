#!/bin/bash
# Daily performance summary script
# Run via cron: 0 11 * * * /home/chalderaaa/swing-screener/screener_v2/run_daily_summary.sh
# (11:00 UTC = 18:00 WIB)

cd "$(dirname "$0")"

# Activate virtual environment if exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Set email config via environment (optional, overrides email_config.json)
# export SMTP_USERNAME="your-email@gmail.com"
# export SMTP_PASSWORD="your-app-password"
# export FROM_EMAIL="your-email@gmail.com"
# export TO_EMAIL="recipient@example.com"

# Run daily summary
python -m performance.run daily >> logs/cron.log 2>&1

# Exit with the exit code of the python command
exit $?
