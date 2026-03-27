import discord
from discord.ext import commands, tasks
import sqlite3
import random

TOKEN = "MTQ4NzEzNzczMzI1MTAzOTMzMg.Ggn1ON.fZBoywFboyexD7N0HxmsEpTUv1HDY1KpVRBE9k"
TASK_CHANNEL_ID = 1479438187654021170
REVIEW_CHANNEL_ID = 1479438187654021170
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# DATABASE
conn = sqlite3.connect("tasks.db")
c = conn.cursor()

c.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER,
    points INTEGER
)""")

c.execute("""CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    task TEXT,
    reward INTEGER,
    proof TEXT,
    status TEXT
)""")

conn.commit()

# ---------------- BUTTON VIEWS ---------------- #

class SubmitView(discord.ui.View):
    def __init__(self, task_id):
        super().__init__(timeout=None)
        self.task_id = task_id

    @discord.ui.button(label="📸 Submit Proof", style=discord.ButtonStyle.primary)
    async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"Upload proof using: `!submit {self.task_id}`",
            ephemeral=True
        )


class ReviewView(discord.ui.View):
    def __init__(self, task_id, user_id, reward):
        super().__init__(timeout=None)
        self.task_id = task_id
        self.user_id = user_id
        self.reward = reward

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        c.execute("SELECT * FROM users WHERE user_id=?", (self.user_id,))
        user = c.fetchone()

        if user:
            c.execute("UPDATE users SET points = points + ? WHERE user_id=?", (self.reward, self.user_id))
        else:
            c.execute("INSERT INTO users VALUES (?, ?)", (self.user_id, self.reward))

        c.execute("UPDATE tasks SET status=? WHERE id=?", ("approved", self.task_id))
        conn.commit()

        await interaction.response.send_message("✅ Approved!", ephemeral=True)

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        c.execute("DELETE FROM tasks WHERE id=?", (self.task_id,))
        conn.commit()

        await interaction.response.send_message("❌ Rejected!", ephemeral=True)

# ---------------- EVENTS ---------------- #

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    daily_tasks.start()

# ---------------- DAILY TASK SYSTEM ---------------- #

@tasks.loop(hours=24)
async def daily_tasks():
    for guild in bot.guilds:
        for member in guild.members:
            if member.bot:
                continue

            task_list = [
                ("Farm 1000 crops", 50),
                ("Mine 300 stone", 40),
                ("Collect 500 wood", 45),
                ("Kill 50 mobs", 60)
            ]

            task = random.choice(task_list)

            c.execute("""
                INSERT INTO tasks (user_id, task, reward, proof, status)
                VALUES (?, ?, ?, ?, ?)
            """, (member.id, task[0], task[1], None, "open"))

    conn.commit()

    channel = bot.get_channel(TASK_CHANNEL_ID)
    if channel:
        await channel.send("🌅 New daily tasks assigned!")

# ---------------- SHOW TASKS ---------------- #

@bot.command()
async def tasks(ctx):
    c.execute("SELECT * FROM tasks WHERE user_id=?", (ctx.author.id,))
    data = c.fetchall()

    if not data:
        await ctx.send("No tasks for you.")
        return

    for t in data:
        embed = discord.Embed(title=f"Task {t[0]}", description=t[2], color=0x00ff00)
        embed.add_field(name="Reward", value=f"{t[3]} coins")
        embed.add_field(name="Status", value=t[5])

        await ctx.send(embed=embed, view=SubmitView(t[0]))

# ---------------- SUBMIT PROOF ---------------- #

@bot.command()
async def submit(ctx, task_id: int):
    c.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
    task = c.fetchone()

    if not task:
        await ctx.send("Task not found.")
        return

    if task[1] != ctx.author.id:
        await ctx.send("Not your task.")
        return

    if not ctx.message.attachments:
        await ctx.send("Attach proof image.")
        return

    proof_url = ctx.message.attachments[0].url

    c.execute("UPDATE tasks SET proof=?, status=? WHERE id=?",
              (proof_url, "pending", task_id))
    conn.commit()

    review_channel = bot.get_channel(REVIEW_CHANNEL_ID)

    embed = discord.Embed(title="📸 Task Review", color=0xffcc00)
    embed.add_field(name="User", value=ctx.author.mention)
    embed.add_field(name="Task", value=task[2])
    embed.add_field(name="Reward", value=task[3])
    embed.set_image(url=proof_url)

    await review_channel.send(
        embed=embed,
        view=ReviewView(task_id, ctx.author.id, task[3])
    )

    await ctx.send("📨 Submitted for review!")

# ---------------- LEADERBOARD ---------------- #

@bot.command()
async def leaderboard(ctx):
    c.execute("SELECT * FROM users ORDER BY points DESC LIMIT 10")
    users = c.fetchall()

    msg = "🏆 Leaderboard:\n"
    for i, u in enumerate(users):
        user = await bot.fetch_user(u[0])
        msg += f"{i+1}. {user.name} - {u[1]} coins\n"

    await ctx.send(msg)
@bot.command()
@commands.has_role("TaskAdmin")  # Only admins can assign
async def assign(ctx, member: discord.Member, task: str, reward: int):
    c.execute("""
        INSERT INTO tasks (user_id, task, reward, proof, status)
        VALUES (?, ?, ?, ?, ?)
    """, (member.id, task, reward, None, "open"))
    conn.commit()
    await ctx.send(f"✅ Task assigned to {member.mention}")

bot.run(TOKEN)