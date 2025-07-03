#!/bin/bash

cd /home/your-username/ChickenHawk

# (Optional) Create virtualenv
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the bot
python3 pubg_bot.py
