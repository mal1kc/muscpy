from __future__ import annotations
from collections.abc import AsyncGenerator, Coroutine
from dataclasses import dataclass
from typing import Any
import discord.ext.commands
from yt_dlp import YoutubeDL
from yt_dlp.utils.networking import random_user_agent
from yt_dlp import std_headers as ytdl_headers

# import stderr for FFmpegPCMAudio
from sys import stderr
from urllib.parse import urlparse
from http import client as http_client
import asyncio
import discord

ytdl_headers['User-Agent'] = random_user_agent()

common_ytdl_options = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": False, # probably should be True but I want to see errors
    "no_warnings": True,
    "source_address": "0.0.0.0",
}

# Configuration for yt_dlp
ytdl_glbl_format_options = {
    "noplaylist": False,
    "playlist_items": "1-100",
    "default_search": "auto",
    "extract_flat": True,
    "flat_playlist": True,
    **common_ytdl_options
}

ytldl_single_url_options = {
    "noplaylist": True,
    **common_ytdl_options
}


ffmpeg_options = {"options": "-vn"}

# ytdl = YoutubeDL(ytdl_glbl_format_options)

@dataclass
class Track:
    original_url: str
    data_url : str
    title: str | None
    length: int | None
    thumbnail: str | None
    extractor: str | None
    requester: discord.Member | discord.User | None = None

    def msg_embed(self,position:int| None = None, queue:list[Track] | None = None,title:str="Track Info") -> discord.Embed:
        embed = discord.Embed(title=title, description=self.title, color=discord.Color.blurple())
        embed.set_thumbnail(url=self.thumbnail)
        embed.add_field(name="Requester", value=self.requester.display_name if self.requester else "Unknown")
        embed.add_field(name="Length", value=self.length)
        if position:
            embed.add_field(name="Position", value=position)
        if queue:
            embed.add_field(name="Queue", value="\n".join([f"{i+1}. {track.title}" for i, track in enumerate(queue)]))
        return embed


    def __str__(self):
        return f"{self.title} requested by {self.requester.display_name if self.requester else 'Unknown'}"
    
    def __repr__(self):
        return f"{self.title} requested by {self.requester.display_name if self.requester else 'Unknown'}"
    
    def __eq__(self, other):
        return self.original_url == other.track.url
    
    @classmethod
    def from_dict(cls,data: dict,requester:discord.Member | None = None) -> Track:
        # if key exists in data, assign it to the variable, otherwise assign None
        # original_url = title = length = thumbnail = extractor = None
        # for key in ['title', 'length', 'thumbnail', 'extractor', 'original_url']:
        #     locals()[key] = data.get(key, None)
        # if not original_url:
        #     original_url = 'Unknown'
        # return cls(original_url, data['url'], title, length, thumbnail, extractor, requester)
        return cls(
            original_url=data.get('original_url', 'Unknown'),
            data_url=data['url'],
            title=data.get('title', 'Unknown'),
            length=data.get('duration', 0),
            thumbnail=data.get('thumbnail', None),
            extractor=data.get('extractor', None),
            requester=requester
        )
       

# Define FFmpeg options for streaming
ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}


class YTDLHandler:
    def __init__(self, bot: discord.ext.commands.Bot, voice_client: discord.VoiceClient):
        self.bot = bot
        self.voice_client = voice_client
        self.queue :list[Track]= []
        self.active_track = None
        self.active_playback = None
        self.paused = True
        self.loop = False

    # TODO: Implement a way to get the top 5 results from a search query and select one to play with discord buttons etc.
    @staticmethod
    async def url_from_search(query: str) -> list[str] | None:
        loop = asyncio.get_event_loop()
        print("Searching for:", query)
        with YoutubeDL(ytdl_glbl_format_options) as ytdl:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch5:{query}", download=False))
            if data and 'entries' in data:
                return [entry['url'] for entry in data['entries']]
        return None

    @staticmethod
    async def display_top_5_results(query: str):
        urls = await YTDLHandler.url_from_search(query)
        if urls:
            for i, url in enumerate(urls, start=1):
                print(f"Result {i}: {url}")
        else:
            print("No results found.")

    @staticmethod
    async def handle_track_url(url: str) -> Track | None:
        loop = asyncio.get_event_loop()
        try:
            with YoutubeDL(ytldl_single_url_options) as ytdl:
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
                if data:
                    return Track.from_dict(data)
        except Exception as e:
            print(f"Failed to get track info: probably its not a url: {url} with error: {e}")


    @staticmethod
    async def generate_track_or_que_urls(url) -> AsyncGenerator[tuple[Coroutine[Any,Any,Track | None], bool], None]:
        loop = asyncio.get_event_loop()
        with YoutubeDL(ytdl_glbl_format_options) as ytdl:
            data_of_urls = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
            if data_of_urls:
                if 'entries' in data_of_urls:
                    # It's a playlist!
                    for entry in data_of_urls['entries']:
                        try:
                            yield YTDLHandler.handle_track_url(entry['url']), True
                        except Exception as e:
                            print(f"Failed to get track info: probably its not a url: {entry} with error: {e}")
                else:
                    # It's a single video!
                    try:
                        yield YTDLHandler.handle_track_url(url), False
                    except Exception as e:
                        print(f"Failed to get track info: probably its not a url: {url} with error: {e}")

    
    async def handle_url(self, interaction: discord.Interaction, url: str,requester: discord.Member | discord.User | None = None)-> None:
        # if is_plist is True, First add first track to queue and start playing and then add the rest of the tracks to the queue
        # else add the track to the queue and start playing
        started_playing = False
        counter = 0
        async for new_track_cr,is_plist in self.generate_track_or_que_urls(url):
            new_track = await new_track_cr
            if not new_track:
                await interaction.edit_original_response(content="Failed to get track info.")
                return
            new_track.requester = requester
            self.queue.append(new_track)
            counter += 1
            if counter >= 100:
                await interaction.edit_original_response(content="Playlist is too large, only the first 100 tracks have been added.")
                break
            if is_plist and not started_playing:
                await self.play(interaction=interaction,resume= not self.voice_client.is_playing())
            else:
                await interaction.edit_original_response(content=f"Added to queue: {new_track.title}")

        # if the queue is empty and the player is paused, start playing else just add to the queue
        await self.play(interaction=interaction,resume= not self.voice_client.is_playing())
        # await interaction.edit_original_response(content="Playing..." if self.active_track else "Queue is empty.")



    async def play(self, interaction: discord.Interaction, url=None,resume=False):
            await interaction.edit_original_response(content="Loading...")
            if url:
                await self.handle_url(interaction, url, requester=interaction.user)
                return
            if resume:
                self.paused = False
            if self.queue and not self.paused and not self.voice_client.is_playing():
                while self.queue:
                    self.active_track = self.queue.pop(0)
                    # Check if the stream is valid
                    if not self.is_stream_valid(self.active_track.data_url):
                        await interaction.edit_original_response(content="Stream is invalid, requesting new stream...")
                        if new_url := await self.get_new_stream_url(self.active_track.original_url):
                            self.active_track.data_url = new_url
                            self.active_playback = discord.FFmpegPCMAudio(self.active_track.data_url, pipe=False, stderr=stderr.buffer, **ffmpeg_options)
                        else:
                            await interaction.edit_original_response(content="Failed to get a new stream.")
                            continue
                    else:
                        self.active_playback = discord.FFmpegPCMAudio(self.active_track.data_url, pipe=False, stderr=stderr.buffer, **ffmpeg_options)
                    self.voice_client.play(self.active_playback, after=lambda e: self.bot.loop.call_soon_threadsafe(self._play_next, interaction, e))
                    await interaction.edit_original_response(content=f"Now playing: {self.active_track.title}")
    
    def is_stream_valid(self, stream_url) -> bool:
        try:
            parsed_url = urlparse(stream_url)
            conn = http_client.HTTPConnection(parsed_url.netloc, timeout=5)
            # only send a HEAD request to check if the stream is valid we don't need the body (stream data)
            conn.request("HEAD", parsed_url.path)
            response = conn.getresponse()
            return response.status == 200
        except Exception:
            return False
        
    @staticmethod
    async def get_new_stream_url(original_url) -> str | None:
        if new_track := await YTDLHandler.handle_track_url(original_url):
            return new_track.data_url

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
        else:
            await interaction.response.send_message("Player is not playing.")

    async def resume(self, interaction: discord.Interaction):
        if self.voice_client.is_paused() or self.paused:
            self.voice_client.resume()
            self.paused = False
            if self.active_track:
                await interaction.response.send_message(f"Resumed: {self.active_track.title}")
            else:
                await interaction.response.send_message("Resumed Queue")
        else:
            await interaction.response.send_message("Player is not paused.")


    async def stop(self, interaction: discord.Interaction):
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()
            self.queue.clear()
            self.paused = True
            self.active_track = None
            await interaction.response.send_message("Stopped")
        else:
            await interaction.response.send_message("Player is not playing.")

    async def skip(self, interaction: discord.Interaction):
        if self.voice_client.is_playing():
            self.voice_client.stop()
            trk_title = "Unknown"
            if self.active_track:
                trk_title = self.active_track.title if self.active_track.title else trk_title
            await interaction.response.send_message("Skipped: " + trk_title)
            await self.play(interaction=interaction)
        else:
            await interaction.response.send_message("Player is not playing.")

    async def set_loop(self, interaction: discord.Interaction, loop: bool):
        self.loop = loop
        await interaction.response.send_message(f"Looping is {'enabled' if loop else 'disabled'}.")

    async def disconnect(self, interaction: discord.Interaction):
        await self.stop(interaction=interaction)
        await self.voice_client.disconnect()

    async def status(self, interaction: discord.Interaction):
        embd_title = "Status"
        embed_msg = discord.Embed(title=embd_title, color=discord.Color.blurple())
        if self.active_track:
            embed_msg = self.active_track.msg_embed(position=self.voice_client.timestamp,title=embd_title,queue=self.queue)
        else:
            embed_msg.add_field(name="Currently playing", value="Nothing")
        await interaction.response.send_message(embed=embed_msg)
    
    async def show_queue(self, interaction: discord.Interaction,is_followup=False) -> None:
        embed = discord.Embed(title="Queue", color=discord.Color.blurple())
        if self.queue:
            embed.add_field(name="Currently playing", value=self.active_track.title if self.active_track else "Nothing")
            embed.add_field(name="Queue", value="\n".join([f"{i+1}. {track.title}" for i, track in enumerate(self.queue)]))
        else:
            embed.add_field(name="Queue", value="Empty")
        if is_followup:
            await interaction.followup.send(embed=embed)
            return
        await interaction.response.send_message(embed=embed)

    async def clear_queue(self, interaction: discord.Interaction) -> None:
        self.queue.clear()
        await interaction.response.send_message("Queue cleared.")
        