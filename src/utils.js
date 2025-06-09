import axios from "axios";

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
  const rolesRes = await axios.post(
    `${DISCORD_API_BASE_URL}/guilds/${guild}/channels`,
    {
      name: channelName,
      type: channelType,
      parent_id: category,
      permission_overwrites: perms,
    },
    {
      headers: {
        Authorization: `Bot ${env.DISCORD_TOKEN}`,
      },
    }
  );
  return rolesRes.data.id;
};
