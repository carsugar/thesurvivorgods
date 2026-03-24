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
import asyncio
import logging
import state
import utils

log = logging.getLogger("TheSurvivorGods.tribes")

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


def _parse_color(raw: str) -> discord.Color:
    raw = raw.strip().lower()
    if raw in TRIBE_COLORS:
        return TRIBE_COLORS[raw]
    try:
        return discord.Color(int(raw.lstrip("#"), 16))
    except (ValueError, AttributeError):
        return discord.Color.blue()


def _swap_intro(tribe_name: str, pos: int, total: int) -> str:
    """Return a dramatic intro line for player pos (0-indexed) out of total."""
    if pos == 0:
        return f"First up for **{tribe_name}**... we have..."
    if pos == total - 1:
        return f"And finally, rounding out **{tribe_name}**..."
    phrases = [
        f"Next, joining **{tribe_name}**...",
        f"Also heading to **{tribe_name}**...",
        f"Adding to **{tribe_name}**...",
        f"Another one for **{tribe_name}**...",
        f"Making their way to **{tribe_name}**...",
    ]
    return phrases[(pos - 1) % len(phrases)]


class TribeSwapModal(discord.ui.Modal, title="Tribe Swap Setup"):
    tribe_names = discord.ui.TextInput(
        label="New Tribe Names (one per line)",
        style=discord.TextStyle.paragraph,
        placeholder="Fire\nWater\nEarth",
        required=True,
    )
    tribe_descriptions = discord.ui.TextInput(
        label="Descriptions (one per line, optional)",
        style=discord.TextStyle.paragraph,
        placeholder="The unstoppable force\nThe calming tide\nThe steady ground",
        required=False,
    )
    tribe_colors = discord.ui.TextInput(
        label="Colors (one per line: name or #hex, optional)",
        style=discord.TextStyle.paragraph,
        placeholder="red\nblue\ngreen",
        required=False,
    )
    tribe_emojis = discord.ui.TextInput(
        label="Emojis (one per line, optional)",
        style=discord.TextStyle.paragraph,
        placeholder="🔥\n💧\n🌍",
        required=False,
    )
    manual_assignments = discord.ui.TextInput(
        label="Manual Assignments (JSON, optional)",
        style=discord.TextStyle.short,
        placeholder='Leave blank for random. {"uid": "Fire"}',
        required=False,
    )

    def __init__(self, season: int):
        super().__init__()
        self.season = season

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        season = self.season
        guild = interaction.guild
        game = state.load(season)

        tribes = [t.strip() for t in str(self.tribe_names).splitlines() if t.strip()]
        if not tribes:
            await interaction.followup.send(embed=utils.error_embed("No tribe names", "Enter at least one tribe name."), ephemeral=True)
            return

        def _parse_lines(field) -> list[str]:
            raw = str(field).strip()
            return [l.strip() for l in raw.splitlines()] if raw else []

        desc_lines  = _parse_lines(self.tribe_descriptions)
        color_lines = _parse_lines(self.tribe_colors)
        emoji_lines = _parse_lines(self.tribe_emojis)

        tribe_descs_map:  dict[str, str]        = {t: desc_lines[i]  if i < len(desc_lines)  else ""   for i, t in enumerate(tribes)}
        tribe_colors_map: dict[str, discord.Color] = {t: _parse_color(color_lines[i]) if i < len(color_lines) else discord.Color.blue() for i, t in enumerate(tribes)}
        tribe_emojis_map: dict[str, str]        = {t: emoji_lines[i] if i < len(emoji_lines) else ""   for i, t in enumerate(tribes)}

        active = state.active_players(game)
        if not active:
            await interaction.followup.send(embed=utils.error_embed("No active players."), ephemeral=True)
            return

        host_role = guild.get_role(game["host_role_id"]) if game["host_role_id"] else None
        theme = state.get_theme(game)

        # ── 1. Build assignments only — no Discord changes yet ────────────────
        import json as _json
        manual_raw = str(self.manual_assignments).strip()
        if manual_raw:
            try:
                uid_to_tribe: dict[str, str] = _json.loads(manual_raw)
            except Exception:
                await interaction.followup.send(
                    embed=utils.error_embed("Bad JSON", "Could not parse manual assignments."),
                    ephemeral=True,
                )
                return
        else:
            player_uids = [uid for uid, _ in active]
            random.shuffle(player_uids)
            uid_to_tribe = {}
            for i, uid in enumerate(player_uids):
                uid_to_tribe[uid] = tribes[i % len(tribes)]

        # Group players by tribe (in the order tribes were listed)
        new_tribe_members: dict[str, list[str]] = {t: [] for t in tribes}
        for uid, t in uid_to_tribe.items():
            new_tribe_members[t].append(uid)

        # ── 2. Live reveal — tribe by tribe, then player by player ────────────
        announce_ch = interaction.channel
        await announce_ch.send("🔀 **The Tribe Swap is upon us...**")
        await asyncio.sleep(2.5)
        await announce_ch.send("...")
        await asyncio.sleep(2)
        await announce_ch.send("...")
        await asyncio.sleep(2.5)

        # Shuffle tribe reveal order for extra drama
        reveal_tribes = list(tribes)
        random.shuffle(reveal_tribes)

        for tribe_name in reveal_tribes:
            uids_in_tribe = new_tribe_members.get(tribe_name, [])
            if not uids_in_tribe:
                continue

            t_emoji = tribe_emojis_map.get(tribe_name) or theme["tribe_emoji"]
            desc    = tribe_descs_map.get(tribe_name, "")

            # Announce the tribe name
            await asyncio.sleep(1)
            header = f"{t_emoji} **{tribe_name.upper()}** {t_emoji}"
            if desc:
                header += f"\n*{desc}*"
            await announce_ch.send(header)
            await asyncio.sleep(3)

            # Reveal each player in this tribe one at a time
            tribe_uids_shuffled = list(uids_in_tribe)
            random.shuffle(tribe_uids_shuffled)
            total = len(tribe_uids_shuffled)

            for pos, uid in enumerate(tribe_uids_shuffled):
                player_name = game["players"][uid]["name"]
                m = await utils.resolve_member(guild, int(uid))
                mention = m.mention if m else f"**{player_name}**"
                await announce_ch.send(_swap_intro(tribe_name, pos, total))
                await asyncio.sleep(2.5)
                await announce_ch.send(f"➡️ {mention}")
                await asyncio.sleep(2)

            await asyncio.sleep(1)

        await announce_ch.send("🔥 **The tribes have been decided. Good luck to everyone!** 🔥")

        # ── 3. Now do all Discord work ────────────────────────────────────────

        for old_tribe_name, tribe_data in game["tribes"].items():
            tribe_members_discord: list[Member] = []
            for uid in tribe_data["members"]:
                tm = await utils.resolve_member(guild, int(uid))
                if tm:
                    tribe_members_discord.append(tm)

            tc = guild.get_channel(tribe_data["tribe_chat_id"])
            if tc:
                await utils.pause_channel(tc, tribe_members_discord)

            for ch_id in tribe_data["ones_channels"].values():
                ch = guild.get_channel(ch_id)
                if ch:
                    await utils.pause_channel(ch, tribe_members_discord)

            tribe_role = guild.get_role(tribe_data["role_id"])
            if tribe_role:
                for tm in tribe_members_discord:
                    await tm.remove_roles(tribe_role)

            log.info(f"Paused old tribe: {old_tribe_name}")

        # Snapshot old tribe data before we overwrite entries with new tribes
        old_tribes = dict(game["tribes"])

        for uid, tribe_name in uid_to_tribe.items():
            game["players"][uid]["tribe"] = tribe_name

        host_summary_lines = []
        live_channel_ids: set[int] = set()  # IDs actively used by new tribes
        for tribe_name, uids in new_tribe_members.items():
            discord_members: list[Member] = []
            for uid in uids:
                m = await utils.resolve_member(guild, int(uid))
                if m:
                    discord_members.append(m)

            if not discord_members:
                continue

            tribe_color = tribe_colors_map.get(tribe_name, discord.Color.blue())
            tribe_role = await utils.get_or_create_role(guild, tribe_name, color=tribe_color, hoist=True)
            for m in discord_members:
                await m.add_roles(tribe_role)

            tribe_cat_overwrites = {
                guild.default_role: PermissionOverwrite(read_messages=False),
                tribe_role:         PermissionOverwrite(read_messages=True, send_messages=True),
            }
            if host_role:
                tribe_cat_overwrites[host_role] = PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)

            t_emoji = tribe_emojis_map.get(tribe_name) or theme["tribe_emoji"]
            tribe_cat = await utils.get_or_create_category(guild, f"{t_emoji} {tribe_name}", overwrites=tribe_cat_overwrites)
            tribe_chat = await utils.get_or_create_text_channel(guild, f"{utils.channel_safe(tribe_name)}-{utils.channel_safe(theme['tribe_chat_label'])}", category=tribe_cat)
            alliances_cat = await utils.get_or_create_category(guild, f"{theme['alliance_emoji']} {tribe_name} {theme['alliances_label']}", overwrites={guild.default_role: PermissionOverwrite(read_messages=False)})
            ones_cat = await utils.get_or_create_category(guild, f"{theme['ones_emoji']} {tribe_name} {theme['ones_label']}", overwrites={guild.default_role: PermissionOverwrite(read_messages=False)})

            ones_channels: dict[str, int] = {}
            for i, m1 in enumerate(discord_members):
                for m2 in discord_members[i + 1:]:
                    uid1, uid2 = str(m1.id), str(m2.id)
                    pair_key = f"{min(uid1, uid2)}-{max(uid1, uid2)}"
                    sorted_names = sorted([
                        utils.channel_safe(game["players"][uid1]["name"]),
                        utils.channel_safe(game["players"][uid2]["name"]),
                    ])
                    ch_name = f"{sorted_names[0]}-{sorted_names[1]}"

                    existing_ch_id = state.find_ones_channel(game, uid1, uid2)
                    if existing_ch_id:
                        ch = guild.get_channel(existing_ch_id)
                        if ch:
                            await ch.edit(category=ones_cat)
                            await ch.set_permissions(m1, read_messages=True, send_messages=True)
                            await ch.set_permissions(m2, read_messages=True, send_messages=True)
                            ones_channels[pair_key] = ch.id
                            continue

                    overwrites = {
                        guild.default_role: PermissionOverwrite(read_messages=False),
                        m1:                 utils.player_rw(m1),
                        m2:                 utils.player_rw(m2),
                        guild.me:           PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True, manage_channels=True),
                    }
                    if host_role:
                        overwrites[host_role] = utils.host_rw(host_role)
                    ch = await guild.create_text_channel(ch_name, category=ones_cat, overwrites=overwrites)
                    ones_channels[pair_key] = ch.id

            spec_role_swap = guild.get_role(game["spectator_role_id"]) if game.get("spectator_role_id") else None
            conf_ow = {guild.default_role: PermissionOverwrite(read_messages=False)}
            if host_role:
                conf_ow[host_role] = PermissionOverwrite(read_messages=True, send_messages=True)
            if spec_role_swap:
                conf_ow[spec_role_swap] = PermissionOverwrite(read_messages=True, send_messages=False)
            subs_ow = {guild.default_role: PermissionOverwrite(read_messages=False)}
            if host_role:
                subs_ow[host_role] = PermissionOverwrite(read_messages=True, send_messages=True)

            tribe_conf_cat = await utils.get_or_create_category(
                guild, f"📖 {tribe_name} {theme['confessionals_label']}", overwrites=conf_ow,
            )
            tribe_subs_cat = await utils.get_or_create_category(
                guild, f"📬 {tribe_name} {theme['submissions_label']}", overwrites=subs_ow,
            )
            for m in discord_members:
                uid = str(m.id)
                conf_ch = guild.get_channel(game["players"][uid].get("confessional_id"))
                if conf_ch:
                    await conf_ch.edit(category=tribe_conf_cat)
                subs_ch = guild.get_channel(game["players"][uid].get("submissions_id"))
                if subs_ch:
                    await subs_ch.edit(category=tribe_subs_cat)

            game["tribes"][tribe_name] = {
                "color":           tribe_color.value,
                "description":     tribe_descs_map.get(tribe_name, ""),
                "emoji":           tribe_emojis_map.get(tribe_name, ""),
                "role_id":         tribe_role.id,
                "category_id":     alliances_cat.id,
                "tribe_cat_id":    tribe_cat.id,
                "tribe_chat_id":   tribe_chat.id,
                "ones_category_id": ones_cat.id,
                "ones_channels":   ones_channels,
                "conf_category_id": tribe_conf_cat.id,
                "subs_category_id": tribe_subs_cat.id,
                "members":         [str(m.id) for m in discord_members],
            }

            live_channel_ids.add(tribe_chat.id)
            for ch_id in ones_channels.values():
                live_channel_ids.add(ch_id)

            names = ", ".join(game["players"][str(m.id)]["name"] for m in discord_members)
            host_summary_lines.append(f"**{tribe_name}:** {names}")
            log.info(f"New tribe {tribe_name}: {names}")

        # ── 4. Archive old tribe channels and remove empty categories ─────────
        archive_cat = await utils.ensure_archive_category(guild, game)

        for old_name, old_data in old_tribes.items():
            # Tribe chat — always archive (never reused)
            tc_id = old_data.get("tribe_chat_id")
            if tc_id and tc_id not in live_channel_ids:
                tc = guild.get_channel(tc_id)
                if tc:
                    await tc.edit(category=archive_cat, sync_permissions=True)

            # 1:1 channels — archive only non-reused ones
            for ch_id in old_data.get("ones_channels", {}).values():
                if ch_id not in live_channel_ids:
                    ch = guild.get_channel(ch_id)
                    if ch:
                        await ch.edit(category=archive_cat, sync_permissions=True)

            # Alliance channels — move to archive, then delete alliance category
            alliance_cat_id = old_data.get("category_id")
            if alliance_cat_id:
                alliance_cat_obj = guild.get_channel(alliance_cat_id)
                if alliance_cat_obj:
                    for ch in list(alliance_cat_obj.channels):
                        await ch.edit(category=archive_cat, sync_permissions=True)
                    await alliance_cat_obj.delete()

            # Delete old structural categories if now empty
            for cat_id in [old_data.get("tribe_cat_id"), old_data.get("ones_category_id")]:
                if cat_id:
                    cat = guild.get_channel(cat_id)
                    if cat and not cat.channels:
                        await cat.delete()

            # Conf/subs categories: delete if empty (active players' channels already moved)
            for cat_id in [old_data.get("conf_category_id"), old_data.get("subs_category_id")]:
                if cat_id:
                    cat = guild.get_channel(cat_id)
                    if cat and not cat.channels:
                        await cat.delete()

        await state.save(season, game)
        await interaction.followup.send(
            embed=utils.success_embed(
                "Tribe Swap Complete! 🔀",
                "\n".join(host_summary_lines) or "No assignments made.",
            ),
            ephemeral=True,
        )


class TribesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /tribesetup ──────────────────────────────────────────────────────────

    @app_commands.command(name="tribesetup", description="Create a tribe and all its channels for the given players.")
    @app_commands.describe(
        tribe_name="Tribe name (e.g. Luzon)",
        members="Space-separated @mentions of all tribe members",
        color="Tribe color (red/blue/yellow/green/purple/orange/teal/pink or hex #RRGGBB)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def tribesetup(
        self,
        interaction: discord.Interaction,
        tribe_name: str,
        members: str,
        color: str = "blue",
    ):
        await interaction.response.defer(ephemeral=True)
        season = state.current_season()
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
        tribe_role = await utils.get_or_create_role(guild, tribe_name, color=tribe_color, hoist=True)
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
            f"{theme['tribe_emoji']} {tribe_name}",
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
            f"{theme['alliance_emoji']} {tribe_name} {theme['alliances_label']}",
            overwrites={guild.default_role: PermissionOverwrite(read_messages=False)},
        )

        # ── 1:1 channels category ─────────────────────────────────────────────
        ones_cat = await utils.get_or_create_category(
            guild,
            f"{theme['ones_emoji']} {tribe_name} {theme['ones_label']}",
            overwrites={guild.default_role: PermissionOverwrite(read_messages=False)},
        )

        ones_channels: dict[str, int] = {}

        # Create every unique pair (sorted so pair_key and channel name are stable)
        for i, m1 in enumerate(discord_members):
            for m2 in discord_members[i + 1:]:
                uid1, uid2 = str(m1.id), str(m2.id)
                pair_key = f"{min(uid1, uid2)}-{max(uid1, uid2)}"
                sorted_names = sorted([
                    utils.channel_safe(game["players"][uid1]["name"]),
                    utils.channel_safe(game["players"][uid2]["name"]),
                ])
                ch_name = f"{sorted_names[0]}-{sorted_names[1]}"

                overwrites = {
                    guild.default_role: PermissionOverwrite(read_messages=False),
                    m1:                 utils.player_rw(m1),
                    m2:                 utils.player_rw(m2),
                }
                if host_role:
                    overwrites[host_role] = utils.host_rw(host_role)

                ch = await utils.get_or_create_text_channel(
                    guild, ch_name, category=ones_cat, overwrites=overwrites,
                    topic=f"Private 1:1 between {game['players'][uid1]['name']} and {game['players'][uid2]['name']}.",
                )
                ones_channels[pair_key] = ch.id

        # ── Per-tribe confessional and submissions categories ─────────────────
        conf_overwrites = {guild.default_role: PermissionOverwrite(read_messages=False)}
        if host_role:
            conf_overwrites[host_role] = PermissionOverwrite(read_messages=True, send_messages=True)
        if spec_role:
            conf_overwrites[spec_role] = PermissionOverwrite(read_messages=True, send_messages=False)

        subs_overwrites = {guild.default_role: PermissionOverwrite(read_messages=False)}
        if host_role:
            subs_overwrites[host_role] = PermissionOverwrite(read_messages=True, send_messages=True)

        tribe_conf_cat = await utils.get_or_create_category(
            guild, f"📖 {tribe_name} {theme['confessionals_label']}", overwrites=conf_overwrites,
        )
        tribe_subs_cat = await utils.get_or_create_category(
            guild, f"📬 {tribe_name} {theme['submissions_label']}", overwrites=subs_overwrites,
        )

        # Move each player's conf/subs channels into the tribe categories
        for m in discord_members:
            uid = str(m.id)
            conf_ch = guild.get_channel(game["players"][uid].get("confessional_id"))
            if conf_ch:
                await conf_ch.edit(category=tribe_conf_cat)
            subs_ch = guild.get_channel(game["players"][uid].get("submissions_id"))
            if subs_ch:
                await subs_ch.edit(category=tribe_subs_cat)

        # ── Persist tribe state ───────────────────────────────────────────────
        game["tribes"][tribe_name] = {
            "color": tribe_color.value,
            "role_id": tribe_role.id,
            "category_id": alliances_cat.id,
            "tribe_cat_id": tribe_cat.id,
            "tribe_chat_id": tribe_chat.id,
            "ones_category_id": ones_cat.id,
            "ones_channels": ones_channels,
            "conf_category_id": tribe_conf_cat.id,
            "subs_category_id": tribe_subs_cat.id,
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

    @app_commands.command(name="tribeswap", description="Reassign active players to new tribes via a setup form.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def tribeswap(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TribeSwapModal(season=state.current_season()))

    # ── /merge ────────────────────────────────────────────────────────────────

    @app_commands.command(name="merge", description="Merge all tribes into a single merged tribe.")
    @app_commands.describe(merge_name="Name of the merged tribe (e.g. 'Vinaka')")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def merge(self, interaction: discord.Interaction, merge_name: str = "Merged"):
        await interaction.response.defer(ephemeral=True)
        season = state.current_season()
        guild = interaction.guild
        game = state.load(season)

        host_role = guild.get_role(game["host_role_id"]) if game["host_role_id"] else None
        spec_role  = guild.get_role(game["spectator_role_id"]) if game["spectator_role_id"] else None
        theme = state.get_theme(game)

        active = state.active_players(game)

        # Snapshot old tribe data before we overwrite with the merged tribe
        old_tribes = dict(game["tribes"])

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
        merged_role = await utils.get_or_create_role(guild, merge_name, color=merged_color, hoist=True)

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

        merge_cat = await utils.get_or_create_category(guild, f"{theme['merge_emoji']} {merge_name}", overwrites=overwrites)
        merge_chat = await utils.get_or_create_text_channel(
            guild, f"{utils.channel_safe(merge_name)}-{utils.channel_safe(theme['merge_chat_label'])}", category=merge_cat,
            topic=f"Merged tribe — {merge_name}. {len(all_members)} players remain.",
        )

        # Cross-tribe 1:1s — restore existing ones, create new ones for new pairs
        ones_cat = await utils.get_or_create_category(guild, f"{theme['ones_emoji']} {merge_name} {theme['ones_label']}", overwrites={guild.default_role: PermissionOverwrite(read_messages=False)})
        ones_channels: dict[str, int] = {}

        for i, m1 in enumerate(all_members):
            for m2 in all_members[i + 1:]:
                uid1, uid2 = str(m1.id), str(m2.id)
                pair_key = f"{min(uid1, uid2)}-{max(uid1, uid2)}"
                sorted_names = sorted([
                    utils.channel_safe(game["players"][uid1]["name"]),
                    utils.channel_safe(game["players"][uid2]["name"]),
                ])
                ch_name = f"{sorted_names[0]}-{sorted_names[1]}"

                # Restore existing 1:1 if it exists
                existing_ch_id = state.find_ones_channel(game, uid1, uid2)
                if existing_ch_id:
                    ch = guild.get_channel(existing_ch_id)
                    if ch:
                        await ch.edit(category=ones_cat)
                        await ch.set_permissions(m1, read_messages=True, send_messages=True)
                        await ch.set_permissions(m2, read_messages=True, send_messages=True)
                        ones_channels[pair_key] = ch.id
                        continue

                ow = {
                    guild.default_role: PermissionOverwrite(read_messages=False),
                    m1:                 utils.player_rw(m1),
                    m2:                 utils.player_rw(m2),
                    guild.me:           PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True, manage_channels=True),
                }
                if host_role:
                    ow[host_role] = utils.host_rw(host_role)
                ch = await guild.create_text_channel(ch_name, category=ones_cat, overwrites=ow)
                ones_channels[pair_key] = ch.id

        # Per-merge conf/subs categories; move player channels in
        conf_ow_m = {guild.default_role: PermissionOverwrite(read_messages=False)}
        if host_role:
            conf_ow_m[host_role] = PermissionOverwrite(read_messages=True, send_messages=True)
        if spec_role:
            conf_ow_m[spec_role] = PermissionOverwrite(read_messages=True, send_messages=False)
        subs_ow_m = {guild.default_role: PermissionOverwrite(read_messages=False)}
        if host_role:
            subs_ow_m[host_role] = PermissionOverwrite(read_messages=True, send_messages=True)

        merge_conf_cat = await utils.get_or_create_category(
            guild, f"📖 {merge_name} {theme['confessionals_label']}", overwrites=conf_ow_m,
        )
        merge_subs_cat = await utils.get_or_create_category(
            guild, f"📬 {merge_name} {theme['submissions_label']}", overwrites=subs_ow_m,
        )
        for m in all_members:
            uid = str(m.id)
            conf_ch = guild.get_channel(game["players"][uid].get("confessional_id"))
            if conf_ch:
                await conf_ch.edit(category=merge_conf_cat)
            subs_ch = guild.get_channel(game["players"][uid].get("submissions_id"))
            if subs_ch:
                await subs_ch.edit(category=merge_subs_cat)

        live_channel_ids: set[int] = {merge_chat.id} | set(ones_channels.values())

        game["tribes"][merge_name] = {
            "color": merged_color.value,
            "role_id": merged_role.id,
            "category_id": ones_cat.id,
            "tribe_cat_id": merge_cat.id,
            "tribe_chat_id": merge_chat.id,
            "ones_category_id": ones_cat.id,
            "ones_channels": ones_channels,
            "conf_category_id": merge_conf_cat.id,
            "subs_category_id": merge_subs_cat.id,
            "members": [str(m.id) for m in all_members],
        }
        game["phase"] = "merged"

        # ── Archive old tribe channels and clean up empty categories ──────────
        archive_cat = await utils.ensure_archive_category(guild, game)

        for old_name, old_data in old_tribes.items():
            # Tribe chat — always archive
            tc_id = old_data.get("tribe_chat_id")
            if tc_id and tc_id not in live_channel_ids:
                tc = guild.get_channel(tc_id)
                if tc:
                    await tc.edit(category=archive_cat, sync_permissions=True)

            # 1:1 channels — archive non-reused ones
            for ch_id in old_data.get("ones_channels", {}).values():
                if ch_id not in live_channel_ids:
                    ch = guild.get_channel(ch_id)
                    if ch:
                        await ch.edit(category=archive_cat, sync_permissions=True)

            # Alliance channels — move to archive, then delete alliance category
            alliance_cat_id = old_data.get("category_id")
            if alliance_cat_id:
                alliance_cat_obj = guild.get_channel(alliance_cat_id)
                if alliance_cat_obj:
                    for ch in list(alliance_cat_obj.channels):
                        await ch.edit(category=archive_cat, sync_permissions=True)
                    await alliance_cat_obj.delete()

            # Delete old structural categories if now empty
            for cat_id in [old_data.get("tribe_cat_id"), old_data.get("ones_category_id")]:
                if cat_id:
                    cat = guild.get_channel(cat_id)
                    if cat and not cat.channels:
                        await cat.delete()

            # Conf/subs categories: delete if empty (active players' channels already moved)
            for cat_id in [old_data.get("conf_category_id"), old_data.get("subs_category_id")]:
                if cat_id:
                    cat = guild.get_channel(cat_id)
                    if cat and not cat.channels:
                        await cat.delete()

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
    ):
        await interaction.response.defer(ephemeral=True)
        season = state.current_season()
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
