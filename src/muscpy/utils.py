import asyncio
from collections.abc import AsyncIterator

import discord


class SharedDict[pool_K, pool_V]:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._pool: dict[pool_K, pool_V] = {}

    async def get(self, key: pool_K) -> pool_V | None:
        async with self._lock:
            return self._pool.get(key)

    async def set(self, key: pool_K, value: pool_V) -> None:
        async with self._lock:
            self._pool[key] = value

    async def delete(self, key: pool_K) -> None:
        async with self._lock:
            if key in self._pool:
                del self._pool[key]

    async def items(self) -> AsyncIterator[tuple[pool_K, pool_V]]:
        async with self._lock:
            for key, value in self._pool.items():
                yield (key, value)


class SharedList[pool_V]:
    def __init__(self) -> None:
        super().__init__()
        self._lock = asyncio.Lock()
        self._pool: list[pool_V] = []

    # asyncio.run() can't be called from inside the running event loop, so
    # these sync accessors work on the list directly (single-threaded loop).
    def __getitem__(self, index: int) -> pool_V | None:
        try:
            return self._pool[index]
        except IndexError:
            return None

    def __setitem__(self, index: int, value: pool_V):
        self._pool[index] = value

    def __delitem__(self, index: int):
        del self._pool[index]

    def __len__(self) -> int:
        return len(self._pool)

    def __iter__(self):
        # iterate over a snapshot so concurrent pops can't break iteration
        return iter(list(self._pool))

    async def get(self, index: int) -> pool_V | None:
        async with self._lock:
            try:
                return self._pool[index]
            except IndexError:
                return None

    async def set(self, index: int, value: pool_V):
        async with self._lock:
            self._pool[index] = value

    async def append(self, value: pool_V):
        async with self._lock:
            self._pool.append(value)

    async def remove(self, value: pool_V):
        async with self._lock:
            self._pool.remove(value)

    async def pop(self, index: int) -> pool_V | None:
        async with self._lock:
            try:
                return self._pool.pop(index)
            except IndexError:
                return None

    async def clear(self):
        async with self._lock:
            self._pool.clear()


async def not_guild(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        await interaction.response.send_message("Bot currently only supports guilds")
        return True
    return False


async def get_voice_client(
    interaction: discord.Interaction,
    voice_ch: discord.VoiceChannel | None = None,
    quiet: bool = True,
) -> discord.VoiceClient | discord.VoiceProtocol | None:
    if (
        voice_ch is None
        and isinstance(interaction.user, discord.Member)
        and isinstance(interaction.user.voice, discord.VoiceState)
        and not isinstance(interaction.user.voice.channel, discord.StageChannel)
    ):
        voice_ch = interaction.user.voice.channel

    if voice_ch is None:
        if not quiet:
            await interaction.response.send_message(
                "I can't find a voice channel to join"
            )
        return None

    if await not_guild(interaction):
        return None
    # from now on we are sure that interaction.guild is not None
    safe_guild: discord.Guild = interaction.guild  # pyright: ignore[reportAssignmentType]

    voice_client = safe_guild.voice_client
    if voice_client is not None and voice_client.channel != voice_ch:
        try:
            voice_client = await voice_ch.connect()
        except discord.ClientException:
            # already connected to a voice channel
            # disconnect and reconnect to specified channel
            await voice_client.disconnect(force=True)
            voice_client = await voice_ch.connect()
    elif voice_client is None:
        voice_client = await voice_ch.connect()

    if not quiet:
        await interaction.response.send_message(f"Connected to {voice_ch.name}")
    return voice_client


def get_txt_channel(interaction: discord.Interaction) -> discord.TextChannel | None:
    if interaction.channel and interaction.channel.type == discord.ChannelType.text:
            return interaction.channel
