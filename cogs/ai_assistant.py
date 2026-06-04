import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import io
import time
import PIL.Image
import urllib.parse
from collections import OrderedDict
from utils import load, save, err, ok
from gemini_guard import ask_gemini, get_stats

USER_COOLDOWN_SECONDS = 15
_user_last_call: dict = {}

def _check_user_cooldown(uid: str) -> float:
    """Returns the remaining cooldown seconds or 0.0 if available."""
    last = _user_last_call.get(uid, 0)
    elapsed = time.time() - last
    remaining = USER_COOLDOWN_SECONDS - elapsed
    return max(0.0, remaining)

class AIAssistant(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Maps user_message_id -> list of bot_message_ids (handles deletion and edits)
        # Capped at 1000 items to guarantee no memory leaks during long uptimes
        self.response_tracker = OrderedDict()

    def get_guild_config(self, gid):
        return load('config.json').get(str(gid), {})

    def _track_response(self, user_msg_id: int, bot_msg_ids: list):
        """Saves response tracking data and drops the oldest entry if limit reached."""
        if len(self.response_tracker) > 1000:
            self.response_tracker.popitem(last=False)
        self.response_tracker[user_msg_id] = bot_msg_ids

    # ══════════════════════════════════════════════════════════
    #  🎨 IMAGE GENERATION FLOW (POLLINATIONS AI - NANO BANANA 2)
    # ══════════════════════════════════════════════════════════
    async def handle_generation_flow(self, message, prompt: str):
        """Triggers when a user says '@Bot generate ...'. Generates a real image using nano-banana-2!"""
        if not prompt:
            sent_msg = await message.reply("❌ Please provide a prompt for the image! (e.g., `@Bot generate a futuristic cyberpunk city`)")
            self._track_response(message.id, [sent_msg.id])
            return

        try:
            # 1. Trigger typing effect to provide visual feedback
            async with message.channel.typing():
                # Clean and encode the prompt so it's safe for a URL parameter
                encoded_prompt = urllib.parse.quote(prompt)
                
                # Unique seed based on timestamp ensures fresh art variations
                seed = int(time.time())
                
                # Dynamic image URL pointing directly to the nano-banana-2 render engine
                image_url = f"https://image.pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed={seed}&nofeed=true&model=nano-banana-2"
                
                # 2. Request the generated image bytes
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as resp:
                        if resp.status == 200:
                            img_data = await resp.read()
                            
                            # 3. Pack raw bytes into a streamable Discord File
                            discord_file = discord.File(io.BytesIO(img_data), filename="generated_asset.png")
                            
                            # 4. Wrap everything inside a clean embedded layout
                            em = discord.Embed(
                                title="🎨 AI Image Generation", 
                                description=f"Successfully generated asset using **Nano Banana 2** for {message.author.mention}", 
                                color=discord.Color.gold()
                            )
                            em.add_field(name="💡 Prompt Used", value=f"*{prompt}*", inline=False)
                            em.set_image(url="attachment://generated_asset.png")
                            
                            # Deliver the asset
                            sent_msg = await message.reply(file=discord_file, embed=em)
                            
                            # Link to tracker so it reacts cleanly to message deletions/edits
                            self._track_response(message.id, [sent_msg.id])
                        else:
                            sent_msg = await message.reply("❌ The nano-banana-2 engine is currently busy. Please try again.")
                            self._track_response(message.id, [sent_msg.id])
                            
        except Exception as e:
            print(f"[Generation Engine Error]: {e}")
            try:
                sent_msg = await message.reply(f"⚠️ Failed to render image: {str(e)[:100]}")
                self._track_response(message.id, [sent_msg.id])
            except: pass

    # ══════════════════════════════════════════════════════════
    #  🧠 STANDARD CONVERSATIONAL AI FLOW
    # ══════════════════════════════════════════════════════════
    async def _execute_ai_flow(self, message, is_edit=False):
        uid = str(message.author.id)
        remaining = _check_user_cooldown(uid)
        
        # Skip cooldown constraints on text edits for a seamless user experience
        if remaining > 0 and not is_edit:
            await message.reply(f"⏱️ Please wait {round(remaining, 1)} seconds before asking another question!", delete_after=5)
            return
        
        _user_last_call[uid] = time.time()

        # Isolate clean message text by stripping bot mentions
        user_input = message.content.replace(f'<@{self.bot.user.id}>', '').replace(f'<@!{self.bot.user.id}>', '').strip()

        # 🔀 INTERNAL ROUTER: Intercept phrases starting with "generate"
        if user_input.lower().startswith("generate"):
            generation_prompt = user_input[len("generate"):].strip()
            await self.handle_generation_flow(message, generation_prompt)
            return

        contents_to_send = []
        has_image = False

        # 📸 Process multimodal attached images
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

        if user_input:
            contents_to_send.append(user_input)
        elif has_image:
            contents_to_send.append("Describe this image or respond to it.")
        else:
            if not is_edit:
                await message.reply("👋 Hello! I am your AI Assistant. Feel free to ask me questions, send images, or use emojis! 🎨✨")
            return

        try:
            async with message.channel.typing():
                chat_system_prompt = (
                    "You are a helpful, friendly, and witty AI Assistant for a Discord server. "
                    "You fully support and love using emojis in your responses! Include them naturally. "
                    "Keep your answers engaging, creative, and try to keep them reasonably concise unless asked for details. "
                    "All interactions must be strictly in English."
                )
                
                response_text = await ask_gemini(contents_to_send, system=chat_system_prompt)
                
                if response_text:
                    bot_sent_messages = []
                    # Handle message segmenting if response exceeds Discord's 2000 character limit
                    if len(response_text) > 2000:
                        chunks = [response_text[i:i+1900] for i in range(0, len(response_text), 1900)]
                        for chunk in chunks:
                            sent_msg = await message.reply(chunk)
                            bot_sent_messages.append(sent_msg.id)
                    else:
                        sent_msg = await message.reply(response_text)
                        bot_sent_messages.append(sent_msg.id)
                    
                    self._track_response(message.id, bot_sent_messages)
                else:
                    sent_msg = await message.reply("❌ Failed to generate a response from the AI core.")
                    self._track_response(message.id, [sent_msg.id])
        except Exception as e:
            print(f"[AI Assistant Error]: {e}")
            try:
                sent_msg = await message.reply(f"⚠️ Error handling request: {str(e)[:100]}")
                self._track_response(message.id, [sent_msg.id])
            except: pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.author.id == self.bot.user.id or not message.guild:
            return

        gid = str(message.guild.id)
        cfg = self.get_guild_config(gid)
        if not cfg.get('ai_enabled', True):
            return

        is_mentioned = self.bot.user in message.mentions
        is_reply_to_bot = False
        
        if message.reference:
            if message.reference.resolved and hasattr(message.reference.resolved, 'author'):
                if message.reference.resolved.author.id == self.bot.user.id:
                    is_reply_to_bot = True
            elif message.reference.cached_message:
                if message.reference.cached_message.author.id == self.bot.user.id:
                    is_reply_to_bot = True

        if is_mentioned or is_reply_to_bot:
            await self._execute_ai_flow(message, is_edit=False)

    # ── 🗑️ LISTENER: ON MESSAGE DELETE ──
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Deletes all chunks of the bot's response if the user deletes their original prompt."""
        if message.id in self.response_tracker:
            bot_msg_ids = self.response_tracker.pop(message.id, [])
            for b_id in bot_msg_ids:
                try:
                    await message.channel.get_partial_message(b_id).delete()
                except Exception:
                    pass

    # ── ✏️ LISTENER: ON MESSAGE EDIT ──
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Deletes the old response and builds a fresh one when a prompt is edited."""
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

    # ── Slash Command: /ai_status ──
    @app_commands.command(name="ai_status", description="Check the AI core load and daily statistics")
    async def ai_status(self, interaction: discord.Interaction):
        try:
            stats = get_stats()
            calls_today = stats.get("calls_today", 0)
            limit = stats.get("daily_limit", 200)
            pct = round((calls_today / limit) * 100) if limit > 0 else 0
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            
            em = discord.Embed(title="🤖 AI Specifications & Status", color=discord.Color.green())
            em.add_field(name="🚀 Core Model", value="`gemini-2.5-flash (Latest Global Multimodal)`", inline=False)
            em.add_field(name="📊 Requests Today", value=f"`{calls_today} / {limit}`", inline=True)
            em.add_field(name="📈 Global Server Load", value=f"`{bar}` {pct}%", inline=False)
            await interaction.response.send_message(embed=em)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error fetching stats: {e}", ephemeral=True)

    # ── Slash Command: /ai_emoji ──
    @app_commands.command(name="ai_emoji", description="Render a custom web dashboard emoji directly into chat")
    @app_commands.describe(name="The unique name of the custom emoji")
    async def ai_emoji(self, interaction: discord.Interaction, name: str):
        gid = str(interaction.guild.id)
        cfg = self.get_guild_config(gid)
        custom_emojis = cfg.get('custom_external_emojis', {})
        
        if name not in custom_emojis:
            return await interaction.response.send_message(
                embed=err(f"Emoji `:{name}:` was not found on the web dashboard!"), ephemeral=True)
        
        await interaction.response.defer()
        url = custom_emojis[name]
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    img_data = await resp.read()
                    await interaction.followup.send(file=discord.File(io.BytesIO(img_data), filename=f"{name}.png"))
                else:
                    await interaction.followup.send(embed=err("Failed to fetch the requested emoji asset."), ephemeral=True)

async def setup(bot):
    await bot.add_cog(AIAssistant(bot))
