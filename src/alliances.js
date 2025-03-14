import { JsonResponse } from "./utils.js";
import { InteractionResponseType } from "discord-interactions";

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

export const createAlliance = (interaction) => {
  console.log("creating an alliance for:", interaction.data);
  return new JsonResponse({
    type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
    data: {
      content: "Creating an alliance!",
    },
  });
};
