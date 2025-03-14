import { JsonResponse } from "./utils.js";
import { InteractionResponseType } from "discord-interactions";

import { createBot } from "@discordeno/bot";

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
  //   const roleNames = interaction.data.options
  //     .filter((option) => option.name === "members")[0]
  //     .value?.split(",");
  //   console.log("roles requested in alliance:", roleNames);
  //   const guild = await client.guilds.fetch(interaction.guild_id);
  //   console.log("guild is:", guild);
  //   const allMembers = await guild.members.fetch();
  //   //   const membersWithCorrectRoles = allMembers.filter()
  const bot = createBot({
    token:
      "MTM0NDQxMzU1NDE5OTIzNjY3MA.GPW9m6.H-YMRIyG98l3ScEq32MdZqR6MttlLFHI0zX1qM",
    events: {
      ready: ({ shardId }) => console.log(`Shard ${shardId} ready`),
    },
  });

  await bot.start();
  console.log("creating an alliance for:", interaction.data.options);
  return new JsonResponse({
    type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
    data: {
      content: "Creating an alliance!",
    },
  });
};
