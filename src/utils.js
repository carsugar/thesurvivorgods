import axios from "axios";
import { ChannelTypes } from "discord-interactions";

export class JsonResponse extends Response {
  constructor(body, init) {
    const jsonBody = JSON.stringify(body);
    init = init || {
      headers: {
        "content-type": "application/json;charset=UTF-8",
      },
    };
    super(jsonBody, init);
  }
}

export const DISCORD_API_BASE_URL = "https://discord.com/api/v10";

export const parseSlashCommandOptions = (options) => {
  const parsedOptions = {};
  options.forEach((option) => (parsedOptions[option.name] = option.value));
  return parsedOptions;
};

export const getRoles = async (guild, env) => {
  const rolesRes = await axios.get(
    `${DISCORD_API_BASE_URL}/guilds/${guild}/roles`,
    {
      headers: {
        Authorization: `Bot ${env.DISCORD_TOKEN}`,
      },
    }
  );
  return rolesRes.data;
};

export const createRole = async (guild, env, roleName) => {
  console.log("Creating new role: ", roleName);
  const newRoleRes = await axios.post(
    `${DISCORD_API_BASE_URL}/guilds/${guild}/roles`,
    {
      name: roleName,
    },
    {
      headers: {
        Authorization: `Bot ${env.DISCORD_TOKEN}`,
      },
    }
  );

  return newRoleRes.data.id;
};

export const addRoleForPlayer = async (
  guild,
  env,
  existingRoles,
  user,
  roleName
) => {
  let newRole = existingRoles.filter((role) => role.name === roleName)[0]?.id;
  if (!newRole) {
    newRole = await createRole(guild, env, roleName);
  }
  await axios.put(
    `${DISCORD_API_BASE_URL}/guilds/${guild}/members/${user}/roles/${newRole}`,
    {},
    {
      headers: {
        Authorization: `Bot ${env.DISCORD_TOKEN}`,
      },
    }
  );
};

export const removeRoleForPlayer = async (
  guild,
  env,
  existingRoles,
  user,
  roleNameOrId
) => {
  let roleToRemove = existingRoles.filter(
    (role) => role.name === roleNameOrId || role.id === roleNameOrId
  )[0]?.id;

  if (roleToRemove) {
    while (true) {
      try {
        await axios.delete(
          `${DISCORD_API_BASE_URL}/guilds/${guild}/members/${user}/roles/${roleToRemove}`,
          {
            headers: {
              Authorization: `Bot ${env.DISCORD_TOKEN}`,
            },
          }
        );
        break; // success, exit loop
      } catch (e) {
        if (e.response?.status === 429) {
          const retryAfter = e.response.data?.retry_after || 1;
          await new Promise((resolve) =>
            setTimeout(resolve, retryAfter * 1000)
          );
        }
      }
    }
  }
};

export const getChannels = async (guild, env) => {
  const rolesRes = await axios.get(
    `${DISCORD_API_BASE_URL}/guilds/${guild}/channels`,
    {
      headers: {
        Authorization: `Bot ${env.DISCORD_TOKEN}`,
      },
    }
  );
  return rolesRes.data;
};

export const createChannel = async (
  guild,
  env,
  channelName,
  channelType,
  perms,
  category
) => {
  console.log("Creating new channel: ", channelName);

  let body = { name: channelName, type: channelType };
  if (category) {
    body.parent_id = category;
  }
  if (perms) {
    body.permission_overwrites = perms;
  }

  const channelRes = await axios.post(
    `${DISCORD_API_BASE_URL}/guilds/${guild}/channels`,
    body,
    {
      headers: {
        Authorization: `Bot ${env.DISCORD_TOKEN}`,
      },
    }
  );

  return channelRes.data.id;
};

export const getOrCreateCategory = async (
  guild,
  env,
  existingChannels,
  categoryName
) => {
  let existingCategory = existingChannels.filter(
    (channel) => channel.name === categoryName
  )[0]?.id;

  let newCategory;
  if (!existingCategory) {
    newCategory = await createChannel(
      guild,
      env,
      categoryName,
      ChannelTypes.GUILD_CATEGORY
    );
  }

  return existingCategory || newCategory;
};

export const getOrCreate1on1 = async (
  guild,
  env,
  existingChannels,
  player1,
  player2,
  category
) => {
  // do we want roles instead of users for the 1:1s? probably doesn't matter if perms
  // are being automated
  const ONE_ON_ONE_PERMS = [
    { id: guild, type: 0, deny: 0x400 }, // @everyone cannot view
    { id: player1.user.id, type: 1, allow: 0x400 | 0x800 }, // player 1 can view + message
    { id: player2.user.id, type: 1, allow: 0x400 | 0x800 }, // player 2 can view + message
  ];

  const player1Formatted = player1.nick.toLowerCase().split(" ").join("-");
  const player2Formatted = player2.nick.toLowerCase().split(" ").join("-");
  const oneOnOneName = `${player1Formatted}-${player2Formatted}`;

  // Look for existing 1:1 for these players
  let existing1on1 = existingChannels.filter(
    (channel) => channel.name === oneOnOneName
  )[0]?.id;

  let new1on1;
  if (existing1on1) {
    // Make sure all the right perms are set, because the 1:1
    // could have been archived in a previous swap.
    await axios.patch(
      `${DISCORD_API_BASE_URL}/channels/${existing1on1}`,
      {
        permission_overwrites: ONE_ON_ONE_PERMS,
      },
      {
        headers: {
          Authorization: `Bot ${env.DISCORD_TOKEN}`,
        },
      }
    );
  } else {
    new1on1 = await createChannel(
      guild,
      env,
      oneOnOneName,
      ChannelTypes.GUILD_TEXT,
      ONE_ON_ONE_PERMS,
      category
    );
  }

  return existing1on1 || new1on1;
};

export const getMembers = async (guild, env) => {
  let after = "0";
  let allMembers = [];
  let hasMore = true;

  while (hasMore) {
    const membersRes = await axios.get(
      `${DISCORD_API_BASE_URL}/guilds/${guild}/members`,
      {
        params: {
          limit: 1000,
          after,
        },
        headers: {
          Authorization: `Bot ${env.DISCORD_TOKEN}`,
        },
      }
    );
    const members = membersRes.data;
    allMembers.push(...members);

    if (members.length < 1000) {
      hasMore = false;
    } else {
      after = members[members.length - 1].user.id;
    }
  }

  return allMembers;
};
