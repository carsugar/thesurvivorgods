// import axios from "axios";
// import { DISCORD_API_BASE_URL, parseSlashCommandOptions } from "./utils";

// export const queuePings = async (interaction) => {
//   try {
//     const args = parseSlashCommandOptions(interaction.data.options);
//     console.log("parsed options", args);

//     await QUEUE_NAMESPACE.create({
//       body: JSON.stringify({
//         channelId: args.channel,
//       }),
//       delay: 30 * 1000, // Delay in milliseconds
//     });
//   } catch (e) {
//     console.log("Failed to queue pings: ", e);
//   }
// };

// export const handlePingQueueEvent = async (event) => {
//   const { channelId, message } = JSON.parse(event.body);

//   // Send the actual ping to Discord
//   await pingChannel(channelId, message, event.env);
// };

// export const pingChannel = async (channelId, message, env) => {
//   try {
//     console.log("ping!", channelId, message);

//     await axios.post(
//       `${DISCORD_API_BASE_URL}/channels/${channelId}/messages`,
//       {
//         content: message,
//       },
//       {
//         headers: {
//           Authorization: `Bot ${env.DISCORD_TOKEN}`,
//         },
//       }
//     );

//     console.log("all done");
//   } catch (e) {
//     console.log("Failed to send ping: ", e);
//   }
// };
