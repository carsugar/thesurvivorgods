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
      type: 3, // STRING
      required: true,
    },
    {
      name: "members",
      description:
        "Comma-separated list of people to add (use their role names!)",
      type: 3, // STRING
      required: true,
    },
  ],
};

export const ADD_PLAYER_COMMAND = {
  name: "add_player",
  description: "Add a player to the game.",
  options: [
    {
      name: "user",
      description: "The user to add",
      type: 6, // USER
      required: true,
    },
    {
      name: "player_name",
      description: "The name the player will use in the game.",
      type: 3, // STRING
      required: true,
    },
    {
      name: "tribe",
      description: "The tribe to which the player will belong.",
      type: 3, // STRING
      required: true,
    },
  ],
};

export const ONE_ON_ONES_COMMAND = {
  name: "one_on_ones",
  description: "Creates one on one chats between players on the same tribe.",
  options: [
    {
      name: "tribes",
      description: "Comma-separated list of tribes",
      type: 3, // STRING
      required: true,
    },
  ],
};

// export const PING_COMMAND = {
//   name: "ping",
//   description:
//     "Ping a channel with a message regularly at a specified interval.",
//   options: [
//     {
//       name: "message",
//       description: "The message to send",
//       type: 3, // STRING
//       required: true,
//     },
//     {
//       name: "channel",
//       description: "The channel to ping",
//       type: 7, // CHANNEL
//       required: true,
//     },
//     {
//       name: "interval",
//       description: "The number of minutes between each ping",
//       type: 4, // INTEGER
//       required: true,
//     },
//   ],
// };

export const INVITE_COMMAND = {
  name: "invite",
  description: "Get an invite link to add the bot to your server.",
};
