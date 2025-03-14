import axios from "axios";
import dotenv from "dotenv";
import process from "node:process";

dotenv.config({ path: ".dev.vars" });

const DISCORD_API_BASE_URL = "https://discord.com/api/v10";

export const createAlliance = async (interaction) => {
  //   const roleNames = interaction.data.options
  //     .filter((option) => option.name === "members")[0]
  //     .value?.split(",");
  //   console.log("roles requested in alliance:", roleNames);
  //   const guild = await client.guilds.fetch(interaction.guild_id);
  //   console.log("guild is:", guild);
  //   const allMembers = await guild.members.fetch();
  //   //   const membersWithCorrectRoles = allMembers.filter()

  console.log("hit create endpoint");

  const response = await axios.get(
    `${DISCORD_API_BASE_URL}/guilds/${interaction.guild_id}/members`,
    {
      headers: {
        Authorization: `Bot ${process.env.DISCORD_TOKEN}`,
      },
    }
  );

  console.log("creating an alliance for:", response);
};
