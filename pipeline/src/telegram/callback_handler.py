"""Telegram callback handler — poll for Save/Dismiss button presses + /start subscriber registration."""

import asyncio
import os

import asyncpg
import httpx
from rich.console import Console

console = Console()

_API = "https://api.telegram.org/bot{token}/{method}"


async def _register_subscriber(pool: asyncpg.Pool, chat_id: int, username: str | None, first_name: str | None) -> bool:
    """Register or reactivate a subscriber. Returns True if new."""
    result = await pool.fetchrow(
        """INSERT INTO telegram_subscribers (chat_id, username, first_name)
           VALUES ($1, $2, $3)
           ON CONFLICT (chat_id) DO UPDATE SET active = TRUE, username = COALESCE($2, telegram_subscribers.username), first_name = COALESCE($3, telegram_subscribers.first_name)
           RETURNING (xmax = 0) AS is_new""",
        chat_id, username, first_name,
    )
    return result["is_new"] if result else False


async def run_callback_handler(pool: asyncpg.Pool) -> None:
    """Long-running poll loop for Telegram callback queries and /start messages.

    Handles:
    - /start → register subscriber
    - fav:<id_prefix> → status = 'favorited'
    - dis:<id_prefix> → status = 'dismissed'
    - undo:<id_prefix> → status = 'active' (restore)
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        console.print("[bold red]TELEGRAM_BOT_TOKEN not set.[/]")
        return

    console.print("[bold]Starting Telegram callback handler (polling)...[/]")
    console.print("[dim]Listening for /start and button presses. Press Ctrl+C to stop.[/dim]")

    offset = 0

    async with httpx.AsyncClient(timeout=35) as client:
        while True:
            try:
                resp = await client.post(
                    _API.format(token=token, method="getUpdates"),
                    json={
                        "offset": offset,
                        "timeout": 30,
                        "allowed_updates": ["callback_query", "message"],
                    },
                )
                data = resp.json()
                if not data.get("ok"):
                    console.print(f"[red]getUpdates error: {data.get('description')}[/]")
                    await asyncio.sleep(5)
                    continue

                for update in data.get("result", []):
                    offset = update["update_id"] + 1

                    # Handle /start messages
                    message = update.get("message")
                    if message:
                        text = (message.get("text") or "").strip()
                        if text == "/start":
                            chat = message["chat"]
                            chat_id = chat["id"]
                            username = message.get("from", {}).get("username")
                            first_name = message.get("from", {}).get("first_name")
                            is_new = await _register_subscriber(pool, chat_id, username, first_name)

                            if is_new:
                                welcome = (
                                    "👋 Welcome to Milan Finder!\n\n"
                                    "You'll receive alerts for new apartments scoring 70+ automatically.\n\n"
                                    "Use the Save/Dismiss buttons on each listing to manage your shortlist."
                                )
                                console.print(f"  [green]New subscriber:[/] {first_name} (@{username}) chat_id={chat_id}")
                            else:
                                welcome = "Welcome back! You're already subscribed. Alerts will come automatically."
                                console.print(f"  [dim]Returning subscriber:[/] {first_name} (@{username}) chat_id={chat_id}")

                            await client.post(
                                _API.format(token=token, method="sendMessage"),
                                json={"chat_id": chat_id, "text": welcome},
                            )
                        continue

                    # Handle callback queries (button presses)
                    callback = update.get("callback_query")
                    if not callback:
                        continue

                    callback_id = callback["id"]
                    callback_data = callback.get("data", "")

                    if callback_data.startswith("fav:"):
                        id_prefix = callback_data[4:]
                        await _handle_action(pool, id_prefix, "favorited", callback_id, token, client, callback)
                    elif callback_data.startswith("dis:"):
                        id_prefix = callback_data[4:]
                        await _handle_action(pool, id_prefix, "dismissed", callback_id, token, client, callback)
                    elif callback_data.startswith("undo:"):
                        id_prefix = callback_data[5:]
                        await _handle_undo(pool, id_prefix, callback_id, token, client, callback)
                    else:
                        await client.post(
                            _API.format(token=token, method="answerCallbackQuery"),
                            json={"callback_query_id": callback_id},
                        )

            except httpx.TimeoutException:
                continue
            except asyncio.CancelledError:
                console.print("[dim]Callback handler stopped.[/dim]")
                return
            except Exception as e:
                console.print(f"[red]Callback handler error: {e}[/]")
                await asyncio.sleep(5)


def _undo_keyboard(id_prefix: str) -> dict:
    """Build inline keyboard with just an Undo button."""
    return {
        "inline_keyboard": [[
            {"text": "\u21a9 Undo", "callback_data": f"undo:{id_prefix}"},
        ]]
    }


async def _handle_action(
    pool: asyncpg.Pool,
    id_prefix: str,
    new_status: str,
    callback_id: str,
    token: str,
    client: httpx.AsyncClient,
    callback: dict,
) -> None:
    """Update listing status and answer the callback query."""
    row = await pool.fetchrow(
        "SELECT id, address, price FROM listings WHERE id LIKE $1 LIMIT 1",
        f"{id_prefix}%",
    )

    if row:
        timestamp_col = "favorited_at" if new_status == "favorited" else "dismissed_at"
        await pool.execute(
            f"UPDATE listings SET status = $1, status_updated_at = NOW(), "
            f"{timestamp_col} = NOW() WHERE id = $2",
            new_status, row["id"],
        )
        emoji = "\U0001f4be" if new_status == "favorited" else "\u2715"
        answer_text = f"{emoji} {new_status.title()}!"
        addr = (row["address"] or "")[:25]
        console.print(f"  [dim]{emoji} {new_status}: \u20ac{row['price']}/mo {addr}[/]")

        message = callback.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")
        if chat_id and message_id:
            old_caption = message.get("caption", "")
            if new_status == "dismissed":
                new_caption = f"\u2715 <b>Dismissed</b>\n\n<s>{old_caption}</s>"
            else:
                new_caption = f"\U0001f4be <b>Saved!</b>\n\n{old_caption}"
            await client.post(
                _API.format(token=token, method="editMessageCaption"),
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "caption": new_caption,
                    "parse_mode": "HTML",
                    "reply_markup": _undo_keyboard(id_prefix),
                },
            )
    else:
        answer_text = "Listing not found"

    await client.post(
        _API.format(token=token, method="answerCallbackQuery"),
        json={
            "callback_query_id": callback_id,
            "text": answer_text,
        },
    )


async def _handle_undo(
    pool: asyncpg.Pool,
    id_prefix: str,
    callback_id: str,
    token: str,
    client: httpx.AsyncClient,
    callback: dict,
) -> None:
    """Restore listing to active status and bring back original buttons."""
    row = await pool.fetchrow(
        "SELECT id, url, address, price FROM listings WHERE id LIKE $1 LIMIT 1",
        f"{id_prefix}%",
    )

    if row:
        await pool.execute(
            "UPDATE listings SET status = 'active', status_updated_at = NOW(), "
            "favorited_at = NULL, dismissed_at = NULL WHERE id = $1",
            row["id"],
        )
        answer_text = "\u21a9 Restored!"
        addr = (row["address"] or "")[:25]
        console.print(f"  [dim]\u21a9 restored: \u20ac{row['price']}/mo {addr}[/]")

        message = callback.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")
        if chat_id and message_id:
            caption = message.get("caption", "")
            for prefix in ["\u2715 Dismissed\n\n", "\U0001f4be Saved!\n\n"]:
                if caption.startswith(prefix):
                    caption = caption[len(prefix):]
                    break
            from src.telegram.notify import _build_keyboard
            await client.post(
                _API.format(token=token, method="editMessageCaption"),
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "caption": caption,
                    "parse_mode": "HTML",
                    "reply_markup": _build_keyboard(id_prefix, row["url"]),
                },
            )
    else:
        answer_text = "Listing not found"

    await client.post(
        _API.format(token=token, method="answerCallbackQuery"),
        json={
            "callback_query_id": callback_id,
            "text": answer_text,
        },
    )
