import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
import time
from typing import Optional, List

# ===== CONFIG =====
TOKEN = os.environ.get('TOKEN')
OWNER_ID = 253335267618848778
START_TIME = time.time()

# ===== BOT SETUP =====
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=None, intents=intents, help_command=None)

# ===== DATA STORAGE =====
auto_react = {}
admins = []

def load_data():
    global auto_react, admins
    try:
        with open('auto_react.json', 'r') as f:
            auto_react = json.load(f)
    except:
        auto_react = {}
    try:
        with open('admins.json', 'r') as f:
            admins = json.load(f)
    except:
        admins = []

def save_data():
    with open('auto_react.json', 'w') as f:
        json.dump(auto_react, f, indent=4)
    with open('admins.json', 'w') as f:
        json.dump(admins, f, indent=4)

load_data()

# ===== HELPER FUNCTIONS =====
def is_owner_or_admin(user_id):
    return user_id == OWNER_ID or user_id in admins

def get_uptime():
    uptime = int(time.time() - START_TIME)
    days = uptime // 86400
    hours = (uptime % 86400) // 3600
    minutes = (uptime % 3600) // 60
    seconds = uptime % 60
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if minutes > 0: parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)

async def resolve_emoji(emoji_input, guild):
    """Resolve custom emojis from any server"""
    if emoji_input.startswith('<') and emoji_input.endswith('>'):
        animated = emoji_input.startswith('<a:')
        parts = emoji_input.split(':')
        if len(parts) >= 3:
            emoji_id = parts[2].replace('>', '')
            for g in bot.guilds:
                emoji = discord.utils.get(g.emojis, id=int(emoji_id))
                if emoji:
                    return emoji
            return emoji_input
    return emoji_input

# ===== INSTANT REACTION SYSTEM =====
async def mass_react(message, emojis):
    """React with multiple emojis instantly - NO RATE LIMIT CARE"""
    for emoji in emojis:
        try:
            resolved = await resolve_emoji(emoji, message.guild)
            await message.add_reaction(resolved)
        except:
            pass

# ===== STATUS LOOP =====
async def status_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        await bot.change_presence(activity=discord.Streaming(
            name="Umar",
            url="https://www.twitch.tv/umar"
        ))
        await asyncio.sleep(60)

# ===== EVENTS =====
@bot.event
async def on_ready():
    print("="*50)
    print("MAR IS ONLINE")
    print(f"Bot ID: {bot.user.id}")
    print(f"Servers: {len(bot.guilds)}")
    print(f"Admins: {len(admins)}")
    print(f"Auto-reacted users: {len(auto_react)}")
    print("="*50)
    bot.loop.create_task(status_loop())
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Failed to sync: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # INSTANT AUTO-REACT - NO DELAY
    if str(message.author.id) in auto_react:
        data = auto_react[str(message.author.id)]
        if data.get('emojis'):
            await mass_react(message, data['emojis'])
    
    await bot.process_commands(message)

# ===== ADMIN COMMANDS =====
admin_group = app_commands.Group(name="admin", description="Admin management")

@admin_group.command(name="add", description="Add a user as admin")
async def admin_add(interaction: discord.Interaction, user: discord.Member):
    if interaction.user.id != OWNER_ID:
        embed = discord.Embed(description="Only the owner can use this command", color=0x000000)
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    if user.id in admins:
        embed = discord.Embed(description=f"{user.mention} is already an admin", color=0x000000)
        return await interaction.response.send_message(embed=embed)
    admins.append(user.id)
    save_data()
    embed = discord.Embed(description=f"{user.mention} is now an admin", color=0x000000)
    await interaction.response.send_message(embed=embed)

@admin_group.command(name="remove", description="Remove admin from a user")
async def admin_remove(interaction: discord.Interaction, user: discord.Member):
    if interaction.user.id != OWNER_ID:
        embed = discord.Embed(description="Only the owner can use this command", color=0x000000)
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    if user.id not in admins:
        embed = discord.Embed(description=f"{user.mention} is not an admin", color=0x000000)
        return await interaction.response.send_message(embed=embed)
    admins.remove(user.id)
    save_data()
    embed = discord.Embed(description=f"{user.mention} is no longer an admin", color=0x000000)
    await interaction.response.send_message(embed=embed)

@admin_group.command(name="list", description="List all admins")
async def admin_list(interaction: discord.Interaction):
    if not is_owner_or_admin(interaction.user.id):
        embed = discord.Embed(description="You don't have permission", color=0x000000)
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    owner = bot.get_user(OWNER_ID)
    owner_text = f"👑 {owner.mention}" if owner else f"👑 Owner ({OWNER_ID})"
    admin_text = "\n".join([f"• {bot.get_user(admin).mention}" for admin in admins if bot.get_user(admin)])
    embed = discord.Embed(description=f"{owner_text}\n{admin_text}" if admins else f"{owner_text}\nNo other admins", color=0x000000)
    await interaction.response.send_message(embed=embed)

# ===== REACT COMMANDS =====
react_group = app_commands.Group(name="react", description="Auto-react management")

@react_group.command(name="add", description="Add auto-reactions to a user (up to 4 emojis)")
@app_commands.describe(user="User to auto-react to", emoji1="First emoji", emoji2="Second emoji (optional)", emoji3="Third emoji (optional)", emoji4="Fourth emoji (optional)")
async def react_add(interaction: discord.Interaction, user: discord.Member, emoji1: str, emoji2: Optional[str] = None, emoji3: Optional[str] = None, emoji4: Optional[str] = None):
    if not is_owner_or_admin(interaction.user.id):
        embed = discord.Embed(description="You don't have permission", color=0x000000)
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    emojis = [emoji1]
    if emoji2: emojis.append(emoji2)
    if emoji3: emojis.append(emoji3)
    if emoji4: emojis.append(emoji4)
    emojis = emojis[:4]
    working_emojis = []
    for e in emojis:
        resolved = await resolve_emoji(e, interaction.guild)
        if resolved: working_emojis.append(e)
    auto_react[str(user.id)] = {'emojis': working_emojis, 'set_by': interaction.user.id}
    save_data()
    embed = discord.Embed(description=f"Now auto-reacting to {user.mention} with {' '.join(working_emojis)}", color=0x000000)
    await interaction.response.send_message(embed=embed)

@react_group.command(name="remove", description="Remove auto-reactions from a user")
async def react_remove(interaction: discord.Interaction, user: discord.Member):
    if not is_owner_or_admin(interaction.user.id):
        embed = discord.Embed(description="You don't have permission", color=0x000000)
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    if str(user.id) in auto_react:
        del auto_react[str(user.id)]
        save_data()
        embed = discord.Embed(description=f"Stopped auto-reacting to {user.mention}", color=0x000000)
    else:
        embed = discord.Embed(description=f"{user.mention} is not being auto-reacted to", color=0x000000)
    await interaction.response.send_message(embed=embed)

@react_group.command(name="list", description="List all auto-reacted users")
async def react_list(interaction: discord.Interaction):
    if not is_owner_or_admin(interaction.user.id):
        embed = discord.Embed(description="You don't have permission", color=0x000000)
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    if not auto_react:
        embed = discord.Embed(description="No users are being auto-reacted to", color=0x000000)
        return await interaction.response.send_message(embed=embed)
    desc = ""
    for user_id, data in auto_react.items():
        user = bot.get_user(int(user_id))
        if user:
            desc += f"• {user.mention}: {' '.join(data['emojis'])}\n"
    embed = discord.Embed(description=desc, color=0x000000)
    await interaction.response.send_message(embed=embed)

# ===== AFK CHECK COMMAND =====
afk_group = app_commands.Group(name="afk", description="AFK check system")

@afk_group.command(name="check", description="Countdown AFK check on a user")
@app_commands.describe(amount="Number of seconds to countdown", user="User to check")
async def afk_check(interaction: discord.Interaction, amount: int, user: discord.Member):
    if amount < 1 or amount > 60:
        embed = discord.Embed(description="Amount must be between 1 and 60", color=0x000000)
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    await interaction.response.send_message(f"AFK check started for {user.mention} for {amount} seconds")
    
    channel = interaction.channel
    
    # Send countdown messages
    for i in range(amount, -1, -1):
        if i == amount:
            msg = await channel.send(f"AFK CHECK {user.mention}")
        elif i > 0:
            msg = await channel.send(f"{i} {user.mention}")
        else:
            msg = await channel.send(f"0 {user.mention}")
        
        # Wait for user to reply "here"
        def check(m):
            return m.author == user and m.content.lower() == "here" and m.channel == channel
        
        try:
            await bot.wait_for('message', timeout=1.0, check=check)
            embed = discord.Embed(description=f"✅ {user.mention} responded with 'here'", color=0x000000)
            await channel.send(embed=embed)
            return
        except asyncio.TimeoutError:
            continue
    
    # If loop completes without "here"
    embed = discord.Embed(description=f"❌ {user.mention} folded", color=0x000000)
    await channel.send(embed=embed)

# ===== BASIC COMMANDS =====
@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    embed = discord.Embed(description=f"{round(bot.latency * 1000)}ms", color=0x000000)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="uptime", description="Show how long the bot has been running")
async def uptime(interaction: discord.Interaction):
    embed = discord.Embed(description=get_uptime(), color=0x000000)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Show all commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="MAR Commands", color=0x000000)
    embed.add_field(name="Basic", value="`/ping` - Check latency\n`/uptime` - Show uptime\n`/help` - This menu", inline=False)
    embed.add_field(name="Admin (Owner Only)", value="`/admin add @user` - Add admin\n`/admin remove @user` - Remove admin\n`/admin list` - List admins", inline=False)
    embed.add_field(name="Auto-React (Owner/Admin)", value="`/react add @user 😈 👍 ❤️` - Add auto-reacts (up to 4)\n`/react remove @user` - Remove auto-reacts\n`/react list` - List auto-reacted users", inline=False)
    embed.add_field(name="AFK Check", value="`/afk check <amount> <user>` - Countdown AFK check", inline=False)
    embed.set_footer(text="Streaming Umar")
    await interaction.response.send_message(embed=embed)

# ===== REGISTER GROUPS =====
bot.tree.add_command(admin_group)
bot.tree.add_command(react_group)
bot.tree.add_command(afk_group)

# ===== RUN BOT =====
if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: No token found!")
        exit(1)
    
    print("Starting MAR...")
    bot.run(TOKEN)
