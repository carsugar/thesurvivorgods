"""
tribal.py — Tribal Council commands.

Commands:
  /opentribal — Open a Tribal Council for a tribe, creating a dedicated channel
                and locking the tribe's regular chat.
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord import PermissionOverwrite
import logging
import state
import utils

log = logging.getLogger("TheSurvivorGods.tribal")

TRIBAL_CATEGORY = "⚖️ Tribal Council"


class OpenTribalModal(discord.ui.Modal):
    def __init__(self, season: int, tribe_name: str):
        super().__init__(title=f"Tribal Council — {tribe_name}")
        self.season = season
        self.tribe_name = tribe_name

        self.welcome_message = discord.ui.TextInput(
            label="Welcome Message",
            style=discord.TextStyle.paragraph,
            default=(
                f"Welcome to Tribal Council, {tribe_name}! "
                f"Tonight, one of you will have your torch snuffed. "
                f"The game is on the line — speak carefully."
            ),
            required=True,
        )
        self.questions = discord.ui.TextInput(
            label="Discussion Questions (optional)",
            style=discord.TextStyle.paragraph,
            placeholder="e.g. Who do you trust most right now?\nDo you feel safe tonight?",
            required=False,
        )

        self.add_item(self.welcome_message)
        self.add_item(self.questions)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        season = self.season
        guild = interaction.guild
        game = state.load(season)
        tribe_name = self.tribe_name

        tribe = state.get_tribe(game, tribe_name)
        if not tribe:
            await interaction.followup.send(
                embed=utils.error_embed("Tribe not found", f"'{tribe_name}' doesn't exist."),
                ephemeral=True,
            )
            return

        host_role = guild.get_role(game["host_role_id"]) if game.get("host_role_id") else None
        spec_role  = guild.get_role(game["spectator_role_id"]) if game.get("spectator_role_id") else None
        tribe_role = guild.get_role(tribe["role_id"]) if tribe.get("role_id") else None

        # ── Increment tribal count ────────────────────────────────────────────
        tribal_num = game.get("tribal_count", 0) + 1
        game["tribal_count"] = tribal_num

        # ── Get/create Tribal Council category ───────────────────────────────
        cat_id = game.get("tribal_category_id")
        tribal_cat = guild.get_channel(cat_id) if cat_id else None
        if tribal_cat is None:
            cat_ow = {guild.default_role: PermissionOverwrite(read_messages=False)}
            if host_role:
                cat_ow[host_role] = PermissionOverwrite(
                    read_messages=True, send_messages=True, manage_messages=True
                )
            if spec_role:
                cat_ow[spec_role] = PermissionOverwrite(read_messages=True, send_messages=False)
            tribal_cat = await utils.get_or_create_category(guild, TRIBAL_CATEGORY, overwrites=cat_ow)
            game["tribal_category_id"] = tribal_cat.id

        # ── Create tribal channel ─────────────────────────────────────────────
        tribe_safe = utils.channel_safe(tribe_name)
        ch_name = f"tribal-{tribal_num}-{tribe_safe}"

        ch_ow = {guild.default_role: PermissionOverwrite(read_messages=False)}
        if tribe_role:
            ch_ow[tribe_role] = PermissionOverwrite(read_messages=True, send_messages=True)
        if host_role:
            ch_ow[host_role] = PermissionOverwrite(
                read_messages=True, send_messages=True, manage_messages=True
            )
        if spec_role:
            ch_ow[spec_role] = PermissionOverwrite(read_messages=True, send_messages=False)

        tribal_ch = await guild.create_text_channel(
            ch_name,
            category=tribal_cat,
            overwrites=ch_ow,
            topic=f"Tribal Council #{tribal_num} — {tribe_name}",
        )
        log.info(f"Created #{ch_name}")

        # ── Lock tribe chat so members can only talk in tribal channel ─────────
        tribe_chat = guild.get_channel(tribe.get("tribe_chat_id")) if tribe.get("tribe_chat_id") else None
        if tribe_chat and tribe_role:
            await tribe_chat.set_permissions(tribe_role, send_messages=False)
            await tribe_chat.send("## CLOSED FOR TRIBAL")
            log.info(f"Locked #{tribe_chat.name} for {tribe_name}")

        # ── Post welcome embed with optional questions ─────────────────────────
        welcome_text = str(self.welcome_message).strip()
        questions_text = str(self.questions).strip()

        e = discord.Embed(
            title=f"⚖️ Tribal Council #{tribal_num} — {tribe_name}",
            description=welcome_text,
            color=utils.TORCH_COLOR,
        )
        if questions_text:
            e.add_field(name="💬 Discussion Questions", value=questions_text, inline=False)

        mentions = " ".join(
            r.mention for r in [tribe_role, spec_role] if r is not None
        )
        await tribal_ch.send(mentions, embed=e)

        # ── Persist ───────────────────────────────────────────────────────────
        game.setdefault("tribals", []).append({
            "number": tribal_num,
            "tribe": tribe_name,
            "channel_id": tribal_ch.id,
        })
        await state.save(season, game)

        log.info(f"Opened Tribal Council #{tribal_num} for {tribe_name}")
        await interaction.followup.send(
            embed=utils.success_embed(
                f"Tribal Council #{tribal_num} opened!",
                f"Channel: {tribal_ch.mention}\nTribe chat locked for writing.",
            ),
            ephemeral=True,
        )


class TribalCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="opentribal", description="Open a Tribal Council for a tribe.")
    @app_commands.describe(tribe_name="Which tribe is attending Tribal Council")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def opentribal(self, interaction: discord.Interaction, tribe_name: str):
        season = state.current_season()
        game = state.load(season)
        if tribe_name not in game["tribes"]:
            await interaction.response.send_message(
                embed=utils.error_embed("Tribe not found", f"'{tribe_name}' isn't a current tribe."),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(OpenTribalModal(season=season, tribe_name=tribe_name))

    @app_commands.command(name="closetribal", description="Close Tribal Council: lock the tribal channel and restore the tribe chat.")
    @app_commands.describe(tribe_name="Which tribe's Tribal Council to close")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def closetribal(self, interaction: discord.Interaction, tribe_name: str):
        await interaction.response.defer(ephemeral=True)
        season = state.current_season()
        guild = interaction.guild
        game = state.load(season)

        tribe = state.get_tribe(game, tribe_name)
        if not tribe:
            await interaction.followup.send(
                embed=utils.error_embed("Tribe not found", f"'{tribe_name}' isn't a current tribe."),
                ephemeral=True,
            )
            return

        # Find the most recent tribal channel for this tribe
        tribal_entry = next(
            (t for t in reversed(game.get("tribals", [])) if t["tribe"] == tribe_name),
            None,
        )

        tribe_role = guild.get_role(tribe["role_id"]) if tribe.get("role_id") else None

        # Lock tribal channel — tribe can no longer write there
        if tribal_entry:
            tribal_ch = guild.get_channel(tribal_entry["channel_id"])
            if tribal_ch and tribe_role:
                await tribal_ch.set_permissions(tribe_role, send_messages=False)
                await tribal_ch.send("## TRIBAL CLOSED")
                log.info(f"Locked #{tribal_ch.name} for {tribe_name}")

        # Restore tribe chat — remove the send_messages deny so it inherits category perms
        tribe_chat = guild.get_channel(tribe.get("tribe_chat_id")) if tribe.get("tribe_chat_id") else None
        if tribe_chat and tribe_role:
            await tribe_chat.set_permissions(tribe_role, overwrite=None)
            await tribe_chat.send("## OPEN")
            log.info(f"Restored #{tribe_chat.name} for {tribe_name}")

        await state.save(season, game)

        lines = []
        if tribal_entry and guild.get_channel(tribal_entry["channel_id"]):
            lines.append(f"Tribal channel locked: {guild.get_channel(tribal_entry['channel_id']).mention}")
        if tribe_chat:
            lines.append(f"Tribe chat restored: {tribe_chat.mention}")

        await interaction.followup.send(
            embed=utils.success_embed(f"Tribal Council closed for {tribe_name}.", "\n".join(lines)),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TribalCog(bot))
