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
  getOrCreate1on1,
} from "./utils";
import { ChannelTypes } from "discord-interactions";

const PLAYER_ROLE_NAME = "Player";

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
    await addRoleForPlayer(guild_id, env, roles, user, PLAYER_ROLE_NAME);

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
    // TODO: maybe just pre-make the tribe roles and pass the role object in here?
    const { tribes } = parseSlashCommandOptions(interaction.data.options);
    const tribeList = tribes.split(",");

    const { guild_id } = interaction;

    const channels = await getChannels(guild_id, env);
    const members = await getMembers(guild_id, env);
    const roles = await getRoles(guild_id, env);

    const playerRole = roles.filter((role) => role.name === "Player")[0]?.id;
    const players = members.filter((member) =>
      member.roles.includes(tribeRole)
    );

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
        await getOrCreate1on1(
          guild_id,
          env,
          channels,
          pair[0],
          pair[1],
          tribe1on1sCategory
        );
      }
    }
  } catch (e) {
    console.log("Failed to create one on ones: ", e);
  }
};

export const swapTribes = async (interaction, env) => {
  try {
    const { old_tribes, new_tribes } = parseSlashCommandOptions(
      interaction.data.options
    );
    const oldTribeList = old_tribes.split(",");
    const newTribeList = new_tribes.split(",");

    const { guild_id } = interaction;

    const channels = await getChannels(guild_id, env);
    const members = await getMembers(guild_id, env);
    const roles = await getRoles(guild_id, env);

    const playerRole = roles.filter((role) => role.name === PLAYER_ROLE_NAME)[0]
      ?.id;
    const players = members.filter((member) =>
      member.roles.includes(playerRole)
    );
    const shuffledPlayers = [...players].sort(() => Math.random() - 0.5);

    let newTribePlayers = {};
    newTribeList.forEach((newTribe) => (newTribePlayers[newTribe] = []));

    shuffledPlayers.forEach((player, index) => {
      const tribe = newTribeList[index % newTribeList.length];
      newTribePlayers[tribe].push(player.nick);
    });

    console.log("newTribePlayers", newTribePlayers);

    // randomize new tribes
    // for each pair of new tribe:
    // look for existing 1:1
    // if found, update perms if old tribe is not the same (which would mean its active and not from a prev swap)
    // if not found, create new 1:1
    // also need to archive unneeded 1:1s - best way to identify these? maybe want to use a special symbol?

    // for (const oldTribe of oldTribeList) {
    //   // get members

    //   const tribe1on1sCategory = await getOrCreateCategory(
    //     guild_id,
    //     env,
    //     channels,
    //     `${tribe} One on Ones`
    //   );

    //   const tribeRole = roles.filter((role) => role.name === tribe)[0]?.id;
    //   const players = members.filter((member) =>
    //     member.roles.includes(tribeRole)
    //   );

    //   const pairs = [];
    //   for (let i = 0; i < players.length; i++) {
    //     for (let j = i + 1; j < players.length; j++) {
    //       const [a, b] = [players[i], players[j]].sort(
    //         (a, b) => a.nick - b.nick
    //       );
    //       pairs.push([a, b]);
    //     }
    //   }

    //   for (const pair of pairs) {
    //     await createChannel(
    //       guild_id,
    //       env,
    //       `${pair[0].nick}-${pair[1].nick}`,
    //       ChannelTypes.GUILD_TEXT,
    //       [
    //         { id: guild_id, type: 0, deny: 0x400 }, // @everyone cannot view
    //         { id: pair[0].user.id, type: 1, allow: 0x400 | 0x800 }, // player 1 can view + message
    //         { id: pair[1].user.id, type: 1, allow: 0x400 | 0x800 }, // player 2 can view + message
    //       ],
    //       tribe1on1sCategory
    //     );
    //   }
    // }

    // const newTribesRundown = ``;

    return JSON.stringify(newTribePlayers);
  } catch (e) {
    console.log("Failed to swap tribes: ", e);
  }
};
