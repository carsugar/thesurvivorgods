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
  removeRoleForPlayer,
  createRole,
} from "./utils";
import { ChannelTypes } from "discord-interactions";

const PLAYER_ROLE_NAME = "Dwarfs";
const PRE_JURY_ROLE_NAME = "Prejury";
const JURY_ROLE_NAME = "Jury";
const SEASON_ROLE_NAME = "S2: Reflections of Fate";
const SPEC_ROLE_NAME = "Spectators";
const TRUSTED_SPEC_ROLE = "Trusted Spectators";
const ARCHIVE_CATEGORY_NAME = "Queens Basement";

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

    await removeRoleForPlayer(guild_id, env, roles, user, SPEC_ROLE_NAME);
    await removeRoleForPlayer(guild_id, env, roles, user, TRUSTED_SPEC_ROLE);

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

export const bootPlayer = async (interaction, env) => {
  try {
    const { user, tribe, is_jury } = parseSlashCommandOptions(
      interaction.data.options
    );

    const { guild_id } = interaction;

    const playerRes = await axios.get(
      `${DISCORD_API_BASE_URL}/guilds/${guild_id}/members/${user}`,
      {
        headers: {
          Authorization: `Bot ${env.DISCORD_TOKEN}`,
        },
      }
    );
    const playerName = playerRes.data.nick;

    const roles = await getRoles(guild_id, env);
    const channels = await getChannels(guild_id, env);

    await addRoleForPlayer(
      guild_id,
      env,
      roles,
      user,
      is_jury ? JURY_ROLE_NAME : PRE_JURY_ROLE_NAME
    );
    await addRoleForPlayer(guild_id, env, roles, user, SEASON_ROLE_NAME);
    if (!is_jury) {
      await addRoleForPlayer(guild_id, env, roles, user, TRUSTED_SPEC_ROLE);
    }
    await removeRoleForPlayer(guild_id, env, roles, user, playerName);
    await removeRoleForPlayer(guild_id, env, roles, user, PLAYER_ROLE_NAME);
    await removeRoleForPlayer(guild_id, env, roles, user, tribe);

    const archiveCategory = await getOrCreateCategory(
      guild_id,
      env,
      channels,
      ARCHIVE_CATEGORY_NAME
    );

    const tribe1on1sCategory = await getOrCreateCategory(
      guild_id,
      env,
      channels,
      `${tribe} One on Ones`
    );

    const oneOnOnes = channels.filter(
      (channel) =>
        channel.parent_id === tribe1on1sCategory &&
        channel.name.includes(playerName.toLowerCase().split(" ").join("-"))
    );

    for (const channel of oneOnOnes) {
      await axios.patch(
        `${DISCORD_API_BASE_URL}/channels/${channel.id}`,
        {
          permission_overwrites: [
            { id: guild_id, type: 0, deny: 0x400 }, // @everyone cannot view
          ],
          parent_id: archiveCategory,
        },
        {
          headers: {
            Authorization: `Bot ${env.DISCORD_TOKEN}`,
          },
        }
      );
    }

    const tribeConfsCategory = await getOrCreateCategory(
      guild_id,
      env,
      channels,
      `${tribe} Confs/Subs`
    );

    const confAndSub = channels.filter(
      (channel) =>
        channel.parent_id === tribeConfsCategory &&
        channel.name.includes(playerName.toLowerCase().split(" ").join("-"))
    );

    for (const channel of confAndSub) {
      await axios.patch(
        `${DISCORD_API_BASE_URL}/channels/${channel.id}`,
        {
          parent_id: archiveCategory,
        },
        {
          headers: {
            Authorization: `Bot ${env.DISCORD_TOKEN}`,
          },
        }
      );
    }
  } catch (e) {
    console.log("Failed to boot player: ", e);
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
          const [a, b] = [players[i], players[j]].sort((a, b) =>
            a.nick.localeCompare(b.nick)
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

    for (const tribe of newTribeList) {
      const newTribeRole = await createRole(guild_id, env, tribe);
      roles.push({ name: tribe, id: newTribeRole }); // Make sure we know not to create the role again
    }

    let oldTribeRoles = [];
    for (const tribe of oldTribeList) {
      const oldTribeRole = roles.filter((role) => role.name === tribe)[0]?.id;
      oldTribeRoles.push(oldTribeRole);
    }

    for (let i = 0; i < shuffledPlayers.length; i++) {
      const tribe = newTribeList[i % newTribeList.length];
      const player = shuffledPlayers[i];
      newTribePlayers[tribe].push(player);

      await addRoleForPlayer(guild_id, env, roles, player.user.id, tribe);

      const rolesToRemove = player.roles.filter((role) =>
        oldTribeRoles.includes(role)
      );

      for (const oldRole of rolesToRemove) {
        await removeRoleForPlayer(
          guild_id,
          env,
          roles,
          player.user.id,
          oldRole
        );
      }
    }

    for (const tribe of newTribeList) {
      const tribePlayers = newTribePlayers[tribe];

      const pairs = [];
      for (let i = 0; i < tribePlayers.length; i++) {
        for (let j = i + 1; j < tribePlayers.length; j++) {
          const [a, b] = [tribePlayers[i], tribePlayers[j]].sort((a, b) =>
            a.nick.localeCompare(b.nick)
          );
          pairs.push([a, b]);
        }
      }

      const tribe1on1sCategory = await getOrCreateCategory(
        guild_id,
        env,
        channels,
        `${tribe} One on Ones`
      );

      for (const pair of pairs) {
        const oneOnOne = await getOrCreate1on1(
          guild_id,
          env,
          channels,
          pair[0],
          pair[1],
          tribe1on1sCategory
        );

        if (oneOnOne.parent_id !== tribe1on1sCategory) {
          await axios.patch(
            `${DISCORD_API_BASE_URL}/channels/${oneOnOne}`,
            {
              permission_overwrites: [
                { id: guild_id, type: 0, deny: 0x400 }, // @everyone cannot view
                { id: pair[0].user.id, type: 1, allow: 0x400 | 0x800 }, // player 1 can view + message
                { id: pair[1].user.id, type: 1, allow: 0x400 | 0x800 }, // player 2 can view + message
              ],
              parent_id: tribe1on1sCategory,
            },
            {
              headers: {
                Authorization: `Bot ${env.DISCORD_TOKEN}`,
              },
            }
          );
        }
      }
    }

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

    return "Tribes swapped!";
  } catch (e) {
    console.log("Failed to swap tribes: ", e);
  }
};
