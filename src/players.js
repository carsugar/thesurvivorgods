import axios from "axios";
import {
  DISCORD_API_BASE_URL,
  parseSlashCommandOptions,
  // getGuildRoles,
} from "./utils";

export const addPlayer = async (interaction, env) => {
  try {
    const { user, player_name } = parseSlashCommandOptions(
      interaction.data.options
    );

    // await env.DB.prepare("insert into players (id, player_name) values (?, ?)")
    //   .bind(user, player_name)
    //   .all();

    // create and add role to player
    // const roles = await getGuildRoles(interaction.guild_id, env);
    // console.log("roles", roles);

    const newRoleRes = await axios.post(
      `${DISCORD_API_BASE_URL}/guilds/${interaction.guild_id}/roles`,
      {
        name: `${player_name}`,
      },
      {
        headers: {
          Authorization: `Bot ${env.DISCORD_TOKEN}`,
        },
      }
    );
    const newRoleId = newRoleRes.data.id;

    await axios.put(
      `${DISCORD_API_BASE_URL}/guilds/${interaction.guild_id}/members/${user}/roles/${newRoleId}`,
      {},
      {
        headers: {
          Authorization: `Bot ${env.DISCORD_TOKEN}`,
        },
      }
    );

    // Dwarves role (for S2)
    await axios.put(
      `${DISCORD_API_BASE_URL}/guilds/${interaction.guild_id}/members/${user}/roles/1380780197195939920`,
      {},
      {
        headers: {
          Authorization: `Bot ${env.DISCORD_TOKEN}`,
        },
      }
    );

    console.log("changing name");
    // Change player name
    await axios.patch(
      `${DISCORD_API_BASE_URL}/guilds/${interaction.guild_id}/members/${user}`,
      { nick: player_name },
      {
        headers: {
          Authorization: `Bot ${env.DISCORD_TOKEN}`,
        },
      }
    );
    console.log("done");
  } catch (e) {
    console.log("Failed to add player: ", e);
  }
};
