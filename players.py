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
from discord import Member, CategoryChannel
from typing import Optional
import logging
import state
import utils

log = logging.getLogger("TheSurvivorGods.players")


class PlayersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /addplayer ───────────────────────────────────────────────────────────

    @app_commands.command(name="addplayer", description="Register a Discord user as a player for this season.")
    @app_commands.describe(
        member="The Discord user to add as a player",
        display_name="The name shown in the game (e.g. first name or alias)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def addplayer(
        self,
        interaction: discord.Interaction,
        member: Member,
        display_name: str,
    ):
        await interaction.response.defer(ephemeral=True)
        season = state.current_season()
        guild = interaction.guild
        game = state.load(season)

        uid = str(member.id)
        if uid in game["players"]:
            await interaction.followup.send(
                embed=utils.warn_embed("Already registered", f"{member.mention} is already a player in Season {season}."),
                ephemeral=True,
            )
            return

        theme = state.get_theme(game)

        # Create or fetch the Player role
        player_role = await utils.get_or_create_role(guild, theme['player_role_label'], color=discord.Color.blurple())

        # Ensure host and spectator roles exist in state (hosts set these up once)
        host_role = guild.get_role(game["host_role_id"]) if game["host_role_id"] else None
        spec_role  = guild.get_role(game["spectator_role_id"]) if game["spectator_role_id"] else None

        # Ensure top-level categories for confessionals and submissions
        conf_cat = await self._ensure_category(guild, theme['confessionals_label'], game, "confessionals_category_id", host_role, spec_role)
        subs_cat = await self._ensure_category(guild, theme['submissions_label'], game, "subs_category_id", host_role, None)

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

        # Assign player role and set server nickname to display name
        await member.add_roles(player_role)
        try:
            await member.edit(nick=display_name)
        except Exception as e:
            log.warning(f"Could not set nickname for {member.name}: {e}")

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
        reason: str = "",
    ):
        await interaction.response.defer()
        season = state.current_season()
        guild = interaction.guild
        game = state.load(season)

        theme = state.get_theme(game)
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
        player_role = discord.utils.get(guild.roles, name=theme['player_role_label'])
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
                bot_ow = dest_ch.overwrites_for(guild.me)
                if not bot_ow.read_messages:
                    try:
                        await dest_ch.set_permissions(
                            guild.me,
                            read_messages=True, send_messages=True,
                            manage_messages=True, manage_channels=True,
                        )
                    except discord.Forbidden:
                        log.error(
                            f"Bot lacks access to #{dest_ch.name} — grant the bot Administrator "
                            f"or add an explicit channel override for it."
                        )
                try:
                    await dest_ch.set_permissions(member, read_messages=True, send_messages=True)
                except discord.Forbidden:
                    log.error(f"Could not grant {member.name} access to #{dest_ch.name} — bot lacks channel access.")
        else:
            log.warning(f"{dest_channel_name} channel not configured. Set game.{{'ponderosa_channel_id'/'jury_lounge_channel_id'}}.")

        # ── Archive 1:1 channels involving this player ───────────────────────
        archive_cat = await utils.ensure_archive_category(guild, game)
        for tribe_data in game["tribes"].values():
            for pair_key, ch_id in list(tribe_data.get("ones_channels", {}).items()):
                if uid in pair_key.split("-"):
                    one_ch = guild.get_channel(ch_id)
                    if one_ch:
                        await one_ch.edit(category=archive_cat, sync_permissions=True)

        # ── Move conf/subs to elimination archive categories ──────────────────
        host_role = guild.get_role(game["host_role_id"]) if game.get("host_role_id") else None
        spec_role_obj = guild.get_role(game.get("spectator_role_id")) if game.get("spectator_role_id") else None

        if destination == "premerge":
            conf_cat_key  = "premerge_conf_cat_id"
            subs_cat_key  = "premerge_subs_cat_id"
            conf_cat_label = f"📖 Pre-Jury {theme['confessionals_label']}"
            subs_cat_label = f"📬 Pre-Jury {theme['submissions_label']}"
        else:
            conf_cat_key  = "jury_conf_cat_id"
            subs_cat_key  = "jury_subs_cat_id"
            conf_cat_label = f"📖 Jury {theme['confessionals_label']}"
            subs_cat_label = f"📬 Jury {theme['submissions_label']}"

        # Conf archive category: spectators + hosts can read, no one writes
        conf_cat_id = game.get(conf_cat_key)
        elim_conf_cat = guild.get_channel(conf_cat_id) if conf_cat_id else None
        if elim_conf_cat is None:
            conf_ow = {guild.default_role: discord.PermissionOverwrite(read_messages=False)}
            if host_role:
                conf_ow[host_role] = discord.PermissionOverwrite(read_messages=True, send_messages=False)
            if spec_role_obj:
                conf_ow[spec_role_obj] = discord.PermissionOverwrite(read_messages=True, send_messages=False)
            elim_conf_cat = await utils.get_or_create_category(guild, conf_cat_label, overwrites=conf_ow)
            game[conf_cat_key] = elim_conf_cat.id

        # Subs archive category: hosts only
        subs_cat_id = game.get(subs_cat_key)
        elim_subs_cat = guild.get_channel(subs_cat_id) if subs_cat_id else None
        if elim_subs_cat is None:
            subs_ow = {guild.default_role: discord.PermissionOverwrite(read_messages=False)}
            if host_role:
                subs_ow[host_role] = discord.PermissionOverwrite(read_messages=True, send_messages=False)
            elim_subs_cat = await utils.get_or_create_category(guild, subs_cat_label, overwrites=subs_ow)
            game[subs_cat_key] = elim_subs_cat.id

        conf_ch = guild.get_channel(player.get("confessional_id")) if player.get("confessional_id") else None
        if conf_ch:
            await conf_ch.edit(category=elim_conf_cat, sync_permissions=True)

        subs_ch = guild.get_channel(player.get("submissions_id")) if player.get("submissions_id") else None
        if subs_ch:
            await subs_ch.edit(category=elim_subs_cat, sync_permissions=True)

        # ── Update state ─────────────────────────────────────────────────────
        # Calculate placement before appending (total - already_out = this place)
        total_players = len(game["players"])
        already_out = len(game["premerge_boot_order"]) + len(game["jury"])
        place = total_players - already_out

        player["status"] = destination
        player["tribe"] = None
        first_premerge = destination == "premerge" and len(game["premerge_boot_order"]) == 0
        first_jury     = destination == "jury"     and len(game["jury"]) == 0

        if destination == "jury":
            game["jury"].append(uid)
        else:
            game["premerge_boot_order"].append(uid)

        # Update server nickname to show season and placement
        try:
            await member.edit(nick=f"{player['name']} [{season}:{place}]")
        except Exception as e:
            log.warning(f"Could not update nickname for {player['name']}: {e}")

        # Unlock spectator read access to destination channel on first use
        spec_role = guild.get_role(game.get("spectator_role_id")) if game.get("spectator_role_id") else None
        if spec_role:
            if first_premerge and game.get("ponderosa_channel_id"):
                ponderosa_ch = guild.get_channel(game["ponderosa_channel_id"])
                if ponderosa_ch:
                    await ponderosa_ch.set_permissions(spec_role, read_messages=True, send_messages=False)
            if first_jury and game.get("jury_lounge_channel_id"):
                jury_ch = guild.get_channel(game["jury_lounge_channel_id"])
                if jury_ch:
                    await jury_ch.set_permissions(spec_role, read_messages=True, send_messages=False)

        await state.save(season, game)

        log.info(f"Snuffed torch of {player['name']} → {destination}")
        await interaction.followup.send(
            embed=utils.torch_embed(
                player["name"], reason,
                snuff_title=theme["snuff_title"],
                snuff_suffix=theme["snuff_suffix"],
            ),
        )

    # ── /listplayers ─────────────────────────────────────────────────────────

    @app_commands.command(name="listplayers", description="Show all players and their current tribe/status.")
    async def listplayers(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        season = state.current_season()
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



async def setup(bot: commands.Bot):
    await bot.add_cog(PlayersCog(bot))
