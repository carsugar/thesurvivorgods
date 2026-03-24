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

1. **Run `/setupseason`** — opens a two-step form:
   - **Step 1 – Structure:** name the Host role, Spectator role, Ponderosa channel, Jury Lounge, and Jury Voting channel
   - **Step 2 – Theme:** set the player role name, tribe/merge emojis, and elimination flavor text

   The bot creates everything and wires it all up automatically.

2. **Run `/addplayer`** for each cast member to register them and create their confessional + submissions channels.

3. **Run `/tribesetup`** for each tribe to kick off the game.

---

## Command Reference

### Player Management

| Command | Description |
|---|---|
| `/addplayer @member "First Name"` | Register a player. Creates confessional + submissions channels. |
| `/snufftorch @member premerge` | Eliminate a player to Ponderosa. |
| `/snufftorch @member jury` | Eliminate a player to Jury Lounge. |
| `/listplayers` | Show all players and their tribes/status. |

### Tribe Management

| Command | Description |
|---|---|
| `/tribesetup "Luzon" "@p1 @p2 @p3" red` | Create a tribe with all its channels. |
| `/tribeswap "Angkor,Ta Keo,Bayon"` | Random tribe swap into named tribes. |
| `/tribeswap "Solana,Aparri" manual_assignments:'{"uid1":"Solana","uid2":"Aparri"}'` | Manual tribe swap. |
| `/merge "Solarrion"` | Merge all tribes into one. |
| `/createalliance "The Cobras" "Luzon" @p1 @p2 @p3` | Create an alliance channel within a tribe. Select members via the Discord user picker (3 required, up to 8). |

### Season Lifecycle

| Command | Description |
|---|---|
| `/setupseason` | Start a new season. Opens a form to name all roles and channels — the bot creates everything. Blocks if a season is already active. |
| `/endseason` | End the season — removes all tribe and player roles from members and deletes them. Pass `delete_channels:True` to also delete all season channels and categories. |

### Season Theme (configured in `/setupseason` Step 2)

| Field | Default | What it controls |
|---|---|---|
| Player Role Name | `Player` | Name of the role given to all active players |
| Tribe Emoji | 🏕 | Emoji prefix on tribe categories |
| Merge Emoji | 🏆 | Emoji prefix on the merge category |
| Elimination Title | `The tribe has spoken.` | Title of the elimination announcement embed |
| Elimination Body | `'s torch has been snuffed.` | Text after the player's name on elimination |

All other channel/category labels (alliances, 1:1s, confessionals, etc.) use sensible defaults.

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

When you run `/tribesetup "Luzon" "@p1 @p2 @p3 @p4"` (defaults shown — all emojis and labels are themeable via `/settheme`):

```
🏕 Luzon               (category — tribe role can read)
  └── #luzon-tribe-chat

🤝 Luzon Alliances     (category — hidden by default)
  └── [created by /createalliance]

💬 Luzon 1:1s          (category — hidden by default)
  ├── #alice-bob        (Alice + Bob + Hosts only)
  ├── #alice-charlie    (Alice + Charlie + Hosts only)
  └── ... (every unique pair)

Confessionals          (category — Spectators read-only)
  ├── #alice-confessional
  └── #bob-confessional

Submissions            (category — Hosts only)
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
- Season theme (emojis, labels, flavor text — set via `/settheme`)

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
