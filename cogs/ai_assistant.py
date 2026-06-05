import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import io
import time
import PIL.Image
import urllib.parse
from collections import OrderedDict, deque
from utils import load, save, err, ok
from gemini_guard import ask_gemini, get_stats

USER_COOLDOWN_SECONDS = 15
_user_last_call: dict = {}

# ── Keywords/signals that indicate a user wants an image generated ────────
IMAGE_REQUEST_KEYWORDS = [
    "generate", "draw", "create", "make", "produce", "render",
    "show me", "give me a picture", "give me an image", "картинка",
    "нарисувай", "генерирай", "направи снимка", "покажи ми снимка"
]

# ── Embed titles / content patterns that identify bot messages by source ──
# If a replied-to bot message matches these → allow AI to respond with context
LEVELUP_SIGNALS = ["level up", "leveled up", "Level", "🎉", "level"]

# These are game / system messages → AI should NOT respond
GAME_BOT_SIGNALS = [
    "trivia", "hangman", "math challenge", "counting", "guessed",
    "correct answer", "game over", "your answer", "⌛", "🎮",
    "started a game", "wins!", "lost!", "the answer was",
    "❌ Wrong", "✅ Correct", "📊", "Story Time",
    "FOTD", "QOTD", "ROTD", "SOTD",   # daily fact/quote/recipe/song cogs
    "Fact of the Day", "Quote of the Day", "Recipe of the Day", "Song of the Day",
    "Welcome", "joined the server",    # welcomer
    "muted", "banned", "kicked", "warned", "unmuted",  # moderation
    "YouTube", "New Video",            # youtube notifier
]

# ── Per-user conversation memory (guild:user → deque of turns) ────────────
# Each entry: {"role": "user"/"model", "parts": [str | PIL.Image]}
MAX_HISTORY = 10   # turns per user (1 turn = user + model pair)
_conversation_memory: dict[str, deque] = {}

def _mem_key(guild_id: int, user_id: int) -> str:
    return f"{guild_id}:{user_id}"

def _get_history(guild_id: int, user_id: int) -> deque:
    key = _mem_key(guild_id, user_id)
    if key not in _conversation_memory:
        _conversation_memory[key] = deque(maxlen=MAX_HISTORY * 2)  # *2 for user+model pairs
    return _conversation_memory[key]

def _push_turn(guild_id: int, user_id: int, role: str, parts: list):
    history = _get_history(guild_id, user_id)
    history.append({"role": role, "parts": parts})

def _clear_history(guild_id: int, user_id: int):
    key = _mem_key(guild_id, user_id)
    _conversation_memory.pop(key, None)


def _check_user_cooldown(uid: str) -> float:
    last = _user_last_call.get(uid, 0)
    elapsed = time.time() - last
    remaining = USER_COOLDOWN_SECONDS - elapsed
    return max(0.0, remaining)


def _is_image_request(text: str) -> bool:
    """Returns True if the user's message is asking for an image to be generated."""
    lowered = text.lower()
    for kw in IMAGE_REQUEST_KEYWORDS:
        if lowered.startswith(kw) or f" {kw} " in lowered or lowered.endswith(kw):
            return True
    # Heuristic: "a/an ... image/picture/photo/art/illustration"
    image_nouns = ["image", "picture", "photo", "pic", "art", "illustration",
                   "drawing", "painting", "снимка", "картинка", "рисунка"]
    for noun in image_nouns:
        if noun in lowered:
            return True
    return False


def _extract_image_prompt(text: str) -> str:
    """Strip trigger words from the front to isolate the actual image prompt."""
    lowered = text.lower()
    for kw in IMAGE_REQUEST_KEYWORDS:
        if lowered.startswith(kw):
            return text[len(kw):].strip(" :,-")
    return text.strip()


def _classify_bot_message(message: discord.Message) -> str:
    """
    Classify what kind of bot message this is.
    Returns: "levelup" | "game" | "ai" | "other"
    """
    # Check embed titles/descriptions
    for embed in message.embeds:
        title = (embed.title or "").lower()
        desc  = (embed.description or "").lower()
        combined = title + " " + desc

        for sig in LEVELUP_SIGNALS:
            if sig.lower() in combined:
                return "levelup"

        for sig in GAME_BOT_SIGNALS:
            if sig.lower() in combined:
                return "game"

    # Check plain text content
    content = message.content or ""
    for sig in LEVELUP_SIGNALS:
        if sig.lower() in content.lower():
            return "levelup"
    for sig in GAME_BOT_SIGNALS:
        if sig.lower() in content.lower():
            return "game"

    # If the message has no embeds and is plain text, it's likely an AI reply
    if not message.embeds:
        return "ai"

    return "other"


def _build_replied_context(replied_msg: discord.Message) -> str | None:
    """
    Build a context string describing what the user replied to.
    Returns None if we should not respond at all (game message).
    """
    kind = _classify_bot_message(replied_msg)

    if kind == "game":
        return None   # Signal: do NOT respond

    if kind == "levelup":
        # Extract level info from embed if available
        for embed in replied_msg.embeds:
            title = embed.title or ""
            desc  = embed.description or ""
            return (
                f"[Context: The user is replying to a Level-Up notification. "
                f"The message says: \"{title} — {desc}\". "
                f"Acknowledge this achievement warmly if relevant.]"
            )
        return "[Context: The user is replying to a Level-Up notification.]"

    if kind == "ai":
        # It's a previous AI reply — just let history handle it naturally
        return ""

    # "other" — some other bot embed (welcomer, youtube, etc.) — provide neutral context
    for embed in replied_msg.embeds:
        title = embed.title or ""
        if title:
            return f"[Context: The user is replying to a bot message titled: \"{title}\".]"

    if replied_msg.content:
        preview = replied_msg.content[:200]
        return f"[Context: The user is replying to a bot message that said: \"{preview}\"]"

    return ""


class AIAssistant(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Maps user_message_id -> list of bot_message_ids
        self.response_tracker = OrderedDict()

    def get_guild_config(self, gid):
        return load('config.json').get(str(gid), {})

    def _track_response(self, user_msg_id: int, bot_msg_ids: list):
        if len(self.response_tracker) > 1000:
            self.response_tracker.popitem(last=False)
        self.response_tracker[user_msg_id] = bot_msg_ids

    # ══════════════════════════════════════════════════════════
    #  🎨 IMAGE GENERATION FLOW
    # ══════════════════════════════════════════════════════════
    async def handle_generation_flow(self, message: discord.Message, prompt: str):
        if not prompt:
            sent_msg = await message.reply(
                "❌ Please provide a prompt! (e.g., `@Bot generate a futuristic cyberpunk city`)")
            self._track_response(message.id, [sent_msg.id])
            return

        try:
            async with message.channel.typing():
                encoded_prompt = urllib.parse.quote(prompt)
                seed = int(time.time())
                image_url = (
                    f"https://image.pollinations.ai/p/{encoded_prompt}"
                    f"?width=1024&height=1024&seed={seed}&nofeed=true&model=nano-banana-2"
                )

                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as resp:
                        if resp.status == 200:
                            img_data = await resp.read()
                            discord_file = discord.File(
                                io.BytesIO(img_data), filename="generated_asset.png")
                            em = discord.Embed(
                                title="🎨 AI Image Generation",
                                description=(
                                    f"Successfully generated image using **Nano Banana 2** "
                                    f"for {message.author.mention}"
                                ),
                                color=discord.Color.gold()
                            )
                            em.add_field(name="💡 Prompt Used", value=f"*{prompt}*", inline=False)
                            em.set_image(url="attachment://generated_asset.png")
                            sent_msg = await message.reply(file=discord_file, embed=em)
                            self._track_response(message.id, [sent_msg.id])
                        else:
                            sent_msg = await message.reply(
                                "❌ The image engine is currently busy. Please try again.")
                            self._track_response(message.id, [sent_msg.id])

        except Exception as e:
            print(f"[Generation Engine Error]: {e}")
            try:
                sent_msg = await message.reply(f"⚠️ Failed to render image: {str(e)[:100]}")
                self._track_response(message.id, [sent_msg.id])
            except:
                pass

    # ══════════════════════════════════════════════════════════
    #  🧠 CONVERSATIONAL AI FLOW  (with memory)
    # ══════════════════════════════════════════════════════════
    async def _execute_ai_flow(self, message: discord.Message, is_edit=False,
                                extra_context: str = ""):
        uid  = str(message.author.id)
        gid  = str(message.guild.id)

        remaining = _check_user_cooldown(uid)
        if remaining > 0 and not is_edit:
            await message.reply(
                f"⏱️ Please wait **{round(remaining, 1)}s** before asking again!",
                delete_after=5)
            return

        _user_last_call[uid] = time.time()

        # Clean mention from text
        user_input = (message.content
                      .replace(f'<@{self.bot.user.id}>', '')
                      .replace(f'<@!{self.bot.user.id}>', '')
                      .strip())

        # ── Image generation intent detection ──────────────────
        if _is_image_request(user_input) and not message.attachments:
            prompt = _extract_image_prompt(user_input)
            await self.handle_generation_flow(message, prompt)
            return

        # ── Build content parts ─────────────────────────────────
        contents_to_send = []
        has_image = False

        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    try:
                        img_bytes = await attachment.read()
                        img = PIL.Image.open(io.BytesIO(img_bytes))
                        contents_to_send.append(img)
                        has_image = True
                    except Exception as img_err:
                        print(f"[AI Error] Image failed to load: {img_err}")

        # Prepend any context about what was replied to
        full_user_text = ""
        if extra_context:
            full_user_text += extra_context + "\n\n"
        if user_input:
            full_user_text += user_input
        elif has_image:
            full_user_text += "Describe this image or respond to it."

        if not full_user_text.strip() and not has_image:
            if not is_edit:
                await message.reply(
                    "👋 Hello! I'm your AI Assistant. Ask me anything, send images, "
                    "or say `generate <prompt>` to create an image! 🎨✨")
            return

        if full_user_text.strip():
            contents_to_send.append(full_user_text)

        # ── Build conversation history for Gemini ───────────────
        history = _get_history(message.guild.id, message.author.id)
        history_list = list(history)   # list of {"role":..., "parts":[...]}

        try:
            async with message.channel.typing():
                system_prompt = (
                    "You are a helpful, friendly, and witty AI Assistant for a Discord server. "
                    "You fully support using emojis naturally in your responses! 🎨✨ "
                    "Keep answers engaging, creative, and reasonably concise unless asked for details. "
                    "You have memory of the recent conversation with each user. "
                    "If the user's message contains [Context: ...], use that context to "
                    "understand what they are replying to and respond accordingly. "
                    "All interactions must be strictly in English."
                )

                # Pass history + new message to Gemini
                response_text = await ask_gemini(
                    contents=contents_to_send,
                    system=system_prompt,
                    history=history_list
                )

                if response_text:
                    # Save this turn to memory (text only for history, no PIL objects)
                    text_parts = [p for p in contents_to_send if isinstance(p, str)]
                    _push_turn(message.guild.id, message.author.id, "user", text_parts or ["[image]"])
                    _push_turn(message.guild.id, message.author.id, "model", [response_text])

                    bot_sent_messages = []
                    if len(response_text) > 2000:
                        chunks = [response_text[i:i+1900]
                                  for i in range(0, len(response_text), 1900)]
                        for chunk in chunks:
                            sent_msg = await message.reply(chunk)
                            bot_sent_messages.append(sent_msg.id)
                    else:
                        sent_msg = await message.reply(response_text)
                        bot_sent_messages.append(sent_msg.id)

                    self._track_response(message.id, bot_sent_messages)
                else:
                    sent_msg = await message.reply(
                        "❌ Failed to generate a response from the AI core.")
                    self._track_response(message.id, [sent_msg.id])

        except Exception as e:
            print(f"[AI Assistant Error]: {e}")
            try:
                sent_msg = await message.reply(f"⚠️ Error handling request: {str(e)[:100]}")
                self._track_response(message.id, [sent_msg.id])
            except:
                pass

    # ══════════════════════════════════════════════════════════
    #  📨 LISTENERS
    # ══════════════════════════════════════════════════════════
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.author.id == self.bot.user.id or not message.guild:
            return

        gid = str(message.guild.id)
        cfg = self.get_guild_config(gid)
        if not cfg.get('ai_enabled', True):
            return

        is_mentioned      = self.bot.user in message.mentions
        is_reply_to_bot   = False
        replied_to_msg    = None

        if message.reference:
            resolved = message.reference.resolved
            if resolved and hasattr(resolved, 'author'):
                if resolved.author.id == self.bot.user.id:
                    is_reply_to_bot = True
                    replied_to_msg  = resolved
            elif message.reference.cached_message:
                cached = message.reference.cached_message
                if cached.author.id == self.bot.user.id:
                    is_reply_to_bot = True
                    replied_to_msg  = cached

        if not (is_mentioned or is_reply_to_bot):
            return

        extra_context = ""

        # ── Handle replies to bot messages ─────────────────────
        if is_reply_to_bot and replied_to_msg is not None:
            ctx = _build_replied_context(replied_to_msg)
            if ctx is None:
                # It's a game/system message — silently ignore
                return
            extra_context = ctx

        await self._execute_ai_flow(message, is_edit=False, extra_context=extra_context)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.id in self.response_tracker:
            bot_msg_ids = self.response_tracker.pop(message.id, [])
            for b_id in bot_msg_ids:
                try:
                    await message.channel.get_partial_message(b_id).delete()
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.content == after.content:
            return

        if after.id in self.response_tracker:
            bot_msg_ids = self.response_tracker.pop(after.id, [])
            for b_id in bot_msg_ids:
                try:
                    await after.channel.get_partial_message(b_id).delete()
                except Exception:
                    pass

            await self._execute_ai_flow(after, is_edit=True)

    # ══════════════════════════════════════════════════════════
    #  🔧 SLASH COMMANDS
    # ══════════════════════════════════════════════════════════
    @app_commands.command(name="ai_status",
                          description="Check the AI core load and daily statistics")
    async def ai_status(self, interaction: discord.Interaction):
        try:
            stats = get_stats()
            calls_today = stats.get("calls_today", 0)
            limit       = stats.get("daily_limit", 200)
            pct         = round((calls_today / limit) * 100) if limit > 0 else 0
            bar_str     = "█" * (pct // 10) + "░" * (10 - pct // 10)

            em = discord.Embed(title="🤖 AI Specifications & Status", color=discord.Color.green())
            em.add_field(name="🚀 Core Model",
                         value="`gemini-2.5-flash (Latest Global Multimodal)`", inline=False)
            em.add_field(name="📊 Requests Today",
                         value=f"`{calls_today} / {limit}`", inline=True)
            em.add_field(name="📈 Global Server Load",
                         value=f"`{bar_str}` {pct}%", inline=False)
            em.add_field(name="🧠 Memory",
                         value=f"`{len(_conversation_memory)} active conversations`", inline=True)
            await interaction.response.send_message(embed=em)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error fetching stats: {e}", ephemeral=True)

    @app_commands.command(name="ai_forget",
                          description="Clear the AI's memory of your conversation")
    async def ai_forget(self, interaction: discord.Interaction):
        _clear_history(interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(
            "🧹 I've cleared my memory of our conversation. Fresh start! ✨",
            ephemeral=True)

    @app_commands.command(name="ai_emoji",
                          description="Render a custom web dashboard emoji directly into chat")
    @app_commands.describe(name="The unique name of the custom emoji")
    async def ai_emoji(self, interaction: discord.Interaction, name: str):
        gid = str(interaction.guild.id)
        cfg = self.get_guild_config(gid)
        custom_emojis = cfg.get('custom_external_emojis', {})

        if name not in custom_emojis:
            return await interaction.response.send_message(
                embed=err(f"Emoji `:{name}:` was not found on the web dashboard!"),
                ephemeral=True)

        await interaction.response.defer()
        url = custom_emojis[name]

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    img_data = await resp.read()
                    await interaction.followup.send(
                        file=discord.File(io.BytesIO(img_data), filename=f"{name}.png"))
                else:
                    await interaction.followup.send(
                        embed=err("Failed to fetch the requested emoji asset."), ephemeral=True)


async def setup(bot):
    await bot.add_cog(AIAssistant(bot))
