import asyncio
import aiohttp
import discord
import threading
import time
from datetime import datetime
from typing import List, Tuple, Optional, Dict

class BotRunner:
    def __init__(self, log_callback):
        self.log = log_callback
        self.running = False
        self.thread = None
        self.loop = None
        self._stop_event = None

    def start(self, tokens: List[str], message: str, channels: List[Tuple[int, int]],
              webhook_url: str = "", embed_config: Optional[Dict] = None):
        if self.running:
            return False, "Bot sudah berjalan."
        if not tokens or not message or not channels:
            return False, "Token, pesan, atau channel tidak lengkap."

        self._stop_event = threading.Event()
        self.thread = threading.Thread(
            target=self._run,
            args=(tokens, message, channels, webhook_url, embed_config or {}),
            daemon=True
        )
        self.thread.start()
        return True, "Bot sedang dinyalakan..."

    def stop(self):
        if not self.running:
            return False, "Bot tidak sedang berjalan."
        self._stop_event.set()
        return True, "Bot sedang dihentikan..."

    def _run(self, tokens, message, channels, webhook_url, embed_config):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.running = True

        # jadwal pengiriman: setiap channel punya waktu kirim berikutnya
        next_send = {}
        for ch, delay in channels:
            # mulai dengan jeda acak 1-5 detik agar tidak serentak
            import random
            next_send[ch] = time.time() + random.uniform(1, 5)

        token_index = 0
        total_tokens = len(tokens)

        # fungsi untuk mengirim satu pesan
        def send_sync(token, channel_id):
            import requests
            url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
            headers = {'Authorization': token, 'Content-Type': 'application/json'}
            payload = {'content': message}
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=10)
                return resp.status_code == 200
            except Exception:
                return False

        # fungsi kirim notifikasi webhook (asinkron)
        async def send_webhook(channel_id, status_text):
            if not webhook_url:
                return
            color = 0x5EEAD4 if status_text == "Terkirim" else 0xF2545B
            embed = discord.Embed(
                title=embed_config.get("title", "📢 Laporan Pengiriman"),
                description=embed_config.get("description", f"Channel: {channel_id}\nStatus: {status_text}"),
                color=color,
                timestamp=datetime.now()
            )
            if embed_config.get("footer"):
                embed.set_footer(text=embed_config["footer"])
            if embed_config.get("thumbnail_url"):
                embed.set_thumbnail(url=embed_config["thumbnail_url"])
            try:
                async with aiohttp.ClientSession() as session:
                    wh = discord.Webhook.from_url(webhook_url, session=session)
                    await wh.send(embed=embed, username="Autopost")
            except Exception as e:
                self.log(f"Gagal kirim webhook: {e}")

        # loop utama
        while not self._stop_event.is_set():
            now = time.time()
            for ch, delay in channels:
                if now >= next_send.get(ch, 0):
                    token = tokens[token_index % total_tokens]
                    success = send_sync(token, ch)
                    status = "Terkirim" if success else "Gagal"
                    self.log(f"{ch}: {status} (token ke-{token_index % total_tokens + 1})")

                    # kirim notifikasi webhook (asinkron)
                    if webhook_url:
                        asyncio.run_coroutine_threadsafe(
                            send_webhook(ch, status),
                            self.loop
                        )

                    # perbarui jadwal
                    next_send[ch] = now + delay
                    token_index += 1

            time.sleep(0.5)  # cek setiap 0.5 detik

        self.running = False
        self.log("Bot berhenti.")