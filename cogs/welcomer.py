import discord
from discord.ext import commands
import json
import os

class WelcomerLeave(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def load_config(self):
        if os.path.exists('config.json'):
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_config(self, config):
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)

    # ══════════════════════════════════════════════════════════
    #  АВТОМАТИЧНИ СЪБИТИЯ (LISTENERS)
    # ══════════════════════════════════════════════════════════
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        cfg = self.load_config().get(str(guild.id), {}).get('welcomer', {})
        
        # 1. ПРОВЕРКА: Дали ГЛАВНИЯТ модул е активиран от сайта
        if not cfg.get('enabled', False):
            return

        # 2. ПРОВЕРКА: Дали под-модулът за Добре дошли (Welcome) е пуснат
        if not cfg.get('welcome_enabled', False):
            return

        # АВТОМАТИЧНИ РОЛИ (Auto-Role)
        if cfg.get('autorole_enabled', False):
            role_ids = [int(r.strip()) for r in cfg.get('autorole_roles', '').split(',') if r.strip().isdigit()]
            for r_id in role_ids:
                role = guild.get_role(r_id)
                if role:
                    try: await member.add_roles(role)
                    except discord.Forbidden: pass

        # ЛИЧНО СЪОБЩЕНИЕ (DM Message)
        if cfg.get('dm_enabled', False):
            dm_msg = cfg.get('dm_message', '').replace('{user.name}', member.name).replace('{server.name}', guild.name).replace('{member_count}', str(guild.member_count))
            if dm_msg:
                try: await member.send(dm_msg)
                except discord.Forbidden: pass

        # СЪОБЩЕНИЕ В КАНАЛ (Channel Message / Embed)
        channel_id = cfg.get('channel')
        if channel_id and str(channel_id).isdigit():
            channel = guild.get_channel(int(channel_id))
            if channel:
                raw_msg = cfg.get('message', 'Здравей {user.mention}, добре дошъл!')
                formatted_msg = raw_msg.replace('{user.mention}', member.mention).replace('{user.name}', member.name).replace('{server.name}', guild.name).replace('{member_count}', str(guild.member_count))
                
                if cfg.get('embed_enabled', False):
                    color_hex = cfg.get('embed_color', '#5865f2').replace('#', '')
                    color = int(color_hex, 16) if all(c in '0123456789abcdefABCDEF' for c in color_hex) else 0x5865f2
                    title = cfg.get('embed_title', '👋 Нов Потребител!').replace('{user.name}', member.name).replace('{server.name}', guild.name)
                    embed = discord.Embed(title=title, description=formatted_msg, color=color)
                    embed.set_thumbnail(url=member.display_avatar.url)
                    await channel.send(embed=embed)
                else:
                    await channel.send(formatted_msg)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild
        cfg = self.load_config().get(str(guild.id), {}).get('welcomer', {})
        
        # 1. ПРОВЕРКА: Дали ГЛАВНИЯТ модул е активиран от сайта
        if not cfg.get('enabled', False):
            return

        # 2. ПРОВЕРКА: Дали под-модулът за Напускане (Leave) е пуснат
        if not cfg.get('leave_enabled', False):
            return

        # СЪОБЩЕНИЕ ПРИ НАПУСКАНЕ В КАНАЛ
        channel_id = cfg.get('leave_channel')
        if channel_id and str(channel_id).isdigit():
            channel = guild.get_channel(int(channel_id))
            if channel:
                raw_msg = cfg.get('leave_message', '')
                formatted_msg = raw_msg.replace('{user.name}', member.name).replace('{server.name}', guild.name).replace('{member_count}', str(guild.member_count))
                
                if cfg.get('leave_embed_enabled', False):
                    color_hex = cfg.get('leave_embed_color', '#f23f43').replace('#', '')
                    color = int(color_hex, 16) if all(c in '0123456789abcdefABCDEF' for c in color_hex) else 0xf23f43
                    title = cfg.get('leave_embed_title', '😢 Потребител напусна').replace('{user.name}', member.name).replace('{server.name}', guild.name)
                    embed = discord.Embed(title=title, description=formatted_msg, color=color)
                    embed.set_thumbnail(url=member.display_avatar.url)
                    await channel.send(embed=embed)
                else:
                    await channel.send(formatted_msg)

def setup(bot):
    bot.add_cog(WelcomerLeave(bot))
