import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from datetime import date
from utils import load, save, err, ok
from gemini_guard import ask_gemini

_last_run_date: dict = {}

class SOTD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sotd_scheduler.start()

    def cog_unload(self):
        self.sotd_scheduler.cancel()

    def get_config(self, gid):
        return load('config.json').get(str(gid), {}).get('sotd_settings', {})

    async def run_sotd(self, guild):
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
            ai_content = await ask_gemini("Recommend a high-energy song (Phonk, EDM, Hip-Hop) for a fast gaming lobby. Format: '**Song** by *Artist* - 1 sentence vibe.' No AI intro.")
        except Exception as e:
            print(f"[SOTD] Gemini error: {e}")
            ai_content = "**Metamorphosis** by *INTERWORLD* - Ultimate high-speed drifts and rocket kills."

        color_map = {"blue": discord.Color.blue(), "red": discord.Color.red(),
                     "orange": discord.Color.orange(), "purple": discord.Color.purple()}
        embed = discord.Embed(
            title="🎵 Song Of The Day",
            description=m_cfg.get('announcement_message', f"> {ai_content}").replace("{content}", ai_content),
            color=color_map.get("purple", discord.Color.purple())
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
    async def sotd_scheduler(self):
        for g in self.bot.guilds:
            await self.run_sotd(g)
            await asyncio.sleep(2)

    @sotd_scheduler.before_loop
    async def before_sotd(self):
        await self.bot.wait_until_ready()
        print("⏳ SOTD task is staggering... waiting 65 seconds on startup.")
        await asyncio.sleep(65)

    @app_commands.command(name="trigger_sotd", description="Test SOTD instantly (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def trigger_sotd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        gid = str(interaction.guild.id)
        _last_run_date.pop(gid, None)
        await self.run_sotd(interaction.guild)
        await interaction.followup.send("✅ SOTD Posted!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(SOTD(bot))
