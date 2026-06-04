import builtins
import discord
import ast
import operator as op
from discord.ext import commands
from discord import app_commands
from utils import load, save, ok, err, info, medal

# ── БЕЗОПАСЕН МАТЕМАТИЧЕСКИ ПАРСЕР ────────────────────────
ALLOWED_OPERATORS = {
    ast.Add: op.add, 
    ast.Sub: op.sub, 
    ast.Mult: op.mul,
    ast.Div: op.truediv, 
    ast.Pow: op.pow, 
    ast.USub: op.neg,
    ast.UAdd: op.pos
}

def safe_math_eval(expr):
    """
    Парсва безопасно математически низове без риск от изпълнение на зловреден код (RCE).
    Връща число (int/float) или None, ако изразът е невалиден или съдържа текст.
    """
    try:
        node = ast.parse(expr, mode='eval').body
        def _eval(n):
            if isinstance(n, ast.Constant): # Числа (напр. 5, 3.14)
                return n.value
            elif isinstance(n, ast.BinOp): # Операции (напр. +, -, *, /, **)
                return ALLOWED_OPERATORS[type(n.op)](_eval(n.left), _eval(n.right))
            elif isinstance(n, ast.UnaryOp): # Унарни оператори (напр. -5)
                return ALLOWED_OPERATORS[type(n.op)](_eval(n.operand))
            else:
                raise ValueError("Неразрешена операция")
        return _eval(node)
    except:
        return None

# ── КРАЙ НА ПАРСЕРА ───────────────────────────────────────

def get_cd(gid):
    data = load('counting.json')
    gid = str(gid)
    if gid not in data:
        data[gid] = {
            "channel": None, "enabled": False, "count": 0,
            "last_user": None, "high_score": 0,
            "allow_same_user": False, "shame_role": False,
            "shame_role_name": "💀 Count Ruiner",
            "delete_invalid": False, 
            "goal": None, "user_stats": {}
        }
        save('counting.json', data)
    return data, gid

class Counting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def apply_shame(self, msg, d):
        if not d.get('shame_role'): return
        name = d.get('shame_role_name', '💀 Count Ruiner')
        role = discord.utils.get(msg.guild.roles, name=name)
        if not role:
            try: role = await msg.guild.create_role(name=name, color=discord.Color.dark_red())
            except: return
        try: await msg.author.add_roles(role)
        except: pass

    async def count_fail(self, msg, d, uid, title, desc):
        reached = d['count']
        if reached > d['high_score']: d['high_score'] = reached
        d['user_stats'].setdefault(uid, {'correct': 0, 'fails': 0})
        d['user_stats'][uid]['fails'] += 1
        d['count'] = 0
        d['last_user'] = None
        
        em = discord.Embed(title=f"💀 {title}", color=discord.Color.red())
        em.description = desc
        em.add_field(name="📉 Reached",    value=f"**{reached}**")
        em.add_field(name="🏆 High Score", value=f"**{d['high_score']}**")
        em.set_footer(text="Next number is 1!")
        em.set_thumbnail(url=msg.author.display_avatar.url)
        
        try: await msg.add_reaction("💀")
        except: pass
        
        await msg.channel.send(embed=em)
        await self.apply_shame(msg, d)

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot or not msg.guild: return
        data = load('counting.json')
        gid = str(msg.guild.id)
        if gid not in data: return
        d = data[gid]
        
        if not d.get('enabled') or not d.get('channel'): return
        try:
            if msg.channel.id != int(d['channel']): return
        except ValueError: return

        uid = str(msg.author.id)

        # Проверка за роля срам
        if d.get('shame_role', False):
            shame_name = d.get('shame_role_name', '💀 Count Ruiner')
            has_shame = discord.utils.get(msg.author.roles, name=shame_name)
            if has_shame:
                if d.get('delete_invalid', False):
                    try: await msg.delete()
                    except: pass
                return 

        # Премахваме интервалите, за да улесним математическия парсер (напр. "2 + 3" става "2+3")
        content = msg.content.strip().replace(' ', '')

        # Изчисляване на математическото уравнение
        result = safe_math_eval(content)

        # Ако резултатът е None, значи съобщението е обикновен текст или развалена математика
        if result is None:
            if d.get('delete_invalid', False):
                try: await msg.delete()
                except: pass
            return

        # Обръщаме резултата в цяло число (защото деления като 4/2 връщат 2.0)
        try:
            number = int(result)
        except (ValueError, TypeError, OverflowError):
            if d.get('delete_invalid', False):
                try: await msg.delete()
                except: pass
            return

        d['user_stats'].setdefault(uid, {'correct': 0, 'fails': 0})
        expected = d['count'] + 1

        # Проверка за броене два пъти подред
        if not d.get('allow_same_user', False) and d['last_user'] == uid:
            if d.get('delete_invalid', False):
                try: await msg.delete()
                except: pass
            await self.count_fail(msg, d, uid, "Counted Twice in a Row!", f"{msg.author.mention} counted twice in a row!")
            save('counting.json', data)
            return

        # Проверка за грешен математически резултат
        if number != expected:
            if d.get('delete_invalid', False):
                try: await msg.delete()
                except: pass
            
            # Показваме оригиналното уравнение и какво всъщност е трябвало да бъде числото
            await self.count_fail(
                msg, d, uid, 
                "Wrong Calculation!", 
                f"{msg.author.mention} submitted `{msg.content}`, which equals **{number}**, but the next expected number was **{expected}**!"
            )
            save('counting.json', data)
            return

        # ✅ Всичко е вярно!
        d['count'] = number
        d['last_user'] = uid
        d['user_stats'][uid]['correct'] += 1
        if number > d['high_score']: d['high_score'] = number

        if number == d.get('goal'):
            try: await msg.add_reaction("🏆")
            except: pass
            await msg.channel.send(embed=discord.Embed(title="🏆 GOAL REACHED!", description=f"🎊 The server reached **{number}**!", color=discord.Color.gold()))
        elif number % 100 == 0:
            try: await msg.add_reaction("🎉")
            except: pass
            await msg.channel.send(embed=discord.Embed(title=f"🎉 {number}!", description=f"Count hit **{number}**! Keep going!", color=discord.Color.gold()))
        elif number % 50 == 0:
            try: await msg.add_reaction("🔥")
            except: pass
        else:
            try: await msg.add_reaction("✅")
            except: pass

        save('counting.json', data)

    # ══════════════════════════════════════════════════════
    #  SLASH COMMANDS
    # ══════════════════════════════════════════════════════
    counting = app_commands.Group(name="counting", description="Counting game commands")

    @counting.command(name="setchannel", description="Set the counting channel")
    @app_commands.describe(channel="The channel for counting")
    @app_commands.default_permissions(manage_channels=True)
    async def setchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data, gid = get_cd(interaction.guild.id)
        data[gid]['channel'] = channel.id
        data[gid]['enabled'] = True
        save('counting.json', data)
        await interaction.response.send_message(embed=ok("Counting Channel Set!", f"Counting in {channel.mention} — now **enabled**!"))

    @counting.command(name="enable", description="Enable the counting game")
    @app_commands.default_permissions(manage_channels=True)
    async def enable(self, interaction: discord.Interaction):
        data, gid = get_cd(interaction.guild.id)
        if not data[gid]['channel']:
            return await interaction.response.send_message(embed=err("Set a channel first: `/counting setchannel`"))
        data[gid]['enabled'] = True
        save('counting.json', data)
        await interaction.response.send_message(embed=ok("Counting Enabled!"))

    @counting.command(name="disable", description="Disable the counting game")
    @app_commands.default_permissions(manage_channels=True)
    async def disable(self, interaction: discord.Interaction):
        data, gid = get_cd(interaction.guild.id)
        data[gid]['enabled'] = False
        save('counting.json', data)
        await interaction.response.send_message(embed=ok("Counting Disabled."))

    @counting.command(name="shamerole", description="Manage the shame role")
    @app_commands.describe(action="on / off / name / remove", name="New name for the role (if action=name)")
    @app_commands.default_permissions(manage_roles=True)
    async def shamerole(self, interaction: discord.Interaction, action: str, name: str = None):
        data, gid = get_cd(interaction.guild.id)
        if action == 'on':
            data[gid]['shame_role'] = True
            save('counting.json', data)
            await interaction.response.send_message(embed=ok("Shame Role On!", f"Ruiners get **{data[gid]['shame_role_name']}** and will be muted from counting!"))
        elif action == 'off':
            data[gid]['shame_role'] = False
            save('counting.json', data)
            await interaction.response.send_message(embed=ok("Shame Role Off."))
        elif action == 'name':
            if not name: return await interaction.response.send_message(embed=err("Provide a name!"))
            data[gid]['shame_role_name'] = name
            save('counting.json', data)
            await interaction.response.send_message(embed=ok("Renamed!", f"Now called **{name}**"))
        elif action == 'remove':
            role = discord.utils.get(interaction.guild.roles, name=data[gid]['shame_role_name'])
            if role:
                count = 0
                for member in interaction.guild.members:
                    if role in member.roles:
                        await member.remove_roles(role)
                        count += 1
                await interaction.response.send_message(embed=ok("Cleared!", f"Removed from **{count}** members."))
            else:
                await interaction.response.send_message(embed=err("Role not found!"))
        else:
            await interaction.response.send_message(embed=err("Use: `on`, `off`, `name`, `remove`"))

    @counting.command(name="allowsameuser", description="Allow the same user to count twice in a row")
    @app_commands.describe(toggle="on or off")
    @app_commands.default_permissions(manage_channels=True)
    async def allowsameuser(self, interaction: discord.Interaction, toggle: str):
        data, gid = get_cd(interaction.guild.id)
        val = toggle.lower() in ('on','true','yes')
        data[gid]['allow_same_user'] = val
        save('counting.json', data)
        await interaction.response.send_message(embed=ok(f"Same User {'Allowed ✅' if val else 'Blocked ❌'}"))

    @counting.command(name="goal", description="Set a counting goal")
    @app_commands.describe(number="The goal number")
    @app_commands.default_permissions(manage_channels=True)
    async def goal(self, interaction: discord.Interaction, number: int):
        if number < 1: return await interaction.response.send_message(embed=err("Goal must be positive!"))
        data, gid = get_cd(interaction.guild.id)
        data[gid]['goal'] = number
        save('counting.json', data)
        await interaction.response.send_message(embed=ok(f"Goal Set: {number}!", "The server will celebrate when you reach it! 🎉"))

    @counting.command(name="reset", description="Reset the count to 0")
    @app_commands.default_permissions(administrator=True)
    async def reset(self, interaction: discord.Interaction):
        data, gid = get_cd(interaction.guild.id)
        old = data[gid]['count']
        data[gid]['count'] = 0
        data[gid]['last_user'] = None
        save('counting.json', data)
        await interaction.response.send_message(embed=ok("Count Reset!", f"Reset from **{old}** to **0**."))

    @counting.command(name="info", description="Show counting info")
    async def c_info(self, interaction: discord.Interaction):
        data, gid = get_cd(interaction.guild.id)
        d = data[gid]
        ch = self.bot.get_channel(int(d['channel'])) if d['channel'] else None
        em = discord.Embed(title="🔢 Counting Info", color=discord.Color.blue())
        em.add_field(name="📍 Channel",    value=ch.mention if ch else "Not set")
        em.add_field(name="🔢 Current",    value=f"**{d['count']}**")
        em.add_field(name="🏆 High Score", value=f"**{d['high_score']}**")
        em.add_field(name="🎯 Goal",       value=f"**{d['goal']}**" if d['goal'] else "None")
        em.add_field(name="✅ Enabled",    value="Yes" if d['enabled'] else "No")
        em.add_field(name="🧹 Clean Chat",  value="Yes (Delete Invalid)" if d.get('delete_invalid') else "No")
        em.add_field(name="💀 Shame Role", value=f"On ({d['shame_role_name']})" if d['shame_role'] else "Off")
        await interaction.response.send_message(embed=em)

    @counting.command(name="stats", description="View counting stats for a user")
    @app_commands.describe(member="Who to check")
    async def c_stats(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        data, gid = get_cd(interaction.guild.id)
        s = data[gid]['user_stats'].get(str(member.id), {'correct': 0, 'fails': 0})
        total = s['correct'] + s['fails']
        acc = round((s['correct'] / total) * 100) if total > 0 else 0
        em = discord.Embed(title=f"📊 Counting Stats — {member.display_name}", color=discord.Color.purple())
        em.set_thumbnail(url=member.display_avatar.url)
        em.add_field(name="✅ Correct",  value=s['correct'])
        em.add_field(name="💀 Fails",    value=s['fails'])
        em.add_field(name="🎯 Accuracy", value=f"{acc}%")
        await interaction.response.send_message(embed=em)

    @counting.command(name="lb", description="Counting leaderboard")
    async def c_lb(self, interaction: discord.Interaction):
        data, gid = get_cd(interaction.guild.id)
        stats = data[gid]['user_stats']
        if not stats: return await interaction.response.send_message(embed=err("No data yet!"))
        sorted_users = sorted(stats.items(), key=lambda x: x[1]['correct'], reverse=True)[:10]
        em = discord.Embed(title="🏆 Counting Leaderboard", color=discord.Color.gold())
        desc = ""
        for i, (uid, s) in enumerate(sorted_users):
            user = self.bot.get_user(int(uid))
            name = user.display_name if user else f"User …{uid[-4:]}"
            desc += f"{medal(i)} **{name}** — {s['correct']} ✅ | {s['fails']} 💀\n"
        em.description = desc
        await interaction.response.send_message(embed=em)

    @counting.command(name="fails", description="Hall of shame — who ruined the count the most")
    async def c_fails(self, interaction: discord.Interaction):
        data, gid = get_cd(interaction.guild.id)
        stats = data[gid]['user_stats']
        if not stats: return await interaction.response.send_message(embed=err("No data yet!"))
        sorted_users = sorted(stats.items(), key=lambda x: x[1]['fails'], reverse=True)[:10]
        em = discord.Embed(title="💀 Hall of Shame", color=discord.Color.red())
        desc = ""
        emojis = ['💀','☠️','🩻']
        for i, (uid, s) in enumerate(sorted_users):
            user = self.bot.get_user(int(uid))
            name = user.display_name if user else f"User …{uid[-4:]}"
            e = emojis[i] if i < 3 else f"**{i+1}.**"
            desc += f"{e} **{name}** — {s['fails']} ruin(s)\n"
        em.description = desc
        await interaction.response.send_message(embed=em)

async def setup(bot):
    await bot.add_cog(Counting(bot))