import axios from "axios";

const DISCORD_API_BASE_URL = "https://discord.com/api/v10";

export const createAlliance = async (interaction, env) => {
  //   const roleNames = interaction.data.options
  //     .filter((option) => option.name === "members")[0]
  //     .value?.split(",");
  //   console.log("roles requested in alliance:", roleNames);
  //   const guild = await client.guilds.fetch(interaction.guild_id);
  //   console.log("guild is:", guild);
  //   const allMembers = await guild.members.fetch();
  //   //   const membersWithCorrectRoles = allMembers.filter()

  console.log(
    "hitting create endpoint for guild: ",
    env.DISCORD_TOKEN?.slice(0, 5)
  );

  try {
    const response = await axios.get(
      `${DISCORD_API_BASE_URL}/guilds/${interaction.guild_id}`,
      {
        headers: {
          Authorization: `Bot ${env.DISCORD_TOKEN}`,
        },
      }
    );
    console.log("created an alliance for:", response);
  } catch (e) {
    console.log("Failed to create alliance: ", e);
  }
};
