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
  let newCategory = existingChannels.filter(
    (channel) => channel.name === categoryName
  )[0]?.id;

  if (!newCategory) {
    newCategory = await createChannel(
      guild,
      env,
      categoryName,
      ChannelTypes.GUILD_CATEGORY
    );
  }

  return newCategory;
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
