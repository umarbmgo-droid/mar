import discord
from discord.ext import commands
import json
import os
import asyncio
import time

# ===== CONFIG =====
TOKEN = os.environ.get('TOKEN')
OWNER_IDS = [253335267618848778, 361069640962801664, 476779797427781642]
AUTOBAN_ALLOWED = [253335267618848778, 361069640962801664, 476779797427781642]
START_TIME = time.time()

# ===== BOT SETUP =====
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='>', intents=intents, help_command=None)

# ===== DATA STORAGE =====
auto_react = {}
hushed_users = {}
autobanned_users = {}
stop_mass_dm = False

def load_data():
    global auto_react, hushed_users, autobanned_users
    try:
        with open('auto_react.json', 'r') as f:
            auto_react = json.load(f)
    except:
        auto_react = {}
    try:
        with open('hushed.json', 'r') as f:
            hushed_users = json.load(f)
    except:
        hushed_users = {}
    try:
        with open('autobanned.json', 'r') as f:
            autobanned_users = json.load(f)
    except:
        autobanned_users = {}

def save_data():
    with open('auto_react.json', 'w') as f:
        json.dump(auto_react, f, indent=4)
    with open('hushed.json', 'w') as f:
        json.dump(hushed_users, f, indent=4)
    with open('autobanned.json', 'w') as f:
        json.dump(autobanned_users, f, indent=4)

load_data()

# ===== HELPERS =====
def is_owner(user_id):
    return user_id in OWNER_IDS

def is_autoban_allowed(user_id):
    return user_id in AUTOBAN_ALLOWED

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
    if emoji_input.startswith('<') and emoji_input.endswith('>'):
        parts = emoji_input.split(':')
        if len(parts) >= 3:
            emoji_id = int(parts[2].replace('>', ''))
            for g in bot.guilds:
                emoji = discord.utils.get(g.emojis, id=emoji_id)
                if emoji:
                    return emoji
    return emoji_input

# ===== BURST REACT =====
async def burst_react(message, emojis):
    tasks = []
    for emoji in emojis:
        try:
            resolved = await resolve_emoji(emoji, message.guild)
            tasks.append(message.add_reaction(resolved))
        except:
            pass
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

# ===== STATUS LOOP =====
async def status_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Streaming(
                name="Umar",
                url="https://www.twitch.tv/umar"
            )
        )
        await asyncio.sleep(60)

status_task = None

# ===== EVENTS =====
@bot.event
async def on_ready():
    print("="*50)
    print("BOT ONLINE")
    print(f"Bot: {bot.user} | ID: {bot.user.id}")
    print(f"Servers: {len(bot.guilds)}")
    print("="*50)
    bot.loop.create_task(status_loop())

    for guild in bot.guilds:
        for user_id_str in list(autobanned_users.keys()):
            user_id = int(user_id_str)
            try:
                bans = [entry async for entry in guild.bans()]
                banned_ids = [entry.user.id for entry in bans]
                if user_id not in banned_ids:
                    await guild.ban(discord.Object(id=user_id), reason="autoban (raid protection)", delete_message_days=1)
            except:
                pass

@bot.event
async def on_member_join(member):
    if str(member.id) in autobanned_users:
        try:
            await member.ban(reason="autoban", delete_message_days=1)
        except:
            pass

@bot.event
async def on_member_unban(guild, user):
    if str(user.id) in autobanned_users:
        try:
            await asyncio.sleep(1)
            await guild.ban(user, reason="autoban active", delete_message_days=0)
        except:
            pass

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if str(message.author.id) in hushed_users:
        try:
            await message.delete()
        except:
            pass
        return

    if str(message.author.id) in auto_react:
        data = auto_react[str(message.author.id)]
        if data.get('emojis'):
            asyncio.create_task(burst_react(message, data['emojis']))

    await bot.process_commands(message)

@bot.check
async def owner_only(ctx):
    return is_owner(ctx.author.id)

@bot.event
async def on_command_error(ctx, error):
    pass

# ===== COMMANDS =====

@bot.command()
async def ping(ctx):
    await ctx.reply(f"{round(bot.latency * 1000)}ms", mention_author=False)

@bot.command()
async def uptime(ctx):
    await ctx.reply(get_uptime(), mention_author=False)

@bot.command(name='r')
async def react(ctx, user: discord.Member, *emojis):
    if not emojis:
        return
    emojis = list(emojis)[:20]
    auto_react[str(user.id)] = {'emojis': emojis, 'set_by': ctx.author.id}
    save_data()
    await ctx.reply(f"reacting to {user.name} with {' '.join(emojis)}", mention_author=False)

@bot.command(name='rs')
async def react_stop(ctx):
    count = len(auto_react)
    auto_react.clear()
    save_data()
    await ctx.reply(f"stopped all reactions ({count} cleared)", mention_author=False)

@bot.command(name='h')
async def hush(ctx, user: discord.Member):
    hushed_users[str(user.id)] = True
    save_data()
    await ctx.reply(f"hushed {user.name}", mention_author=False)

@bot.command(name='hs')
async def hush_stop(ctx):
    count = len(hushed_users)
    hushed_users.clear()
    save_data()
    await ctx.reply(f"unhushed everyone ({count} cleared)", mention_author=False)

@bot.command(name='ab')
async def autoban(ctx, user_input: str):
    if not is_autoban_allowed(ctx.author.id):
        return
    user_id = None
    try:
        user_id = int(user_input.strip('<@!>'))
    except:
        try:
            member = await commands.MemberConverter().convert(ctx, user_input)
            user_id = member.id
        except:
            await ctx.reply("couldn't find that user", mention_author=False)
            return

    autobanned_users[str(user_id)] = True
    save_data()

    banned_in = 0
    for guild in bot.guilds:
        try:
            await guild.ban(discord.Object(id=user_id), reason="autoban (raid protection)", delete_message_days=1)
            banned_in += 1
        except:
            pass

    await ctx.reply(f"autobanned `{user_id}` — banned in {banned_in} server(s), will re-ban on rejoin/unban", mention_author=False)

@bot.command(name='rab')
async def remove_autoban(ctx, user_input: str):
    if not is_autoban_allowed(ctx.author.id):
        return
    user_id = None
    try:
        user_id = int(user_input.strip('<@!>'))
    except:
        try:
            member = await commands.MemberConverter().convert(ctx, user_input)
            user_id = member.id
        except:
            await ctx.reply("couldn't find that user", mention_author=False)
            return

    if str(user_id) in autobanned_users:
        del autobanned_users[str(user_id)]
        save_data()
        await ctx.reply(f"removed autoban for `{user_id}` — you can unban them manually now", mention_author=False)
    else:
        await ctx.reply(f"`{user_id}` wasn't on the autoban list", mention_author=False)

@bot.command()
async def unreact(ctx, user: discord.Member):
    if str(user.id) in auto_react:
        del auto_react[str(user.id)]
        save_data()
        await ctx.reply(f"stopped reacting to {user.name}", mention_author=False)
    else:
        await ctx.reply("wasn't reacting to them", mention_author=False)

@bot.command()
async def unhush(ctx, user: discord.Member):
    if str(user.id) in hushed_users:
        del hushed_users[str(user.id)]
        save_data()
        await ctx.reply(f"unhushed {user.name}", mention_author=False)
    else:
        await ctx.reply("they weren't hushed", mention_author=False)

@bot.command()
async def dm(ctx, user: discord.Member, *, message):
    try:
        await user.send(message)
        await ctx.reply(f"sent to {user.name}", mention_author=False)
    except Exception as e:
        await ctx.reply(f"couldn't dm them: {e}", mention_author=False)

@bot.command()
async def massdm(ctx, *, message):
    global stop_mass_dm
    stop_mass_dm = False
    sent = 0
    failed = 0
    seen = set()
    await ctx.reply("starting mass dm...", mention_author=False)
    for guild in bot.guilds:
        if stop_mass_dm:
            break
        async for member in guild.fetch_members(limit=None):
            if stop_mass_dm:
                break
            if member.bot or member.id in seen or member.id in OWNER_IDS:
                continue
            seen.add(member.id)
            try:
                await member.send(message)
                sent += 1
            except:
                failed += 1
            await asyncio.sleep(0.5)
    await ctx.reply(f"done. sent: {sent}, failed: {failed}", mention_author=False)

@bot.command()
async def smassdm(ctx):
    global stop_mass_dm
    stop_mass_dm = True
    await ctx.reply("stopped mass dm", mention_author=False)

@bot.command()
async def status(ctx, *, message):
    global status_task
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.CustomActivity(name=message)
    )
    await ctx.reply(f"status set: {message}", mention_author=False)

    async def revert_after_24h():
        await asyncio.sleep(86400)
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Streaming(name="Umar", url="https://www.twitch.tv/umar")
        )

    if status_task:
        status_task.cancel()
    status_task = asyncio.create_task(revert_after_24h())

@bot.command()
async def removestatus(ctx):
    global status_task
    if status_task:
        status_task.cancel()
        status_task = None
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Streaming(name="Umar", url="https://www.twitch.tv/umar")
    )
    await ctx.reply("status removed, back to streaming", mention_author=False)

# ===== RUN =====
if __name__ == "__main__":
    if not TOKEN:
        print("no token found")
        exit(1)
    print("starting...")
    bot.run(TOKEN)
