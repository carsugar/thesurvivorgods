import axios from "axios";
import {
  DISCORD_API_BASE_URL,
  getChannels,
  createChannel,
  parseSlashCommandOptions,
  getRoles,
  addRoleForPlayer,
  getMembers,
  getOrCreateCategory,
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

    const tribeConfsCategory = await getOrCreateCategory(
      guild_id,
      env,
      channels,
      `${tribe} Confs/Subs`
    );

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
      tribeConfsCategory
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
      tribeConfsCategory
    );
  } catch (e) {
    console.log("Failed to add player: ", e);
  }
};

export const create1on1s = async (interaction, env) => {
  try {
    const { tribes } = parseSlashCommandOptions(interaction.data.options);
    const tribeList = tribes.split(",");

    const { guild_id } = interaction;

    const channels = await getChannels(guild_id, env);
    const members = await getMembers(guild_id, env);
    const roles = await getRoles(guild_id, env);

    for (const tribe of tribeList) {
      const tribe1on1sCategory = await getOrCreateCategory(
        guild_id,
        env,
        channels,
        `${tribe} One on Ones`
      );

      const tribeRole = roles.filter((role) => role.name === tribe)[0]?.id;
      const players = members.filter((member) =>
        member.roles.includes(tribeRole)
      );

      const pairs = [];
      for (let i = 0; i < players.length; i++) {
        for (let j = i + 1; j < players.length; j++) {
          const [a, b] = [players[i], players[j]].sort(
            (a, b) => a.nick - b.nick
          );
          pairs.push([a, b]);
        }
      }

      for (const pair of pairs) {
        await createChannel(
          guild_id,
          env,
          `${pair[0].nick}-${pair[1].nick}`,
          ChannelTypes.GUILD_TEXT,
          [
            { id: guild_id, type: 0, deny: 0x400 }, // @everyone cannot view
            { id: pair[0].user.id, type: 1, allow: 0x400 | 0x800 }, // player 1 can view + message
            { id: pair[1].user.id, type: 1, allow: 0x400 | 0x800 }, // player 2 can view + message
          ],
          tribe1on1sCategory
        );
      }
    }
  } catch (e) {
    console.log("Failed to create one on ones: ", e);
  }
};
