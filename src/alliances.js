import axios from "axios";
import { ChannelTypes } from "discord-interactions";
const DISCORD_API_BASE_URL = "https://discord.com/api/v10";

export const createAlliance = async (interaction, env) => {
  try {
    // Fetch roles for the guild.
    const guildRolesRes = await axios.get(
      `${DISCORD_API_BASE_URL}/guilds/${interaction.guild_id}/roles`,
      {
        headers: {
          Authorization: `Bot ${env.DISCORD_TOKEN}`,
        },
      }
    );

    // Find the roles that match the ones requested for the alliance.
    const rolesToAdd = interaction.data.options
      .filter((option) => option.name === "members")[0]
      .value?.split(",");
    const roleIdsToAdd = guildRolesRes.data
      .filter((role) => rolesToAdd.includes(role.name))
      .map((role) => role.id);

    // Create a new channel with the correct name and members.
    const allianceName = interaction.data.options.filter(
      (option) => option.name === "name"
    )[0].value;

    const rolePermissions = roleIdsToAdd.map((roleId) => {
      return {
        id: roleId,
        type: 0,
        allow: "3072", // Read and write in channel.
      };
    });

    await axios.post(
      `${DISCORD_API_BASE_URL}/guilds/${interaction.guild_id}/channels`,
      {
        name: allianceName,
        type: ChannelTypes.GUILD_TEXT,
        parent_id: "1339381891777957918",
        permission_overwrites: [
          {
            id: "1328343957608071178", // @everyone role
            type: 0,
            deny: "1024", // Deny VIEW_CHANNEL (bitwise value)
          },
          ...rolePermissions,
        ],
      },
      {
        headers: {
          Authorization: `Bot ${env.DISCORD_TOKEN}`,
        },
      }
    );
  } catch (e) {
    console.log("Failed to create alliance: ", e);
  }
};
