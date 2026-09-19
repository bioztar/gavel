# Setting up the Discord app and inviting Karen

Karen reaches Discord through one bot, run by `ears-discord`. This page covers creating
that bot, putting its token where ears reads it, and handing out the link people use to
add Karen to their own servers.

## 1. Create the application

1. Open the [Discord Developer Portal](https://discord.com/developers/applications) and
   sign in with the account that should own the bot.
2. **New Application** → name it (the name is what people see in the invite dialog,
   e.g. `Karen`) → accept the terms → **Create**.
3. **General Information** → set an app icon and a description. Both show up on the
   invite screen. Copy the **Application ID**. You need it for the invite link. It is
   not a secret.

## 2. Configure the bot

**Bot** tab:

| Setting | Value | Why |
|---|---|---|
| Username / avatar | Karen | What people see in the voice channel |
| **Public Bot** | **on** to let anyone with the link add it; **off** to keep it to servers you manage | Off hides the bot from everyone except the app owner/team |
| Requires OAuth2 Code Grant | **off** | On breaks the plain invite link |
| Presence Intent | off | not used |
| Server Members Intent | off | not used |
| Message Content Intent | off | not used |

ears asks only for the `Guilds` and `Guild Voice States` intents
(`packages/ears-discord/src/ears/voice.py`). Neither is privileged, so none of the three
toggles above needs to be on.

### Token

**Bot** → **Reset Token** → copy it once and put it in the repo-root `.env`:

```
DISCORD_EARS_TOKEN=<token>
```

> **The token is a password.** Anyone who has it can run the bot as Karen in every
> server it is in. Keep it in `.env` (gitignored). Never put it in a tracked file, an
> issue, or a chat message. If it leaks, **Reset Token** here makes the old one stop
> working right away. Then update `.env` and restart ears.

Use one token per running process. If the Concierge is revived, it gets its own
application and `DISCORD_CONCIERGE_TOKEN`.

## 3. Permissions

The bot needs these permissions in the meeting channel:

| Permission | Bit | Needed for |
|---|---|---|
| View Channel | `1 << 10` | seeing the voice channel at all |
| Connect | `1 << 20` | joining it |
| Speak | `1 << 21` | the chair's voice |
| Use Voice Activity | `1 << 25` | speaking without push-to-talk |
| Mute Members | `1 << 22` | the brain's `mute` / `unmute` |
| Priority Speaker | `1 << 8` | `priority: true` lines ducking the room |

Together these make **`40895744`**. Without Mute Members and Priority Speaker
(**`36701184`**), Karen still listens and talks, but `mute` comes back `failed` and
priority lines don't duck the room.

## 4. The invite link

You can build it by hand or have the portal generate it. Either way it must include the
**`bot`** scope. A link with only `applications.commands` adds the app, but no bot
user joins the server, so ears never sees that server.

### Option A: build it

```
https://discord.com/oauth2/authorize?client_id=1550818383845400670&scope=bot&permissions=40895744
```

Optional query parameters:

- `&guild_id=<SERVER_ID>` preselects a server in the dropdown.
- `&guild_id=<SERVER_ID>&disable_guild_select=true` locks the link to that one server.
  This is useful when you send a link to a specific team.

### Option B: let the portal generate it

**Installation** tab:

1. **Installation Contexts**: tick **Guild Install**, untick **User Install**. Karen
   only works as a server member.
2. **Install Link**: choose **Discord Provided Link**.
3. **Default Install Settings → Guild Install**: scopes `bot` (and
   `applications.commands` if you like), then tick the six permissions from §3.
4. **Save Changes** and copy the link. It has the form
   `https://discord.com/oauth2/authorize?client_id=1550818383845400670`, and Discord fills in the
   scopes and permissions from these defaults.

Option B gives a short link, and the portal also shows **Add App** on the bot's profile.
If you change the permissions later, update them there and the same link picks them up.

The **OAuth2 → URL Generator** tab also works: tick `bot`, tick the permissions, and copy
the URL at the bottom. It produces the same thing as Option A.

## 5. Sharing the link

Send the link to whoever runs the target server. When they open it, they:

1. Pick a server from the dropdown. Only servers where they have **Manage Server**
   appear. If a server is missing, they need that permission or someone who has it.
2. Review the permissions, then click **Authorize** and complete the captcha.

Karen then shows up in the member list with a role named after the bot. That role
carries the permissions from the link.

Things that commonly go wrong after the invite:

- **Private meeting channel.** Channel overrides beat the role. If the voice channel
  hides itself from `@everyone`, give the Karen role (or the bot) View Channel,
  Connect and Speak on that channel.
- **Someone unticked permissions** in the invite dialog. Fix it in *Server Settings →
  Roles → Karen*, or kick the bot and invite it again with the full link.
- **The bot joins but no one hears it.** Check that Speak and Use Voice Activity aren't
  denied on the channel or its category.

Unverified bots can join up to **100 servers**. Beyond that, Discord requires app
verification (Developer Portal → **App Verification**).

## 6. Pick the meeting channel

Adding the bot does not make it join anything. With ears running:

1. Open the console at `http://127.0.0.1:8787/console` → **Discord servers**. A newly
   added server appears there without a restart (`discord.guild_joined` in the log).
2. Choose one meeting voice channel for that server. The choice is saved in Postgres.
3. Karen joins when a person enters that channel. She leaves
   `DISCORD_LEAVE_GRACE_SECONDS` (default 10) after the last person goes.

ears holds **one voice connection at a time**. If meeting channels in two servers are
occupied at once, Karen stays in whichever one she joined first.

The old `DISCORD_GUILD_ID` + `DISCORD_VOICE_CHANNEL_ID` pair in `.env` still works as a
seed for a single server, but the console is the normal way to choose the channel.

## Removing Karen from a server

A server admin can kick the bot from the member list. Or, as the app owner, reset the
token to cut off every server at once.
