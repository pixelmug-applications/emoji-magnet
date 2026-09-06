import { BubbleBot, InlineKeyboard, isNeedBindDeviceError } from "../../jeejio-bubble/sdk/BubbleSDK.js";
import PixelMugS1 from "../../jeejio-bubble/devices/ext/PixelMugS1_1.0.ext.js";
import { apiBaseUrl, token, mpsID, mpsVersion } from "./config.dev.js";


const CALLBACK_OPEN = "emoji-magnet:open";
const CALLBACK_SOUND_ON = "emoji-magnet:sound:on";
const CALLBACK_SOUND_OFF = "emoji-magnet:sound:off";
const READY_EVENT = "MPS_IS_RUNNING";
const FAILED_EVENTS = new Set(["INSTALL_FAIL", "RUNNING_FAIL"]);
const OPEN_TIMEOUT_MS = Number(process.env.MPS_OPEN_TIMEOUT_MS || 45000);
const mpsLaunchConfig = { id: mpsID, version: mpsVersion };
const pendingLaunches = new Map();

if (!token) throw new Error("Missing BUBBLE_BOT_TOKEN.");
if (!mpsID || !mpsVersion) throw new Error("Missing MPS_ID or MPS_VERSION.");

const pixelMug = new PixelMugS1();
const bot = new BubbleBot(token, {
  apiBaseUrl,
  debug: process.env.DEBUG !== "false",
  observeWebAppDeviceCalls: false,
  webAppDeviceAccess: "none",
});

bot.registerDevices([pixelMug]);

bot.on("error", async (ctx) => {
  console.error("[emoji-magnet-bot]", ctx.error || ctx);
});

bot.on("contact_added", async (ctx) => {
  await sendIntroduction(ctx);
});

bot.on("joined_group", async (ctx) => {
  await sendIntroduction(ctx, { mentionOnly: false });
});

bot.on("message", async (ctx) => {
  const parsed = parseCommand(messageText(ctx));
  if (!parsed) {
    await sendHelp(ctx);
    return;
  }

  if (parsed.command === "/bindPixelMug") {
    await sendBindDevice(ctx);
    return;
  }

  if (parsed.command === "/startEmojiMagnet") {
    const keyboard = new InlineKeyboard().text("Open on PixelMug", CALLBACK_OPEN);
    await ctx.sendKeyboard(startMarkdown(), keyboard, mentionOptions(ctx));
    return;
  }

  if (parsed.command === "/SoundEffect") {
    const value = normalizeSwitch(parsed.args[0]);
    if (value === null) await sendSoundEffectKeyboard(ctx);
    else await configureSoundEffect(ctx, value);
    return;
  }


  if (parsed.command === "/License") {
    await ctx.sendMarkdown(licenseMarkdown(), mentionOptions(ctx));
    return;
  }

  await sendHelp(ctx);
});

bot.on("callback", async (ctx) => {
  const value = extractCallbackValue(ctx.callback?.value);
  if (value === CALLBACK_OPEN) await openOnPixelMug(ctx);
  else if (value === CALLBACK_SOUND_ON) await configureSoundEffect(ctx, true);
  else if (value === CALLBACK_SOUND_OFF) await configureSoundEffect(ctx, false);
});

bot.on("device_notify", async (ctx) => {
  const events = pixelMug.parseNotify(ctx.tal?.notify || []);
  const key = deviceKeyFromNotify(ctx);
  for (const event of events) {
    const pending = key ? pendingLaunches.get(key) : firstPendingLaunch();
    if (!pending) continue;

    if (event.name === "mpyVmError") {
      finishPendingLaunch(pending);
      await pending.ctx.sendText(`Emoji Magnet install failed: ${event.params?.value || "unknown error"}`);
      continue;
    }

    if (event.name !== "mpyVmEvent") continue;
    const value = String(event.params?.value || "");
    if (value === READY_EVENT) {
      finishPendingLaunch(pending);
      await pending.ctx.sendText("Emoji Magnet is running on your PixelMug. ✨");
    } else if (FAILED_EVENTS.has(value)) {
      finishPendingLaunch(pending);
      await pending.ctx.sendText(`Emoji Magnet failed to start: ${value}`);
    }
  }
});

await bot.setCommands([
  { command: "bindPixelMug", description: "Bind PixelMug" },
  { command: "startEmojiMagnet", description: "Open Emoji Magnet" },
  { command: "SoundEffect", description: "Configure sound effects" },
  { command: "License", description: "Show artwork licenses" },
]);

await bot.start({ device: true });

console.log("mps-emoji-magnet bot is running.");
console.log(`MPS launch config: ${mpsLaunchConfig.id}@${mpsLaunchConfig.version}`);


async function openOnPixelMug(ctx) {
  await ctx.sendText("Opening Emoji Magnet on your PixelMug... ✨");
  try {
    const responseCtx = await bot.callDevice(
      ctx.chat,
      pixelMug,
      pixelMug.rpc.talMpyExecOneScript(mpsLaunchConfig),
    );
    const code = mpyExecReturnCode(responseCtx.tal?.result);
    if (code === 264) {
      await ctx.sendText("Emoji Magnet is already running on your PixelMug.");
      return;
    }
    if (![260, 261, 262, 263, 265].includes(code)) {
      await ctx.sendText(`Could not open Emoji Magnet. Device returned code ${code || "unknown"}.`);
      return;
    }
    waitForMpsRunning(ctx, deviceKeyFromResponse(responseCtx));
  } catch (error) {
    if (isNeedBindDeviceError(error)) {
      await sendBindDevice(ctx);
      return;
    }
    await ctx.sendText(`Could not open Emoji Magnet: ${errorMessage(error)}`);
    console.error("[emoji-magnet-bot] launch failed", error);
  }
}

async function configureSoundEffect(ctx, enabled) {
  const message = JSON.stringify({
    type: "emoji-magnet",
    command: "config",
    soundEffect: Boolean(enabled),
  });
  try {
    const responseCtx = await bot.callDevice(
      ctx.chat,
      pixelMug,
      pixelMug.rpc.pushMessage({ message }),
    );
    const result = responseCtx.tal?.result;
    if (result === false || result?.return === false) {
      await ctx.sendText("PixelMug rejected the setting. Start Emoji Magnet first, then try again.");
      return;
    }
    await ctx.sendText(`Emoji Magnet sound effects are now ${enabled ? "on" : "off"}.`);
  } catch (error) {
    if (isNeedBindDeviceError(error)) {
      await sendBindDevice(ctx);
      return;
    }
    await ctx.sendText(`Could not configure sound effects: ${errorMessage(error)}`);
    console.error("[emoji-magnet-bot] sound config failed", error);
  }
}

async function sendSoundEffectKeyboard(ctx) {
  const keyboard = new InlineKeyboard()
    .text("Sound On", CALLBACK_SOUND_ON)
    .text("Sound Off", CALLBACK_SOUND_OFF);
  await ctx.sendKeyboard("Choose the Emoji Magnet sound-effect setting.", keyboard, mentionOptions(ctx));
}

function sendIntroduction(ctx, options = {}) {
  return ctx.sendBindDevice({
    content: "Emoji Magnet turns a 9×9 emoji into colorful particles when you shake your PixelMug, then magnetically assembles a new emoji when the mug becomes still. Bind your PixelMug to begin.",
    actionButtonTitle: "Bind PixelMug",
    ...options,
  });
}

function sendBindDevice(ctx) {
  return ctx.sendBindDevice({
    content: "Bind a PixelMug to use Emoji Magnet.",
    actionButtonTitle: "Bind PixelMug",
  });
}

function sendHelp(ctx) {
  return ctx.sendMarkdown([
    "# Emoji Magnet",
    "",
    "- `/bindPixelMug` — bind your device",
    "- `/startEmojiMagnet` — install and open the app",
    "- `/SoundEffect` — turn sound effects on or off",
    "- `/License` — show artwork licenses",
  ].join("\n"), mentionOptions(ctx));
}

function startMarkdown() {
  return [
    "# Emoji Magnet",
    "",
    "Discover **3,584** hand-pixelled 9×9 emoji, derived from [PixelTwemojiMC-9](https://github.com/AmberWat/PixelTwemojiMC-9) and Twemoji.",
    "",
    "Shake your PixelMug to scatter an emoji into particles. Put it down and they magnetically assemble into a new one.",
    "",
    "Found a favorite? While it is still on screen, tap the touch button once to lock it. Tap again to unlock and continue exploring.",
    "",
    "Tap **Open on PixelMug** to install and start it.",
  ].join("\n");
}

function licenseMarkdown() {
  return [
    "📜 **Emoji Magnet — Artwork License**",
    "",
    "Emoji artwork is derived from [PixelTwemojiMC-9](https://github.com/AmberWat/PixelTwemojiMC-9) by Amber.",
    "",
    "Original graphics are based on Twemoji © 2018 Twitter, Inc. and contributors. Pixel-art and resource-pack adaptation © 2020 Amber.",
    "",
    "Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).",
    "",
    "Emoji Magnet modifies the source artwork by extracting 9×9 emoji, splitting it into pages, and mapping it to the app palette.",
  ].join("\n");
}

function waitForMpsRunning(ctx, deviceKey) {
  const key = deviceKey || chatKey(ctx.chat);
  clearPendingLaunch(key);
  const pending = {
    key,
    ctx,
    timer: setTimeout(async () => {
      pendingLaunches.delete(key);
      await ctx.sendText("Still waiting for Emoji Magnet to report ready on your PixelMug...");
    }, OPEN_TIMEOUT_MS),
  };
  if (typeof pending.timer.unref === "function") pending.timer.unref();
  pendingLaunches.set(key, pending);
}

function finishPendingLaunch(pending) {
  clearTimeout(pending.timer);
  pendingLaunches.delete(pending.key);
}

function clearPendingLaunch(key) {
  const pending = pendingLaunches.get(key);
  if (pending) finishPendingLaunch(pending);
}

function firstPendingLaunch() {
  return pendingLaunches.values().next().value;
}

function parseCommand(text) {
  const match = String(text || "").trim().match(/^\/(\w[\w-]*)(?:@[\w-]+)?(?:\s+(.*))?$/);
  if (!match) return null;
  const known = {
    bindpixelmug: "/bindPixelMug",
    startemojimagnet: "/startEmojiMagnet",
    soundeffect: "/SoundEffect",
    license: "/License",
  };
  const command = known[match[1].toLowerCase()] || `/${match[1]}`;
  const args = String(match[2] || "").trim().split(/\s+/).filter(Boolean);
  return { command, args };
}

function normalizeSwitch(value) {
  const normalized = String(value || "").toLowerCase();
  if (["on", "enable", "enabled", "1", "true"].includes(normalized)) return true;
  if (["off", "disable", "disabled", "0", "false"].includes(normalized)) return false;
  return null;
}

function messageText(ctx) {
  return ctx.message?.content ?? ctx.message?.text ?? "";
}

function mentionOptions(ctx) {
  return { mentionOnly: ctx.chat?.type === "group" ? true : undefined };
}

function extractCallbackValue(value) {
  if (typeof value === "string") return value;
  return value?.value || value?.data || "";
}

function mpyExecReturnCode(response) {
  if (typeof response === "number" || typeof response === "string") {
    const direct = Number(response);
    if (Number.isFinite(direct)) return direct;
  }
  const data = response || {};
  const result = data.result;
  const value = typeof result === "object" && result !== null
    ? result.value ?? result.return
    : result ?? data.value ?? data.return;
  const code = Number(value);
  return Number.isFinite(code) ? code : Number(data.code);
}

function deviceKeyFromResponse(ctx) {
  return String(ctx.from?.id || ctx.webAppDeviceCall?.deviceId || ctx.tal?.response?.from || "");
}

function deviceKeyFromNotify(ctx) {
  return String(ctx.from?.id || "");
}

function chatKey(chat) {
  return `${chat?.type || "chat"}:${chat?.id || chat?.name || ""}`;
}

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error || "Unknown error");
}
