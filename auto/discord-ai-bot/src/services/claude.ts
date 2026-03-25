import Anthropic from "@anthropic-ai/sdk";
import { config } from "../config";

const client = new Anthropic({ apiKey: config.anthropicApiKey });

interface Message {
  role: "user" | "assistant";
  content: string;
}

const conversationHistory = new Map<string, Message[]>();
const MAX_HISTORY = 20;

function getHistory(channelId: string): Message[] {
  if (!conversationHistory.has(channelId)) {
    conversationHistory.set(channelId, []);
  }
  return conversationHistory.get(channelId)!;
}

export async function chat(channelId: string, userMessage: string): Promise<string> {
  const history = getHistory(channelId);

  history.push({ role: "user", content: userMessage });

  if (history.length > MAX_HISTORY) {
    history.splice(0, history.length - MAX_HISTORY);
  }

  const response = await client.messages.create({
    model: "claude-sonnet-4-20250514",
    max_tokens: 1024,
    system: "あなたはDiscordサーバーのフレンドリーなAIアシスタントです。簡潔で親しみやすい日本語で応答してください。",
    messages: history,
  });

  const assistantMessage =
    response.content[0].type === "text" ? response.content[0].text : "応答を生成できませんでした。";

  history.push({ role: "assistant", content: assistantMessage });

  return assistantMessage;
}

export function clearHistory(channelId: string): void {
  conversationHistory.delete(channelId);
}
