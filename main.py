import os
import json
import threading
import builtins
import asyncio
import discord
from discord.ext import commands
from dashboard import app

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

bot.cached_data = {
    'moderation': {},
    'levels':     {},
    'counting':   {},
    'story':      {},
    'welcomer':   {},
    'youtube':    {}
}

def refresh_bot_cache():
    try:
        for key in bot.cached_data:
            bot.cached_data[key] = {}

        if os.path.exists('config.json'):
            with open('config.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                for gid, cfg in data.items():
                    bot.cached_data['moderation'][gid] = cfg
                    if 'welcomer' in cfg:
                        bot.cached_data['welcomer'][gid] = cfg['welcomer']

        for key in ['levels', 'counting', 'story']:
            filename = f"{key}.json"
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    bot.cached_data[key] = json.load(f)

        if os.path.exists('youtube.json'):
            with open('youtube.json', 'r', encoding='utf-8') as f:
                bot.cached_data['youtube'] = json.load(f)

        print("✅ Cache refreshed")
    except Exception as e:
        print(f"❌ Cache error: {e}")

builtins.refresh_bot_cache = refresh_bot_cache

@bot.event
async def setup_hook():
    if os.path.exists('cogs'):
        for filename in os.listdir('cogs'):
            if filename.endswith('.py') and not filename.startswith('__'):
                cog_name = f'cogs.{filename[:-3]}'
                try:
                    await bot.load_extension(cog_name)
                    print(f"✅ Loaded: {cog_name}")
                except Exception as e:
                    print(f"❌ Failed {cog_name}: {e}")
    refresh_bot_cache()

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Sync error: {e}")
    print(f"✅ {bot.user.name} is online!")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.playing, name="/help 🎮")
    )

def run_dashboard():
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Dashboard on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    app.config['BOT'] = bot
    flask_thread = threading.Thread(target=run_dashboard, daemon=True)
    flask_thread.start()

    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN not set!")
    else:
        print("🚀 Starting bot...")
        bot.run(token)
