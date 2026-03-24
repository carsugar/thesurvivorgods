"""
utils.py — Shared helpers for TheSurvivorGods.

Permission logic lives here so every cog applies it consistently.
"""

import discord
from discord import (
    CategoryChannel,
    TextChannel,
    Guild,
    Role,
    Member,
    PermissionOverwrite,
)
from typing import Optional
import logging

log = logging.getLogger("TheSurvivorGods.utils")

# ── Embed factory ────────────────────────────────────────────────────────────

TORCH_COLOR   = discord.Color.from_rgb(214, 82, 50)   # fire orange
SUCCESS_COLOR = discord.Color.from_rgb(52, 168, 83)   # green
INFO_COLOR    = discord.Color.from_rgb(66, 133, 244)  # blue
WARN_COLOR    = discord.Color.from_rgb(251, 188, 5)   # amber
ERROR_COLOR   = discord.Color.from_rgb(234, 67, 53)   # red


def embed(title: str, description: str = "", color: discord.Color = INFO_COLOR, **fields) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color)
    for name, value in fields.items():
        e.add_field(name=name, value=value, inline=False)
    return e


def success_embed(title: str, description: str = "") -> discord.Embed:
    return embed(title, description, color=SUCCESS_COLOR)


def error_embed(title: str, description: str = "") -> discord.Embed:
    return embed(title, description, color=ERROR_COLOR)


def warn_embed(title: str, description: str = "") -> discord.Embed:
    return embed(title, description, color=WARN_COLOR)


def torch_embed(
    name: str,
    reason: str = "",
    snuff_title: str = "The tribe has spoken.",
    snuff_suffix: str = "'s torch has been snuffed.",
) -> discord.Embed:
    e = discord.Embed(
        title=f"🔥 {snuff_title}",
        description=f"**{name}**{snuff_suffix}" + (f"\n{reason}" if reason else ""),
        color=TORCH_COLOR,
    )
    return e


# ── Permission builders ──────────────────────────────────────────────────────

def hidden(guild: Guild) -> dict:
    """No one can see (default deny). Used as base overwrites for private channels."""
    return {guild.default_role: PermissionOverwrite(read_messages=False)}


def player_rw(member: Member) -> PermissionOverwrite:
    return PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True)


def player_ro(member: Member) -> PermissionOverwrite:
    """Read-only — used for paused channels."""
    return PermissionOverwrite(read_messages=True, send_messages=False)


def host_rw(role: Role) -> PermissionOverwrite:
    return PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)


def spectator_ro(role: Role) -> PermissionOverwrite:
    return PermissionOverwrite(read_messages=True, send_messages=False)


# ── Role helpers ─────────────────────────────────────────────────────────────

async def get_or_create_role(guild: Guild, name: str, color: discord.Color = discord.Color.default(), **kwargs) -> Role:
    role = discord.utils.get(guild.roles, name=name)
    if role is None:
        role = await guild.create_role(name=name, color=color, **kwargs)
        log.info(f"Created role: {name}")
    return role


async def get_or_create_category(guild: Guild, name: str, overwrites: dict = None, position: int = None) -> CategoryChannel:
    cat = discord.utils.get(guild.categories, name=name)
    if cat is None:
        ow = dict(overwrites) if overwrites else {}
        ow[guild.me] = PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        kwargs = {"name": name, "overwrites": ow}
        if position is not None:
            kwargs["position"] = position
        cat = await guild.create_category(**kwargs)
        log.info(f"Created category: {name}")
    else:
        # Ensure the bot has an explicit override even on pre-existing categories
        if guild.me not in cat.overwrites or not cat.overwrites[guild.me].manage_channels:
            await cat.set_permissions(guild.me, read_messages=True, send_messages=True, manage_channels=True)
    return cat


async def get_or_create_text_channel(
    guild: Guild,
    name: str,
    category: Optional[CategoryChannel] = None,
    overwrites: dict = None,
    topic: str = "",
) -> TextChannel:
    existing = discord.utils.get(guild.text_channels, name=name)
    if existing:
        # Ensure the bot has explicit access on pre-existing channels
        bot_ow = existing.overwrites_for(guild.me)
        if not bot_ow.read_messages:
            await existing.set_permissions(
                guild.me,
                read_messages=True, send_messages=True,
                manage_messages=True, manage_channels=True,
            )
        return existing
    ow = dict(overwrites) if overwrites else {}
    # Bot must always have an explicit override in channels it creates
    ow[guild.me] = PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True, manage_channels=True)
    kwargs = {"name": name, "overwrites": ow}
    if category:
        kwargs["category"] = category
    if topic:
        kwargs["topic"] = topic
    channel = await guild.create_text_channel(**kwargs)
    log.info(f"Created channel: #{name}")
    return channel


# ── Channel pause / resume ───────────────────────────────────────────────────

async def pause_channel(channel: TextChannel, members: list[Member]):
    """Make a channel read-only for specific members (tribe swap / boot)."""
    for member in members:
        await channel.set_permissions(member, overwrite=player_ro(member))
    log.info(f"Paused #{channel.name} for {len(members)} members")


async def lock_channel(channel: TextChannel):
    """Fully hide a channel from everyone (used after snuff for tribe chats)."""
    await channel.set_permissions(channel.guild.default_role, overwrite=PermissionOverwrite(read_messages=False))
    log.info(f"Locked #{channel.name}")


# ── Archive helpers ──────────────────────────────────────────────────────────

async def ensure_archive_category(guild: Guild, game: dict) -> CategoryChannel:
    """Get or create the season archive category (host read-only, hidden from everyone else)."""
    cat_id = game.get("archive_category_id")
    if cat_id:
        cat = guild.get_channel(cat_id)
        if cat:
            return cat
    host_role = guild.get_role(game["host_role_id"]) if game.get("host_role_id") else None
    ow = {guild.default_role: PermissionOverwrite(read_messages=False)}
    if host_role:
        ow[host_role] = PermissionOverwrite(read_messages=True, send_messages=False)
    cat = await get_or_create_category(guild, "📦 Archive", overwrites=ow)
    game["archive_category_id"] = cat.id
    return cat


# ── Member resolution ────────────────────────────────────────────────────────

async def resolve_member(guild: Guild, user_id: int) -> Optional[Member]:
    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except discord.NotFound:
            return None
    return member


# ── Name sanitization ────────────────────────────────────────────────────────

def channel_safe(name: str) -> str:
    """Convert a display name to a valid Discord channel name."""
    return name.lower().replace(" ", "-").replace("_", "-").replace("'", "").replace('"', "")[:50]
