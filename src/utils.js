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

export const getGuildRoles = async (guild, env) => {
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
