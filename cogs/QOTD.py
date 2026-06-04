import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from datetime import date
from utils import load, save, err, ok
from gemini_guard import ask_gemini

_last_run_date: dict = {}

class QOTD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.qotd_scheduler.start()

    def cog_unload(self):
        self.qotd_scheduler.cancel()

    def get_config(self, gid):
        return load('config.json').get(str(gid), {}).get('qotd_settings', {})

    async def run_qotd(self, guild):
        gid   = str(guild.id)
        m_cfg = self.get_config(guild.id)
        if not m_cfg.get('enabled', True): return

        channel = guild.get_channel(int(m_cfg.get('channel_id', 0))) if m_cfg.get('channel_id') else None
        if not channel: return

        today = date.today()
        if _last_run_date.get(gid) == today:
            return
        _last_run_date[gid] = today

        try:
            ai_content = await ask_gemini("Generate a fun, engaging Question of the Day for a Smash Karts gaming community. No AI filler, just the question.")
        except Exception as e:
            print(f"[QOTD] Gemini error: {e}")
            ai_content = "What is your absolute favorite weapon in Smash Karts?"

        color_map = {"blue": discord.Color.blue(), "red": discord.Color.red(),
                     "orange": discord.Color.orange(), "purple": discord.Color.purple()}
        embed = discord.Embed(
            title="❓ Question Of The Day",
            description=m_cfg.get('announcement_message', f"> {ai_content}").replace("{content}", ai_content),
            color=color_map.get("red", discord.Color.red())
        )

        pings = "".join([f"<@&{rid}>" for rid in m_cfg.get('mentioned_roles', [])])
        msg   = await channel.send(content=pings if pings else None, embed=embed)

        try:
            thread = await msg.create_thread(
                name=m_cfg.get('thread_name', "💬 Discussion"),
                auto_archive_duration=int(m_cfg.get('archive_duration', 1440))
            )
            if int(m_cfg.get('slowmode', 0)) > 0:
                await thread.edit(slowmode_delay=int(m_cfg.get('slowmode', 0)))
        except: pass

    @tasks.loop(hours=24)
    async def qotd_scheduler(self):
        for g in self.bot.guilds:
            await self.run_qotd(g)
            await asyncio.sleep(2)

    @qotd_scheduler.before_loop
    async def before_qotd(self):
        await self.bot.wait_until_ready()
        print("⏳ QOTD task is staggering... waiting 25 seconds on startup.")
        await asyncio.sleep(25)

    @app_commands.command(name="trigger_qotd", description="Test QOTD instantly (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def trigger_qotd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        gid = str(interaction.guild.id)
        _last_run_date.pop(gid, None)
        await self.run_qotd(interaction.guild)
        await interaction.followup.send("✅ QOTD Posted!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(QOTD(bot))
