import builtins
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import re
from utils import load, save, ok, err, info

# ── Helpers ────────────────────────────────────────────────
def get_mc(guild_id):
    return load('mod_config.json').get(str(guild_id), {})

async def log_action(bot, guild, title, description, color=None):
    mc    = get_mc(guild.id)
    if not mc.get('logging'): return
    ch_id = mc.get('log_channel')
    if not ch_id: return
    ch = bot.get_channel(int(ch_id))
    if not ch: return
    try:
        punch_hex = mc.get('punch_color', '#ed4245').replace('#', '')
        embed_color = int(punch_hex, 16)
    except:
        embed_color = 0xed4245
    em = discord.Embed(title=title, description=description,
                       color=embed_color, timestamp=datetime.now())
    em.set_footer(text="Mod Log")
    await ch.send(embed=em)

async def send_ghost(member, guild, message):
    if not get_mc(guild.id).get('ghost_msg'): return
    try:
        em = discord.Embed(
            title=f"📨 Moderation Notice — {guild.name}",
            description=message,
            color=0xed4245
        )
        em.set_thumbnail(url=guild.icon.url if guild.icon else None)
        await member.send(embed=em)
    except: pass

async def check_auto_punch(interaction, member, warnings):
    mc = get_mc(interaction.guild.id)
    if not mc.get('auto_punch'): return
    threshold = mc.get('ap_threshold', 3)
    if warnings < threshold: return
    action   = mc.get('ap_action', 'timeout')
    duration = mc.get('ap_duration', 60)
    reason   = f"Auto-punishment: {warnings} warnings reached"
    try:
        if action == 'timeout':
            await member.timeout(timedelta(minutes=duration), reason=reason)
            desc = f"muted for **{duration} min**"
        elif action == 'kick':
            await member.kick(reason=reason)
            desc = "**kicked**"
        elif action == 'ban':
            await member.ban(reason=reason)
            desc = "**banned**"
        else:
            return
        await interaction.followup.send(embed=discord.Embed(
            title="🤖 Auto-Punishment Triggered",
            description=f"{member.mention} was automatically {desc} after reaching **{warnings} warnings**!",
            color=0xff6b35
        ))
        await log_action(interaction.client, interaction.guild,
            "🤖 Auto-Punishment", f"**User:** {member.mention}\n**Action:** {action}\n**Warnings:** {warnings}")
    except Exception as e:
        print(f"[AutoPunch] Error: {e}")

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── /ban ──────────────────────────────────────────────
    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.describe(member="Who to ban", reason="Reason", delete_days="Delete message history (days, 0-7)")
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member,
                  reason: str = "No reason provided", delete_days: int = 0):
        delete_days = max(0, min(7, delete_days))
        await member.ban(reason=reason, delete_message_days=delete_days)
        mc  = get_mc(interaction.guild.id)
        col = int(mc.get('punch_color','#ed4245').replace('#',''), 16)
        em  = discord.Embed(title="🔨 Banned", color=col)
        em.add_field(name="User",   value=f"{member.mention} (`{member}`)")
        em.add_field(name="Reason", value=reason)
        if delete_days: em.add_field(name="Messages Deleted", value=f"{delete_days} day(s)")
        em.set_footer(text=f"By {interaction.user}")
        em.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=em)
        await send_ghost(member, interaction.guild, f"You were **banned** from **{interaction.guild.name}**.\nReason: {reason}")
        await log_action(self.bot, interaction.guild, "🔨 Member Banned",
            f"**User:** {member.mention} (`{member.id}`)\n**By:** {interaction.user.mention}\n**Reason:** {reason}")

    # ── /unban ────────────────────────────────────────────
    @app_commands.command(name="unban", description="Unban a user by their ID")
    @app_commands.describe(user_id="The user's Discord ID", reason="Reason for unban")
    @app_commands.default_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=reason)
            await interaction.response.send_message(embed=ok("Unbanned", f"**{user}** has been unbanned.\nReason: {reason}"))
            await log_action(self.bot, interaction.guild, "✅ Member Unbanned",
                f"**User:** {user} (`{user_id}`)\n**By:** {interaction.user.mention}\n**Reason:** {reason}")
        except discord.NotFound:
            await interaction.response.send_message(embed=err("User not found or not banned!"), ephemeral=True)
        except ValueError:
            await interaction.response.send_message(embed=err("Invalid user ID!"), ephemeral=True)

    # ── /softban ──────────────────────────────────────────
    @app_commands.command(name="softban", description="Ban then immediately unban (deletes messages, user can rejoin)")
    @app_commands.describe(member="Who to softban", reason="Reason", delete_days="Days of messages to delete")
    @app_commands.default_permissions(ban_members=True)
    async def softban(self, interaction: discord.Interaction, member: discord.Member,
                      reason: str = "No reason provided", delete_days: int = 1):
        await member.ban(reason=f"[Softban] {reason}", delete_message_days=min(7, delete_days))
        await interaction.guild.unban(member, reason="Softban unban")
        em = discord.Embed(title="🪃 Softbanned", description=f"{member.mention} was softbanned.\n**Reason:** {reason}", color=0xff9800)
        em.set_footer(text=f"By {interaction.user}")
        await interaction.response.send_message(embed=em)
        await send_ghost(member, interaction.guild, f"You were **softbanned** (messages deleted, you may rejoin).\nReason: {reason}")
        await log_action(self.bot, interaction.guild, "🪃 Member Softbanned",
            f"**User:** {member.mention}\n**By:** {interaction.user.mention}\n**Reason:** {reason}")

    # ── /tempban ──────────────────────────────────────────
    @app_commands.command(name="tempban", description="Temporarily ban a member")
    @app_commands.describe(member="Who to tempban", hours="Duration in hours", reason="Reason")
    @app_commands.default_permissions(ban_members=True)
    async def tempban(self, interaction: discord.Interaction, member: discord.Member,
                      hours: int = 24, reason: str = "No reason provided"):
        await member.ban(reason=f"[Tempban {hours}h] {reason}", delete_message_days=0)
        em = discord.Embed(title="⏳ Temp Banned", color=0xff6b35)
        em.add_field(name="User",     value=member.mention)
        em.add_field(name="Duration", value=f"{hours} hour(s)")
        em.add_field(name="Reason",   value=reason, inline=False)
        em.set_footer(text=f"By {interaction.user}")
        await interaction.response.send_message(embed=em)
        await send_ghost(member, interaction.guild, f"You were **temporarily banned** for {hours}h.\nReason: {reason}")
        await log_action(self.bot, interaction.guild, "⏳ Temp Ban",
            f"**User:** {member.mention}\n**Duration:** {hours}h\n**By:** {interaction.user.mention}\n**Reason:** {reason}")

        async def unban_later():
            await asyncio.sleep(hours * 3600)
            try:
                await interaction.guild.unban(member, reason="Tempban expired")
            except: pass
        self.bot.loop.create_task(unban_later())

    # ── /kick ─────────────────────────────────────────────
    @app_commands.command(name="kick", description="Kick a member")
    @app_commands.describe(member="Who to kick", reason="Reason")
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        await member.kick(reason=reason)
        mc  = get_mc(interaction.guild.id)
        col = int(mc.get('punch_color','#ed4245').replace('#',''), 16)
        em  = discord.Embed(title="👢 Kicked", description=f"{member.mention} was kicked!\n**Reason:** {reason}", color=col)
        em.set_footer(text=f"By {interaction.user}")
        await interaction.response.send_message(embed=em)
        await send_ghost(member, interaction.guild, f"You were **kicked** from **{interaction.guild.name}**.\nReason: {reason}")
        await log_action(self.bot, interaction.guild, "👢 Member Kicked",
            f"**User:** {member.mention}\n**By:** {interaction.user.mention}\n**Reason:** {reason}")

    # ── /mute ─────────────────────────────────────────────
    @app_commands.command(name="mute", description="Timeout a member")
    @app_commands.describe(member="Who to mute", minutes="Duration in minutes", reason="Reason")
    @app_commands.default_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member,
                   minutes: int = 10, reason: str = "No reason provided"):
        await member.timeout(timedelta(minutes=minutes), reason=reason)
        em = discord.Embed(title="🔇 Muted",
            description=f"{member.mention} muted for **{minutes} min**!\n**Reason:** {reason}",
            color=discord.Color.greyple())
        em.set_footer(text=f"By {interaction.user}")
        await interaction.response.send_message(embed=em)
        await send_ghost(member, interaction.guild, f"You were **muted** for {minutes} minutes.\nReason: {reason}")
        await log_action(self.bot, interaction.guild, "🔇 Member Muted",
            f"**User:** {member.mention}\n**Duration:** {minutes} min\n**By:** {interaction.user.mention}\n**Reason:** {reason}")

    # ── /unmute ───────────────────────────────────────────
    @app_commands.command(name="unmute", description="Remove timeout from a member")
    @app_commands.default_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        await member.timeout(None)
        await interaction.response.send_message(embed=ok("🔊 Unmuted", f"{member.mention} has been unmuted!"))
        await log_action(self.bot, interaction.guild, "🔊 Member Unmuted",
            f"**User:** {member.mention}\n**By:** {interaction.user.mention}")

    # ── /warn ─────────────────────────────────────────────
    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(member="Who to warn", reason="Reason")
    @app_commands.default_permissions(manage_messages=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        await interaction.response.defer()
        w = load('warnings.json')
        gid, uid = str(interaction.guild.id), str(member.id)
        w.setdefault(gid, {}).setdefault(uid, []).append({
            'reason': reason, 'time': str(datetime.now())[:10], 'by': str(interaction.user)
        })
        save('warnings.json', w)
        count = len(w[gid][uid])
        em = discord.Embed(title=f"⚠️ Warning #{count}",
            description=f"{member.mention} received warning #{count}.\n**Reason:** {reason}",
            color=discord.Color.yellow())
        em.set_footer(text=f"By {interaction.user}")
        await interaction.followup.send(embed=em)
        await send_ghost(member, interaction.guild, f"You received **Warning #{count}**.\nReason: {reason}")
        await log_action(self.bot, interaction.guild, f"⚠️ Warning #{count}",
            f"**User:** {member.mention}\n**By:** {interaction.user.mention}\n**Reason:** {reason}")
        if hasattr(builtins, 'refresh_bot_cache'): builtins.refresh_bot_cache()
        await check_auto_punch(interaction, member, count)

    # ── /warnings ─────────────────────────────────────────
    @app_commands.command(name="warnings", description="View warnings for a member")
    @app_commands.describe(member="Who to check")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        w = load('warnings.json').get(str(interaction.guild.id), {}).get(str(member.id), [])
        em = discord.Embed(title=f"⚠️ Warnings — {member.display_name}", color=discord.Color.yellow())
        em.set_thumbnail(url=member.display_avatar.url)
        em.description = "No warnings! 😇" if not w else ""
        for i, x in enumerate(w, 1):
            em.add_field(name=f"#{i} — {x.get('time','?')} | By {x.get('by','?')}", value=x['reason'], inline=False)
        await interaction.response.send_message(embed=em)

    # ── /clearwarns ───────────────────────────────────────
    @app_commands.command(name="clearwarns", description="Clear warnings for a member")
    @app_commands.describe(member="Who to clear", count="How many to remove (leave empty for all)")
    @app_commands.default_permissions(manage_messages=True)
    async def clearwarns(self, interaction: discord.Interaction, member: discord.Member, count: int = 0):
        w = load('warnings.json')
        gid, uid = str(interaction.guild.id), str(member.id)
        warns = w.get(gid, {}).get(uid, [])
        if not warns:
            return await interaction.response.send_message(embed=err("No warnings found!"), ephemeral=True)
        if count > 0:
            removed = warns[-count:]
            w[gid][uid] = warns[:-count]
        else:
            removed = warns
            w[gid][uid] = []
        save('warnings.json', w)
        await interaction.response.send_message(embed=ok(f"Cleared {len(removed)} warning(s) for {member.display_name}"))

    # ── /clear ────────────────────────────────────────────
    @app_commands.command(name="clear", description="Delete messages from a channel")
    @app_commands.describe(amount="How many to delete", member="Only delete from this member (optional)")
    @app_commands.default_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int = 10, member: discord.Member = None):
        await interaction.response.defer(ephemeral=True)
        if member:
            def check(m): return m.author == member
            deleted = await interaction.channel.purge(limit=amount * 5, check=check, bulk=True)
            deleted = deleted[:amount]
        else:
            deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(embed=ok(f"Deleted {len(deleted)} messages!"), ephemeral=True)
        await log_action(self.bot, interaction.guild, "🗑️ Messages Purged",
            f"**{len(deleted)} messages** in {interaction.channel.mention}\n**By:** {interaction.user.mention}"
            + (f"\n**From:** {member.mention}" if member else ""))

    # ── /slowmode ─────────────────────────────────────────
    @app_commands.command(name="slowmode", description="Set slowmode in a channel")
    @app_commands.describe(seconds="Slowmode seconds (0 to disable)", channel="Channel (leave empty for current)")
    @app_commands.default_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: int, channel: discord.TextChannel = None):
        ch = channel or interaction.channel
        await ch.edit(slowmode_delay=max(0, min(21600, seconds)))
        if seconds == 0:
            await interaction.response.send_message(embed=ok("⚡ Slowmode Disabled", f"Removed slowmode in {ch.mention}"))
        else:
            await interaction.response.send_message(embed=ok("🐢 Slowmode Set", f"**{seconds}s** slowmode in {ch.mention}"))
        await log_action(self.bot, interaction.guild, "🐢 Slowmode Changed",
            f"**Channel:** {ch.mention}\n**Delay:** {seconds}s\n**By:** {interaction.user.mention}")

    # ── /lock ─────────────────────────────────────────────
    @app_commands.command(name="lock", description="Lock a channel so members can't send messages")
    @app_commands.describe(channel="Channel to lock", reason="Reason")
    @app_commands.default_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction, channel: discord.TextChannel = None, reason: str = "No reason provided"):
        ch = channel or interaction.channel
        overwrite = ch.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await ch.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=reason)
        em = discord.Embed(title="🔒 Channel Locked",
            description=f"{ch.mention} has been locked.\n**Reason:** {reason}",
            color=discord.Color.red())
        await interaction.response.send_message(embed=em)
        await log_action(self.bot, interaction.guild, "🔒 Channel Locked",
            f"**Channel:** {ch.mention}\n**By:** {interaction.user.mention}\n**Reason:** {reason}")

    # ── /unlock ───────────────────────────────────────────
    @app_commands.command(name="unlock", description="Unlock a locked channel")
    @app_commands.describe(channel="Channel to unlock")
    @app_commands.default_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        ch = channel or interaction.channel
        overwrite = ch.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await ch.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        em = discord.Embed(title="🔓 Channel Unlocked",
            description=f"{ch.mention} is now unlocked.", color=discord.Color.green())
        await interaction.response.send_message(embed=em)
        await log_action(self.bot, interaction.guild, "🔓 Channel Unlocked",
            f"**Channel:** {ch.mention}\n**By:** {interaction.user.mention}")

    # ── /hide / /unhide ───────────────────────────────────
    @app_commands.command(name="hide", description="Hide a channel from regular members")
    @app_commands.describe(channel="Channel to hide", reason="Reason")
    @app_commands.default_permissions(manage_channels=True)
    async def hide(self, interaction: discord.Interaction, channel: discord.TextChannel = None, reason: str = "No reason"):
        ch = channel or interaction.channel
        overwrite = ch.overwrites_for(interaction.guild.default_role)
        overwrite.view_channel = False
        await ch.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=reason)
        await interaction.response.send_message(embed=ok("👁️ Channel Hidden", f"{ch.mention} is now hidden."))
        await log_action(self.bot, interaction.guild, "👁️ Channel Hidden",
            f"**Channel:** {ch.mention}\n**By:** {interaction.user.mention}\n**Reason:** {reason}")

    @app_commands.command(name="unhide", description="Unhide a hidden channel")
    @app_commands.describe(channel="Channel to unhide")
    @app_commands.default_permissions(manage_channels=True)
    async def unhide(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        ch = channel or interaction.channel
        overwrite = ch.overwrites_for(interaction.guild.default_role)
        overwrite.view_channel = None
        await ch.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(embed=ok("👁️ Channel Visible", f"{ch.mention} is now visible."))

    # ── /nick ─────────────────────────────────────────────
    @app_commands.command(name="nick", description="Change a member's nickname")
    @app_commands.describe(member="Target member", nickname="New nickname (leave empty to reset)")
    @app_commands.default_permissions(manage_nicknames=True)
    async def nick(self, interaction: discord.Interaction, member: discord.Member, nickname: str = None):
        old = member.display_name
        await member.edit(nick=nickname)
        if nickname:
            await interaction.response.send_message(embed=ok("✏️ Nickname Changed", f"**{old}** → **{nickname}**"))
        else:
            await interaction.response.send_message(embed=ok("✏️ Nickname Reset", f"**{member.name}**'s nickname was reset."))
        await log_action(self.bot, interaction.guild, "✏️ Nickname Changed",
            f"**User:** {member.mention}\n**Old:** {old}\n**New:** {nickname or 'Reset'}\n**By:** {interaction.user.mention}")

    # ── /note ─────────────────────────────────────────────
    @app_commands.command(name="note", description="Add a private moderator note about a user")
    @app_commands.describe(member="Target member", note="The note")
    @app_commands.default_permissions(manage_messages=True)
    async def note(self, interaction: discord.Interaction, member: discord.Member, note: str):
        notes = load('notes.json')
        gid, uid = str(interaction.guild.id), str(member.id)
        notes.setdefault(gid, {}).setdefault(uid, []).append({
            'note': note, 'by': str(interaction.user), 'time': str(datetime.now())[:16]
        })
        save('notes.json', notes)
        count = len(notes[gid][uid])
        await interaction.response.send_message(
            embed=ok(f"📝 Note Added (#{count})", f"Note about {member.mention}:\n> {note}"), ephemeral=True)

    @app_commands.command(name="notes", description="View moderator notes about a user")
    @app_commands.describe(member="Target member")
    @app_commands.default_permissions(manage_messages=True)
    async def notes(self, interaction: discord.Interaction, member: discord.Member):
        notes = load('notes.json').get(str(interaction.guild.id), {}).get(str(member.id), [])
        em = discord.Embed(title=f"📝 Notes — {member.display_name}", color=discord.Color.blue())
        em.set_thumbnail(url=member.display_avatar.url)
        if not notes:
            em.description = "No notes for this user."
        for i, n in enumerate(notes, 1):
            em.add_field(name=f"#{i} — {n.get('time','?')} by {n.get('by','?')}", value=n['note'], inline=False)
        await interaction.response.send_message(embed=em, ephemeral=True)

    # ── /announce ─────────────────────────────────────────
    @app_commands.command(name="announce", description="Send an announcement embed")
    @app_commands.describe(
        title="Announcement title",
        message="Announcement message",
        channel="Where to send (leave empty for current)",
        color="Hex color like #5865f2 (optional)",
        ping_role="Role to ping (optional)"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def announce(self, interaction: discord.Interaction,
                       title: str, message: str,
                       channel: discord.TextChannel = None,
                       color: str = "#5865f2",
                       ping_role: discord.Role = None):
        ch = channel or interaction.channel
        try:
            col = int(color.replace('#', ''), 16)
        except:
            col = 0x5865f2
        em = discord.Embed(title=title, description=message, color=col, timestamp=datetime.now())
        em.set_footer(text=f"{interaction.guild.name}", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        ping = f"{ping_role.mention} " if ping_role else ""
        await ch.send(content=ping if ping else None, embed=em)
        await interaction.response.send_message(embed=ok("📢 Announced!", f"Sent to {ch.mention}"), ephemeral=True)

    # ── /role ─────────────────────────────────────────────
    @app_commands.command(name="role", description="Add or remove a role from a member")
    @app_commands.describe(action="add or remove", member="Target member", role="Which role")
    @app_commands.default_permissions(manage_roles=True)
    async def role(self, interaction: discord.Interaction, action: str, member: discord.Member, role: discord.Role):
        if action == 'add':
            await member.add_roles(role)
            await interaction.response.send_message(embed=ok("✅ Role Added", f"Added {role.mention} to {member.mention}"))
        elif action == 'remove':
            await member.remove_roles(role)
            await interaction.response.send_message(embed=ok("✅ Role Removed", f"Removed {role.mention} from {member.mention}"))
        else:
            await interaction.response.send_message(embed=err("Use `add` or `remove`"), ephemeral=True)
        await log_action(self.bot, interaction.guild, f"🎭 Role {action.capitalize()}ed",
            f"**User:** {member.mention}\n**Role:** {role.mention}\n**By:** {interaction.user.mention}")

    # ── /massrole ─────────────────────────────────────────
    @app_commands.command(name="massrole", description="Add or remove a role from ALL members")
    @app_commands.describe(action="add or remove", role="Which role")
    @app_commands.default_permissions(administrator=True)
    async def massrole(self, interaction: discord.Interaction, action: str, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        count = 0
        for member in interaction.guild.members:
            if member.bot: continue
            try:
                if action == 'add' and role not in member.roles:
                    await member.add_roles(role)
                    count += 1
                elif action == 'remove' and role in member.roles:
                    await member.remove_roles(role)
                    count += 1
            except: pass
        await interaction.followup.send(embed=ok(f"Mass Role — {action.capitalize()}",
            f"{role.mention} {action}ed for **{count}** members."), ephemeral=True)
        await log_action(self.bot, interaction.guild, f"🎭 Mass Role {action.capitalize()}",
            f"**Role:** {role.mention}\n**Affected:** {count} members\n**By:** {interaction.user.mention}")

    # ── /setlogchannel ────────────────────────────────────
    @app_commands.command(name="setlogchannel", description="Set the mod log channel")
    @app_commands.describe(channel="Where to send mod logs")
    @app_commands.default_permissions(administrator=True)
    async def setlogchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        cfg = load('mod_config.json')
        cfg.setdefault(str(interaction.guild.id), {})['log_channel'] = channel.id
        cfg[str(interaction.guild.id)]['logging'] = True
        save('mod_config.json', cfg)
        await interaction.response.send_message(embed=ok("✅ Log Channel Set!", f"Mod logs → {channel.mention}"))

    # ── /serverinfo ───────────────────────────────────────
    @app_commands.command(name="serverinfo", description="Show server information")
    async def serverinfo(self, interaction: discord.Interaction):
        g  = interaction.guild
        bots   = sum(1 for m in g.members if m.bot)
        humans = g.member_count - bots
        em = discord.Embed(title=f"ℹ️ {g.name}", color=discord.Color.blue(), timestamp=datetime.now())
        if g.icon: em.set_thumbnail(url=g.icon.url)
        em.add_field(name="👑 Owner",     value=g.owner.mention)
        em.add_field(name="👥 Members",   value=f"{humans} humans, {bots} bots")
        em.add_field(name="📅 Created",   value=g.created_at.strftime("%d/%m/%Y"))
        em.add_field(name="💬 Channels",  value=f"{len(g.text_channels)} text, {len(g.voice_channels)} voice")
        em.add_field(name="🎭 Roles",     value=len(g.roles))
        em.add_field(name="😀 Emojis",    value=len(g.emojis))
        em.add_field(name="🆙 Boost Lvl", value=g.premium_tier)
        em.add_field(name="🔒 Verif.",    value=str(g.verification_level).capitalize())
        await interaction.response.send_message(embed=em)

    # ── /userinfo ─────────────────────────────────────────
    @app_commands.command(name="userinfo", description="Show user information")
    @app_commands.describe(member="Who to check")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        w      = load('warnings.json').get(str(interaction.guild.id), {}).get(str(member.id), [])
        notes  = load('notes.json').get(str(interaction.guild.id), {}).get(str(member.id), [])
        em = discord.Embed(title=f"👤 {member.display_name}", color=member.color or discord.Color.blurple(), timestamp=datetime.now())
        em.set_thumbnail(url=member.display_avatar.url)
        em.add_field(name="🆔 ID",        value=f"`{member.id}`")
        em.add_field(name="📅 Joined",    value=member.joined_at.strftime("%d/%m/%Y") if member.joined_at else '?')
        em.add_field(name="📅 Created",   value=member.created_at.strftime("%d/%m/%Y"))
        em.add_field(name="⚠️ Warnings",  value=len(w))
        em.add_field(name="📝 Mod Notes", value=len(notes))
        em.add_field(name="🤖 Bot?",      value="Yes" if member.bot else "No")
        roles = [r.mention for r in member.roles[1:]]
        em.add_field(name=f"🎭 Roles ({len(roles)})", value=' '.join(roles[:10]) or "None", inline=False)
        status_map = {discord.Status.online: "🟢 Online", discord.Status.idle: "🟡 Idle",
                      discord.Status.dnd: "🔴 DND", discord.Status.offline: "⚫ Offline"}
        em.add_field(name="💬 Status", value=status_map.get(member.status, "Unknown"))
        await interaction.response.send_message(embed=em)

    # ── /setwelcome / /setautorole ─────────────────────────
    @app_commands.command(name="setwelcome", description="Set the welcome channel")
    @app_commands.describe(channel="Welcome channel")
    @app_commands.default_permissions(administrator=True)
    async def setwelcome(self, interaction: discord.Interaction, channel: discord.TextChannel):
        cfg = load('config.json')
        cfg.setdefault(str(interaction.guild.id), {})['welcome_channel'] = channel.id
        save('config.json', cfg)
        await interaction.response.send_message(embed=ok("Welcome Channel Set!", f"Welcome messages → {channel.mention}"))

    @app_commands.command(name="setautorole", description="Set the auto-role for new members")
    @app_commands.describe(role="Role to give")
    @app_commands.default_permissions(administrator=True)
    async def setautorole(self, interaction: discord.Interaction, role: discord.Role):
        cfg = load('config.json')
        cfg.setdefault(str(interaction.guild.id), {})['auto_role'] = role.id
        save('config.json', cfg)
        await interaction.response.send_message(embed=ok("Auto-role Set!", f"New members get {role.mention}"))

    # ── on_member_join ────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member):
        cfg = load('config.json').get(str(member.guild.id), {})
        ch  = self.bot.get_channel(cfg.get('welcome_channel'))
        if ch:
            em = discord.Embed(title=f"🎉 Welcome to {member.guild.name}!",
                description=f"Hey {member.mention}! Glad you're here! 🎮",
                color=discord.Color.green())
            em.set_thumbnail(url=member.display_avatar.url)
            em.set_footer(text=f"Member #{member.guild.member_count}")
            await ch.send(embed=em)
        role_id = cfg.get('auto_role')
        if role_id:
            role = member.guild.get_role(int(role_id))
            if role:
                try: await member.add_roles(role)
                except: pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await log_action(self.bot, member.guild, "🚪 Member Left",
            f"**{member}** (`{member.id}`) left the server.")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
