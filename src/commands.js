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

export const SWAP_TRIBES_COMMAND = {
  name: "swap_tribes",
  description:
    "Divides players into new tribes and handles movement of confs/subs/1:1s.",
  options: [
    {
      name: "old_tribes",
      description: "Comma-separated list of current tribes",
      type: 3, // STRING
      required: true,
    },
    {
      name: "new_tribes",
      description: "Comma-separated list of new tribes",
      type: 3, // STRING
      required: true,
    },
  ],
};

// Can't have more than 25 inputs!! Not great for this game...
// const MASTERMIND_CHOICES = [
//   { name: "Wolfsbane", value: "Wolfsbane" },
//   { name: "Nightshade", value: "Nightshade" },
//   { name: "Dragon’s Blood Resin", value: "Dragon’s Blood Resin" },
//   { name: "Mirror Shard", value: "Mirror Shard" },
//   { name: "Dwarf Beard Hair", value: "Dwarf Beard Hair" },
//   { name: "Frogspawn", value: "Frogspawn" },
//   { name: "Raven Feather", value: "Raven Feather" },
//   { name: "Crushed Ruby", value: "Crushed Ruby" },
//   { name: "Enchanted Apple Slice", value: "Enchanted Apple Slice" },
//   { name: "Snake Fang", value: "Snake Fang" },
//   { name: "Unicorn Hair", value: "Unicorn Hair" },
//   { name: "Thorny Vine", value: "Thorny Vine" },
//   { name: "Ashes of a Cursed Scroll", value: "Ashes of a Cursed Scroll" },
//   { name: "Glowcap Mushroom", value: "Glowcap Mushroom" },
//   { name: "Liquid Moonlight", value: "Liquid Moonlight" },
//   { name: "Snowdrop Petal", value: "Snowdrop Petal" },
//   { name: "Phoenix Tear", value: "Phoenix Tear" },
//   { name: "Beetle Carapace", value: "Beetle Carapace" },
//   { name: "Silver Thread", value: "Silver Thread" },
//   { name: "Root of Mandrake", value: "Root of Mandrake" },
//   { name: "Whispering Willow Bark", value: "Whispering Willow Bark" },
//   { name: "Spider Silk", value: "Spider Silk" },
//   { name: "Petal of Eternal Rose", value: "Petal of Eternal Rose" },
//   { name: "Cloudberry", value: "Cloudberry" },
//   { name: "Goblin Toenail", value: "Goblin Toenail" },
//   { name: "Elixir of Lies", value: "Elixir of Lies" },
//   { name: "Hair from a Sleeping Maiden", value: "Hair from a Sleeping Maiden" },
//   { name: "Smoldering Coal", value: "Smoldering Coal" },
//   { name: "Mist of the Forgotten", value: "Mist of the Forgotten" },
//   { name: "Salt of the Earth", value: "Salt of the Earth" },
// ];

// export const MASTERMIND_COMMAND = {
//   name: "mastermind",
//   description:
//     "Guess the 10 items / order and recieve a response about the correctness of your guess.",
//   options: [
//     {
//       name: "item1",
//       description: "The first item",
//       type: 3, // STRING,
//       choices: MASTERMIND_CHOICES,
//       required: true,
//     },
//     {
//       name: "item2",
//       description: "The second item",
//       type: 3, // STRING,
//       choices: MASTERMIND_CHOICES,
//       required: true,
//     },
//     {
//       name: "item3",
//       description: "The third item",
//       type: 3, // STRING,
//       choices: MASTERMIND_CHOICES,
//       required: true,
//     },
//     {
//       name: "item4",
//       description: "The fourth item",
//       type: 3, // STRING,
//       choices: MASTERMIND_CHOICES,
//       required: true,
//     },
//     {
//       name: "item5",
//       description: "The fifth item",
//       type: 3, // STRING,
//       choices: MASTERMIND_CHOICES,
//       required: true,
//     },
//     {
//       name: "item6",
//       description: "The sixth item",
//       type: 3, // STRING,
//       choices: MASTERMIND_CHOICES,
//       required: true,
//     },
//     {
//       name: "item7",
//       description: "The seventh item",
//       type: 3, // STRING,
//       choices: MASTERMIND_CHOICES,
//       required: true,
//     },
//     {
//       name: "item8",
//       description: "The eighth item",
//       type: 3, // STRING,
//       choices: MASTERMIND_CHOICES,
//       required: true,
//     },
//     {
//       name: "item9",
//       description: "The ninth item",
//       type: 3, // STRING,
//       choices: MASTERMIND_CHOICES,
//       required: true,
//     },
//     {
//       name: "item10",
//       description: "The tenth item",
//       type: 3, // STRING,
//       choices: MASTERMIND_CHOICES,
//       required: true,
//     },
//   ],
// };

export const INVITE_COMMAND = {
  name: "invite",
  description: "Get an invite link to add the bot to your server.",
};
