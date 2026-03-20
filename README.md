# TheSurvivorGods 🔥

A Discord bot for running Survivor ORGs (Online Reality Games). Handles all the channel plumbing, role management, and game state so hosts can focus on running a great season.

---

## Setup

### 1. Create the Discord Application

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) → **New Application** → name it `TheSurvivorGods`
2. Go to **Bot** → **Add Bot**
3. Enable **Privileged Gateway Intents**: `Server Members Intent` + `Message Content Intent`
4. Copy the **Bot Token** — you'll need it in step 4
5. Go to **OAuth2 → URL Generator** → select `bot` + `applications.commands`, then permissions:
   - Manage Roles, Manage Channels, Read Messages, Send Messages, Manage Messages, Attach Files
   - Copy the generated URL and invite the bot to your server

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set your token

```bash
export DISCORD_TOKEN="your-bot-token-here"
# Windows: set DISCORD_TOKEN=your-bot-token-here
```

### 4. Run

```bash
python bot.py
```

Slash commands sync on startup. They may take a few minutes to appear in Discord globally. For instant testing during development, sync to a specific guild by editing `bot.py` and passing `guild=discord.Object(id=YOUR_GUILD_ID)` to `self.tree.sync()`.

---

## Pre-Season Setup Checklist

Before running `/addplayer`, do this once in your server:

1. **Create roles manually** (or let the bot create them):
   - `Host` — full access to everything
   - `Spectator` — read-only on confessionals, hidden from game channels

2. **Create channels manually**:
   - `#ponderosa` — for premerge boots
   - `#jury-lounge` — for jury members
   - `#jury-voting` — for final jury vote

3. **Run `/setupchannels`** — tells the bot where those channels are:
   ```
   /setupchannels ponderosa:#ponderosa jury_lounge:#jury-lounge jury_voting:#jury-voting host_role:@Host spectator_role:@Spectator season:1
   ```

---

## Command Reference

### Player Management

| Command | Description |
|---|---|
| `/addplayer @member "First Name"` | Register a player. Creates confessional + submissions channels. |
| `/snufftorch @member premerge` | Eliminate a player to Ponderosa. |
| `/snufftorch @member jury` | Eliminate a player to Jury Lounge. |
| `/listplayers` | Show all players and their tribes/status. |
| `/setupchannels` | Point the bot at Ponderosa, Jury Lounge, Jury Voting, Host role, Spectator role. |

### Tribe Management

| Command | Description |
|---|---|
| `/tribesetup "Luzon" "@p1 @p2 @p3" red` | Create a tribe with all its channels. |
| `/tribeswap "Angkor,Ta Keo,Bayon"` | Random tribe swap into named tribes. |
| `/tribeswap "Solana,Aparri" manual_assignments:'{"uid1":"Solana","uid2":"Aparri"}'` | Manual tribe swap. |
| `/merge "Solarrion"` | Merge all tribes into one. |
| `/createalliance "The Cobras" "@p1 @p2 @p3" "Luzon"` | Create an alliance channel within a tribe. |

### Advantage Management

| Command | Description |
|---|---|
| `/giveidol @member` | Give a Hidden Immunity Idol. Player is DMed secretly. |
| `/giveadvantage @member extra_vote` | Give any advantage type. |
| `/playidol KEY` | Play an advantage (player command). |
| `/playidol KEY target:@player` | Play an idol on someone else's behalf. |
| `/transferadvantage KEY @recipient` | Give your advantage to another player. |
| `/listadvantages` | Hosts see all; players see only their own. |
| `/expireadvantage KEY` | Host removes an advantage without it being played. |

---

## How Channels Are Structured

When you run `/tribesetup "Luzon" "@p1 @p2 @p3 @p4"`:

```
S1 🏕 Luzon           (category — tribe role can read)
  └── #luzon-tribe-chat

S1 🤝 Luzon Alliances  (category — hidden by default)
  └── [created by /createalliance]

S1 💬 Luzon 1:1s       (category — hidden by default)
  ├── #alice-bob       (Alice + Bob + Hosts only)
  ├── #alice-charlie   (Alice + Charlie + Hosts only)
  └── ... (every unique pair)

S1 Confessionals       (category — Spectators read-only)
  ├── #alice-confessional
  └── #bob-confessional

S1 Submissions         (category — Hosts only)
  ├── #alice-submissions
  └── #bob-submissions
```

### Tribe Swap
`/tribeswap` **pauses** (makes read-only) all existing tribe chats and 1:1s, then creates new ones for the new tribes. Old channels stay archived but uneditable.

### Merge
`/merge` pauses all tribal channels and creates a full merged-tribe set: one merge chat + every possible 1:1 between remaining players.

### Snuff Torch
`/snufftorch` removes the player from:
- Their tribe role
- Tribe chat permissions
- All 1:1 channels
- All alliance channels

It **preserves** their confessional and submissions channels.

---

## Game State

All state is stored in `data/season_N.json`. You can inspect or edit this file directly if you need to fix something manually — just restart the bot after editing.

The file stores:
- All registered players (username, display name, tribe, status, channel IDs, advantages held)
- All tribes (role IDs, category IDs, channel IDs, member lists)
- All advantages (type, holder, expiry, played status)
- Jury and boot order
- Pointers to Ponderosa/Jury/host/spectator IDs

---

## Roadmap

**Next up (V2):**
- Voting system — `/openvoting`, `/vote`, `/closevoting` with anonymous tallies
- Challenge hosting — timed submission windows, automatic scoring
- Idol hunt system — clues hidden in channels, bot tracks finds
- Bootlist game for spectators
- Season statistics dashboard
- Multi-season stats tracking per player

---

## Notes for Hosts

- **Advantage keys** are 8-character codes (e.g. `A3F7B2C1`). The player gets their key via DM. Hosts see all keys in `/listadvantages`.
- **Cross-tribe communication** is prevented by permission structure — players only have access to their own tribe's channels.
- **The bot never deletes channels** — it only modifies permissions. This means you have a full archive of the season after it ends.
- If a channel gets out of sync, you can re-run `/tribesetup` — it will skip channels that already exist.
