import asyncio
from dataclasses import dataclass
import discord
from muscpy.utils import SharedDict
from muscpy.config import IDLE_CHECK_TIMEOUT, IDLE_TIMEOUT


@dataclass
class GuildTimerData:
    timeout: float
    voice_client: discord.VoiceClient | discord.VoiceProtocol | None
    text_channel: discord.TextChannel


class IdleChecker:
    def __init__(self):
        self._timers: SharedDict[str, GuildTimerData] = SharedDict()

    async def init_idle_state_for_client(
        self,
        guild_id: str,
        voice_client: discord.VoiceClient | discord.VoiceProtocol,
        text_channel: discord.TextChannel,
    ):
        """
        Start a new idle timer for the given guild, or reset an existing one.
        When the timer expires, the bot will be disconnected from the voice channel.
        """
        print("IdleChecker init_idle_state_for_client")
        prev_data = await self._timers.get(guild_id)
        if prev_data:
            prev_data.timeout = IDLE_TIMEOUT
            prev_data.voice_client = voice_client
        else:
            await self._timers.set(
                guild_id,
                GuildTimerData(
                    timeout=IDLE_TIMEOUT,
                    voice_client=voice_client,
                    text_channel=text_channel,
                ),
            )

    async def deinit_idlestate_of_client(self, guild_id: str):
        await self._timers.delete(guild_id)

    async def _idle_loop(self):
        """
        Continuously check for expired idle timers.
        """
        while True:
            expired_guids: list[str] = []
            async for guild_id, guild_data in self._timers.items():
                if guild_data.voice_client is None:
                    expired_guids.append(guild_id)
                else:
                    if guild_data.voice_client.is_playing():  # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType]
                        guild_data.timeout = IDLE_TIMEOUT
                    if guild_data.timeout <= 0:
                        # Disconnect from the voice channel
                        await guild_data.voice_client.disconnect()
                        expired_guids.append(guild_id)
                    else:
                        guild_data.timeout -= IDLE_CHECK_TIMEOUT
            for guild_id in expired_guids:
                guild_data = await self._timers.get(guild_id)
                if guild_data:
                    _ = await guild_data.text_channel.send(
                        content="disconnected because of idling"
                    )
                await self._timers.delete(str(guild_id))
            await asyncio.sleep(IDLE_CHECK_TIMEOUT)

    async def run_idle_loop(self):
        print("IdleChecker loop started")
        await self._idle_loop()
        print("IdleChecker loop ended")
