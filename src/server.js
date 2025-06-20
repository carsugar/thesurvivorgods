/**
 * The core server that runs on a Cloudflare worker.
 */

import { AutoRouter } from "itty-router";
import {
  InteractionResponseType,
  InteractionType,
  verifyKey,
} from "discord-interactions";
import {
  ALLIANCE_COMMAND,
  ADD_PLAYER_COMMAND,
  BOOT_PLAYER_COMMAND,
  INVITE_COMMAND,
  ONE_ON_ONES_COMMAND,
  SWAP_TRIBES_COMMAND,
} from "./commands.js";
import { createAlliance } from "./alliances.js";
import { addPlayer, bootPlayer, create1on1s, swapTribes } from "./players.js";
import { InteractionResponseFlags } from "discord-interactions";
import { JsonResponse } from "./utils.js";

const router = AutoRouter();

/**
 * A simple :wave: hello page to verify the worker is working.
 */
router.get("/", (request, env) => {
  return new Response(`👋 ${env.DISCORD_APPLICATION_ID}`);
});

/**
 * Main route for all requests sent from Discord.  All incoming messages will
 * include a JSON payload described here:
 * https://discord.com/developers/docs/interactions/receiving-and-responding#interaction-object
 */
router.post("/", async (request, env) => {
  const { isValid, interaction } = await server.verifyDiscordRequest(
    request,
    env
  );
  if (!isValid || !interaction) {
    return new Response("Bad request signature.", { status: 401 });
  }

  if (interaction.type === InteractionType.PING) {
    // The `PING` message is used during the initial webhook handshake, and is
    // required to configure the webhook in the developer portal.
    return new JsonResponse({
      type: InteractionResponseType.PONG,
    });
  }

  if (interaction.type === InteractionType.APPLICATION_COMMAND) {
    // Most user commands will come as `APPLICATION_COMMAND`.
    switch (interaction.data.name.toLowerCase()) {
      case ALLIANCE_COMMAND.name.toLowerCase(): {
        await createAlliance(interaction, env);
        return new JsonResponse({
          type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
          data: {
            content: "Creating your alliance!",
          },
        });
      }
      case ADD_PLAYER_COMMAND.name.toLowerCase(): {
        await addPlayer(interaction, env);
        return new JsonResponse({
          type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
          data: {
            content: "Player added!",
          },
        });
      }
      case BOOT_PLAYER_COMMAND.name.toLowerCase(): {
        await bootPlayer(interaction, env);
        return new JsonResponse({
          type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
          data: {
            content: "Player booted!",
          },
        });
      }
      case ONE_ON_ONES_COMMAND.name.toLowerCase(): {
        await create1on1s(interaction, env);
        return new JsonResponse({
          type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
          data: {
            content: "1 on 1s Created!",
          },
        });
      }
      case SWAP_TRIBES_COMMAND.name.toLowerCase(): {
        const newTribes = await swapTribes(interaction, env);
        return new JsonResponse({
          type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
          data: {
            content: `New tribes are: ${newTribes}`,
          },
        });
      }
      case INVITE_COMMAND.name.toLowerCase(): {
        const applicationId = env.DISCORD_APPLICATION_ID;
        const INVITE_URL = `https://discord.com/oauth2/authorize?client_id=${applicationId}&scope=applications.commands`;
        return new JsonResponse({
          type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
          data: {
            content: INVITE_URL,
            flags: InteractionResponseFlags.EPHEMERAL,
          },
        });
      }
      default:
        return new JsonResponse({ error: "Unknown Type" }, { status: 400 });
    }
  }

  console.error("Unknown Type");
  return new JsonResponse({ error: "Unknown Type" }, { status: 400 });
});
router.all("*", () => new Response("Not Found.", { status: 404 }));

async function verifyDiscordRequest(request, env) {
  const signature = request.headers.get("x-signature-ed25519");
  const timestamp = request.headers.get("x-signature-timestamp");
  const body = await request.text();
  const isValidRequest =
    signature &&
    timestamp &&
    (await verifyKey(body, signature, timestamp, env.DISCORD_PUBLIC_KEY));
  if (!isValidRequest) {
    return { isValid: false };
  }

  return { interaction: JSON.parse(body), isValid: true };
}

const server = {
  verifyDiscordRequest,
  fetch: router.fetch,
};

export default server;
