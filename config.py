"""
config.py — Season lifecycle commands.

Commands:
  /setupseason — Create a new season via a setup modal (role names + flavor text)
  /editseason  — Edit an existing season's role names and flavor text
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

# Default channel names — not prompted, just used when creating
DEFAULT_PONDEROSA    = "ponderosa"
DEFAULT_JURY_LOUNGE  = "jury-lounge"
DEFAULT_JURY_VOTING  = "jury-voting"


# ── Shared setup/edit modal ───────────────────────────────────────────────────

class SeasonModal(discord.ui.Modal):
    """Single modal covering role names and flavor text.
    Pass current values to pre-fill for edits; omit for fresh setup defaults.
    """

    def __init__(self, season: int, mode: str = "setup", current: dict = None):
        super().__init__(title=f"Season {season} — {'Setup' if mode == 'setup' else 'Edit'}")
        self.season = season
        self.mode = mode
        c = current or {}

        self.host_role = discord.ui.TextInput(
            label="Host Role Name",
            default=c.get("host_role_name", "Host"),
            required=True,
        )
        self.spectator_role = discord.ui.TextInput(
            label="Spectator Role Name",
            default=c.get("spectator_role_name", "Spectator"),
            required=True,
        )
        self.player_role = discord.ui.TextInput(
            label="Player Role Name",
            default=c.get("player_role_label", "Player"),
            required=True,
        )
        self.snuff_title = discord.ui.TextInput(
            label="Elimination Title",
            default=c.get("snuff_title", "The tribe has spoken."),
            required=True,
        )
        self.snuff_suffix = discord.ui.TextInput(
            label="Elimination Body (after player name)",
            default=c.get("snuff_suffix", "'s torch has been snuffed."),
            required=True,
        )

        self.add_item(self.host_role)
        self.add_item(self.spectator_role)
        self.add_item(self.player_role)
        self.add_item(self.snuff_title)
        self.add_item(self.snuff_suffix)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        season = self.season
        game = state.load(season)

        host_name    = str(self.host_role)
        spec_name    = str(self.spectator_role)
        player_name  = str(self.player_role)

        if self.mode == "setup":
            # ── Create roles ──────────────────────────────────────────────────
            host_role = await utils.get_or_create_role(
                guild, host_name, color=discord.Color.dark_red(), hoist=True,
            )
            spec_role = await utils.get_or_create_role(
                guild, spec_name, color=discord.Color.greyple(),
            )

            # ── Create channels ───────────────────────────────────────────────
            hidden = {guild.default_role: PermissionOverwrite(read_messages=False)}

            # Ponderosa and jury channels are hidden from spectators until first use.
            # snufftorch unlocks them when the first premerge/jury player is sent there.
            ponderosa_ch = await utils.get_or_create_text_channel(
                guild, DEFAULT_PONDEROSA,
                overwrites={**hidden, host_role: utils.host_rw(host_role)},
                topic="Ponderosa — premerge players hang out here.",
            )
            jury_lounge_ch = await utils.get_or_create_text_channel(
                guild, DEFAULT_JURY_LOUNGE,
                overwrites={**hidden, host_role: utils.host_rw(host_role)},
                topic="Jury Lounge — jury members only.",
            )
            jury_voting_ch = await utils.get_or_create_text_channel(
                guild, DEFAULT_JURY_VOTING,
                overwrites={**hidden, host_role: utils.host_rw(host_role)},
                topic="Jury Voting — final vote, hosts only.",
            )

            game["host_role_id"]           = host_role.id
            game["spectator_role_id"]      = spec_role.id
            game["ponderosa_channel_id"]   = ponderosa_ch.id
            game["jury_lounge_channel_id"] = jury_lounge_ch.id
            game["jury_voting_channel_id"] = jury_voting_ch.id

            desc = (
                f"**Host role:** {host_role.mention}\n"
                f"**Spectator role:** {spec_role.mention}\n"
                f"**Ponderosa:** {ponderosa_ch.mention}\n"
                f"**Jury Lounge:** {jury_lounge_ch.mention}\n"
                f"**Jury Voting:** {jury_voting_ch.mention}\n\n"
                f"Now run `/addplayer` to register players, then `/tribesetup` to begin."
            )
            title = f"Season {season} is ready!"
            log.info(f"Season {season} set up")

        else:  # edit
            # ── Rename existing Discord roles if names changed ─────────────────
            old_host_role = guild.get_role(game.get("host_role_id"))
            if old_host_role and old_host_role.name != host_name:
                await old_host_role.edit(name=host_name)

            old_spec_role = guild.get_role(game.get("spectator_role_id"))
            if old_spec_role and old_spec_role.name != spec_name:
                await old_spec_role.edit(name=spec_name)

            old_player_role = discord.utils.get(guild.roles, name=game["theme"].get("player_role_label", "Player"))
            if old_player_role and old_player_role.name != player_name:
                await old_player_role.edit(name=player_name)

            desc = (
                f"**Host role:** {host_name}\n"
                f"**Spectator role:** {spec_name}\n"
                f"**Player role:** {player_name}\n"
                f"**Elimination title:** {str(self.snuff_title)}\n"
                f"**Elimination body:** _{str(self.snuff_suffix)}_"
            )
            title = f"Season {season} updated!"
            log.info(f"Season {season} edited")

        # ── Save theme ────────────────────────────────────────────────────────
        theme = state.get_theme(game)
        theme["player_role_label"] = player_name
        theme["snuff_title"]       = str(self.snuff_title)
        theme["snuff_suffix"]      = str(self.snuff_suffix)
        game["theme"] = theme
        await state.save(season, game)

        await interaction.followup.send(
            embed=utils.success_embed(title, desc),
            ephemeral=True,
        )


# ── Cog ───────────────────────────────────────────────────────────────────────

class ConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /setupseason ─────────────────────────────────────────────────────────

    @app_commands.command(name="setupseason", description="Start a new season and create all roles and channels.")
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
        await interaction.response.send_modal(SeasonModal(season=next_num, mode="setup"))

    # ── /editseason ───────────────────────────────────────────────────────────

    @app_commands.command(name="editseason", description="Edit role names and flavor text for a season.")
    @app_commands.describe(season="Season number (defaults to current season)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def editseason(self, interaction: discord.Interaction, season: Optional[int] = None):
        if season is None:
            season = state.current_season()
        game = state.load(season)
        theme = state.get_theme(game)

        # Resolve current role names from Discord so the modal shows what's actually set
        guild = interaction.guild
        host_role   = guild.get_role(game.get("host_role_id"))
        spec_role   = guild.get_role(game.get("spectator_role_id"))

        current = {
            "host_role_name":      host_role.name if host_role else "Host",
            "spectator_role_name": spec_role.name if spec_role else "Spectator",
            "player_role_label":   theme["player_role_label"],
            "snuff_title":         theme["snuff_title"],
            "snuff_suffix":        theme["snuff_suffix"],
        }

        await interaction.response.send_modal(
            SeasonModal(season=season, mode="edit", current=current)
        )

    # ── /endseason ────────────────────────────────────────────────────────────

    @app_commands.command(name="endseason", description="End the season and remove all season roles. Optionally delete channels too.")
    @app_commands.describe(delete_channels="Also delete all season channels and categories (default: False)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def endseason(
        self,
        interaction: discord.Interaction,
        delete_channels: bool = False,
    ):
        await interaction.response.defer(ephemeral=True)
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

        for tribe_name, tribe_data in game["tribes"].items():
            tribe_role = guild.get_role(tribe_data["role_id"])
            if tribe_role:
                for uid in tribe_data["members"]:
                    m = await utils.resolve_member(guild, int(uid))
                    if m and tribe_role in m.roles:
                        await m.remove_roles(tribe_role)
                await tribe_role.delete(reason=f"Season {season} ended")
                roles_deleted += 1

        player_role = discord.utils.get(guild.roles, name=theme["player_role_label"])
        if player_role:
            for uid, _ in state.active_players(game):
                m = await utils.resolve_member(guild, int(uid))
                if m and player_role in m.roles:
                    await m.remove_roles(player_role)
            await player_role.delete(reason=f"Season {season} ended")
            roles_deleted += 1

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

        game["phase"] = "ended"
        await state.save(season, game)

        log.info(f"Season {season} ended. Roles: {roles_deleted}, Channels: {channels_deleted}")
        desc = f"Roles removed and deleted: **{roles_deleted}**"
        if delete_channels:
            desc += f"\nChannels/categories deleted: **{channels_deleted}**"
        else:
            desc += "\nChannels preserved — use `delete_channels:True` to remove them."

        await interaction.followup.send(
            embed=utils.success_embed(f"Season {season} has ended.", desc),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))
