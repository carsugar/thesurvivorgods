"""
TheSurvivorGods — Discord bot for running Survivor ORGs.
Entry point: run with `python bot.py`
"""

import discord
from discord.ext import commands
import os
import logging
from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("TheSurvivorGods")

COGS = [
    "players",
    "tribes",
    "advantages",
    "config",
]

class SurvivorBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info(f"Loaded cog: {cog}")
            except Exception as e:
                log.error(f"Failed to load cog {cog}: {e}")

        # Sync commands to guild for instant updates
        guild_obj = discord.Object(id=1336577033181855884)
        self.tree.copy_global_to(guild=guild_obj)
        await self.tree.sync(guild=guild_obj)
        log.info("Slash commands synced.")

    async def on_ready(self):
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Game(name="Survivor ORG | /addplayer to start")
        )


def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN environment variable not set.")
    bot = SurvivorBot()
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
