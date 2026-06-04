import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from datetime import date
from utils import load, save, err, ok
from gemini_guard import ask_gemini

_last_run_date: dict = {}

class FOTD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.fotd_scheduler.start()

    def cog_unload(self):
        self.fotd_scheduler.cancel()

    def get_config(self, gid):
        return load('config.json').get(str(gid), {}).get('fotd_settings', {})

    async def run_fotd(self, guild):
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
            ai_content = await ask_gemini("Generate a mind-blowing, fun Fact of the Day about gaming, history, or crazy tech. Keep it under 3 sentences. Just the fact, no AI intro.")
        except Exception as e:
            print(f"[FOTD] Gemini error: {e}")
            ai_content = "Did you know the first video game tournament was held in 1972 at Stanford University?"

        color_map = {"blue": discord.Color.blue(), "red": discord.Color.red(),
                     "orange": discord.Color.orange(), "purple": discord.Color.purple()}
        embed = discord.Embed(
            title="🧠 Fact Of The Day",
            description=m_cfg.get('announcement_message', f"> {ai_content}").replace("{content}", ai_content),
            color=color_map.get("blue", discord.Color.blue())
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
    async def fotd_scheduler(self):
        for g in self.bot.guilds:
            await self.run_fotd(g)
            await asyncio.sleep(2)

    @fotd_scheduler.before_loop
    async def before_fotd(self):
        await self.bot.wait_until_ready()
        print("⏳ FOTD task is staggering... waiting 5 seconds on startup.")
        await asyncio.sleep(5)

    @app_commands.command(name="trigger_fotd", description="Test FOTD instantly (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def trigger_fotd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        gid = str(interaction.guild.id)
        _last_run_date.pop(gid, None)
        await self.run_fotd(interaction.guild)
        await interaction.followup.send("✅ FOTD Posted!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(FOTD(bot))
