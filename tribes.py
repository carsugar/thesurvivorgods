"""
cogs/tribes.py — Tribe lifecycle commands.

Commands:
  /tribesetup    — Create a tribe and all its channels for a list of players
  /tribeswap     — Randomly (or manually) reassign players to new tribes
  /merge         — Collapse all tribes into a single merged tribe
  /createalliance — Let a player (or host) create an alliance chat
  /disbandalliance — Remove an alliance channel
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord import Guild, Member, PermissionOverwrite
from typing import Optional
import random
import logging
import state
import utils

log = logging.getLogger("TheSurvivorGods.tribes")

DEFAULT_SEASON = 1

# Preset tribe colors. Hosts can also pass a hex value.
TRIBE_COLORS = {
    "red":    discord.Color.red(),
    "blue":   discord.Color.blue(),
    "yellow": discord.Color.yellow(),
    "green":  discord.Color.green(),
    "purple": discord.Color.purple(),
    "orange": discord.Color.orange(),
    "teal":   discord.Color.teal(),
    "pink":   discord.Color.magenta(),
}


class TribesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /tribesetup ──────────────────────────────────────────────────────────

    @app_commands.command(name="tribesetup", description="Create a tribe and all its channels for the given players.")
    @app_commands.describe(
        tribe_name="Tribe name (e.g. Luzon)",
        members="Space-separated @mentions of all tribe members",
        color="Tribe color (red/blue/yellow/green/purple/orange/teal/pink or hex #RRGGBB)",
        season="Season number (default: 1)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def tribesetup(
        self,
        interaction: discord.Interaction,
        tribe_name: str,
        members: str,
        color: str = "blue",
        season: int = DEFAULT_SEASON,
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        game = state.load(season)

        # Parse members
        member_ids = [int(m.strip("<@!>")) for m in members.split() if m.startswith("<@")]
        if not member_ids:
            await interaction.followup.send(
                embed=utils.error_embed("No members", "Please @mention all tribe members."),
                ephemeral=True,
            )
            return

        discord_members: list[Member] = []
        missing: list[str] = []
        for mid in member_ids:
            m = await utils.resolve_member(guild, mid)
            if m:
                discord_members.append(m)
            else:
                missing.append(str(mid))

        if missing:
            await interaction.followup.send(
                embed=utils.warn_embed("Members not found", f"Could not find: {', '.join(missing)}"),
                ephemeral=True,
            )
            return

        # Validate all are registered players
        for m in discord_members:
            if str(m.id) not in game["players"]:
                await interaction.followup.send(
                    embed=utils.error_embed("Unregistered player", f"{m.mention} hasn't been added via /addplayer."),
                    ephemeral=True,
                )
                return

        # Parse color
        tribe_color = TRIBE_COLORS.get(color.lower())
        if not tribe_color:
            try:
                tribe_color = discord.Color(int(color.lstrip("#"), 16))
            except ValueError:
                tribe_color = discord.Color.blue()

        host_role = guild.get_role(game["host_role_id"]) if game["host_role_id"] else None
        spec_role  = guild.get_role(game["spectator_role_id"]) if game["spectator_role_id"] else None
        theme = state.get_theme(game)

        # Create tribe role
        tribe_role = await utils.get_or_create_role(guild, f"S{season} {tribe_name}", color=tribe_color, hoist=True)
        for m in discord_members:
            await m.add_roles(tribe_role)

        # ── Tribe category (tribe chat + alliance category header) ────────────
        tribe_cat_overwrites = {
            guild.default_role: PermissionOverwrite(read_messages=False),
            tribe_role:         PermissionOverwrite(read_messages=True, send_messages=True),
        }
        if host_role:
            tribe_cat_overwrites[host_role] = PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)

        tribe_cat = await utils.get_or_create_category(
            guild,
            f"S{season} {theme['tribe_emoji']} {tribe_name}",
            overwrites=tribe_cat_overwrites,
        )

        # Tribe chat — all tribe members + hosts
        tribe_chat = await utils.get_or_create_text_channel(
            guild,
            f"{utils.channel_safe(tribe_name)}-{utils.channel_safe(theme['tribe_chat_label'])}",
            category=tribe_cat,
            topic=f"🌴 {tribe_name} tribe chat — all members.",
        )

        # ── Alliances category ────────────────────────────────────────────────
        alliances_cat = await utils.get_or_create_category(
            guild,
            f"S{season} {theme['alliance_emoji']} {tribe_name} {theme['alliances_label']}",
            overwrites={guild.default_role: PermissionOverwrite(read_messages=False)},
        )

        # ── 1:1 channels category ─────────────────────────────────────────────
        ones_cat = await utils.get_or_create_category(
            guild,
            f"S{season} {theme['ones_emoji']} {tribe_name} {theme['ones_label']}",
            overwrites={guild.default_role: PermissionOverwrite(read_messages=False)},
        )

        ones_channels: dict[str, int] = {}

        # Create every unique pair
        for i, m1 in enumerate(discord_members):
            for m2 in discord_members[i + 1:]:
                n1 = utils.channel_safe(game["players"][str(m1.id)]["name"])
                n2 = utils.channel_safe(game["players"][str(m2.id)]["name"])
                ch_name = f"{n1}-{n2}"
                pair_key = f"{m1.id}-{m2.id}"

                overwrites = {
                    guild.default_role: PermissionOverwrite(read_messages=False),
                    m1:                 utils.player_rw(m1),
                    m2:                 utils.player_rw(m2),
                }
                if host_role:
                    overwrites[host_role] = utils.host_rw(host_role)

                ch = await utils.get_or_create_text_channel(
                    guild,
                    ch_name,
                    category=ones_cat,
                    overwrites=overwrites,
                    topic=f"Private 1:1 between {game['players'][str(m1.id)]['name']} and {game['players'][str(m2.id)]['name']}.",
                )
                ones_channels[pair_key] = ch.id

        # ── Persist tribe state ───────────────────────────────────────────────
        game["tribes"][tribe_name] = {
            "color": tribe_color.value,
            "role_id": tribe_role.id,
            "category_id": alliances_cat.id,
            "tribe_cat_id": tribe_cat.id,
            "tribe_chat_id": tribe_chat.id,
            "ones_category_id": ones_cat.id,
            "ones_channels": ones_channels,
            "members": [str(m.id) for m in discord_members],
        }

        for m in discord_members:
            game["players"][str(m.id)]["tribe"] = tribe_name

        await state.save(season, game)

        pair_count = len(ones_channels)
        log.info(f"Tribe {tribe_name} set up with {len(discord_members)} players, {pair_count} 1:1s")
        await interaction.followup.send(
            embed=utils.success_embed(
                f"Tribe {tribe_name} created!",
                f"**Members:** {', '.join(m.display_name for m in discord_members)}\n"
                f"**Tribe chat:** {tribe_chat.mention}\n"
                f"**1:1 channels created:** {pair_count}\n"
                f"**Alliance category:** {alliances_cat.name}",
            ),
            ephemeral=True,
        )

    # ── /tribeswap ────────────────────────────────────────────────────────────

    @app_commands.command(name="tribeswap", description="Reassign active players to new tribes (random or manual).")
    @app_commands.describe(
        new_tribe_names="Comma-separated new tribe names (e.g. 'Angkor,Ta Keo,Bayon')",
        manual_assignments="Optional: JSON string mapping Discord user IDs to tribe names",
        season="Season number (default: 1)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def tribeswap(
        self,
        interaction: discord.Interaction,
        new_tribe_names: str,
        manual_assignments: Optional[str] = None,
        season: int = DEFAULT_SEASON,
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        game = state.load(season)

        tribes = [t.strip() for t in new_tribe_names.split(",") if t.strip()]
        if not tribes:
            await interaction.followup.send(embed=utils.error_embed("No tribe names given."), ephemeral=True)
            return

        active = state.active_players(game)
        if not active:
            await interaction.followup.send(embed=utils.error_embed("No active players."), ephemeral=True)
            return

        host_role = guild.get_role(game["host_role_id"]) if game["host_role_id"] else None
        theme = state.get_theme(game)

        # ── 1. Pause old tribe channels ───────────────────────────────────────
        for tribe_name, tribe_data in game["tribes"].items():
            tribe_members_discord: list[Member] = []
            for uid in tribe_data["members"]:
                m = await utils.resolve_member(guild, int(uid))
                if m:
                    tribe_members_discord.append(m)

            # Pause tribe chat
            tc = guild.get_channel(tribe_data["tribe_chat_id"])
            if tc:
                await utils.pause_channel(tc, tribe_members_discord)

            # Pause 1:1s
            for ch_id in tribe_data["ones_channels"].values():
                ch = guild.get_channel(ch_id)
                if ch:
                    await utils.pause_channel(ch, tribe_members_discord)

            # Remove tribe roles
            tribe_role = guild.get_role(tribe_data["role_id"])
            if tribe_role:
                for m in tribe_members_discord:
                    await m.remove_roles(tribe_role)

            log.info(f"Paused old tribe: {tribe_name}")

        # ── 2. Assign players to new tribes ──────────────────────────────────
        import json as _json
        if manual_assignments:
            try:
                uid_to_tribe: dict[str, str] = _json.loads(manual_assignments)
            except Exception:
                await interaction.followup.send(
                    embed=utils.error_embed("Bad JSON", "Could not parse manual_assignments."),
                    ephemeral=True,
                )
                return
        else:
            # Random shuffle, distribute as evenly as possible
            player_uids = [uid for uid, _ in active]
            random.shuffle(player_uids)
            uid_to_tribe = {}
            for i, uid in enumerate(player_uids):
                uid_to_tribe[uid] = tribes[i % len(tribes)]

        # ── 3. Create new tribe setups ────────────────────────────────────────
        new_tribe_members: dict[str, list[str]] = {t: [] for t in tribes}
        for uid, tribe_name in uid_to_tribe.items():
            new_tribe_members[tribe_name].append(uid)
            game["players"][uid]["tribe"] = tribe_name

        summary_lines = []
        for tribe_name, uids in new_tribe_members.items():
            discord_members: list[Member] = []
            for uid in uids:
                m = await utils.resolve_member(guild, int(uid))
                if m:
                    discord_members.append(m)

            if not discord_members:
                continue

            # Re-use tribesetup logic inline (simplified — color defaults to blue)
            tribe_color = discord.Color.blue()
            tribe_role = await utils.get_or_create_role(guild, f"S{season} {tribe_name}", color=tribe_color, hoist=True)
            for m in discord_members:
                await m.add_roles(tribe_role)

            tribe_cat_overwrites = {
                guild.default_role: PermissionOverwrite(read_messages=False),
                tribe_role:         PermissionOverwrite(read_messages=True, send_messages=True),
            }
            if host_role:
                tribe_cat_overwrites[host_role] = PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)

            tribe_cat = await utils.get_or_create_category(guild, f"S{season} {theme['tribe_emoji']} {tribe_name}", overwrites=tribe_cat_overwrites)
            tribe_chat = await utils.get_or_create_text_channel(guild, f"{utils.channel_safe(tribe_name)}-{utils.channel_safe(theme['tribe_chat_label'])}", category=tribe_cat)
            alliances_cat = await utils.get_or_create_category(guild, f"S{season} {theme['alliance_emoji']} {tribe_name} {theme['alliances_label']}", overwrites={guild.default_role: PermissionOverwrite(read_messages=False)})
            ones_cat = await utils.get_or_create_category(guild, f"S{season} {theme['ones_emoji']} {tribe_name} {theme['ones_label']}", overwrites={guild.default_role: PermissionOverwrite(read_messages=False)})

            ones_channels: dict[str, int] = {}
            for i, m1 in enumerate(discord_members):
                for m2 in discord_members[i + 1:]:
                    n1 = utils.channel_safe(game["players"][str(m1.id)]["name"])
                    n2 = utils.channel_safe(game["players"][str(m2.id)]["name"])
                    overwrites = {
                        guild.default_role: PermissionOverwrite(read_messages=False),
                        m1:                 utils.player_rw(m1),
                        m2:                 utils.player_rw(m2),
                    }
                    if host_role:
                        overwrites[host_role] = utils.host_rw(host_role)
                    ch = await utils.get_or_create_text_channel(guild, f"{n1}-{n2}-swap", category=ones_cat, overwrites=overwrites)
                    ones_channels[f"{m1.id}-{m2.id}"] = ch.id

            game["tribes"][tribe_name] = {
                "color": tribe_color.value,
                "role_id": tribe_role.id,
                "category_id": alliances_cat.id,
                "tribe_cat_id": tribe_cat.id,
                "tribe_chat_id": tribe_chat.id,
                "ones_category_id": ones_cat.id,
                "ones_channels": ones_channels,
                "members": [str(m.id) for m in discord_members],
            }

            names = ", ".join(game["players"][str(m.id)]["name"] for m in discord_members)
            summary_lines.append(f"**{tribe_name}:** {names}")
            log.info(f"New tribe {tribe_name}: {names}")

        await state.save(season, game)
        await interaction.followup.send(
            embed=utils.success_embed(
                "Tribe Swap Complete! 🔀",
                "\n".join(summary_lines) or "No assignments made.",
            ),
            ephemeral=True,
        )

    # ── /merge ────────────────────────────────────────────────────────────────

    @app_commands.command(name="merge", description="Merge all tribes into a single merged tribe.")
    @app_commands.describe(
        merge_name="Name of the merged tribe (e.g. 'Vinaka')",
        season="Season number (default: 1)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def merge(self, interaction: discord.Interaction, merge_name: str = "Merged", season: int = DEFAULT_SEASON):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        game = state.load(season)

        host_role = guild.get_role(game["host_role_id"]) if game["host_role_id"] else None
        spec_role  = guild.get_role(game["spectator_role_id"]) if game["spectator_role_id"] else None
        theme = state.get_theme(game)

        active = state.active_players(game)

        # Pause all existing tribe channels
        for tribe_data in game["tribes"].values():
            tribe_members_discord = []
            for uid in tribe_data["members"]:
                m = await utils.resolve_member(guild, int(uid))
                if m:
                    tribe_members_discord.append(m)

            tc = guild.get_channel(tribe_data["tribe_chat_id"])
            if tc:
                await utils.pause_channel(tc, tribe_members_discord)

            for ch_id in tribe_data["ones_channels"].values():
                ch = guild.get_channel(ch_id)
                if ch:
                    await utils.pause_channel(ch, tribe_members_discord)

            tribe_role = guild.get_role(tribe_data["role_id"])
            if tribe_role:
                for m in tribe_members_discord:
                    await m.remove_roles(tribe_role)

        # Create merged tribe role
        merged_color = discord.Color.gold()
        merged_role = await utils.get_or_create_role(guild, f"S{season} {merge_name}", color=merged_color, hoist=True)

        all_members: list[Member] = []
        for uid, _ in active:
            m = await utils.resolve_member(guild, int(uid))
            if m:
                all_members.append(m)
                await m.add_roles(merged_role)
                game["players"][uid]["tribe"] = merge_name

        # Merged tribe category
        overwrites = {
            guild.default_role: PermissionOverwrite(read_messages=False),
            merged_role:        PermissionOverwrite(read_messages=True, send_messages=True),
        }
        if host_role:
            overwrites[host_role] = PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)

        merge_cat = await utils.get_or_create_category(guild, f"S{season} {theme['merge_emoji']} {merge_name}", overwrites=overwrites)
        merge_chat = await utils.get_or_create_text_channel(
            guild, f"{utils.channel_safe(merge_name)}-{utils.channel_safe(theme['merge_chat_label'])}", category=merge_cat,
            topic=f"Merged tribe — {merge_name}. {len(all_members)} players remain.",
        )

        # Cross-tribe 1:1s — every new pair that didn't previously exist
        ones_cat = await utils.get_or_create_category(guild, f"S{season} {theme['ones_emoji']} {merge_name} {theme['ones_label']}", overwrites={guild.default_role: PermissionOverwrite(read_messages=False)})
        ones_channels: dict[str, int] = {}

        for i, m1 in enumerate(all_members):
            for m2 in all_members[i + 1:]:
                n1 = utils.channel_safe(game["players"][str(m1.id)]["name"])
                n2 = utils.channel_safe(game["players"][str(m2.id)]["name"])
                pair_key = f"{m1.id}-{m2.id}"
                ow = {
                    guild.default_role: PermissionOverwrite(read_messages=False),
                    m1:                 utils.player_rw(m1),
                    m2:                 utils.player_rw(m2),
                }
                if host_role:
                    ow[host_role] = utils.host_rw(host_role)
                ch = await utils.get_or_create_text_channel(guild, f"{n1}-{n2}-merge", category=ones_cat, overwrites=ow)
                ones_channels[pair_key] = ch.id

        game["tribes"][merge_name] = {
            "color": merged_color.value,
            "role_id": merged_role.id,
            "category_id": ones_cat.id,
            "tribe_cat_id": merge_cat.id,
            "tribe_chat_id": merge_chat.id,
            "ones_category_id": ones_cat.id,
            "ones_channels": ones_channels,
            "members": [str(m.id) for m in all_members],
        }
        game["phase"] = "merged"

        await state.save(season, game)
        log.info(f"Merge into {merge_name} with {len(all_members)} players")
        await interaction.followup.send(
            embed=utils.success_embed(
                f"⚔️ The merge has happened! Welcome to {merge_name}.",
                f"{len(all_members)} players remain.\n"
                f"Merge chat: {merge_chat.mention}\n"
                f"New 1:1 channels: {len(ones_channels)}",
            ),
            ephemeral=True,
        )

    # ── /createalliance ───────────────────────────────────────────────────────

    @app_commands.command(name="createalliance", description="Create a private alliance chat within the tribe.")
    @app_commands.describe(
        alliance_name="Name for the alliance channel",
        tribe_name="Which tribe's alliance category to use",
        member1="Alliance member",
        member2="Alliance member",
        member3="Alliance member",
        member4="Alliance member",
        member5="Alliance member",
        member6="Alliance member",
        member7="Alliance member",
        member8="Alliance member",
        season="Season number (default: 1)",
    )
    async def createalliance(
        self,
        interaction: discord.Interaction,
        alliance_name: str,
        tribe_name: str,
        member1: discord.Member,
        member2: discord.Member,
        member3: discord.Member,
        member4: Optional[discord.Member] = None,
        member5: Optional[discord.Member] = None,
        member6: Optional[discord.Member] = None,
        member7: Optional[discord.Member] = None,
        member8: Optional[discord.Member] = None,
        season: int = DEFAULT_SEASON,
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        game = state.load(season)

        tribe = state.get_tribe(game, tribe_name)
        if not tribe:
            await interaction.followup.send(embed=utils.error_embed("Tribe not found", f"'{tribe_name}' doesn't exist."), ephemeral=True)
            return

        host_role = guild.get_role(game["host_role_id"]) if game["host_role_id"] else None

        # Validate requester is in the tribe (unless host)
        uid = str(interaction.user.id)
        is_host = host_role and host_role in interaction.user.roles
        if not is_host and uid not in tribe["members"]:
            await interaction.followup.send(embed=utils.error_embed("Not in tribe", "You must be in this tribe to create an alliance."), ephemeral=True)
            return

        # Collect selected members, deduplicating
        seen: set[int] = set()
        discord_members: list[Member] = []
        for m in [member1, member2, member3, member4, member5, member6, member7, member8]:
            if m is not None and m.id not in seen:
                seen.add(m.id)
                discord_members.append(m)

        # All must be in the tribe
        for m in discord_members:
            if str(m.id) not in tribe["members"]:
                await interaction.followup.send(
                    embed=utils.error_embed("Cross-tribe alliance", f"{m.display_name} is not in {tribe_name}."),
                    ephemeral=True,
                )
                return

        alliances_cat = guild.get_channel(tribe["category_id"])
        if not alliances_cat:
            await interaction.followup.send(embed=utils.error_embed("Category not found", "Alliance category missing."), ephemeral=True)
            return

        overwrites = {guild.default_role: PermissionOverwrite(read_messages=False)}
        for m in discord_members:
            overwrites[m] = utils.player_rw(m)
        if host_role:
            overwrites[host_role] = utils.host_rw(host_role)

        ch = await guild.create_text_channel(
            name=utils.channel_safe(alliance_name),
            category=alliances_cat,
            overwrites=overwrites,
            topic=f"Alliance: {alliance_name}",
        )

        await interaction.followup.send(
            embed=utils.success_embed(
                f"Alliance '{alliance_name}' created!",
                f"Members: {', '.join(m.display_name for m in discord_members)}\n{ch.mention}",
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TribesCog(bot))
