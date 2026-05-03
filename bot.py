import discord
from discord.ext import commands
import json
import os
import asyncio
import time

# ===== CONFIG =====
TOKEN = os.environ.get('TOKEN')
OWNER_ID = 253335267618848778
START_TIME = time.time()

# ===== BOT SETUP =====
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='>', intents=intents, help_command=None)

# ===== DATA =====
auto_react = {}
hushed_users = {}
autobanned_users = {}
role_locks = {}
role_blacklist = {}
whitelist = {}
stop_mass_dm = False

def load_data():
    global auto_react, hushed_users, autobanned_users, role_locks, role_blacklist, whitelist
    files = {
        'auto_react':       ('auto_react.json',     {}),
        'hushed_users':     ('hushed.json',          {}),
        'autobanned_users': ('autobanned.json',      {}),
        'role_locks':       ('role_locks.json',      {}),
        'role_blacklist':   ('role_blacklist.json',  {}),
        'whitelist':        ('whitelist.json',       {}),
    }
    for var, (fname, default) in files.items():
        try:
            with open(fname, 'r') as f:
                globals()[var] = json.load(f)
        except:
            globals()[var] = dict(default)

def save_data():
    files = {
        'auto_react':       'auto_react.json',
        'hushed_users':     'hushed.json',
        'autobanned_users': 'autobanned.json',
        'role_locks':       'role_locks.json',
        'role_blacklist':   'role_blacklist.json',
        'whitelist':        'whitelist.json',
    }
    for var, fname in files.items():
        with open(fname, 'w') as f:
            json.dump(globals()[var], f, indent=4)

load_data()

# ===== HELPERS =====

def is_owner(uid):
    return uid == OWNER_ID

def is_whitelisted(uid):
    return str(uid) in whitelist

def can_use(uid):
    return is_owner(uid) or is_whitelisted(uid)

def get_uptime():
    s = int(time.time() - START_TIME)
    parts = []
    for unit, val in [('d', 86400), ('h', 3600), ('m', 60), ('s', 1)]:
        if s >= val:
            parts.append(f"{s // val}{unit}")
            s %= val
    return ' '.join(parts) or '0s'

async def resolve_emoji(emoji_input, guild):
    if emoji_input.startswith('<') and emoji_input.endswith('>'):
        parts = emoji_input.split(':')
        if len(parts) >= 3:
            try:
                eid = int(parts[2].replace('>', ''))
                for g in bot.guilds:
                    e = discord.utils.get(g.emojis, id=eid)
                    if e:
                        return e
            except:
                pass
    return emoji_input

async def resolve_role(guild, role_input):
    role_input = role_input.strip('<@&>')
    try:
        role = guild.get_role(int(role_input))
        if role:
            return role
    except:
        pass
    low = role_input.lower()
    for role in guild.roles:
        if role.name.lower() == low:
            return role
    return None

async def resolve_user(ctx, user_input):
    user_input = user_input.strip('<@!>')
    try:
        uid = int(user_input)
        member = ctx.guild.get_member(uid)
        if member:
            return member
        try:
            return await ctx.guild.fetch_member(uid)
        except:
            pass
    except:
        pass
    low = user_input.lower()
    for m in ctx.guild.members:
        if m.name.lower() == low or (m.nick and m.nick.lower() == low):
            return m
    return None

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
            activity=discord.Streaming(name="Umar", url="https://www.twitch.tv/umar")
        )
        await asyncio.sleep(60)

status_task = None

# ===== EVENTS =====
@bot.event
async def on_ready():
    print("=" * 50)
    print(f"  {bot.user}  |  {bot.user.id}")
    print(f"  Guilds: {len(bot.guilds)}")
    print("=" * 50)
    bot.loop.create_task(status_loop())

    for guild in bot.guilds:
        for uid_str in list(autobanned_users.keys()):
            uid = int(uid_str)
            try:
                bans = [e async for e in guild.bans()]
                if uid not in [e.user.id for e in bans]:
                    await guild.ban(discord.Object(id=uid), reason="autoban", delete_message_days=1)
            except:
                pass

@bot.event
async def on_member_join(member):
    uid_str = str(member.id)

    if uid_str in autobanned_users:
        try:
            await member.ban(reason="autoban", delete_message_days=1)
            return
        except:
            pass

    if uid_str in role_locks:
        for rid in role_locks[uid_str]:
            role = member.guild.get_role(rid)
            if role:
                try:
                    await member.add_roles(role, reason="role lock")
                except:
                    pass

    if uid_str in role_blacklist:
        for rid in role_blacklist[uid_str]:
            role = member.guild.get_role(rid)
            if role and role in member.roles:
                try:
                    await member.remove_roles(role, reason="role blacklist")
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
async def on_member_update(before, after):
    uid_str = str(after.id)
    before_roles = set(r.id for r in before.roles)
    after_roles = set(r.id for r in after.roles)

    if uid_str in role_locks:
        for rid in role_locks[uid_str]:
            if rid not in after_roles:
                role = after.guild.get_role(rid)
                if role:
                    try:
                        await after.add_roles(role, reason="role lock enforced")
                    except:
                        pass

    if uid_str in role_blacklist:
        for rid in role_blacklist[uid_str]:
            if rid in after_roles and rid not in before_roles:
                role = after.guild.get_role(rid)
                if role:
                    try:
                        await after.remove_roles(role, reason="role blacklist enforced")
                    except:
                        pass

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid_str = str(message.author.id)

    if uid_str in hushed_users:
        try:
            await message.delete()
        except:
            pass
        return

    if uid_str in auto_react and auto_react[uid_str].get('emojis'):
        asyncio.create_task(burst_react(message, auto_react[uid_str]['emojis']))

    await bot.process_commands(message)

@bot.check
async def global_check(ctx):
    # >wl command is owner only, everything else is owner + whitelisted
    if ctx.command and ctx.command.name == 'wl':
        return is_owner(ctx.author.id)
    return can_use(ctx.author.id)

@bot.event
async def on_command_error(ctx, error):
    pass

# ===== COMMANDS =====

# ── Info ─────────────────────────────────────────────────────────────────────

@bot.command()
async def ping(ctx):
    await ctx.reply(f"`{round(bot.latency * 1000)}ms`", mention_author=False)

@bot.command()
async def uptime(ctx):
    await ctx.reply(f"`{get_uptime()}`", mention_author=False)

@bot.command(name='help')
async def help_cmd(ctx):
    e = discord.Embed(color=0x111111)
    e.set_author(name="Command Reference")

    e.add_field(name="React", value=(
        "`>r <user> <emojis...>` — auto react to every message\n"
        "`>unreact <user>` — stop reacting to a user\n"
        "`>rs` — clear all active reactions"
    ), inline=False)

    e.add_field(name="Hush", value=(
        "`>h <user>` — silently delete all messages from user\n"
        "`>unhush <user>` — stop hushing a user\n"
        "`>hs` — unhush everyone"
    ), inline=False)

    e.add_field(name="Autoban", value=(
        "`>ab <user/id>` — ban across all servers, re-bans on rejoin\n"
        "`>rab <user/id>` — remove autoban"
    ), inline=False)

    e.add_field(name="Role Lock", value=(
        "`>rrl <user/id> <role>` — force a role on a user permanently\n"
        "`>sl <user/id> <role>` — remove a role lock"
    ), inline=False)

    e.add_field(name="Role Blacklist", value=(
        "`>rb <user/id> <role>` — prevent a user from ever having a role\n"
        "`>srb <user/id> <role>` — remove a role blacklist"
    ), inline=False)

    e.add_field(name="DM", value=(
        "`>dm <user> <message>` — DM a specific user\n"
        "`>massdm <message>` — DM every member in all servers\n"
        "`>smassdm` — stop an active mass DM"
    ), inline=False)

    e.add_field(name="Status", value=(
        "`>status <text>` — set a custom status (reverts after 24h)\n"
        "`>removestatus` — revert to default streaming status"
    ), inline=False)

    if is_owner(ctx.author.id):
        e.add_field(name="Whitelist", value=(
            "`>wl <user/id>` — grant a user access to all commands\n"
            "`>uwl <user/id>` — remove whitelist access\n"
            "`>wls` — list all whitelisted users"
        ), inline=False)

    e.add_field(name="Misc", value=(
        "`>ping` — latency\n"
        "`>uptime` — bot uptime"
    ), inline=False)

    e.set_footer(text="prefix: >")
    await ctx.reply(embed=e, mention_author=False)

# ── Whitelist ─────────────────────────────────────────────────────────────────

@bot.command(name='wl')
async def whitelist_add(ctx, user_input: str):
    member = await resolve_user(ctx, user_input)
    uid = None
    if member:
        uid = member.id
        name = member.name
    else:
        try:
            uid = int(user_input.strip('<@!>'))
            name = str(uid)
        except:
            await ctx.reply("couldn't find that user", mention_author=False)
            return

    if uid == OWNER_ID:
        await ctx.reply("that's you", mention_author=False)
        return

    whitelist[str(uid)] = {'name': name}
    save_data()
    await ctx.reply(f"whitelisted **{name}**", mention_author=False)

@bot.command(name='uwl')
async def whitelist_remove(ctx, user_input: str):
    if not is_owner(ctx.author.id):
        return
    member = await resolve_user(ctx, user_input)
    uid = None
    if member:
        uid = member.id
    else:
        try:
            uid = int(user_input.strip('<@!>'))
        except:
            await ctx.reply("couldn't find that user", mention_author=False)
            return

    uid_str = str(uid)
    if uid_str in whitelist:
        name = whitelist[uid_str].get('name', str(uid))
        del whitelist[uid_str]
        save_data()
        await ctx.reply(f"removed **{name}** from whitelist", mention_author=False)
    else:
        await ctx.reply("they aren't whitelisted", mention_author=False)

@bot.command(name='wls')
async def whitelist_list(ctx):
    if not is_owner(ctx.author.id):
        return
    if not whitelist:
        await ctx.reply("whitelist is empty", mention_author=False)
        return
    lines = [f"`{uid}` — {data.get('name', 'unknown')}" for uid, data in whitelist.items()]
    e = discord.Embed(description='\n'.join(lines), color=0x111111)
    e.set_author(name=f"Whitelist — {len(whitelist)} user(s)")
    await ctx.reply(embed=e, mention_author=False)

# ── React ─────────────────────────────────────────────────────────────────────

@bot.command(name='r')
async def react(ctx, user: discord.Member, *emojis):
    if not emojis:
        return
    emojis = list(emojis)[:20]
    auto_react[str(user.id)] = {'emojis': emojis, 'set_by': ctx.author.id}
    save_data()
    await ctx.reply(f"reacting to **{user.name}** with {' '.join(emojis)}", mention_author=False)

@bot.command()
async def unreact(ctx, user: discord.Member):
    if str(user.id) in auto_react:
        del auto_react[str(user.id)]
        save_data()
        await ctx.reply(f"stopped reacting to **{user.name}**", mention_author=False)
    else:
        await ctx.reply("not reacting to them", mention_author=False)

@bot.command(name='rs')
async def react_stop(ctx):
    count = len(auto_react)
    auto_react.clear()
    save_data()
    await ctx.reply(f"cleared all reactions — `{count}` removed", mention_author=False)

# ── Hush ──────────────────────────────────────────────────────────────────────

@bot.command(name='h')
async def hush(ctx, user: discord.Member):
    hushed_users[str(user.id)] = True
    save_data()
    await ctx.reply(f"hushed **{user.name}**", mention_author=False)

@bot.command()
async def unhush(ctx, user: discord.Member):
    if str(user.id) in hushed_users:
        del hushed_users[str(user.id)]
        save_data()
        await ctx.reply(f"unhushed **{user.name}**", mention_author=False)
    else:
        await ctx.reply("they weren't hushed", mention_author=False)

@bot.command(name='hs')
async def hush_stop(ctx):
    count = len(hushed_users)
    hushed_users.clear()
    save_data()
    await ctx.reply(f"unhushed everyone — `{count}` cleared", mention_author=False)

# ── Autoban ───────────────────────────────────────────────────────────────────

@bot.command(name='ab')
async def autoban(ctx, user_input: str):
    member = await resolve_user(ctx, user_input)
    uid = None
    if member:
        uid = member.id
    else:
        try:
            uid = int(user_input.strip('<@!>'))
        except:
            await ctx.reply("couldn't find that user", mention_author=False)
            return

    autobanned_users[str(uid)] = True
    save_data()

    banned_in = 0
    for guild in bot.guilds:
        try:
            await guild.ban(discord.Object(id=uid), reason="autoban", delete_message_days=1)
            banned_in += 1
        except:
            pass

    await ctx.reply(f"autobanned `{uid}` across `{banned_in}` server(s) — will re-ban on rejoin/unban", mention_author=False)

@bot.command(name='rab')
async def remove_autoban(ctx, user_input: str):
    try:
        uid = int(user_input.strip('<@!>'))
    except:
        member = await resolve_user(ctx, user_input)
        if not member:
            await ctx.reply("couldn't find that user", mention_author=False)
            return
        uid = member.id

    uid_str = str(uid)
    if uid_str in autobanned_users:
        del autobanned_users[uid_str]
        save_data()
        await ctx.reply(f"removed autoban for `{uid}` — you can unban them manually now", mention_author=False)
    else:
        await ctx.reply(f"`{uid}` wasn't on the autoban list", mention_author=False)

# ── Role Lock ─────────────────────────────────────────────────────────────────

@bot.command(name='rrl')
async def role_lock_add(ctx, user_input: str, *, role_input: str):
    member = await resolve_user(ctx, user_input)
    if not member:
        await ctx.reply("couldn't find that user", mention_author=False)
        return

    role = await resolve_role(ctx.guild, role_input)
    if not role:
        await ctx.reply("couldn't find that role", mention_author=False)
        return

    uid_str = str(member.id)
    if uid_str not in role_locks:
        role_locks[uid_str] = []

    if role.id in role_locks[uid_str]:
        await ctx.reply(f"**{role.name}** is already locked on **{member.name}**", mention_author=False)
        return

    role_locks[uid_str].append(role.id)
    save_data()

    try:
        await member.add_roles(role, reason="role lock applied")
    except:
        pass

    await ctx.reply(f"locked **{role.name}** on **{member.name}** — they cannot lose this role", mention_author=False)

@bot.command(name='sl')
async def role_lock_remove(ctx, user_input: str, *, role_input: str):
    member = await resolve_user(ctx, user_input)
    if not member:
        await ctx.reply("couldn't find that user", mention_author=False)
        return

    role = await resolve_role(ctx.guild, role_input)
    if not role:
        await ctx.reply("couldn't find that role", mention_author=False)
        return

    uid_str = str(member.id)
    if uid_str not in role_locks or role.id not in role_locks[uid_str]:
        await ctx.reply(f"**{role.name}** isn't locked on **{member.name}**", mention_author=False)
        return

    role_locks[uid_str].remove(role.id)
    if not role_locks[uid_str]:
        del role_locks[uid_str]
    save_data()

    await ctx.reply(f"removed role lock for **{role.name}** on **{member.name}**", mention_author=False)

# ── Role Blacklist ────────────────────────────────────────────────────────────

@bot.command(name='rb')
async def role_blacklist_add(ctx, user_input: str, *, role_input: str):
    member = await resolve_user(ctx, user_input)
    if not member:
        await ctx.reply("couldn't find that user", mention_author=False)
        return

    role = await resolve_role(ctx.guild, role_input)
    if not role:
        await ctx.reply("couldn't find that role", mention_author=False)
        return

    uid_str = str(member.id)
    if uid_str not in role_blacklist:
        role_blacklist[uid_str] = []

    if role.id in role_blacklist[uid_str]:
        await ctx.reply(f"**{role.name}** is already blacklisted on **{member.name}**", mention_author=False)
        return

    role_blacklist[uid_str].append(role.id)
    save_data()

    try:
        await member.remove_roles(role, reason="role blacklist applied")
    except:
        pass

    await ctx.reply(f"blacklisted **{role.name}** from **{member.name}** — they cannot gain this role", mention_author=False)

@bot.command(name='srb')
async def role_blacklist_remove(ctx, user_input: str, *, role_input: str):
    member = await resolve_user(ctx, user_input)
    if not member:
        await ctx.reply("couldn't find that user", mention_author=False)
        return

    role = await resolve_role(ctx.guild, role_input)
    if not role:
        await ctx.reply("couldn't find that role", mention_author=False)
        return

    uid_str = str(member.id)
    if uid_str not in role_blacklist or role.id not in role_blacklist[uid_str]:
        await ctx.reply(f"**{role.name}** isn't blacklisted on **{member.name}**", mention_author=False)
        return

    role_blacklist[uid_str].remove(role.id)
    if not role_blacklist[uid_str]:
        del role_blacklist[uid_str]
    save_data()

    await ctx.reply(f"removed role blacklist for **{role.name}** on **{member.name}**", mention_author=False)

# ── DM ────────────────────────────────────────────────────────────────────────

@bot.command()
async def dm(ctx, user: discord.Member, *, message):
    try:
        await user.send(message)
        await ctx.reply(f"sent to **{user.name}**", mention_author=False)
    except Exception as e:
        await ctx.reply(f"couldn't dm them: `{e}`", mention_author=False)

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
            if member.bot or member.id in seen or member.id == OWNER_ID:
                continue
            seen.add(member.id)
            try:
                await member.send(message)
                sent += 1
            except:
                failed += 1
            await asyncio.sleep(0.5)
    await ctx.reply(f"done — sent: `{sent}`, failed: `{failed}`", mention_author=False)

@bot.command()
async def smassdm(ctx):
    global stop_mass_dm
    stop_mass_dm = True
    await ctx.reply("stopped mass dm", mention_author=False)

# ── Status ────────────────────────────────────────────────────────────────────

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
    await ctx.reply("status removed", mention_author=False)

# ===== RUN =====
if __name__ == "__main__":
    if not TOKEN:
        print("no token found")
        exit(1)
    print("starting...")
    bot.run(TOKEN)

# ── Role Duplicate ────────────────────────────────────────────────────────────

@bot.command(name='rd')
async def role_duplicate(ctx, *, role_input: str):
    role = await resolve_role(ctx.guild, role_input)
    if not role:
        await ctx.reply("couldn't find that role", mention_author=False)
        return

    icon = None
    if role.icon:
        try:
            icon = await role.icon.read()
        except:
            icon = None

    try:
        new_role = await ctx.guild.create_role(
            name=f"{role.name} (copy)",
            permissions=role.permissions,
            color=role.color,
            hoist=role.hoist,
            mentionable=role.mentionable,
            reason=f"duplicated from {role.name} by {ctx.author}"
        )

        if icon:
            try:
                await new_role.edit(display_icon=icon)
            except:
                pass

        await ctx.reply(
            f"duplicated **{role.name}** — created **{new_role.name}** `({new_role.id})`",
            mention_author=False
        )
    except discord.Forbidden:
        await ctx.reply("missing permissions to create roles", mention_author=False)
    except Exception as e:
        await ctx.reply(f"failed: `{e}`", mention_author=False)
