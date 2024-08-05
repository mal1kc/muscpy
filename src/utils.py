import asyncio
from typing import Generic, TypeVar

import discord

pool_K = TypeVar('pool_K')
pool_V = TypeVar('pool_V')

class SharedDict(Generic[pool_K, pool_V]):
    def __init__(self):
        self._lock = asyncio.Lock()
        self._pool : dict[pool_K, pool_V] = {}

    async def get(self, key:pool_K) -> pool_V | None:
        async with self._lock:
            return self._pool.get(key)

    async def set(self, key:pool_K, value:pool_V):
        async with self._lock:
            self._pool[key] = value

    async def delete(self, key:pool_K):
        async with self._lock:
            if key in self._pool:
                del self._pool[key]


class SharedList(Generic[pool_V]):
    def __init__(self) -> None:
        super().__init__()
        self._lock = asyncio.Lock()
        self._pool : list[pool_V] = []

    def __getitem__(self, index:int) -> pool_V | None:
        return asyncio.run(self.get(index))
    
    def __setitem__(self, index:int, value:pool_V):
        asyncio.run(self.set(index, value))
    
    def __delitem__(self, index:int):
        asyncio.run(self.pop(index))

    def __len__(self) -> int:
        return len(self._pool)
    
    def __iter__(self):
        return iter(self._pool)

    async def get(self, index:int) -> pool_V | None:
        async with self._lock:
            try:
                return self._pool[index]
            except IndexError:
                return None
        
    async def set(self, index:int, value:pool_V):
        async with self._lock:
            self._pool[index] = value

    async def append(self, value:pool_V):
        async with self._lock:
            self._pool.append(value)

    async def remove(self, value:pool_V):
        async with self._lock:
            self._pool.remove(value)

    async def pop(self, index:int) -> pool_V | None:
        async with self._lock:
            try:
                return self._pool.pop(index)
            except IndexError:
                return None
    
    async def clear(self):
        async with self._lock:
            self._pool.clear()



async def not_guild(interaction:discord.Interaction) -> bool:
    if interaction.guild is None:
        await interaction.response.send_message("Bot currently only supports guilds")
        return True
    return False

async def get_voice_client(interaction:discord.Interaction,
                           voice_ch:discord.VoiceChannel | None = None,
                           quiet:bool = True,
                           ) -> discord.VoiceClient | discord.VoiceProtocol | None:
    if voice_ch is None:
        if isinstance(interaction.user, discord.Member):
            if isinstance(interaction.user.voice, discord.VoiceState):
                voice_ch = interaction.user.voice.channel # type: ignore
        
    if voice_ch is None:
        if not quiet:
            await interaction.response.send_message("I can't find a voice channel to join")
        return None
    
    if await not_guild(interaction):
        return None
    # from now on we are sure that interaction.guild is not None
    safe_guild : discord.Guild  = interaction.guild # type: ignore


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
    
    if not quiet :
        await interaction.response.send_message(f"Connected to {voice_ch.name}")
    return voice_client
    



    
    


 


