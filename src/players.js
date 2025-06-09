import axios from "axios";
import {
  createRole,
  DISCORD_API_BASE_URL,
  getChannels,
  createChannel,
  parseSlashCommandOptions,
  getRoles,
  addRoleForPlayer,
} from "./utils";
import { ChannelTypes } from "discord-interactions";

export const addPlayer = async (interaction, env) => {
  try {
    const { user, player_name, tribe } = parseSlashCommandOptions(
      interaction.data.options
    );

    const { guild_id } = interaction;

    const roles = await getRoles(guild_id, env);

    // await env.DB.prepare("insert into players (id, player_name) values (?, ?)")
    //   .bind(user, player_name)
    //   .all();

    // Add individual role for player
    await addRoleForPlayer(guild_id, env, roles, user, player_name);

    // Add role for tribe
    await addRoleForPlayer(guild_id, env, roles, user, tribe);

    // Add general player role
    await addRoleForPlayer(guild_id, env, roles, user, "Player");

    // Change player name
    await axios.patch(
      `${DISCORD_API_BASE_URL}/guilds/${guild_id}/members/${user}`,
      { nick: player_name },
      {
        headers: {
          Authorization: `Bot ${env.DISCORD_TOKEN}`,
        },
      }
    );

    // Create confessional + submissions channels (creating tribe category if needed)
    const channels = await getChannels(guild_id, env);
    let tribeConfsChannel = channels.filter(
      (channel) => channel.name === `${tribe} Confs`
    )[0]?.id;

    if (!tribeConfsChannel) {
      tribeConfsChannel = await createChannel(
        guild_id,
        env,
        `${tribe} Confs`,
        ChannelTypes.GUILD_CATEGORY
      );
    }

    // Create confessional and submissions channels
    await createChannel(
      guild_id,
      env,
      `${player_name}-confessional`,
      ChannelTypes.GUILD_TEXT,
      [
        { id: guild_id, type: 0, deny: 0x400 }, // @everyone cannot view
        { id: user, type: 1, allow: 0x400 | 0x800 }, // player can view + message
        // TODO: let trusted specs view but not message
      ],
      tribeConfsChannel
    );

    await createChannel(
      guild_id,
      env,
      `${player_name}-submissions`,
      ChannelTypes.GUILD_TEXT,
      [
        { id: guild_id, type: 0, deny: 0x400 }, // @everyone cannot view
        { id: user, type: 1, allow: 0x400 | 0x800 }, // player can view + message
      ],
      tribeConfsChannel
    );
  } catch (e) {
    console.log("Failed to add player: ", e);
  }
};
