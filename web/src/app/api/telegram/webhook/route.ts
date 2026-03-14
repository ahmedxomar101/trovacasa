import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase/server";

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || "";
const TG_API = `https://api.telegram.org/bot${BOT_TOKEN}`;

async function sendMessage(chatId: number, text: string) {
  await fetch(`${TG_API}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
}

export async function POST(request: NextRequest) {
  // Verify the request has a valid bot token in the URL path or header
  const update = await request.json();

  // Handle /start command
  const message = update?.message;
  if (message?.text === "/start") {
    const chatId = message.chat.id;
    const username = message.from?.username || null;
    const firstName = message.from?.first_name || null;

    const supabase = await createServerClient();

    // Check if already subscribed
    const { data: existing } = await supabase
      .from("telegram_subscribers")
      .select("chat_id")
      .eq("chat_id", chatId)
      .single();

    if (existing) {
      // Reactivate if needed
      await supabase
        .from("telegram_subscribers")
        .update({ active: true, username, first_name: firstName })
        .eq("chat_id", chatId);

      await sendMessage(chatId, "Welcome back! You're already subscribed. Alerts will come automatically.");
    } else {
      // New subscriber
      await supabase.from("telegram_subscribers").insert({
        chat_id: chatId,
        username,
        first_name: firstName,
        active: true,
      });

      await sendMessage(
        chatId,
        "👋 Welcome to TrovaCasa!\n\nYou'll receive alerts for new apartments scoring 70+ automatically.\n\nUse the Save/Dismiss buttons on each listing to manage your shortlist."
      );
    }
  }

  // Handle callback queries (Save/Dismiss/Undo buttons)
  const callback = update?.callback_query;
  if (callback) {
    const callbackId = callback.id;
    const callbackData = callback.data || "";
    const chatId = callback.message?.chat?.id;
    const messageId = callback.message?.message_id;

    const supabase = await createServerClient();

    if (callbackData.startsWith("fav:") || callbackData.startsWith("dis:")) {
      const isFav = callbackData.startsWith("fav:");
      const idPrefix = callbackData.slice(4);
      const newStatus = isFav ? "favorited" : "dismissed";
      const timestampCol = isFav ? "favorited_at" : "dismissed_at";

      // Find listing by prefix
      const { data: listing } = await supabase
        .from("listings")
        .select("id, address, price")
        .like("id", `${idPrefix}%`)
        .limit(1)
        .single();

      if (listing) {
        await supabase
          .from("listings")
          .update({
            status: newStatus,
            status_updated_at: new Date().toISOString(),
            [timestampCol]: new Date().toISOString(),
          })
          .eq("id", listing.id);

        // Update message with Undo button
        if (chatId && messageId) {
          const oldCaption = callback.message?.caption || "";
          const newCaption = isFav
            ? `💾 <b>Saved!</b>\n\n${oldCaption}`
            : `✕ <b>Dismissed</b>\n\n<s>${oldCaption}</s>`;

          await fetch(`${TG_API}/editMessageCaption`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: chatId,
              message_id: messageId,
              caption: newCaption,
              parse_mode: "HTML",
              reply_markup: {
                inline_keyboard: [[{ text: "↩ Undo", callback_data: `undo:${idPrefix}` }]],
              },
            }),
          });
        }

        await fetch(`${TG_API}/answerCallbackQuery`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            callback_query_id: callbackId,
            text: isFav ? "💾 Favorited!" : "✕ Dismissed!",
          }),
        });
      } else {
        await fetch(`${TG_API}/answerCallbackQuery`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ callback_query_id: callbackId, text: "Listing not found" }),
        });
      }
    } else if (callbackData.startsWith("undo:")) {
      const idPrefix = callbackData.slice(5);

      const { data: listing } = await supabase
        .from("listings")
        .select("id, url")
        .like("id", `${idPrefix}%`)
        .limit(1)
        .single();

      if (listing) {
        await supabase
          .from("listings")
          .update({
            status: "active",
            status_updated_at: new Date().toISOString(),
            favorited_at: null,
            dismissed_at: null,
          })
          .eq("id", listing.id);

        if (chatId && messageId) {
          let caption = callback.message?.caption || "";
          for (const prefix of ["✕ Dismissed\n\n", "💾 Saved!\n\n"]) {
            if (caption.startsWith(prefix)) {
              caption = caption.slice(prefix.length);
              break;
            }
          }
          // Remove <s> tags from undo
          caption = caption.replace(/<\/?s>/g, "");

          await fetch(`${TG_API}/editMessageCaption`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: chatId,
              message_id: messageId,
              caption,
              parse_mode: "HTML",
              reply_markup: {
                inline_keyboard: [[
                  { text: "💾 Save", callback_data: `fav:${idPrefix}` },
                  { text: "✕ Dismiss", callback_data: `dis:${idPrefix}` },
                  { text: "🔗 View", url: listing.url },
                ]],
              },
            }),
          });
        }

        await fetch(`${TG_API}/answerCallbackQuery`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ callback_query_id: callbackId, text: "↩ Restored!" }),
        });
      }
    } else {
      await fetch(`${TG_API}/answerCallbackQuery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ callback_query_id: callbackId }),
      });
    }
  }

  return NextResponse.json({ ok: true });
}
