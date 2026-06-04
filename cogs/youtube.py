import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from utils import load, save, ok, err, info

YOUTUBE_RSS_BY_ID     = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
YOUTUBE_RSS_BY_USER   = "https://www.youtube.com/feeds/videos.xml?user={username}"

# ── URL → Channel ID resolver ──────────────────────────────
async def resolve_youtube_url(raw: str) -> tuple:
    """Returns (channel_id, display_name) or (None, error_msg)"""
    raw = raw.strip()

    # Already looks like a channel ID
    if re.match(r'^UC[a-zA-Z0-9_-]{22}$', raw):
        return raw, None

    # Normalize to full URL
    if raw.startswith('@'):
        url = f"https://www.youtube.com/{raw}"
    elif not raw.startswith('http'):
        url = f"https://www.youtube.com/@{raw}"
    else:
        url = raw

    # Try extracting channel ID directly from URL
    m = re.search(r'youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})', url)
    if m:
        return m.group(1), None

    # Try RSS by username (old-style)
    m_user = re.search(r'youtube\.com/user/([^/?&]+)', url)
    if m_user:
        username = m_user.group(1)
        rss_url  = YOUTUBE_RSS_BY_USER.format(username=username)
        cid = await _fetch_channel_id_from_rss(rss_url)
        if cid:
            return cid, None

    # Fetch the page and extract channelId from HTML/JS
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; bot)'}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                if resp.status != 200:
                    return None, f"YouTube returned HTTP {resp.status}"
                text = await resp.text()

        # Look for channelId in page source
        patterns = [
            r'"channelId"\s*:\s*"(UC[a-zA-Z0-9_-]{22})"',
            r'channel/(UC[a-zA-Z0-9_-]{22})',
            r'externalId"\s*:\s*"(UC[a-zA-Z0-9_-]{22})"',
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                return m.group(1), None

        return None, "Could not extract Channel ID from that link. Try using the direct channel ID (UC...)."
    except Exception as e:
        return None, f"Error fetching page: {e}"

async def _fetch_channel_id_from_rss(rss_url: str) -> str | None:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(rss_url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status != 200:
                    return None
                text = await r.text()
        ns = {'yt': 'http://www.youtube.com/xml/schemas/2015'}
        root = ET.fromstring(text)
        cid = root.find('yt:channelId', ns)
        return cid.text if cid is not None else None
    except:
        return None

# ── RSS video fetcher ──────────────────────────────────────
async def fetch_latest_video(channel_id: str) -> dict | None:
    url = YOUTUBE_RSS_BY_ID.format(channel_id=channel_id)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                text = await resp.text()
        ns = {
            'atom':  'http://www.w3.org/2005/Atom',
            'yt':    'http://www.youtube.com/xml/schemas/2015',
            'media': 'http://search.yahoo.com/mrss/'
        }
        root  = ET.fromstring(text)
        entry = root.find('atom:entry', ns)
        if entry is None:
            return None
        video_id   = entry.find('yt:videoId', ns).text
        title      = entry.find('atom:title', ns).text
        link       = entry.find('atom:link', ns).attrib.get('href', '')
        author_el  = root.find('atom:author/atom:name', ns)
        author     = author_el.text if author_el is not None else 'Unknown'
        published  = entry.find('atom:published', ns)
        published  = published.text if published is not None else ''
        views_el   = entry.find('media:group/media:community/media:statistics', ns)
        views      = views_el.attrib.get('views', '?') if views_el is not None else '?'
        desc_el    = entry.find('media:group/media:description', ns)
        description= (desc_el.text or '')[:200] + '...' if desc_el is not None and desc_el.text else ''
        thumbnail  = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        return {
            'id': video_id, 'title': title, 'url': link,
            'author': author, 'thumbnail': thumbnail,
            'published': published, 'views': views,
            'description': description
        }
    except Exception as e:
        print(f"[YouTube] Fetch error {channel_id}: {e}")
        return None

def get_yt_cfg(gid: str) -> dict:
    return load('youtube.json').get(str(gid), {})

def save_yt_cfg(gid: str, cfg: dict):
    data = load('youtube.json')
    data[str(gid)] = cfg
    save('youtube.json', data)

class YouTube(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_videos.start()

    def cog_unload(self):
        self.check_videos.cancel()

    async def post_video(self, guild: discord.Guild, video: dict, ch_cfg: dict):
        discord_ch = guild.get_channel(int(ch_cfg.get('discord_channel', 0)))
        if not discord_ch:
            return

        msg_tpl  = ch_cfg.get('message', '🎬 **{author}** just uploaded a new video!\n**{title}**\n{url}')
        msg_text = (msg_tpl
            .replace('{author}',      video['author'])
            .replace('{title}',       video['title'])
            .replace('{url}',         video['url'])
            .replace('{views}',       str(video.get('views', '?')))
            .replace('{description}', video.get('description', ''))
            .replace('{channel}',     ch_cfg.get('name', video['author'])))

        em = discord.Embed(
            title=video['title'][:256],
            url=video['url'],
            color=discord.Color.red()
        )
        if video.get('description'):
            em.description = video['description']
        em.set_image(url=video['thumbnail'])
        em.set_author(name=video['author'],
                      icon_url="https://www.youtube.com/favicon.ico")
        em.add_field(name="👁️ Views",    value=f"{int(video['views']):,}" if str(video.get('views','')).isdigit() else '?')
        em.add_field(name="🔔 Channel",  value=ch_cfg.get('name', video['author']))
        em.set_footer(text="YouTube • New Video")
        if video.get('published'):
            try:
                dt = datetime.fromisoformat(video['published'].replace('Z', '+00:00'))
                em.timestamp = dt
            except: pass

        ping = ''
        if ch_cfg.get('ping_role'):
            ping = f"<@&{ch_cfg['ping_role']}> "
        if ch_cfg.get('ping_everyone'):
            ping = "@everyone "

        await discord_ch.send(content=(ping + msg_text) if ping else msg_text, embed=em)

    @tasks.loop(minutes=10)
    async def check_videos(self):
        for guild in self.bot.guilds:
            gid = str(guild.id)
            cfg = get_yt_cfg(gid)
            channels = cfg.get('channels', {})
            if not channels:
                continue
            changed = False
            for yt_cid, ch_cfg in list(channels.items()):
                if not ch_cfg.get('enabled', True):
                    continue
                video = await fetch_latest_video(yt_cid)
                if not video:
                    continue
                last_id = ch_cfg.get('last_video_id')
                if video['id'] != last_id:
                    if last_id is not None:
                        await self.post_video(guild, video, ch_cfg)
                    ch_cfg['last_video_id'] = video['id']
                    changed = True
                await asyncio.sleep(1)
            if changed:
                save_yt_cfg(gid, cfg)

    @check_videos.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    # ══════════════════════════════════════════════════════
    #  SLASH COMMANDS
    # ══════════════════════════════════════════════════════
    yt = app_commands.Group(name="youtube", description="YouTube alert commands")

    @yt.command(name="add", description="Add a YouTube channel using its link or @handle")
    @app_commands.describe(
        youtube_url="Channel link, @handle, or Channel ID",
        discord_channel="Where to post alerts",
        name="Friendly name (optional)",
        ping_role="Role to ping (optional)"
    )
    @app_commands.default_permissions(administrator=True)
    async def add(self, interaction: discord.Interaction,
                  youtube_url: str,
                  discord_channel: discord.TextChannel,
                  name: str = "",
                  ping_role: discord.Role = None):
        await interaction.response.defer(ephemeral=True)

        channel_id, error = await resolve_youtube_url(youtube_url)
        if not channel_id:
            return await interaction.followup.send(
                embed=err(f"❌ {error}"), ephemeral=True)

        video = await fetch_latest_video(channel_id)
        if not video:
            return await interaction.followup.send(
                embed=err("❌ Found the channel but couldn't fetch videos. Try again."), ephemeral=True)

        gid = str(interaction.guild.id)
        cfg = get_yt_cfg(gid)
        cfg.setdefault('channels', {})
        cfg['channels'][channel_id] = {
            'name':           name or video['author'],
            'url':            youtube_url,
            'discord_channel': discord_channel.id,
            'ping_role':      str(ping_role.id) if ping_role else None,
            'ping_everyone':  False,
            'message':        '🎬 **{author}** just uploaded a new video!\n**{title}**\n{url}',
            'enabled':        True,
            'last_video_id':  video['id']
        }
        save_yt_cfg(gid, cfg)

        em = ok("YouTube Alert Added! 🎬",
            f"📺 Channel: **{name or video['author']}**\n"
            f"📌 Alerts → {discord_channel.mention}\n"
            f"🎥 Latest: **{video['title']}**\n"
            f"🔍 Channel ID: `{channel_id}`")
        await interaction.followup.send(embed=em, ephemeral=True)

    @yt.command(name="remove", description="Remove a YouTube alert")
    @app_commands.describe(channel_id="YouTube Channel ID (use /youtube list to find it)")
    @app_commands.default_permissions(administrator=True)
    async def remove(self, interaction: discord.Interaction, channel_id: str):
        gid = str(interaction.guild.id)
        cfg = get_yt_cfg(gid)
        if channel_id in cfg.get('channels', {}):
            name = cfg['channels'][channel_id].get('name', channel_id)
            del cfg['channels'][channel_id]
            save_yt_cfg(gid, cfg)
            await interaction.response.send_message(embed=ok(f"Removed **{name}**"), ephemeral=True)
        else:
            await interaction.response.send_message(embed=err("Channel not found! Use `/youtube list` to see IDs."), ephemeral=True)

    @yt.command(name="list", description="List all monitored YouTube channels")
    async def list_channels(self, interaction: discord.Interaction):
        gid = str(interaction.guild.id)
        cfg = get_yt_cfg(gid)
        channels = cfg.get('channels', {})
        if not channels:
            return await interaction.response.send_message(
                embed=info("📺 No YouTube Alerts", "Add one with `/youtube add <link>`"))

        em = discord.Embed(title="📺 YouTube Alerts", color=discord.Color.red())
        for cid, ch in channels.items():
            discord_ch = interaction.guild.get_channel(int(ch.get('discord_channel', 0)))
            status = "✅ Enabled" if ch.get('enabled', True) else "❌ Disabled"
            em.add_field(
                name=f"📺 {ch.get('name', cid)}",
                value=f"**ID:** `{cid}`\n**Status:** {status}\n**Alerts →** {discord_ch.mention if discord_ch else 'Not set'}",
                inline=False
            )
        await interaction.response.send_message(embed=em)

    @yt.command(name="test", description="Send a test alert for a channel")
    @app_commands.describe(channel_id="YouTube Channel ID")
    @app_commands.default_permissions(administrator=True)
    async def test(self, interaction: discord.Interaction, channel_id: str):
        await interaction.response.defer(ephemeral=True)
        gid = str(interaction.guild.id)
        cfg = get_yt_cfg(gid)
        ch_cfg = cfg.get('channels', {}).get(channel_id)
        if not ch_cfg:
            return await interaction.followup.send(embed=err("Channel not found!"), ephemeral=True)
        video = await fetch_latest_video(channel_id)
        if not video:
            return await interaction.followup.send(embed=err("Could not fetch video!"), ephemeral=True)
        await self.post_video(interaction.guild, video, ch_cfg)
        await interaction.followup.send(embed=ok("✅ Test alert posted!"), ephemeral=True)

    @yt.command(name="toggle", description="Enable or disable a YouTube alert")
    @app_commands.describe(channel_id="YouTube Channel ID", enabled="True/False")
    @app_commands.default_permissions(administrator=True)
    async def toggle(self, interaction: discord.Interaction, channel_id: str, enabled: bool):
        gid = str(interaction.guild.id)
        cfg = get_yt_cfg(gid)
        if channel_id not in cfg.get('channels', {}):
            return await interaction.response.send_message(embed=err("Channel not found!"), ephemeral=True)
        cfg['channels'][channel_id]['enabled'] = enabled
        save_yt_cfg(gid, cfg)
        name = cfg['channels'][channel_id].get('name', channel_id)
        await interaction.response.send_message(
            embed=ok(f"{'Enabled ✅' if enabled else 'Disabled ❌'} — **{name}**"), ephemeral=True)

    @yt.command(name="setmessage", description="Customize the alert message for a channel")
    @app_commands.describe(
        channel_id="YouTube Channel ID",
        message="Use {author} {title} {url} {views} {channel} {description}"
    )
    @app_commands.default_permissions(administrator=True)
    async def setmessage(self, interaction: discord.Interaction, channel_id: str, message: str):
        gid = str(interaction.guild.id)
        cfg = get_yt_cfg(gid)
        if channel_id not in cfg.get('channels', {}):
            return await interaction.response.send_message(embed=err("Channel not found!"), ephemeral=True)
        cfg['channels'][channel_id]['message'] = message
        save_yt_cfg(gid, cfg)
        await interaction.response.send_message(embed=ok("Message Updated!", f"`{message}`"), ephemeral=True)

    @yt.command(name="latest", description="Show the latest video from a tracked channel")
    @app_commands.describe(channel_id="YouTube Channel ID")
    async def latest(self, interaction: discord.Interaction, channel_id: str):
        await interaction.response.defer()
        gid = str(interaction.guild.id)
        cfg = get_yt_cfg(gid)
        if channel_id not in cfg.get('channels', {}):
            return await interaction.followup.send(embed=err("Channel not tracked! Add it first."))
        video = await fetch_latest_video(channel_id)
        if not video:
            return await interaction.followup.send(embed=err("Could not fetch video!"))
        em = discord.Embed(title=video['title'], url=video['url'], color=discord.Color.red())
        em.set_image(url=video['thumbnail'])
        em.set_author(name=video['author'])
        em.set_footer(text="Latest Video")
        await interaction.followup.send(embed=em)

async def setup(bot):
    await bot.add_cog(YouTube(bot))
