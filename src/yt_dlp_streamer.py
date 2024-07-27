from __future__ import annotations
from dataclasses import dataclass
import discord.ext.commands
import yt_dlp
import asyncio
import discord

import discord.ext

# Suppress yt_dlp's bug report message
yt_dlp.utils.bug_reports_message = lambda: ""

# Configuration for yt_dlp
ytdl_format_options = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": False, # probably should be True but I want to see errors
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
}

ffmpeg_options = {"options": "-vn"}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

@dataclass
class Track:
    url: str
    data_url : str
    title: str | None
    length: int | None
    thumbnail: str | None
    src: str | None

class YTDL_Streamer(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data

    @classmethod
    async def from_url(cls, url, *args) -> YTDL_Streamer | None:
        data = ytdl.extract_info(url, download=False)
        if data:
            if "entries" in data:
                data = data["entries"][0]
            if "url" in data:
                return cls(discord.FFmpegPCMAudio(data["url"], **ffmpeg_options), data=data)
            
    @classmethod
    async def from_track(cls, track: Track) -> YTDL_Streamer | None:
        if track.data_url:
            return cls(discord.FFmpegPCMAudio(track.data_url, **ffmpeg_options), data=track)
    
    @classmethod
    async def create_track(cls, url) -> Track | None:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        if data:
            if "entries" in data:
                data = data["entries"][0]
            new_track = Track(url, None, None, None, None, None)
            if "url" in data:
                new_track.data_url = data["url"]
            if "duration" in data:
                new_track.length = data["duration"]
            if "title" in data:
                new_track.title = data["title"]
            if "thumbnail" in data:
                new_track.thumbnail = data["thumbnail"]
            if "youtube" in data["extractor"]:
                new_track.src = "youtube"
            return new_track
    
    @classmethod
    async def check_track_availability(cls, track:Track) -> bool:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(track.url, download=False))
        if data:
            if "entries" in data:
                data = data["entries"][0]
        return data is not None
    
    @classmethod
    async def refresh_track(cls, track: Track) -> Track | None:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(track.url, download=False))
        if data:
            if "entries" in data:
                data = data["entries"][0]
            if "url" in data:
                track.data_url = data["url"]
            if "duration" in data:
                track.length = data["duration"]
            if "title" in data:
                track.title = data["title"]
            if "thumbnail" in data:
                track.thumbnail = data["thumbnail"]
            if "youtube" in data["extractor"]:
                track.src = "youtube"
            return track


class YTDL_Player:
    def __init__(self,bot:discord.ext.commands.Bot, interaction: discord.Interaction, voice_client: discord.VoiceClient):
        self.bot = bot
        self.interaction = interaction
        self.active_track: Track | None = None
        self.voice_client = voice_client
        self.queue: list[Track] = []
        self.paused = True
        self.loop = False

    async def play(self, url=None):
        await self.interaction.edit_original_response(content="Loading...")
        if url:
            new_track = await YTDL_Streamer.create_track(url)
            if new_track is None:
                await self.interaction.edit_original_response(content="Error adding track.")
                return
            self.queue.append(new_track)
            await self.interaction.edit_original_response(content=f"Added to queue: {new_track.title}")
            self.paused = False
            await self.play()
        if self.queue and not self.paused:
            while self.queue:
                self.active_track = self.queue.pop(0)
                print(f"Playing: {self.active_track.title}")
                player = await YTDL_Streamer.from_track(self.active_track)
                print(f"Player: {player}")
                if player is None:
                    await self.interaction.edit_original_response(content="Error playing track.")
                    return
                self.voice_client.play(player, after=self._play_next)
                await self.interaction.edit_original_response(content=f"Now playing: {self.active_track.title}")
                print("Playing")

    def _play_next(self, error):
        if error:
            print(f"Player error: {error}")
        if self.loop and self.active_track:
            self.queue.append(self.active_track)
        if self.queue:
            asyncio.run_coroutine_threadsafe(self.play(),self.bot.loop)

    async def add(self, url):
        try:
            new_track = await YTDL_Streamer.create_track(url)
            if new_track is None:
                await self.interaction.response.send_message("Error adding track.")
                return
            self.queue.append(new_track)
        except Exception as e:
            print(f"Error adding track: {e}")
            await self.interaction.response.send_message("unexpected error adding track")
        await self.interaction.response.send_message(f"Added to queue: {new_track.title if new_track else 'Unknown'}")



    async def pause(self):
        if self.voice_client.is_playing():
            self.voice_client.pause()
            self.paused = True

    async def resume(self):
        if self.voice_client.is_paused():
            self.voice_client.resume()
            self.paused = False

    async def stop(self):
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()
            self.queue.clear()
            self.paused = True

    async def skip(self):
        if self.voice_client.is_playing():
            self.voice_client.stop()
            await self.play()

    async def set_loop(self, loop: bool):
        self.loop = loop
        await self.interaction.response.send_message(f"Looping is {'enabled' if loop else 'disabled'}.")

    async def disconnect(self):
        await self.stop()
        await self.voice_client.disconnect()

    async def status(self):
        status_msg = "Currently playing: "
        if self.active_track:
            status_msg += f"{self.active_track.title}\n"
        else:
            status_msg += "Nothing\n"
        await self.interaction.response.send_message(status_msg)

    async def ensure_voice(self):
        if self.voice_client is None:
            if self.interaction.user.voice is not None:
                if self.interaction.user.voice.channel is not None:
                    self.voice_client = await self.interaction.user.voice.channel.connect()
                else:
                    await self.interaction.response.send_message("You are not connected to a voice channel.")
                    raise discord.ext.commands.CommandError(f"{self.interaction.user.display_name} user not connected to a voice channel.")
            else:
                await self.interaction.response.send_message("You are not connected to a voice channel.")
                raise discord.ext.commands.CommandError(f"{self.interaction.user.display_name} user not connected to a voice channel.")
        elif self.voice_client.is_playing():
            self.voice_client.stop()

