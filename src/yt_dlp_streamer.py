from __future__ import annotations
from dataclasses import dataclass
import discord.ext.commands
from yt_dlp import YoutubeDL

# import stderr for FFmpegPCMAudio
from sys import stderr
import asyncio
import discord

# Configuration for yt_dlp
ytdl_format_options = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": False,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": False, # probably should be True but I want to see errors
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
}

ffmpeg_options = {"options": "-vn"}

ytdl = YoutubeDL(ytdl_format_options)

@dataclass
class Track:
    url: str
    data_url : str
    title: str | None
    length: int | None
    thumbnail: str | None
    src: str | None

# Define FFmpeg options for streaming
ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

# Set up YouTube-DL
ytdl = YoutubeDL(ytdl_format_options)


class YTDLHandler:
    def __init__(self, bot: discord.ext.commands.Bot, voice_client: discord.VoiceClient):
        self.bot = bot
        self.voice_client = voice_client
        self.queue = []
        self.active_track = None
        self.active_playback = None
        self.paused = True
        self.loop = False

    @staticmethod
    async def create_track(url) -> Track | None:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        if data:
            if 'entries' in data:
                data = data['entries'][0]
            new_track = Track(url, "", None, None, None, None)
            if 'url' in data:
                new_track.data_url = data['url']
            if 'duration' in data:
                new_track.length = data['duration']
            if 'title' in data:
                new_track.title = data['title']
            if 'thumbnail' in data:
                new_track.thumbnail = data['thumbnail']
            if 'youtube' in data['extractor']:
                new_track.src = 'youtube'
            return new_track

    async def play(self, interaction: discord.Interaction, url=None):
        await interaction.edit_original_response(content="Loading...")
        if url:
            new_track = await self.create_track(url)
            if new_track is None:
                await interaction.edit_original_response(content="Error adding track.")
                return
            self.queue.append(new_track)
            await interaction.edit_original_response(content=f"Added to queue: {new_track.title}")
            self.paused = False
            await self.play(interaction=interaction)
        if self.queue and not self.paused:
            while self.queue:
                self.active_track = self.queue.pop(0)
                self.active_playback = discord.FFmpegPCMAudio(self.active_track.data_url, pipe=False, stderr=stderr.buffer, **ffmpeg_options)
                self.voice_client.play(self.active_playback, after=lambda e: self.bot.loop.call_soon_threadsafe(self._play_next, interaction, e))
                await interaction.edit_original_response(content=f"Now playing: {self.active_track.title}")

    def _play_next(self, interaction: discord.Interaction, error):
        if error:
            print(f"Player error: {error}")
        if self.loop and self.active_track:
            self.queue.append(self.active_track)
        if self.queue:
            asyncio.run_coroutine_threadsafe(self.play(interaction=interaction), self.bot.loop)

    async def pause(self, interaction: discord.Interaction):
        if self.voice_client.is_playing():
            self.voice_client.pause()
            self.paused = True
            if self.active_track:
                await interaction.response.send_message(f"Paused: {self.active_track.title}")
            else:
                await interaction.response.send_message("Paused Queue")

    async def resume(self, interaction: discord.Interaction):
        if self.voice_client.is_paused():
            self.voice_client.resume()
            self.paused = False
            if self.active_track:
                await interaction.response.send_message(f"Resumed: {self.active_track.title}")
            else:
                await interaction.response.send_message("Resumed Queue")


    async def stop(self, interaction: discord.Interaction):
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()
            self.queue.clear()
            self.paused = True
            self.active_track = None
            await interaction.response.send_message("Stopped")

    async def skip(self, interaction: discord.Interaction):
        if self.voice_client.is_playing():
            self.voice_client.stop()
            await self.play(interaction=interaction)
            await interaction.response.send_message("Skipped")

    async def set_loop(self, interaction: discord.Interaction, loop: bool):
        self.loop = loop
        await interaction.response.send_message(f"Looping is {'enabled' if loop else 'disabled'}.")

    async def disconnect(self, interaction: discord.Interaction):
        await self.stop(interaction=interaction)
        await self.voice_client.disconnect()

    async def status(self, interaction: discord.Interaction):
        status_msg = "Currently playing: "
        if self.active_track:
            status_msg += f"{self.active_track.title}\n"
            status_msg += f"Length: {self.active_track.length}\n"
            # Position tracking via FFmpeg is not directly possible; consider using an external library or custom solution for better accuracy.
            status_msg += f"Position: {self.voice_client.timestamp}\n"
            status_msg += "Queue:\n"
            for i, track in enumerate(self.queue):
                status_msg += f"{i+1}. {track.title}\n"
        else:
            status_msg += "Nothing\n"
        await interaction.response.send_message(status_msg)

    # async def ensure_voice(self, interaction: discord.Interaction):
    #     if self.voice_client is None:
    #         if interaction.user.voice is not None and interaction.user.voice.channel is not None:
    #             self.voice_client = await interaction.user.voice.channel.connect()
    #         else:
    #             await interaction.response.send_message("You are not connected to a voice channel.")
    #             raise discord.ext.commands.CommandError(f"{interaction.user.display_name} is not connected to a voice channel.")
    #     elif self.voice_client.is_playing():
    #         self.voice_client.stop()

