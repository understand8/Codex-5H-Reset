"""Multi-channel Webhook Dispatcher for remote alerts."""
import json
import logging
import threading
from typing import Dict, Any, Optional

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger('codex_timer.webhooks')


class WebhookDispatcher:
    """Dispatches event notifications to DingTalk, Feishu, WeCom, Telegram, ServerChan, or Generic Webhooks."""

    @staticmethod
    def send(config: Dict[str, Any], title: str, content: str) -> None:
        if not config.get('enabled') or not requests:
            return

        def _worker():
            try:
                provider = config.get('provider', 'generic').lower()
                url = config.get('url', '').strip()
                token = config.get('token', '').strip()
                chat_id = config.get('chat_id', '').strip()

                if provider == 'dingtalk' and url:
                    payload = {
                        'msgtype': 'markdown',
                        'markdown': {
                            'title': title,
                            'text': f"### {title}\n\n{content}\n\n> *Codex-5H-Reset 自动提醒*"
                        }
                    }
                    requests.post(url, json=payload, timeout=8)

                elif provider == 'feishu' and url:
                    payload = {
                        'msg_type': 'interactive',
                        'card': {
                            'header': {'title': {'tag': 'plain_text', 'content': title}},
                            'elements': [{'tag': 'div', 'text': {'tag': 'lark_md', 'content': content}}]
                        }
                    }
                    requests.post(url, json=payload, timeout=8)

                elif provider == 'wecom' and url:
                    payload = {
                        'msgtype': 'markdown',
                        'markdown': {
                            'content': f"### {title}\n{content}"
                        }
                    }
                    requests.post(url, json=payload, timeout=8)

                elif provider == 'telegram' and token and chat_id:
                    tg_url = f"https://api.telegram.org/bot{token}/sendMessage"
                    payload = {
                        'chat_id': chat_id,
                        'text': f"*{title}*\n\n{content}",
                        'parse_mode': 'Markdown'
                    }
                    requests.post(tg_url, json=payload, timeout=10)

                elif provider == 'serverchan' and (url or token):
                    sc_url = url if url else f"https://sctapi.ftqq.com/{token}.send"
                    payload = {'title': title, 'desp': content}
                    requests.post(sc_url, data=payload, timeout=8)

                elif provider == 'generic' and url:
                    payload = {
                        'event': 'codex_timer_notification',
                        'title': title,
                        'content': content
                    }
                    requests.post(url, json=payload, timeout=8)

            except Exception as exc:
                logger.warning(f"Webhook dispatch failed: {exc}")

        threading.Thread(target=_worker, daemon=True).start()
