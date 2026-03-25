import { SlashCommandBuilder, ChatInputCommandInteraction } from "discord.js";
import { chat, clearHistory } from "../services/claude";

export const chatCommand = new SlashCommandBuilder()
  .setName("chat")
  .setDescription("AIとチャットする")
  .addStringOption((option) =>
    option.setName("message").setDescription("AIに送るメッセージ").setRequired(true)
  );

export const clearCommand = new SlashCommandBuilder()
  .setName("clear")
  .setDescription("このチャンネルの会話履歴をリセットする");

export async function handleChat(interaction: ChatInputCommandInteraction): Promise<void> {
  const message = interaction.options.getString("message", true);

  await interaction.deferReply();

  try {
    const response = await chat(interaction.channelId, message);

    if (response.length > 2000) {
      const chunks = response.match(/.{1,2000}/gs) ?? [];
      if (chunks.length > 0) {
        await interaction.editReply(chunks[0]!);
        for (let i = 1; i < chunks.length; i++) {
          await interaction.followUp(chunks[i]!);
        }
      }
    } else {
      await interaction.editReply(response);
    }
  } catch (error) {
    console.error("Claude API error:", error);
    await interaction.editReply("エラーが発生しました。しばらくしてからもう一度お試しください。");
  }
}

export async function handleClear(interaction: ChatInputCommandInteraction): Promise<void> {
  clearHistory(interaction.channelId);
  await interaction.reply("会話履歴をリセットしました。");
}
