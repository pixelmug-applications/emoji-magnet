import { BubbleBot, InlineKeyboard, isNeedBindDeviceError } from "@jeejio-bubble/bot/sdk";
import PixelMugS1 from "@jeejio-bubble/bot/devices/pixelmug-s1/ext";

const messages = {
  "zh-CN": {
    bindContent: "请先绑定 PixelMug 以使用 Emoji Magnet。",
    bindButton: "绑定 PixelMug",
    addedIntro: "你好，我是磁吸表情应用智能体。摇晃 PixelMug，Emoji Magnet 会将 9×9 表情变成彩色粒子；静止后，粒子会磁吸重组成新的表情。绑定 PixelMug 即可开始。",
    openButton: "在 PixelMug 上打开",
    intro: "# Emoji Magnet / 表情包磁贴\n\n探索 **3,584** 个手工像素化的 9×9 表情，资源改编自 [PixelTwemojiMC-9](https://github.com/AmberWat/PixelTwemojiMC-9) 和 Twemoji。\n\n摇晃 PixelMug，让表情散成粒子；放稳后，它们会磁吸组成新的表情。\n\n喜欢当前表情？在画面静止时单击触摸键即可锁定；再次单击解锁，继续探索。\n\n点击 **在 PixelMug 上打开** 即可安装并启动。",
    help: "# Emoji Magnet / 表情包磁贴\n\n- `/bindPixelMug` — 绑定设备\n- `/startEmojiMagnet` — 安装并打开应用\n- `/SoundEffect` — 开启或关闭音效\n- `/License` — show artwork licenses",
    commandBind: "绑定 PixelMug",
    commandStart: "打开表情包磁贴",
    commandSound: "设置音效",
    opening: "正在 PixelMug 上打开 Emoji Magnet… ✨",
    running: "Emoji Magnet 已在你的 PixelMug 上运行。 ✨",
    alreadyRunning: "Emoji Magnet 已在你的 PixelMug 上运行。",
    installFailed: "Emoji Magnet 安装失败",
    startFailed: "Emoji Magnet 启动失败",
    cannotOpen: "无法打开 Emoji Magnet",
    rejectedSetting: "PixelMug 未接受此设置。请先启动 Emoji Magnet 后重试。",
    soundOn: "Emoji Magnet 音效现已开启。",
    soundOff: "Emoji Magnet 音效现已关闭。",
    cannotConfigureSound: "无法设置音效",
    soundPrompt: "选择 Emoji Magnet 的音效设置。",
    soundOnButton: "开启音效",
    soundOffButton: "关闭音效",
    waitingReady: "仍在等待 PixelMug 报告 Emoji Magnet 已就绪…",
  },
  "en-US": {
    bindContent: "Bind a PixelMug to use Emoji Magnet.",
    bindButton: "Bind PixelMug",
    addedIntro: "Hi, I am Emoji Magnet. Shake your PixelMug to turn a 9×9 emoji into colorful particles. When the mug becomes still, they magnetically assemble into a new emoji. Bind your PixelMug to begin.",
    openButton: "Open on PixelMug",
    intro: "# Emoji Magnet\n\nDiscover **3,584** hand-pixelled 9×9 emoji, derived from [PixelTwemojiMC-9](https://github.com/AmberWat/PixelTwemojiMC-9) and Twemoji.\n\nShake your PixelMug to scatter an emoji into particles. Put it down and they magnetically assemble into a new one.\n\nFound a favorite? While it is still on screen, tap the touch button once to lock it. Tap again to unlock and continue exploring.\n\nTap **Open on PixelMug** to install and start it.",
    help: "# Emoji Magnet\n\n- `/bindPixelMug` — bind your device\n- `/startEmojiMagnet` — install and open the app\n- `/SoundEffect` — turn sound effects on or off\n- `/License` — show artwork licenses",
    commandBind: "Bind PixelMug",
    commandStart: "Open Emoji Magnet",
    commandSound: "Configure sound effects",
    opening: "Opening Emoji Magnet on your PixelMug… ✨",
    running: "Emoji Magnet is running on your PixelMug. ✨",
    alreadyRunning: "Emoji Magnet is already running on your PixelMug.",
    installFailed: "Emoji Magnet installation failed",
    startFailed: "Emoji Magnet failed to start",
    cannotOpen: "Could not open Emoji Magnet",
    rejectedSetting: "PixelMug rejected the setting. Start Emoji Magnet first, then try again.",
    soundOn: "Emoji Magnet sound effects are now on.",
    soundOff: "Emoji Magnet sound effects are now off.",
    cannotConfigureSound: "Could not configure sound effects",
    soundPrompt: "Choose the Emoji Magnet sound-effect setting.",
    soundOnButton: "Sound On",
    soundOffButton: "Sound Off",
    waitingReady: "Still waiting for Emoji Magnet to report ready on your PixelMug…",
  },
};

const CALLBACK_OPEN = "emoji-magnet:open";
const CALLBACK_SOUND_ON = "emoji-magnet:sound:on";
const CALLBACK_SOUND_OFF = "emoji-magnet:sound:off";
const READY_EVENT = "MPS_IS_RUNNING";
const FAILED_EVENTS = new Set(["INSTALL_FAIL", "RUNNING_FAIL"]);
const OPEN_TIMEOUT_MS = Number(process.env.MPS_OPEN_TIMEOUT_MS || 45000);
const mpsLaunchConfig = {
  id: requiredEnv("STUDIO_MPS_ID"),
  version: requiredEnv("STUDIO_MPS_VERSION"),
};
const pendingLaunches = new Map();

const pixelMug = new PixelMugS1();
const bot = new BubbleBot(requiredEnv("BOT_TOKEN"), {
  apiBaseUrl: process.env.BOT_API_BASE_URL,
  observeWebAppDeviceCalls: false,
  webAppDeviceAccess: "none",
});

bot.registerDevices([pixelMug]);
bot.on("error", async (ctx) => console.error("[emoji-magnet-bot]", ctx.error || ctx));
bot.on("contact_added", async (ctx) => sendIntroduction(ctx));
bot.on("joined_group", async (ctx) => sendIntroduction(ctx, { mentionOnly: false }));

bot.on("message", async (ctx) => {
  const language = localeFromContext(ctx);
  const parsed = parseCommand(messageText(ctx));
  if (!parsed) return sendHelp(ctx, language);

  if (parsed.command === "/bindPixelMug") return sendBindDevice(ctx, language);
  if (parsed.command === "/startEmojiMagnet") {
    const keyboard = new InlineKeyboard().text(text(language, "openButton"), CALLBACK_OPEN);
    return ctx.sendKeyboard(text(language, "intro"), keyboard, mentionOptions(ctx));
  }
  if (parsed.command === "/SoundEffect") {
    const value = normalizeSwitch(parsed.args[0]);
    if (value === null) return sendSoundEffectKeyboard(ctx, language);
    return configureSoundEffect(ctx, value, language);
  }
  if (parsed.command === "/License") return ctx.sendMarkdown(licenseMarkdown(), mentionOptions(ctx));
  return sendHelp(ctx, language);
});

bot.on("callback", async (ctx) => {
  const value = extractCallbackValue(ctx.callback?.value);
  const language = localeFromContext(ctx);
  if (value === CALLBACK_OPEN) await openOnPixelMug(ctx, language);
  else if (value === CALLBACK_SOUND_ON) await configureSoundEffect(ctx, true, language);
  else if (value === CALLBACK_SOUND_OFF) await configureSoundEffect(ctx, false, language);
});

bot.on("device_notify", async (ctx) => {
  const events = pixelMug.parseNotify(ctx.tal?.notify || []);
  const key = deviceKeyFromNotify(ctx);
  for (const event of events) {
    const pending = key ? pendingLaunches.get(key) : firstPendingLaunch();
    if (!pending) continue;
    const language = localeFromContext(pending.ctx);

    if (event.name === "mpyVmError") {
      finishPendingLaunch(pending);
      await pending.ctx.sendText(`${text(language, "installFailed")}: ${event.params?.value || "unknown error"}`);
      continue;
    }
    if (event.name !== "mpyVmEvent") continue;
    const value = String(event.params?.value || "");
    if (value === READY_EVENT) {
      finishPendingLaunch(pending);
      await pending.ctx.sendText(text(language, "running"));
    } else if (FAILED_EVENTS.has(value)) {
      finishPendingLaunch(pending);
      await pending.ctx.sendText(`${text(language, "startFailed")}: ${value}`);
    }
  }
});

await bot.setCommands([
  commandDefinition("bindPixelMug", "commandBind"),
  commandDefinition("startEmojiMagnet", "commandStart"),
  commandDefinition("SoundEffect", "commandSound"),
  { command: "License", description: "Show artwork licenses" },
]);
await bot.start({ device: true });
console.log("mps-emoji-magnet bot is running.");
console.log(`MPS launch config: ${mpsLaunchConfig.id}@${mpsLaunchConfig.version}`);

async function openOnPixelMug(ctx, language = localeFromContext(ctx)) {
  await ctx.sendText(text(language, "opening"));
  try {
    const responseCtx = await bot.callDevice(ctx.chat, pixelMug, pixelMug.rpc.talMpyExecOneScript(mpsLaunchConfig));
    const code = mpyExecReturnCode(responseCtx.tal?.result);
    if (code === 264) return ctx.sendText(text(language, "alreadyRunning"));
    if (![260, 261, 262, 263, 265].includes(code)) {
      return ctx.sendText(`${text(language, "cannotOpen")}. ${language === "zh-CN" ? "设备返回代码" : "Device returned code"} ${code || "unknown"}.`);
    }
    waitForMpsRunning(ctx, deviceKeyFromResponse(responseCtx), language);
  } catch (error) {
    if (isNeedBindDeviceError(error)) return sendBindDevice(ctx, language);
    await ctx.sendText(`${text(language, "cannotOpen")}: ${errorMessage(error)}`);
    console.error("[emoji-magnet-bot] launch failed", error);
  }
}

async function configureSoundEffect(ctx, enabled, language = localeFromContext(ctx)) {
  const message = JSON.stringify({ type: "emoji-magnet", command: "config", soundEffect: Boolean(enabled) });
  try {
    const responseCtx = await bot.callDevice(ctx.chat, pixelMug, pixelMug.rpc.pushMessage({ message }));
    const result = responseCtx.tal?.result;
    if (result === false || result?.return === false) return ctx.sendText(text(language, "rejectedSetting"));
    await ctx.sendText(text(language, enabled ? "soundOn" : "soundOff"));
  } catch (error) {
    if (isNeedBindDeviceError(error)) return sendBindDevice(ctx, language);
    await ctx.sendText(`${text(language, "cannotConfigureSound")}: ${errorMessage(error)}`);
    console.error("[emoji-magnet-bot] sound config failed", error);
  }
}

function sendSoundEffectKeyboard(ctx, language = localeFromContext(ctx)) {
  const keyboard = new InlineKeyboard()
    .text(text(language, "soundOnButton"), CALLBACK_SOUND_ON)
    .text(text(language, "soundOffButton"), CALLBACK_SOUND_OFF);
  return ctx.sendKeyboard(text(language, "soundPrompt"), keyboard, mentionOptions(ctx));
}

function sendIntroduction(ctx, options = {}) {
  const language = localeFromContext(ctx);
  return ctx.sendBindDevice({ content: text(language, "addedIntro"), actionButtonTitle: text(language, "bindButton"), ...options });
}

function sendBindDevice(ctx, language = localeFromContext(ctx)) {
  return ctx.sendBindDevice({ content: text(language, "bindContent"), actionButtonTitle: text(language, "bindButton") });
}

function sendHelp(ctx, language = localeFromContext(ctx)) {
  return ctx.sendMarkdown(text(language, "help"), mentionOptions(ctx));
}

function licenseMarkdown() {
  return [
    "# Emoji Magnet — Artwork License",
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

function waitForMpsRunning(ctx, deviceKey, language = localeFromContext(ctx)) {
  const key = deviceKey || chatKey(ctx.chat);
  clearPendingLaunch(key);
  const pending = {
    key,
    ctx,
    timer: setTimeout(async () => {
      pendingLaunches.delete(key);
      await ctx.sendText(text(language, "waitingReady"));
    }, OPEN_TIMEOUT_MS),
  };
  if (typeof pending.timer.unref === "function") pending.timer.unref();
  pendingLaunches.set(key, pending);
}

function commandDefinition(command, key) {
  return {
    command,
    description: text("en-US", key),
    descTranslations: { "zh-CN": text("zh-CN", key), en: text("en-US", key) },
  };
}

function localeFromContext(ctx) {
  const source = String(ctx.chat?.language || ctx.from?.language || process.env.APP_LOCALE || "").toLowerCase();
  return source.startsWith("zh") ? "zh-CN" : "en-US";
}

function text(language, key) {
  return messages[language]?.[key] || messages["en-US"][key] || key;
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

function parseCommand(value) {
  const match = String(value || "").trim().match(/^\/(\w[\w-]*)(?:@[\w-]+)?(?:\s+(.*))?$/);
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

function requiredEnv(name) {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
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
