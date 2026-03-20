"""
cogs/players.py — Player management commands.

Commands:
  /addplayer  — Register a Discord user as a player for the season
  /snufftorch — Eliminate a player (premerge boot or jury)
  /listplayers — Show all active players and their tribes
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord import Member, TextChannel, CategoryChannel
from typing import Optional
import logging
import state
import utils

log = logging.getLogger("TheSurvivorGods.players")

# Season currently being managed. In a multi-season server you'd store this
# per-guild, but a simple module-level default is fine for V1.
DEFAULT_SEASON = 1


class PlayersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /addplayer ───────────────────────────────────────────────────────────

    @app_commands.command(name="addplayer", description="Register a Discord user as a player for this season.")
    @app_commands.describe(
        member="The Discord user to add as a player",
        display_name="The name shown in the game (e.g. first name or alias)",
        season="Season number (default: 1)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def addplayer(
        self,
        interaction: discord.Interaction,
        member: Member,
        display_name: str,
        season: int = DEFAULT_SEASON,
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        game = state.load(season)

        uid = str(member.id)
        if uid in game["players"]:
            await interaction.followup.send(
                embed=utils.warn_embed("Already registered", f"{member.mention} is already a player in Season {season}."),
                ephemeral=True,
            )
            return

        # Create or fetch the Player role
        player_role = await utils.get_or_create_role(guild, f"S{season} Player", color=discord.Color.blurple())

        # Ensure host and spectator roles exist in state (hosts set these up once)
        host_role = guild.get_role(game["host_role_id"]) if game["host_role_id"] else None
        spec_role  = guild.get_role(game["spectator_role_id"]) if game["spectator_role_id"] else None

        # Ensure top-level categories for confessionals and submissions
        conf_cat = await self._ensure_category(guild, f"S{season} Confessionals", game, "confessionals_category_id", host_role, spec_role)
        subs_cat = await self._ensure_category(guild, f"S{season} Submissions", game, "subs_category_id", host_role, None)

        # Confessional: visible to spectators + hosts, player can write
        conf_overwrites = {
            guild.default_role:  discord.PermissionOverwrite(read_messages=False),
            member:              discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        if host_role:
            conf_overwrites[host_role] = utils.host_rw(host_role)
        if spec_role:
            conf_overwrites[spec_role] = utils.spectator_ro(spec_role)

        safe_name = utils.channel_safe(display_name)
        conf_channel = await utils.get_or_create_text_channel(
            guild,
            f"{safe_name}-confessional",
            category=conf_cat,
            overwrites=conf_overwrites,
            topic=f"📖 {display_name}'s confessional — spectators can read, only {display_name} writes.",
        )

        # Submissions: private between player and hosts only
        subs_overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member:             discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
        }
        if host_role:
            subs_overwrites[host_role] = utils.host_rw(host_role)

        subs_channel = await utils.get_or_create_text_channel(
            guild,
            f"{safe_name}-submissions",
            category=subs_cat,
            overwrites=subs_overwrites,
            topic=f"📬 {display_name}'s submissions — private.",
        )

        # Assign player role
        await member.add_roles(player_role)

        # Persist
        game["players"][uid] = {
            "username": member.name,
            "name": display_name,
            "tribe": None,
            "status": "active",
            "confessional_id": conf_channel.id,
            "submissions_id": subs_channel.id,
            "advantages": [],
        }
        await state.save(season, game)

        log.info(f"Added player {display_name} ({member.name}) to Season {season}")
        await interaction.followup.send(
            embed=utils.success_embed(
                f"Player added: {display_name}",
                f"{member.mention} is now registered for Season {season}.\n"
                f"Confessional: {conf_channel.mention}\n"
                f"Submissions: {subs_channel.mention}",
            ),
            ephemeral=True,
        )

    async def _ensure_category(
        self,
        guild,
        name: str,
        game: dict,
        key: str,
        host_role,
        spec_role,
    ) -> CategoryChannel:
        """Get-or-create a top-level category and persist its ID."""
        cat_id = game.get(key)
        if cat_id:
            cat = guild.get_channel(cat_id)
            if cat:
                return cat

        overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False)}
        if host_role:
            overwrites[host_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        if spec_role:
            overwrites[spec_role] = discord.PermissionOverwrite(read_messages=True, send_messages=False)

        cat = await utils.get_or_create_category(guild, name, overwrites=overwrites)
        game[key] = cat.id
        return cat

    # ── /snufftorch ──────────────────────────────────────────────────────────

    @app_commands.command(name="snufftorch", description="Eliminate a player from the game.")
    @app_commands.describe(
        member="The player being eliminated",
        destination="premerge (goes to Ponderosa) or jury (goes to Jury Lounge)",
        season="Season number (default: 1)",
        reason="Optional note (not shown publicly)",
    )
    @app_commands.choices(destination=[
        app_commands.Choice(name="Premerge boot → Ponderosa", value="premerge"),
        app_commands.Choice(name="Jury member → Jury Lounge", value="jury"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def snufftorch(
        self,
        interaction: discord.Interaction,
        member: Member,
        destination: str,
        season: int = DEFAULT_SEASON,
        reason: str = "",
    ):
        await interaction.response.defer()
        guild = interaction.guild
        game = state.load(season)

        uid = str(member.id)
        player = state.get_player(game, uid)
        if not player:
            await interaction.followup.send(
                embed=utils.error_embed("Unknown player", f"{member.mention} is not registered for Season {season}."),
                ephemeral=True,
            )
            return
        if player["status"] != "active":
            await interaction.followup.send(
                embed=utils.warn_embed("Already eliminated", f"{player['name']} is already out of the game."),
                ephemeral=True,
            )
            return

        tribe_name = player.get("tribe")

        # ── Remove from all tribe channels ──────────────────────────────────
        if tribe_name and tribe_name in game["tribes"]:
            tribe = game["tribes"][tribe_name]

            # Remove tribe role
            tribe_role = guild.get_role(tribe["role_id"])
            if tribe_role and tribe_role in member.roles:
                await member.remove_roles(tribe_role)

            # Revoke perms on tribe chat
            tc = guild.get_channel(tribe["tribe_chat_id"])
            if tc:
                await tc.set_permissions(member, overwrite=None)

            # Revoke perms on all 1:1 channels involving this player
            for pair_key, ch_id in tribe["ones_channels"].items():
                if uid in pair_key.split("-"):
                    ch = guild.get_channel(ch_id)
                    if ch:
                        await ch.set_permissions(member, overwrite=None)

            # Remove from tribe member list
            if uid in tribe["members"]:
                tribe["members"].remove(uid)

        # ── Also remove from any alliance channels in their category ─────────
        if tribe_name and tribe_name in game["tribes"]:
            alliance_cat_id = game["tribes"][tribe_name].get("category_id")
            if alliance_cat_id:
                alliance_cat = guild.get_channel(alliance_cat_id)
                if alliance_cat:
                    for ch in alliance_cat.channels:
                        if member in ch.overwrites:
                            await ch.set_permissions(member, overwrite=None)

        # ── Remove Player role ───────────────────────────────────────────────
        player_role = discord.utils.get(guild.roles, name=f"S{season} Player")
        if player_role and player_role in member.roles:
            await member.remove_roles(player_role)

        # ── Add to destination channel ───────────────────────────────────────
        dest_channel_id = (
            game["jury_lounge_channel_id"] if destination == "jury"
            else game["ponderosa_channel_id"]
        )
        dest_channel_name = "Jury Lounge" if destination == "jury" else "Ponderosa"

        if dest_channel_id:
            dest_ch = guild.get_channel(dest_channel_id)
            if dest_ch:
                await dest_ch.set_permissions(member, read_messages=True, send_messages=True)
        else:
            log.warning(f"{dest_channel_name} channel not configured. Set game.{{'ponderosa_channel_id'/'jury_lounge_channel_id'}}.")

        # Conf + subs channels are deliberately untouched.

        # ── Update state ─────────────────────────────────────────────────────
        player["status"] = destination
        player["tribe"] = None
        if destination == "jury":
            game["jury"].append(uid)
        else:
            game["premerge_boot_order"].append(uid)

        await state.save(season, game)

        log.info(f"Snuffed torch of {player['name']} → {destination}")
        await interaction.followup.send(
            embed=utils.torch_embed(player["name"], reason),
        )

    # ── /listplayers ─────────────────────────────────────────────────────────

    @app_commands.command(name="listplayers", description="Show all players and their current tribe/status.")
    @app_commands.describe(season="Season number (default: 1)")
    async def listplayers(self, interaction: discord.Interaction, season: int = DEFAULT_SEASON):
        await interaction.response.defer(ephemeral=True)
        game = state.load(season)

        if not game["players"]:
            await interaction.followup.send(
                embed=utils.warn_embed("No players", f"No players registered for Season {season} yet."),
                ephemeral=True,
            )
            return

        lines_by_tribe: dict[str, list[str]] = {}
        for uid, p in game["players"].items():
            tribe = p.get("tribe") or p["status"].upper()
            icon = {"active": "🟢", "premerge": "💀", "jury": "⚖️", "winner": "🏆", "runner_up": "🥈"}.get(p["status"], "❓")
            lines_by_tribe.setdefault(tribe, []).append(f"{icon} {p['name']} ({p['username']})")

        e = discord.Embed(title=f"Season {season} — Players", color=utils.INFO_COLOR)
        for tribe, lines in sorted(lines_by_tribe.items()):
            e.add_field(name=tribe, value="\n".join(lines), inline=True)

        await interaction.followup.send(embed=e, ephemeral=True)

    # ── /setupchannels ───────────────────────────────────────────────────────

    @app_commands.command(name="setupchannels", description="Set IDs for Ponderosa, Jury Lounge, and Jury Voting channels.")
    @app_commands.describe(
        ponderosa="The #ponderosa channel",
        jury_lounge="The #jury-lounge channel",
        jury_voting="The #jury-voting channel",
        host_role="The host role (gets read/write on all private channels)",
        spectator_role="The spectator role (read-only on confessionals)",
        season="Season number (default: 1)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setupchannels(
        self,
        interaction: discord.Interaction,
        ponderosa: TextChannel,
        jury_lounge: TextChannel,
        jury_voting: TextChannel,
        host_role: discord.Role,
        spectator_role: discord.Role,
        season: int = DEFAULT_SEASON,
    ):
        await interaction.response.defer(ephemeral=True)
        game = state.load(season)
        game["ponderosa_channel_id"]   = ponderosa.id
        game["jury_lounge_channel_id"] = jury_lounge.id
        game["jury_voting_channel_id"] = jury_voting.id
        game["host_role_id"]           = host_role.id
        game["spectator_role_id"]      = spectator_role.id
        await state.save(season, game)

        await interaction.followup.send(
            embed=utils.success_embed(
                "Season channels configured",
                f"Ponderosa: {ponderosa.mention}\n"
                f"Jury Lounge: {jury_lounge.mention}\n"
                f"Jury Voting: {jury_voting.mention}\n"
                f"Host role: {host_role.mention}\n"
                f"Spectator role: {spectator_role.mention}",
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(PlayersCog(bot))
