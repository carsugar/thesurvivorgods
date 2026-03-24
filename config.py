"""
config.py — Season lifecycle and theming commands.

Commands:
  /setupseason — Create a new season and all server roles/channels via a modal form
  /endseason   — End a season, clean up all roles, optionally delete channels
  /settheme    — Customize emojis, labels, and flavor text for a season
  /showtheme   — Display the current theme settings
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord import PermissionOverwrite
from typing import Optional
import logging
import state
import utils

log = logging.getLogger("TheSurvivorGods.config")


class SeasonSetupModal(discord.ui.Modal):
    host_role_name = discord.ui.TextInput(
        label="Host Role Name",
        default="Host",
        required=True,
    )
    spectator_role_name = discord.ui.TextInput(
        label="Spectator Role Name",
        default="Spectator",
        required=True,
    )
    ponderosa_name = discord.ui.TextInput(
        label="Ponderosa Channel Name",
        default="ponderosa",
        required=True,
    )
    jury_lounge_name = discord.ui.TextInput(
        label="Jury Lounge Channel Name",
        default="jury-lounge",
        required=True,
    )
    jury_voting_name = discord.ui.TextInput(
        label="Jury Voting Channel Name",
        default="jury-voting",
        required=True,
    )

    def __init__(self, season: int):
        super().__init__(title=f"Season {season} Setup")
        self.season = season

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        season = self.season
        game = state.load(season)

        # ── Create roles ──────────────────────────────────────────────────────
        host_role = await utils.get_or_create_role(
            guild, str(self.host_role_name),
            color=discord.Color.dark_red(), hoist=True,
        )
        spec_role = await utils.get_or_create_role(
            guild, str(self.spectator_role_name),
            color=discord.Color.greyple(),
        )

        # ── Create channels ───────────────────────────────────────────────────
        hidden = {guild.default_role: PermissionOverwrite(read_messages=False)}

        ponderosa_ch = await utils.get_or_create_text_channel(
            guild, utils.channel_safe(str(self.ponderosa_name)),
            overwrites={
                **hidden,
                host_role: utils.host_rw(host_role),
                spec_role: utils.spectator_ro(spec_role),
            },
            topic="Ponderosa — premerge players hang out here.",
        )
        jury_lounge_ch = await utils.get_or_create_text_channel(
            guild, utils.channel_safe(str(self.jury_lounge_name)),
            overwrites={
                **hidden,
                host_role: utils.host_rw(host_role),
                spec_role: utils.spectator_ro(spec_role),
            },
            topic="Jury Lounge — jury members only.",
        )
        jury_voting_ch = await utils.get_or_create_text_channel(
            guild, utils.channel_safe(str(self.jury_voting_name)),
            overwrites={
                **hidden,
                host_role: utils.host_rw(host_role),
            },
            topic="Jury Voting — final vote, hosts only.",
        )

        # ── Persist ───────────────────────────────────────────────────────────
        game["host_role_id"]           = host_role.id
        game["spectator_role_id"]      = spec_role.id
        game["ponderosa_channel_id"]   = ponderosa_ch.id
        game["jury_lounge_channel_id"] = jury_lounge_ch.id
        game["jury_voting_channel_id"] = jury_voting_ch.id
        await state.save(season, game)

        log.info(f"Season {season} set up: host={host_role.name}, spec={spec_role.name}")
        await interaction.followup.send(
            embed=utils.success_embed(
                f"Season {season} is ready!",
                f"**Host role:** {host_role.mention}\n"
                f"**Spectator role:** {spec_role.mention}\n"
                f"**Ponderosa:** {ponderosa_ch.mention}\n"
                f"**Jury Lounge:** {jury_lounge_ch.mention}\n"
                f"**Jury Voting:** {jury_voting_ch.mention}\n\n"
                f"Now run `/addplayer` to register players, then `/tribesetup` to begin.",
            ),
            ephemeral=True,
        )


class ConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /setupseason ─────────────────────────────────────────────────────────

    @app_commands.command(name="setupseason", description="Start a new season and create all roles and channels via a setup form.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setupseason(self, interaction: discord.Interaction):
        seasons = state.list_seasons()
        for n in seasons:
            s = state.load(n)
            if s.get("phase") != "ended":
                await interaction.response.send_message(
                    embed=utils.warn_embed(
                        "Active season exists",
                        f"Season {n} is still active (phase: **{s['phase']}**). Run `/endseason` first.",
                    ),
                    ephemeral=True,
                )
                return

        next_num = max(seasons) + 1 if seasons else 1
        state.load(next_num)  # creates and persists default state
        await interaction.response.send_modal(SeasonSetupModal(season=next_num))

    # ── /endseason ────────────────────────────────────────────────────────────

    @app_commands.command(name="endseason", description="End the season and remove all season roles. Optionally delete channels too.")
    @app_commands.describe(
        delete_channels="Also delete all season channels and categories (default: False)",
        season="Season number (defaults to current season)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def endseason(
        self,
        interaction: discord.Interaction,
        delete_channels: bool = False,
        season: Optional[int] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        if season is None:
            season = state.current_season()
        guild = interaction.guild
        game = state.load(season)

        if game["phase"] == "ended":
            await interaction.followup.send(
                embed=utils.warn_embed("Already ended", f"Season {season} is already marked as ended."),
                ephemeral=True,
            )
            return

        theme = state.get_theme(game)
        roles_deleted = 0

        # ── 1. Remove tribe roles from members and delete them ────────────────
        for tribe_name, tribe_data in game["tribes"].items():
            tribe_role = guild.get_role(tribe_data["role_id"])
            if tribe_role:
                for uid in tribe_data["members"]:
                    m = await utils.resolve_member(guild, int(uid))
                    if m and tribe_role in m.roles:
                        await m.remove_roles(tribe_role)
                await tribe_role.delete(reason=f"Season {season} ended")
                roles_deleted += 1
                log.info(f"Deleted role: {tribe_name}")

        # ── 2. Remove and delete the Player role ──────────────────────────────
        player_role = discord.utils.get(guild.roles, name=theme["player_role_label"])
        if player_role:
            for uid, _ in state.active_players(game):
                m = await utils.resolve_member(guild, int(uid))
                if m and player_role in m.roles:
                    await m.remove_roles(player_role)
            await player_role.delete(reason=f"Season {season} ended")
            roles_deleted += 1
            log.info(f"Deleted role: {theme['player_role_label']}")

        # ── 3. Optionally delete all channels and categories ──────────────────
        channels_deleted = 0
        if delete_channels:
            # Per-player confessional and submission channels
            for uid, player in game["players"].items():
                for ch_id in [player.get("confessional_id"), player.get("submissions_id")]:
                    if ch_id:
                        ch = guild.get_channel(ch_id)
                        if ch:
                            await ch.delete(reason=f"Season {season} ended")
                            channels_deleted += 1

            # Top-level confessionals and submissions categories
            for cat_key in ["confessionals_category_id", "subs_category_id"]:
                cat_id = game.get(cat_key)
                if cat_id:
                    cat = guild.get_channel(cat_id)
                    if cat:
                        await cat.delete(reason=f"Season {season} ended")
                        channels_deleted += 1

            # Tribe channels and categories
            for tribe_data in game["tribes"].values():
                # Tribe chat
                tc = guild.get_channel(tribe_data.get("tribe_chat_id"))
                if tc:
                    await tc.delete(reason=f"Season {season} ended")
                    channels_deleted += 1

                # 1:1 channels
                for ch_id in tribe_data.get("ones_channels", {}).values():
                    ch = guild.get_channel(ch_id)
                    if ch:
                        await ch.delete(reason=f"Season {season} ended")
                        channels_deleted += 1

                # Alliance channels (children of alliance category)
                alliance_cat = guild.get_channel(tribe_data.get("category_id"))
                if alliance_cat:
                    for ch in list(alliance_cat.channels):
                        await ch.delete(reason=f"Season {season} ended")
                        channels_deleted += 1

                # Categories
                seen_cats: set[int] = set()
                for cat_id in [
                    tribe_data.get("tribe_cat_id"),
                    tribe_data.get("category_id"),
                    tribe_data.get("ones_category_id"),
                ]:
                    if cat_id and cat_id not in seen_cats:
                        seen_cats.add(cat_id)
                        cat = guild.get_channel(cat_id)
                        if cat:
                            await cat.delete(reason=f"Season {season} ended")
                            channels_deleted += 1

        # ── 4. Mark season as ended ───────────────────────────────────────────
        game["phase"] = "ended"
        await state.save(season, game)

        log.info(f"Season {season} ended. Roles deleted: {roles_deleted}, Channels deleted: {channels_deleted}")
        desc = f"Roles removed and deleted: **{roles_deleted}**"
        if delete_channels:
            desc += f"\nChannels/categories deleted: **{channels_deleted}**"
        else:
            desc += "\nChannels were preserved — run `/endseason delete_channels:True` to also remove them."

        await interaction.followup.send(
            embed=utils.success_embed(f"Season {season} has ended.", desc),
            ephemeral=True,
        )

    # ── /showtheme ────────────────────────────────────────────────────────────

    @app_commands.command(name="showtheme", description="Show the current season theme settings.")
    @app_commands.describe(season="Season number (defaults to current season)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def showtheme(self, interaction: discord.Interaction, season: Optional[int] = None):
        if season is None:
            season = state.current_season()
        game = state.load(season)
        theme = state.get_theme(game)

        lines = [
            f"**Tribe category emoji:** {theme['tribe_emoji']}",
            f"**Alliance category emoji:** {theme['alliance_emoji']}",
            f"**1:1s category emoji:** {theme['ones_emoji']}",
            f"**Merge category emoji:** {theme['merge_emoji']}",
            f"**Tribe chat label:** {theme['tribe_chat_label']}",
            f"**Alliances label:** {theme['alliances_label']}",
            f"**1:1s label:** {theme['ones_label']}",
            f"**Merge chat label:** {theme['merge_chat_label']}",
            f"**Confessionals label:** {theme['confessionals_label']}",
            f"**Submissions label:** {theme['submissions_label']}",
            f"**Player role label:** {theme['player_role_label']}",
            f"**Elimination title:** {theme['snuff_title']}",
            f"**Elimination body suffix:** {theme['snuff_suffix']}",
        ]

        await interaction.response.send_message(
            embed=utils.embed(f"Season {season} Theme", "\n".join(lines)),
            ephemeral=True,
        )

    # ── /settheme ─────────────────────────────────────────────────────────────

    @app_commands.command(name="settheme", description="Customize emojis, channel labels, and flavor text for the season.")
    @app_commands.describe(
        tribe_emoji="Emoji for tribe categories (default: 🏕)",
        alliance_emoji="Emoji for alliance categories (default: 🤝)",
        ones_emoji="Emoji for 1:1 categories (default: 💬)",
        merge_emoji="Emoji for the merge category (default: 🏆)",
        tribe_chat_label="Label for tribe chat channels (default: tribe-chat)",
        alliances_label="Label for alliance categories (default: Alliances)",
        ones_label="Label for 1:1 categories (default: 1:1s)",
        merge_chat_label="Label for merge chat channel (default: merge-chat)",
        confessionals_label="Label for confessionals category (default: Confessionals)",
        submissions_label="Label for submissions category (default: Submissions)",
        player_role_label="Name for the player role (default: Player)",
        snuff_title="Title shown when a player is eliminated (default: The tribe has spoken.)",
        snuff_suffix="Text after player name on elimination (default: 's torch has been snuffed.)",
        season="Season number (defaults to current season)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def settheme(
        self,
        interaction: discord.Interaction,
        tribe_emoji: Optional[str] = None,
        alliance_emoji: Optional[str] = None,
        ones_emoji: Optional[str] = None,
        merge_emoji: Optional[str] = None,
        tribe_chat_label: Optional[str] = None,
        alliances_label: Optional[str] = None,
        ones_label: Optional[str] = None,
        merge_chat_label: Optional[str] = None,
        confessionals_label: Optional[str] = None,
        submissions_label: Optional[str] = None,
        player_role_label: Optional[str] = None,
        snuff_title: Optional[str] = None,
        snuff_suffix: Optional[str] = None,
        season: Optional[int] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        if season is None:
            season = state.current_season()
        game = state.load(season)
        theme = state.get_theme(game)

        updates = {
            "tribe_emoji": tribe_emoji,
            "alliance_emoji": alliance_emoji,
            "ones_emoji": ones_emoji,
            "merge_emoji": merge_emoji,
            "tribe_chat_label": tribe_chat_label,
            "alliances_label": alliances_label,
            "ones_label": ones_label,
            "merge_chat_label": merge_chat_label,
            "confessionals_label": confessionals_label,
            "submissions_label": submissions_label,
            "player_role_label": player_role_label,
            "snuff_title": snuff_title,
            "snuff_suffix": snuff_suffix,
        }

        changed = []
        for key, value in updates.items():
            if value is not None:
                theme[key] = value
                changed.append(f"**{key}** → {value}")

        if not changed:
            await interaction.followup.send(
                embed=utils.warn_embed("No changes", "Provide at least one field to update."),
                ephemeral=True,
            )
            return

        game["theme"] = theme
        await state.save(season, game)
        log.info(f"Season {season} theme updated: {', '.join(changed)}")

        await interaction.followup.send(
            embed=utils.success_embed(
                f"Season {season} theme updated!",
                "\n".join(changed),
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))
