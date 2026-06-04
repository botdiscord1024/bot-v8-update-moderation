import discord
from discord.ext import commands
from discord import app_commands
import random, asyncio
from utils import load, save, ok, err, info

TRIVIA = [
    {"q":"Capital of France?","a":"paris"},
    {"q":"Sides on a hexagon?","a":"6"},
    {"q":"15 x 15?","a":"225"},
    {"q":"Fastest land animal?","a":"cheetah"},
    {"q":"Largest planet?","a":"jupiter"},
    {"q":"7 x 8?","a":"56"},
    {"q":"Colors in a rainbow?","a":"7"},
    {"q":"Capital of Japan?","a":"tokyo"},
    {"q":"Spider legs?","a":"8"},
    {"q":"Square root of 144?","a":"12"},
    {"q":"Largest ocean?","a":"pacific"},
    {"q":"Players on a football team?","a":"11"},
    {"q":"Chemical symbol for water?","a":"h2o"},
    {"q":"Continents on Earth?","a":"7"},
    {"q":"Longest river?","a":"nile"},
    {"q":"Smallest planet?","a":"mercury"},
    {"q":"Bones in the human body?","a":"206"},
    {"q":"This bot is written in?","a":"python"},
]

HANGMAN_WORDS = ['computer','keyboard','monitor','internet','discord','gaming',
                 'headset','controller','microphone','javascript','python','server']
HANGMAN_ART = [
    "```\n  +---+\n  |   |\n      |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n  |   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n /    |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n      |\n=========```",
]

# ── Tic Tac Toe ───────────────────────────────────────────
class TTTButton(discord.ui.Button):
    def __init__(self, x, y):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x, self.y = x, y

    async def callback(self, interaction: discord.Interaction):
        v: TTTView = self.view
        if interaction.user not in (v.p1, v.p2):
            return await interaction.response.send_message("You're not in this game!", ephemeral=True)
        if interaction.user != v.current:
            return await interaction.response.send_message("Not your turn!", ephemeral=True)
        if v.board[self.y][self.x] != 0:
            return await interaction.response.send_message("Cell taken!", ephemeral=True)
        sym = 1 if v.current == v.p1 else 2
        v.board[self.y][self.x] = sym
        self.label = "❌" if sym == 1 else "⭕"
        self.style = discord.ButtonStyle.danger if sym == 1 else discord.ButtonStyle.primary
        self.disabled = True
        winner = v.check_winner()
        if winner:
            for c in v.children: c.disabled = True
            name = v.p1.display_name if winner == 1 else v.p2.display_name
            return await interaction.response.edit_message(content=f"🎉 **{name}** wins!", view=v)
        if all(v.board[r][c] != 0 for r in range(3) for c in range(3)):
            for c in v.children: c.disabled = True
            return await interaction.response.edit_message(content="**Draw!** 🤝", view=v)
        v.current = v.p2 if v.current == v.p1 else v.p1
        await interaction.response.edit_message(content=f"🎮 **{v.current.display_name}'s** turn!", view=v)

class TTTView(discord.ui.View):
    def __init__(self, p1, p2):
        super().__init__(timeout=120)
        self.p1, self.p2, self.current = p1, p2, p1
        self.board = [[0]*3 for _ in range(3)]
        for y in range(3):
            for x in range(3): self.add_item(TTTButton(x, y))

    def check_winner(self):
        b = self.board
        for line in [[b[0][0],b[0][1],b[0][2]],[b[1][0],b[1][1],b[1][2]],[b[2][0],b[2][1],b[2][2]],
                     [b[0][0],b[1][0],b[2][0]],[b[0][1],b[1][1],b[2][1]],[b[0][2],b[1][2],b[2][2]],
                     [b[0][0],b[1][1],b[2][2]],[b[0][2],b[1][1],b[2][0]]]:
            if line == [1,1,1]: return 1
            if line == [2,2,2]: return 2
        return None

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── /rps ──────────────────────────────────────────────
    @app_commands.command(name="rps", description="Rock Paper Scissors vs the bot")
    @app_commands.describe(choice="rock, paper, or scissors")
    async def rps(self, interaction: discord.Interaction, choice: str):
        aliases = {'r':'rock','p':'paper','s':'scissors',
                   'rock':'rock','paper':'paper','scissors':'scissors'}
        choice = aliases.get(choice.lower())
        if not choice:
            return await interaction.response.send_message(embed=err("Choose `rock`, `paper`, or `scissors`!"), ephemeral=True)
        bot_c = random.choice(['rock','paper','scissors'])
        wins = {('rock','scissors'),('paper','rock'),('scissors','paper')}
        emojis = {'rock':'🪨','paper':'📄','scissors':'✂️'}
        if choice == bot_c: res, col = "Tie! 🤝", discord.Color.yellow()
        elif (choice, bot_c) in wins: res, col = "You win! 🎉", discord.Color.green()
        else: res, col = "I win! 😈", discord.Color.red()
        em = discord.Embed(title="✂️ Rock Paper Scissors", color=col)
        em.add_field(name="You", value=f"{emojis[choice]} {choice.capitalize()}")
        em.add_field(name="Bot", value=f"{emojis[bot_c]} {bot_c.capitalize()}")
        em.add_field(name="Result", value=res, inline=False)
        await interaction.response.send_message(embed=em)

    # ── /8ball ────────────────────────────────────────────
    @app_commands.command(name="8ball", description="Ask the magic 8ball")
    @app_commands.describe(question="Your question")
    async def eightball(self, interaction: discord.Interaction, question: str):
        answers = ["Yes, definitely! ✅","Without a doubt! ✅","Most likely! ✅","Yes! ✅",
                   "Don't count on it ❌","No! ❌","Very doubtful ❌","Definitely not ❌",
                   "Ask again later 🤔","Not sure 🤔","Maybe 🤔","Signs point to yes 🤔"]
        em = discord.Embed(title="🎱 Magic 8Ball", color=discord.Color.purple())
        em.add_field(name="❓ Question", value=question, inline=False)
        em.add_field(name="💬 Answer",   value=random.choice(answers), inline=False)
        await interaction.response.send_message(embed=em)

    # ── /coinflip ─────────────────────────────────────────
    @app_commands.command(name="coinflip", description="Flip a coin")
    async def coinflip(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=discord.Embed(
            title="🪙 Coin Flip",
            description=f"**{random.choice(['Heads 🌕','Tails 🌑'])}**",
            color=discord.Color.gold()
        ))

    # ── /roll ─────────────────────────────────────────────
    @app_commands.command(name="roll", description="Roll a dice")
    @app_commands.describe(sides="Number of sides (default 6)")
    async def roll(self, interaction: discord.Interaction, sides: int = 6):
        if sides < 2 or sides > 1000:
            return await interaction.response.send_message(embed=err("Enter a number between 2 and 1000!"), ephemeral=True)
        await interaction.response.send_message(embed=discord.Embed(
            title="🎲 Dice Roll",
            description=f"Rolled **d{sides}** → **{random.randint(1, sides)}**!",
            color=discord.Color.blue()
        ))

    # ── /trivia ───────────────────────────────────────────
    @app_commands.command(name="trivia", description="Answer a trivia question")
    async def trivia(self, interaction: discord.Interaction):
        q = random.choice(TRIVIA)
        em = discord.Embed(title="🧠 Trivia", description=f"**{q['q']}**", color=discord.Color.blue())
        em.set_footer(text="⏳ 20 seconds! Type your answer in chat.")
        await interaction.response.send_message(embed=em)
        def check(m): return m.channel == interaction.channel and not m.author.bot
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=20.0)
            if msg.content.lower() == q['a']:
                await interaction.followup.send(embed=ok(f"Correct, {msg.author.display_name}! 🎉", f"Answer: **{q['a']}**"))
            else:
                await interaction.followup.send(embed=err(f"Wrong! Answer was **{q['a']}**"))
        except asyncio.TimeoutError:
            await interaction.followup.send(embed=err(f"⏰ Time's up! Answer: **{q['a']}**"))

    # ── /hangman ──────────────────────────────────────────
    @app_commands.command(name="hangman", description="Play hangman")
    async def hangman(self, interaction: discord.Interaction):
        word = random.choice(HANGMAN_WORDS)
        guessed = set()
        lives = 6

        def display(): return ' '.join(c if c in guessed else '_' for c in word)

        async def update(gm):
            col = discord.Color.blue() if lives > 2 else discord.Color.red()
            em = discord.Embed(title="🪓 Hangman", color=col)
            em.description = HANGMAN_ART[6 - lives]
            em.add_field(name="Word", value=f"`{display()}`", inline=False)
            em.add_field(name=f"Lives {'❤️'*lives}{'🖤'*(6-lives)}", value=f"Guessed: `{''.join(sorted(guessed)) or '-'}`", inline=False)
            em.set_footer(text="Type one letter in chat!")
            await gm.edit(embed=em)

        em = discord.Embed(title="🪓 Hangman", description=HANGMAN_ART[0], color=discord.Color.blue())
        em.add_field(name="Word", value=f"`{display()}`")
        em.set_footer(text="Type one letter in chat!")
        await interaction.response.send_message(embed=em)
        gm = await interaction.original_response()

        def check(m): return m.channel == interaction.channel and m.author == interaction.user and len(m.content) == 1 and m.content.isalpha()

        while lives > 0 and not all(c in guessed for c in word):
            try:
                g = await self.bot.wait_for('message', check=check, timeout=30.0)
                letter = g.content.lower()
                if letter in guessed:
                    await interaction.channel.send("Already guessed!", delete_after=3)
                    continue
                guessed.add(letter)
                if letter not in word: lives -= 1
                await update(gm)
            except asyncio.TimeoutError:
                return await interaction.followup.send(embed=err(f"⏰ Time's up! Word was **{word}**!"))

        if lives == 0: await interaction.followup.send(embed=err(f"💀 You lost! Word was **{word}**!"))
        else: await interaction.followup.send(embed=ok(f"You got it: **{word}**! 🎉"))

    # ── /guess ────────────────────────────────────────────
    @app_commands.command(name="guess", description="Guess a number between 1 and 100")
    async def guess(self, interaction: discord.Interaction):
        number = random.randint(1, 100)
        await interaction.response.send_message(embed=info("🔢 Guess the Number", "Number from **1 to 100** — 7 attempts! Type in chat."))
        def check(m): return m.channel == interaction.channel and m.author == interaction.user and m.content.isdigit()
        for attempt in range(1, 8):
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                n = int(msg.content)
                if n == number:
                    return await interaction.followup.send(embed=ok("Correct! 🎉", f"Number was **{number}**! Got it in **{attempt}** attempt(s)!"))
                await interaction.followup.send(embed=info("📈 Higher!" if n < number else "📉 Lower!", f"Attempt {attempt}/7"))
            except asyncio.TimeoutError:
                return await interaction.followup.send(embed=err(f"⏰ Time's up! Number was **{number}**!"))
        await interaction.followup.send(embed=err(f"💀 Out of attempts! Number was **{number}**!"))

    # ── /tictactoe ────────────────────────────────────────
    @app_commands.command(name="tictactoe", description="Play Tic Tac Toe with someone")
    @app_commands.describe(opponent="Who to play against")
    async def tictactoe(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot: return await interaction.response.send_message(embed=err("Can't play against a bot!"), ephemeral=True)
        if opponent == interaction.user: return await interaction.response.send_message(embed=err("Can't play against yourself!"), ephemeral=True)
        view = TTTView(interaction.user, opponent)
        await interaction.response.send_message(
            content=f"❌ **{interaction.user.display_name}** vs ⭕ **{opponent.display_name}**\n🎮 **{interaction.user.display_name}'s** turn!",
            view=view
        )

    # ── /poll ─────────────────────────────────────────────
    @app_commands.command(name="poll", description="Create a poll")
    @app_commands.describe(question="The poll question")
    async def poll(self, interaction: discord.Interaction, question: str):
        em = discord.Embed(title="📊 Poll", description=question, color=discord.Color.blue())
        em.set_footer(text=f"By {interaction.user.display_name}")
        await interaction.response.send_message(embed=em)
        msg = await interaction.original_response()
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

    # ── /joke ─────────────────────────────────────────────
    @app_commands.command(name="joke", description="Tell a joke")
    async def joke(self, interaction: discord.Interaction):
        jokes = [
            "Why do programmers prefer dark mode? Light attracts bugs! 🐛",
            "How many programmers to change a lightbulb? None — hardware problem! 💡",
            "Why did the scarecrow win an award? Outstanding in his field! 🌾",
            "Why don't scientists trust atoms? They make up everything! ⚛️",
        ]
        await interaction.response.send_message(embed=discord.Embed(
            title="😂 Joke", description=random.choice(jokes), color=discord.Color.yellow()
        ))

    # ── /avatar ───────────────────────────────────────────
    @app_commands.command(name="avatar", description="Show someone's avatar")
    @app_commands.describe(member="Who to check")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        em = discord.Embed(title=f"🖼️ {member.display_name}'s Avatar", color=discord.Color.blue())
        em.set_image(url=member.display_avatar.url)
        await interaction.response.send_message(embed=em)

async def setup(bot):
    await bot.add_cog(Games(bot))
