/**
 * Share command metadata from a common spot to be used for both runtime
 * and registration.
 */

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

export const AWW_COMMAND = {
  name: "awwww",
  description: "Drop some cuteness on this channel.",
};

export const INVITE_COMMAND = {
  name: "invite",
  description: "Get an invite link to add the bot to your server.",
};
