"""
config.py — Season lifecycle commands.

Commands:
  /setupseason — Create a new season via a two-step modal form (structure + theme)
  /endseason   — End a season, clean up all roles, optionally delete channels
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


# ── Modal 2: Theme ────────────────────────────────────────────────────────────

class SeasonThemeModal(discord.ui.Modal):
    player_role_label = discord.ui.TextInput(
        label="Player Role Name",
        default="Player",
        required=True,
    )
    tribe_emoji = discord.ui.TextInput(
        label="Tribe Category Emoji",
        default="🏕",
        required=True,
        max_length=8,
    )
    merge_emoji = discord.ui.TextInput(
        label="Merge Category Emoji",
        default="🏆",
        required=True,
        max_length=8,
    )
    snuff_title = discord.ui.TextInput(
        label="Elimination Title",
        default="The tribe has spoken.",
        required=True,
    )
    snuff_suffix = discord.ui.TextInput(
        label="Elimination Body (after player name)",
        default="'s torch has been snuffed.",
        required=True,
    )

    def __init__(self, season: int, setup_data: dict):
        super().__init__(title=f"Season {season} Theme")
        self.season = season
        self.setup_data = setup_data  # carries over data from Modal 1

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        season = self.season
        game = state.load(season)

        d = self.setup_data

        # ── Create roles ──────────────────────────────────────────────────────
        host_role = await utils.get_or_create_role(
            guild, d["host_role_name"],
            color=discord.Color.dark_red(), hoist=True,
        )
        spec_role = await utils.get_or_create_role(
            guild, d["spectator_role_name"],
            color=discord.Color.greyple(),
        )

        # ── Create channels ───────────────────────────────────────────────────
        hidden = {guild.default_role: PermissionOverwrite(read_messages=False)}

        ponderosa_ch = await utils.get_or_create_text_channel(
            guild, utils.channel_safe(d["ponderosa_name"]),
            overwrites={
                **hidden,
                host_role: utils.host_rw(host_role),
                spec_role: utils.spectator_ro(spec_role),
            },
            topic="Ponderosa — premerge players hang out here.",
        )
        jury_lounge_ch = await utils.get_or_create_text_channel(
            guild, utils.channel_safe(d["jury_lounge_name"]),
            overwrites={
                **hidden,
                host_role: utils.host_rw(host_role),
                spec_role: utils.spectator_ro(spec_role),
            },
            topic="Jury Lounge — jury members only.",
        )
        jury_voting_ch = await utils.get_or_create_text_channel(
            guild, utils.channel_safe(d["jury_voting_name"]),
            overwrites={
                **hidden,
                host_role: utils.host_rw(host_role),
            },
            topic="Jury Voting — final vote, hosts only.",
        )

        # ── Persist structure + theme ─────────────────────────────────────────
        game["host_role_id"]           = host_role.id
        game["spectator_role_id"]      = spec_role.id
        game["ponderosa_channel_id"]   = ponderosa_ch.id
        game["jury_lounge_channel_id"] = jury_lounge_ch.id
        game["jury_voting_channel_id"] = jury_voting_ch.id

        theme = state.get_theme(game)
        theme["player_role_label"] = str(self.player_role_label)
        theme["tribe_emoji"]       = str(self.tribe_emoji)
        theme["merge_emoji"]       = str(self.merge_emoji)
        theme["snuff_title"]       = str(self.snuff_title)
        theme["snuff_suffix"]      = str(self.snuff_suffix)
        game["theme"] = theme

        await state.save(season, game)

        log.info(f"Season {season} fully set up")
        await interaction.followup.send(
            embed=utils.success_embed(
                f"Season {season} is ready!",
                f"**Host role:** {host_role.mention}\n"
                f"**Spectator role:** {spec_role.mention}\n"
                f"**Ponderosa:** {ponderosa_ch.mention}\n"
                f"**Jury Lounge:** {jury_lounge_ch.mention}\n"
                f"**Jury Voting:** {jury_voting_ch.mention}\n"
                f"**Player role name:** {theme['player_role_label']}\n\n"
                f"Now run `/addplayer` to register players, then `/tribesetup` to begin.",
            ),
            ephemeral=True,
        )


# ── Modal 1: Structure ────────────────────────────────────────────────────────

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
        setup_data = {
            "host_role_name":      str(self.host_role_name),
            "spectator_role_name": str(self.spectator_role_name),
            "ponderosa_name":      str(self.ponderosa_name),
            "jury_lounge_name":    str(self.jury_lounge_name),
            "jury_voting_name":    str(self.jury_voting_name),
        }
        await interaction.response.send_modal(
            SeasonThemeModal(season=self.season, setup_data=setup_data)
        )


# ── Cog ───────────────────────────────────────────────────────────────────────

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
            for uid, player in game["players"].items():
                for ch_id in [player.get("confessional_id"), player.get("submissions_id")]:
                    if ch_id:
                        ch = guild.get_channel(ch_id)
                        if ch:
                            await ch.delete(reason=f"Season {season} ended")
                            channels_deleted += 1

            for cat_key in ["confessionals_category_id", "subs_category_id"]:
                cat_id = game.get(cat_key)
                if cat_id:
                    cat = guild.get_channel(cat_id)
                    if cat:
                        await cat.delete(reason=f"Season {season} ended")
                        channels_deleted += 1

            for tribe_data in game["tribes"].values():
                tc = guild.get_channel(tribe_data.get("tribe_chat_id"))
                if tc:
                    await tc.delete(reason=f"Season {season} ended")
                    channels_deleted += 1

                for ch_id in tribe_data.get("ones_channels", {}).values():
                    ch = guild.get_channel(ch_id)
                    if ch:
                        await ch.delete(reason=f"Season {season} ended")
                        channels_deleted += 1

                alliance_cat = guild.get_channel(tribe_data.get("category_id"))
                if alliance_cat:
                    for ch in list(alliance_cat.channels):
                        await ch.delete(reason=f"Season {season} ended")
                        channels_deleted += 1

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


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))
