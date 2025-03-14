import { JsonResponse } from "./utils.js";
import { InteractionResponseType } from "discord-interactions";
import { Client, GatewayIntentBits } from "discord.js";
import { token } from "./register.js";

const client = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMembers],
});

client.login(token);

export const ALLIANCE_COMMAND = {
  name: "alliance",
  description: "Create an alliance between players.",
  options: [
    {
      name: "name",
      description: "The name of the alliance",
      type: 3, // 3 is type STRING
      required: true,
    },
    {
      name: "members",
      description:
        "Comma-separated list of people to add (use their role names!)",
      type: 3, // 3 is type STRING
      required: true,
    },
  ],
};

export const createAlliance = async (interaction) => {
  const roleNames = interaction.data.options
    .filter((option) => option.name === "members")
    .value.split(",");
  console.log("roles requested in alliance:", roleNames);
  const guild = await client.guilds.fetch(interaction.guild_id);
  console.log("guild is:", guild);
  const allMembers = await guild.members.fetch();
  //   const membersWithCorrectRoles = allMembers.filter()
  console.log("creating an alliance for:", allMembers);
  return new JsonResponse({
    type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
    data: {
      content: "Creating an alliance!",
    },
  });
};
