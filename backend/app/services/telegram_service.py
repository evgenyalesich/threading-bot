from __future__ import annotations

import httpx

from app.core.settings import Settings


class TelegramService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def enabled(self) -> bool:
        return bool(
            self._settings.telegram_notifications_enabled
            and self._settings.telegram_bot_token
            and self._settings.telegram_chat_id
        )

    async def send_message(self, text: str, chat_id: str | None = None, reply_markup: dict | None = None) -> dict | None:
        if not self.enabled():
            return None
        token = str(self._settings.telegram_bot_token).strip()
        target_chat_id = str(chat_id or self._settings.telegram_chat_id).strip()
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": target_chat_id,
            "text": text[:4000],
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code >= 400:
                try:
                    description = (response.json() or {}).get("description", "")
                except Exception:
                    description = response.text
                if "message is not modified" in str(description).lower():
                    return None
                raise RuntimeError(f"telegram_send_failed: {response.status_code} {description}")
            return (response.json() or {}).get("result")

    async def edit_message_text(
        self,
        text: str,
        message_id: int,
        chat_id: str | None = None,
        reply_markup: dict | None = None,
    ) -> dict | None:
        if not self.enabled():
            return None
        token = str(self._settings.telegram_bot_token).strip()
        target_chat_id = str(chat_id or self._settings.telegram_chat_id).strip()
        url = f"https://api.telegram.org/bot{token}/editMessageText"
        payload = {
            "chat_id": target_chat_id,
            "message_id": int(message_id),
            "text": text[:4000],
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code >= 400:
                try:
                    description = (response.json() or {}).get("description", "")
                except Exception:
                    description = response.text
                if "message is not modified" in str(description).lower():
                    return None
                response.raise_for_status()
            return (response.json() or {}).get("result")

    async def get_updates(self, offset: int = 0) -> list[dict]:
        if not self.enabled():
            return []
        token = str(self._settings.telegram_bot_token).strip()
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params={"offset": offset, "timeout": 10})
            response.raise_for_status()
            payload = response.json()
            return payload.get("result") or []

    async def answer_callback_query(self, callback_query_id: str, text: str | None = None) -> None:
        if not self.enabled():
            return
        token = str(self._settings.telegram_bot_token).strip()
        url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text[:200]
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=payload)

    def default_keyboard(self) -> dict:
        return {
            "keyboard": [
                [{"text": "Панель"}, {"text": "Обновить"}],
                [{"text": "Запуск / Стоп"}, {"text": "Проверить рынок"}],
            ],
            "resize_keyboard": True,
            "is_persistent": True,
            "input_field_placeholder": "Открой панель управления",
        }

    def main_menu_keyboard(self, enabled: bool = False) -> dict:
        return {
            "inline_keyboard": [
                [
                    {"text": "Живой статус", "callback_data": "menu:live"},
                    {"text": "Сигналы", "callback_data": "menu:signals"},
                ],
                [
                    {"text": "Позиции", "callback_data": "menu:positions"},
                    {"text": "Ожидают решения", "callback_data": "menu:pending"},
                ],
                [
                    {"text": "Автоматизация", "callback_data": "menu:automation"},
                    {"text": "Рынок", "callback_data": "menu:market"},
                ],
                [
                    {"text": "Риск", "callback_data": "menu:risk"},
                    {"text": "Диагностика", "callback_data": "menu:diagnostics"},
                ],
                [
                    {
                        "text": "Остановить" if enabled else "Запустить",
                        "callback_data": "control:disable" if enabled else "control:enable",
                    },
                    {"text": "Проверить сейчас", "callback_data": "control:run"},
                    {"text": "Обновить", "callback_data": "menu:home"},
                ],
            ]
        }

    def navigation_keyboard(self, rows: list[list[dict]] | None = None) -> dict:
        keyboard = list(rows or [])
        keyboard.append(
            [
                {"text": "Главная", "callback_data": "menu:home"},
                {"text": "Обновить", "callback_data": "menu:refresh"},
            ]
        )
        return {"inline_keyboard": keyboard}

    def automation_keyboard(self, enabled: bool, mode: str, trade_env: str) -> dict:
        return self.navigation_keyboard(
            [
                [
                    {"text": f"{'✓ ' if mode == 'semi' else ''}SEMI", "callback_data": "config:mode:semi"},
                    {"text": f"{'✓ ' if mode == 'auto' else ''}AUTO", "callback_data": "config:mode:auto"},
                ],
                [
                    {"text": f"{'✓ ' if trade_env == 'testnet' else ''}DEMO", "callback_data": "config:env:testnet"},
                    {"text": f"{'✓ ' if trade_env == 'real' else ''}REAL", "callback_data": "config:env:real"},
                ],
                [
                    {
                        "text": "Остановить worker" if enabled else "Запустить worker",
                        "callback_data": "control:disable" if enabled else "control:enable",
                    },
                    {"text": "Один цикл", "callback_data": "control:run"},
                ],
            ]
        )

    def market_keyboard(self, market: str, market_wide: bool) -> dict:
        return self.navigation_keyboard(
            [
                [
                    {"text": f"{'✓ ' if market == 'spot' else ''}SPOT", "callback_data": "config:market:spot"},
                    {"text": f"{'✓ ' if market == 'futures' else ''}FUTURES", "callback_data": "config:market:futures"},
                ],
                [
                    {
                        "text": f"{'✓ ' if market_wide else ''}Все пары",
                        "callback_data": "config:universe:market",
                    },
                    {
                        "text": f"{'✓ ' if not market_wide else ''}Одна пара",
                        "callback_data": "config:universe:single",
                    },
                ],
                [
                    {"text": "Выбрать пару", "callback_data": "menu:pair"},
                    {"text": "Таймфреймы", "callback_data": "menu:tf"},
                ],
            ]
        )

    def timeframe_keyboard(self, current: str) -> dict:
        frames = ["15m", "1h", "4h", "1d"]
        rows = []
        row = []
        for frame in frames:
            label = f"• {frame}" if frame == current else frame
            row.append({"text": label, "callback_data": f"config:tf:{frame}"})
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        rows.append([{"text": "Назад к рынку", "callback_data": "menu:market"}])
        return self.navigation_keyboard(rows)

    def risk_keyboard(self, current: str) -> dict:
        return {
            "inline_keyboard": [
                [
                    {"text": f"{'• ' if current == 'sniper' else ''}Sniper", "callback_data": "config:risk:sniper"},
                    {"text": f"{'• ' if current == 'balanced' else ''}Balanced", "callback_data": "config:risk:balanced"},
                ],
                [
                    {"text": f"{'• ' if current == 'aggressive' else ''}Aggressive", "callback_data": "config:risk:aggressive"},
                ],
                [{"text": "Настройки исполнения", "callback_data": "menu:execution"}],
                [{"text": "Назад", "callback_data": "menu:home"}],
            ]
        }

    def symbol_keyboard(self, current: str, market: str) -> dict:
        presets = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT"]
        rows = []
        row = []
        current_symbol = current.upper()
        for symbol in presets:
            label = f"• {symbol}" if symbol == current_symbol else symbol
            row.append({"text": label, "callback_data": f"config:symbol:{symbol}"})
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        rows.append([{"text": f"Рынок: {market.upper()}", "callback_data": "menu:market"}])
        rows.append([{"text": "Назад к рынку", "callback_data": "menu:market"}])
        return self.navigation_keyboard(rows)

    def signal_actions_keyboard(self, signal_id: int) -> dict:
        return self.navigation_keyboard(
            [
                [
                    {"text": "Войти", "callback_data": f"approve:{signal_id}"},
                    {"text": "Отклонить", "callback_data": f"reject:{signal_id}"},
                ],
            ]
        )

    def order_actions_keyboard(self, order_id: int, active: bool = True) -> dict:
        rows = []
        if active:
            rows.extend(
                [
                    [
                        {"text": "SL в безубыток", "callback_data": f"be:{order_id}"},
                        {"text": "Закрыть", "callback_data": f"close:{order_id}"},
                    ],
                    [
                        {"text": "Изменить SL", "callback_data": f"input:sl:{order_id}"},
                        {"text": "Изменить TP", "callback_data": f"input:tp:{order_id}"},
                    ],
                [
                        {"text": "SL -0.25%", "callback_data": f"nudge:sl:-1:{order_id}"},
                        {"text": "SL +0.25%", "callback_data": f"nudge:sl:1:{order_id}"},
                    ],
                    [
                        {"text": "TP -0.25%", "callback_data": f"nudge:tp:-1:{order_id}"},
                        {"text": "TP +0.25%", "callback_data": f"nudge:tp:1:{order_id}"},
                    ],
                ]
            )
        rows.append([{"text": "К списку позиций", "callback_data": "menu:positions"}])
        return self.navigation_keyboard(rows)

    def order_list_keyboard(self, orders: list, active_only: bool = False) -> dict:
        rows = []
        for order in orders[:8]:
            active = str(order.status or "").lower() not in {"closed", "filled", "cancelled", "rejected"}
            if active_only and not active:
                continue
            marker = "●" if active else "○"
            rows.append(
                [
                    {
                        "text": f"{marker} #{order.id} {order.side} {order.symbol}",
                        "callback_data": f"order:{order.id}",
                    }
                ]
            )
        return self.navigation_keyboard(rows)

    def signal_list_keyboard(self, signals: list, pending_ids: set[int] | None = None) -> dict:
        pending_ids = pending_ids or set()
        rows = []
        for signal in signals[:8]:
            marker = "!" if signal.id in pending_ids else "·"
            rows.append(
                [
                    {
                        "text": f"{marker} #{signal.id} {signal.signal_type.upper()} {signal.symbol}",
                        "callback_data": f"signal:{signal.id}",
                    }
                ]
            )
        return self.navigation_keyboard(rows)

    def execution_keyboard(self, attach_orders: bool, auto_breakeven: bool, leverage: int | None) -> dict:
        leverage = int(leverage or 1)
        return self.navigation_keyboard(
            [
                [
                    {
                        "text": f"{'✓ ' if attach_orders else ''}SL/TP сразу",
                        "callback_data": f"config:attach:{0 if attach_orders else 1}",
                    },
                    {
                        "text": f"{'✓ ' if auto_breakeven else ''}Auto BE",
                        "callback_data": f"config:be:{0 if auto_breakeven else 1}",
                    },
                ],
                [
                    {"text": "Плечо -", "callback_data": "config:lev:down"},
                    {"text": f"x{leverage}", "callback_data": "menu:execution"},
                    {"text": "Плечо +", "callback_data": "config:lev:up"},
                ],
                [
                    {"text": "Сумма сделки", "callback_data": "input:amount:0"},
                    {"text": "Период проверки", "callback_data": "input:poll:0"},
                ],
                [{"text": "Назад", "callback_data": "menu:risk"}],
            ]
        )
