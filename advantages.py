"""
cogs/advantages.py — Hidden immunity idols and advantage management.

Commands:
  /giveadvantage   — Host gives any advantage type to a player
  /giveidol        — Shorthand: give an immunity idol
  /playidol        — Player plays their idol (or host plays on behalf)
  /transferadvantage — Player gives their advantage to another player
  /listadvantages  — Show all advantages (host-only full view, player sees their own)
  /expireadvantage — Host manually expires/removes an advantage

Advantage types and their behaviour:
  idol            — Played before votes are read; nullifies votes against holder (or target)
  extra_vote      — Played before voting; holder casts an additional vote
  steal_a_vote    — Played before voting; steals another player's vote this round
  block_a_vote    — Played before voting; prevents one player from voting this round
  nullifier       — Played against another idol; cancels that idol (rare)
  legacy          — Special idol passed on death; activates at final X

Players receive a DM with their advantage details when granted.
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord import Member
from typing import Optional
import uuid
import logging
import state
import utils

log = logging.getLogger("TheSurvivorGods.advantages")

ADVANTAGE_TYPES = [
    app_commands.Choice(name="Hidden immunity idol",  value="idol"),
    app_commands.Choice(name="Extra vote",            value="extra_vote"),
    app_commands.Choice(name="Steal-a-vote",          value="steal_a_vote"),
    app_commands.Choice(name="Block-a-vote",          value="block_a_vote"),
    app_commands.Choice(name="Idol nullifier",        value="nullifier"),
    app_commands.Choice(name="Legacy advantage",      value="legacy"),
    app_commands.Choice(name="Custom / other",        value="custom"),
]

ADVANTAGE_DESCRIPTIONS = {
    "idol":         "Hidden Immunity Idol — can be played after votes are cast to nullify votes against you (or a named target).",
    "extra_vote":   "Extra Vote — can be played before voting to cast a second vote this Tribal Council.",
    "steal_a_vote": "Steal-a-Vote — played before voting; steals one player's vote for your own use.",
    "block_a_vote": "Block-a-Vote — played before voting; prevents one player from casting a vote.",
    "nullifier":    "Idol Nullifier — played secretly against another player; cancels their idol if they play it.",
    "legacy":       "Legacy Advantage — bequeath it on elimination; activates at the holder's next Tribal Council.",
    "custom":       "Custom advantage — see your submissions channel for details from the hosts.",
}


class AdvantagesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _next_key(self) -> str:
        return str(uuid.uuid4())[:8].upper()

    async def _dm_advantage(self, member: Member, adv: dict, key: str):
        """Send a DM to the player with their advantage details."""
        adv_type = adv["type"]
        desc = ADVANTAGE_DESCRIPTIONS.get(adv_type, adv.get("notes", ""))
        expires = f"\n**Expires:** {adv['expires']}" if adv.get("expires") else ""
        e = discord.Embed(
            title=f"🎴 You found an advantage!",
            description=(
                f"**Type:** {adv_type.replace('_', ' ').title()}\n"
                f"**Reference key:** `{key}`\n\n"
                f"{desc}{expires}\n\n"
                f"Use `/playidol` or `/transferadvantage` to use it.\n"
                f"Keep this advantage secret — only you and the hosts know you have it."
            ),
            color=utils.WARN_COLOR,
        )
        try:
            await member.send(embed=e)
        except discord.Forbidden:
            log.warning(f"Could not DM {member.name} — DMs may be closed.")

    # ── /giveadvantage ────────────────────────────────────────────────────────

    @app_commands.command(name="giveadvantage", description="[Host] Give any advantage to a player.")
    @app_commands.describe(
        member="Player receiving the advantage",
        advantage_type="Type of advantage",
        expires="Tribal Council # it expires (e.g. 'tribal_5'), or leave blank for never",
        notes="Optional notes visible only to hosts",
    )
    @app_commands.choices(advantage_type=ADVANTAGE_TYPES)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveadvantage(
        self,
        interaction: discord.Interaction,
        member: Member,
        advantage_type: str,
        expires: Optional[str] = None,
        notes: str = "",
    ):
        await interaction.response.defer(ephemeral=True)
        season = state.current_season()
        game = state.load(season)

        uid = str(member.id)
        if not state.get_player(game, uid):
            await interaction.followup.send(embed=utils.error_embed("Unknown player", f"{member.mention} is not registered."), ephemeral=True)
            return

        key = self._next_key()
        adv = {
            "type": advantage_type,
            "holder_uid": uid,
            "given_at": game.get("phase", "pregame"),
            "expires": expires,
            "played": False,
            "notes": notes,
        }
        game["advantages"][key] = adv
        game["players"][uid]["advantages"].append(key)
        await state.save(season, game)

        await self._dm_advantage(member, adv, key)

        log.info(f"Gave {advantage_type} (key={key}) to {game['players'][uid]['name']}")
        await interaction.followup.send(
            embed=utils.success_embed(
                f"Advantage given: {advantage_type.replace('_', ' ').title()}",
                f"**Recipient:** {member.mention}\n**Key:** `{key}`\nPlayer has been DMed.",
            ),
            ephemeral=True,
        )

    # ── /giveidol — convenience alias ─────────────────────────────────────────

    @app_commands.command(name="giveidol", description="[Host] Give a Hidden Immunity Idol to a player.")
    @app_commands.describe(
        member="Player receiving the idol",
        expires="Tribal Council # it expires, or blank for never",
        notes="Optional host notes",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveidol(
        self,
        interaction: discord.Interaction,
        member: Member,
        expires: Optional[str] = None,
        notes: str = "",
    ):
        await interaction.response.defer(ephemeral=True)
        season = state.current_season()
        game = state.load(season)
        uid = str(member.id)
        if not state.get_player(game, uid):
            await interaction.followup.send(embed=utils.error_embed("Unknown player"), ephemeral=True)
            return

        key = self._next_key()
        adv = {"type": "idol", "holder_uid": uid, "given_at": game.get("phase"), "expires": expires, "played": False, "notes": notes}
        game["advantages"][key] = adv
        game["players"][uid]["advantages"].append(key)
        await state.save(season, game)
        await self._dm_advantage(member, adv, key)

        await interaction.followup.send(
            embed=utils.success_embed("🗿 Idol given!", f"{member.mention} now holds idol `{key}`. They've been DMed."),
            ephemeral=True,
        )

    # ── /playidol ─────────────────────────────────────────────────────────────

    @app_commands.command(name="playidol", description="Play a Hidden Immunity Idol (or other advantage).")
    @app_commands.describe(
        advantage_key="The reference key of the advantage to play",
        target="Player to protect (idols only — leave blank to protect yourself)",
    )
    async def playidol(
        self,
        interaction: discord.Interaction,
        advantage_key: str,
        target: Optional[Member] = None,
    ):
        await interaction.response.defer()
        season = state.current_season()
        guild = interaction.guild
        game = state.load(season)
        host_role = guild.get_role(game["host_role_id"]) if game["host_role_id"] else None

        key = advantage_key.upper()
        adv = state.get_advantage(game, key)
        if not adv:
            await interaction.followup.send(embed=utils.error_embed("Advantage not found", f"Key `{key}` doesn't exist."), ephemeral=True)
            return

        uid = str(interaction.user.id)
        is_host = host_role and host_role in interaction.user.roles

        if adv["holder_uid"] != uid and not is_host:
            await interaction.followup.send(embed=utils.error_embed("Not yours", "You don't hold this advantage."), ephemeral=True)
            return

        if adv["played"]:
            await interaction.followup.send(embed=utils.error_embed("Already played", f"Advantage `{key}` has already been used."), ephemeral=True)
            return

        holder_uid = adv["holder_uid"]
        holder_name = game["players"].get(holder_uid, {}).get("name", "Unknown")
        adv_type = adv["type"]

        adv["played"] = True
        if key in game["players"].get(holder_uid, {}).get("advantages", []):
            game["players"][holder_uid]["advantages"].remove(key)

        await state.save(season, game)

        target_str = ""
        if target:
            target_name = game["players"].get(str(target.id), {}).get("name", target.display_name)
            target_str = f" protecting **{target_name}**"

        description = (
            f"**{holder_name}** plays their **{adv_type.replace('_', ' ').title()}**{target_str}!\n\n"
            f"{ADVANTAGE_DESCRIPTIONS.get(adv_type, '')}"
        )

        e = discord.Embed(title="🏺 An advantage has been played!", description=description, color=utils.TORCH_COLOR)
        await interaction.followup.send(embed=e)
        log.info(f"Advantage {key} ({adv_type}) played by {holder_name}")

    # ── /transferadvantage ────────────────────────────────────────────────────

    @app_commands.command(name="transferadvantage", description="Give your advantage to another player.")
    @app_commands.describe(
        advantage_key="The reference key of the advantage",
        recipient="Player to give it to",
    )
    async def transferadvantage(
        self,
        interaction: discord.Interaction,
        advantage_key: str,
        recipient: Member,
    ):
        await interaction.response.defer(ephemeral=True)
        season = state.current_season()
        guild = interaction.guild
        game = state.load(season)
        host_role = guild.get_role(game["host_role_id"]) if game["host_role_id"] else None

        key = advantage_key.upper()
        adv = state.get_advantage(game, key)
        uid = str(interaction.user.id)
        is_host = host_role and host_role in interaction.user.roles

        if not adv:
            await interaction.followup.send(embed=utils.error_embed("Advantage not found"), ephemeral=True)
            return
        if adv["played"]:
            await interaction.followup.send(embed=utils.error_embed("Already played"), ephemeral=True)
            return
        if adv["holder_uid"] != uid and not is_host:
            await interaction.followup.send(embed=utils.error_embed("Not yours"), ephemeral=True)
            return

        old_uid = adv["holder_uid"]
        new_uid = str(recipient.id)

        if not state.get_player(game, new_uid):
            await interaction.followup.send(embed=utils.error_embed("Recipient not registered"), ephemeral=True)
            return

        if key in game["players"].get(old_uid, {}).get("advantages", []):
            game["players"][old_uid]["advantages"].remove(key)
        game["players"][new_uid]["advantages"].append(key)
        adv["holder_uid"] = new_uid

        await state.save(season, game)
        await self._dm_advantage(recipient, adv, key)

        giver_name = game["players"].get(old_uid, {}).get("name", "Unknown")
        recip_name = game["players"].get(new_uid, {}).get("name", recipient.display_name)

        log.info(f"Advantage {key} transferred from {giver_name} to {recip_name}")
        await interaction.followup.send(
            embed=utils.success_embed(
                "Advantage transferred",
                f"**{giver_name}** → **{recip_name}**\nKey: `{key}`\nRecipient has been DMed.",
            ),
            ephemeral=True,
        )

    # ── /listadvantages ───────────────────────────────────────────────────────

    @app_commands.command(name="listadvantages", description="List all advantages. Hosts see all; players see only their own.")
    async def listadvantages(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        season = state.current_season()
        guild = interaction.guild
        game = state.load(season)
        host_role = guild.get_role(game["host_role_id"]) if game["host_role_id"] else None
        is_host = host_role and host_role in interaction.user.roles
        uid = str(interaction.user.id)

        active_advs = {k: v for k, v in game["advantages"].items() if not v["played"]}
        if not active_advs:
            await interaction.followup.send(embed=utils.embed("No active advantages", "All clear!"), ephemeral=True)
            return

        e = discord.Embed(title="🗃 Active Advantages", color=utils.WARN_COLOR)
        for key, adv in active_advs.items():
            holder_uid = adv["holder_uid"]
            if not is_host and holder_uid != uid:
                continue
            holder_name = game["players"].get(holder_uid, {}).get("name", "Unknown")
            e.add_field(
                name=f"`{key}` — {adv['type'].replace('_', ' ').title()}",
                value=(
                    f"Held by: **{holder_name}**\n"
                    f"Expires: {adv.get('expires') or 'Never'}"
                    + (f"\nNotes: {adv['notes']}" if is_host and adv.get("notes") else "")
                ),
                inline=False,
            )

        if not e.fields:
            e.description = "You hold no active advantages."

        await interaction.followup.send(embed=e, ephemeral=True)

    # ── /expireadvantage ──────────────────────────────────────────────────────

    @app_commands.command(name="expireadvantage", description="[Host] Manually expire/remove an advantage without playing it.")
    @app_commands.describe(advantage_key="The reference key")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def expireadvantage(self, interaction: discord.Interaction, advantage_key: str):
        await interaction.response.defer(ephemeral=True)
        season = state.current_season()
        game = state.load(season)
        key = advantage_key.upper()
        adv = state.get_advantage(game, key)
        if not adv:
            await interaction.followup.send(embed=utils.error_embed("Not found"), ephemeral=True)
            return

        holder_uid = adv["holder_uid"]
        if key in game["players"].get(holder_uid, {}).get("advantages", []):
            game["players"][holder_uid]["advantages"].remove(key)
        adv["played"] = True

        await state.save(season, game)
        await interaction.followup.send(
            embed=utils.success_embed("Advantage expired", f"`{key}` has been removed from play."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AdvantagesCog(bot))
