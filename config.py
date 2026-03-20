"""
config.py — Season theming and configuration commands.

Commands:
  /settheme  — Customize emojis, labels, and flavor text for a season
  /showtheme — Display the current theme settings
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import logging
import state
import utils

log = logging.getLogger("TheSurvivorGods.config")

DEFAULT_SEASON = 1


class ConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /showtheme ────────────────────────────────────────────────────────────

    @app_commands.command(name="showtheme", description="Show the current season theme settings.")
    @app_commands.describe(season="Season number (default: 1)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def showtheme(self, interaction: discord.Interaction, season: int = DEFAULT_SEASON):
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
        player_role_label="Suffix for the player role name (default: Player)",
        snuff_title="Title shown when a player is eliminated (default: The tribe has spoken.)",
        snuff_suffix="Text after player name on elimination (default: 's torch has been snuffed.)",
        season="Season number (default: 1)",
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
        season: int = DEFAULT_SEASON,
    ):
        await interaction.response.defer(ephemeral=True)
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
