import discord
from discord.ext import commands, tasks
from discord import app_commands
import time
import random
from utils import load, save, ok, err, info

def xp_for_level(level):
    return 5 * (level ** 2) + 50 * level + 100

def total_xp_for_level(level):
    return sum(xp_for_level(i) for i in range(level))

def get_level(xp):
    level = 0
    while xp >= total_xp_for_level(level + 1):
        level += 1
        if level > 500: 
            break
    return level

def xp_progress(xp):
    level = get_level(xp)
    cur = xp - total_xp_for_level(level)
    needed = xp_for_level(level)
    return level, cur, needed

def generate_bar(cur, total, length=12):
    filled = round((cur / total) * length) if total > 0 else 0
    return "█" * filled + "░" * (length - filled)

XP_CD = {}       
VOICE_LAST_CHECK = {} 

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_xp_ticker.start()

    def cog_unload(self):
        self.voice_xp_ticker.cancel()

    def get_guild_settings(self, gid: str):
        cfg = load('config.json')
        if gid not in cfg:
            cfg[gid] = {}
        if 'leveling' not in cfg[gid]:
            cfg[gid]['leveling'] = {
                'level_up_msg': "🎉 GG {user}, you just leveled up to **Level {level}**! 🚀",
                'level_channel': ""
            }
        return cfg[gid]['leveling']

    async def handle_level_up(self, member, old_level, new_level, default_channel=None):
        if new_level > old_level:
            gid = str(member.guild.id)
            settings = self.get_guild_settings(gid)
            
            # Взимаме съобщението от таблото и заместваме таговете
            raw_msg = settings.get('level_up_msg', "🎉 GG {user}, you just leveled up to **Level {level}**! 🚀")
            msg = raw_msg.replace('{user}', member.mention).replace('{level}', str(new_level))
            
            # Проверяваме дали има зададен специфичен канал
            target_channel_id = settings.get('level_channel', '')
            send_channel = default_channel

            if target_channel_id and target_channel_id.isdigit():
                found_channel = member.guild.get_channel(int(target_channel_id))
                if found_channel:
                    send_channel = found_channel

            if send_channel:
                try:
                    await send_channel.send(msg)
                except Exception as e:
                    print(f"[Leveling] Could not send level up message: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        uid = str(message.author.id)
        gid = str(message.guild.id)
        now = time.time()

        if gid not in XP_CD: XP_CD[gid] = {}
        
        # 60 секунди cooldown за писане
        if now - XP_CD[gid].get(uid, 0) < 60:
            return

        XP_CD[gid][uid] = now
        lvl_data = load('levels.json')
        
        if gid not in lvl_data: lvl_data[gid] = {}
        if uid not in lvl_data[gid]: lvl_data[gid][uid] = {"xp": 0, "name": message.author.name}
        
        old_xp = lvl_data[gid][uid]["xp"]
        old_level = get_level(old_xp)
        
        # Добавяме рандъм XP
        lvl_data[gid][uid]["xp"] += random.randint(15, 25)
        lvl_data[gid][uid]["name"] = message.author.name
        
        new_level = get_level(lvl_data[gid][uid]["xp"])
        save('levels.json', lvl_data)

        # Проверка за качване на ниво
        await self.handle_level_up(message.author, old_level, new_level, default_channel=message.channel)

    @tasks.loop(minutes=2)
    async def voice_xp_ticker(self):
        lvl_data = load('levels.json')
        for guild in self.bot.guilds:
            gid = str(guild.id)
            if gid not in lvl_data: lvl_data[gid] = {}
            
            for voice_channel in guild.voice_channels:
                members = [m for m in voice_channel.members if not m.bot and not m.voice.self_deaf and not m.voice.self_mute]
                
                # Даваме XP само ако има повече от 1 човек в канала
                if len(members) < 2:
                    continue
                    
                for member in members:
                    uid = str(member.id)
                    if uid not in lvl_data[gid]: lvl_data[gid][uid] = {"xp": 0, "name": member.name}
                    
                    old_xp = lvl_data[gid][uid]["xp"]
                    old_level = get_level(old_xp)
                    
                    lvl_data[gid][uid]["xp"] += random.randint(10, 20)
                    lvl_data[gid][uid]["name"] = member.name
                    
                    new_level = get_level(lvl_data[gid][uid]["xp"])
                    
                    # Ако е вдигнал ниво във Voice, пращаме в default channel на сървъра
                    if new_level > old_level:
                        default_chan = guild.system_channel or next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
                        await self.handle_level_up(member, old_level, new_level, default_channel=default_chan)
                        
            save('levels.json', lvl_data)

    @voice_xp_ticker.before_loop
    async def before_voice_xp(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="rank", description="Check your current level progress status")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        gid = str(interaction.guild.id)
        uid = str(member.id)
        
        lvl_data = load('levels.json').get(gid, {}).get(uid, {"xp": 0})
        xp = lvl_data["xp"]
        level, cur_xp, needed_xp = xp_progress(xp)
        progress_bar = generate_bar(cur_xp, needed_xp)
        
        em = discord.Embed(title=f"📊 Rank Statistics for {member.name}", color=discord.Color.purple())
        em.set_thumbnail(url=member.display_avatar.url)
        em.add_field(name="✨ Current Level", value=f"`Level {level}`", inline=True)
        em.add_field(name="📈 Total XP Collected", value=f"`{xp} XP`", inline=True)
        em.add_field(name="🎯 Next Level Progress", value=f"`{cur_xp} / {needed_xp} XP`", inline=False)
        em.add_field(name="Progress Bar", value=f"`[{progress_bar}]`", inline=False)
        
        await interaction.response.send_message(embed=em)

async def setup(bot):
    await bot.add_cog(Leveling(bot))
