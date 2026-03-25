import {
  Client,
  GatewayIntentBits,
  REST,
  Routes,
  Events,
  ChatInputCommandInteraction,
} from "discord.js";
import { config } from "./config";
import { chatCommand, clearCommand, handleChat, handleClear } from "./commands/chat";
import { chat } from "./services/claude";

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
  ],
});

// Register slash commands
async function registerCommands(): Promise<void> {
  const rest = new REST().setToken(config.discordToken);
  const commands = [chatCommand.toJSON(), clearCommand.toJSON()];

  console.log("スラッシュコマンドを登録中...");
  await rest.put(Routes.applicationCommands(config.discordClientId), { body: commands });
  console.log("スラッシュコマンドの登録完了");
}

// Handle slash commands
client.on(Events.InteractionCreate, async (interaction) => {
  if (!interaction.isChatInputCommand()) return;

  const command = interaction as ChatInputCommandInteraction;

  switch (command.commandName) {
    case "chat":
      await handleChat(command);
      break;
    case "clear":
      await handleClear(command);
      break;
  }
});

// Handle mentions
client.on(Events.MessageCreate, async (message) => {
  if (message.author.bot) return;
  if (!client.user || !message.mentions.has(client.user)) return;

  const content = message.content.replace(/<@!?\d+>/g, "").trim();
  if (!content) {
    await message.reply("何か話しかけてください！");
    return;
  }

  try {
    await message.channel.sendTyping();
    const response = await chat(message.channelId, content);

    if (response.length > 2000) {
      const chunks = response.match(/.{1,2000}/gs) ?? [];
      if (chunks.length > 0) {
        await message.reply(chunks[0]!);
        for (let i = 1; i < chunks.length; i++) {
          await message.channel.send(chunks[i]!);
        }
      }
    } else {
      await message.reply(response);
    }
  } catch (error) {
    console.error("Claude API error:", error);
    await message.reply("エラーが発生しました。しばらくしてからもう一度お試しください。");
  }
});

// Start
client.once(Events.ClientReady, (c) => {
  console.log(`${c.user.tag} としてログインしました`);
});

async function main(): Promise<void> {
  await registerCommands();
  await client.login(config.discordToken);
}

main().catch(console.error);
