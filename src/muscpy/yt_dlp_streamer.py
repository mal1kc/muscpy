from __future__ import annotations


# pyright: reportPrivateUsage=warning, reportMissingTypeStubs=false,reportAttributeAccessIssue=false

# pyright: basic

import asyncio

from collections.abc import AsyncGenerator, Coroutine, Iterable

from dataclasses import dataclass

from sys import stderr

from typing import Any, override

from urllib.parse import urlparse


import discord

import discord.ext.commands

from muscpy.utils import SharedList
from yt_dlp import YoutubeDL

from yt_dlp import std_headers as ytdl_headers

from yt_dlp.utils.networking import random_user_agent


class PlayButton(discord.ui.Button["PlayButtonView"]):
    def __init__(self, ytdl_handler: YTDLHandler, track: Track):
        super().__init__(
            label=track.title[:40] + "..."
            if track.title and len(track.title) > 80
            else track.title or "Unkown",
            style=discord.ButtonStyle.primary,
        )

        self.ytdl_handler = ytdl_handler

        self.track = track

    @override
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"from_query Playing: {self.track.title[:40] if self.track.title else "unknown"} \nurl: {self.track.original_url}",
            ephemeral=False,
        )

        if not hasattr(self.ytdl_handler, "handle_track"):
            await interaction.response.send_message(
                "Internal error: Handler does not have handle_track method"
            )

        await self.ytdl_handler.handle_track(interaction, self.track)


class PlayButtonView(discord.ui.View):
    def __init__(self, ytdl_handler: YTDLHandler, tracks: Iterable[Track]):
        super().__init__()

        self.tracks = tracks

        for track in tracks:
            _ = self.add_item(PlayButton(ytdl_handler, track))


ytdl_headers["User-Agent"] = random_user_agent()


common_ytdl_options = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": False,
    "no_warnings": True,
    "source_address": "0.0.0.0",
}

ytdl_search_options = {
    "noplaylist": True,
    "playlist_items": "1-5",
    "default_search": "https://music.youtube.com/search?q=",
    "extract_flat": True,
    "flat_playlist": True,
    **common_ytdl_options,
}


ytdl_glbl_format_options = {
    "noplaylist": False,
    "playlist_items": "1-100",
    "default_search": "auto",
    "extract_flat": True,
    "flat_playlist": True,
    **common_ytdl_options,
}


ytldl_single_url_options = {"noplaylist": True, **common_ytdl_options}


ffmpeg_options = {
    "options": "-vn",
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
}


@dataclass
class Track:
    original_url: str
    data_url: str

    title: str | None

    length: int | None

    thumbnail: str | None

    extractor: str | None

    playlist_url: str | None

    requester: discord.Member | discord.User | None = None

    fetched: bool = False

    def msg_embed(
        self,
        position: float | None = None,
        queue: SharedList[Track] | None = None,
        title: str = "Track Info",
    ) -> discord.Embed:
        embed = discord.Embed(
            title=title, description=self.title, color=discord.Color.blurple()
        )

        embed = (
            embed.set_thumbnail(url=self.thumbnail)
            .add_field(
                name="Requester",
                value=self.requester.display_name if self.requester else "Unknown",
            )
            .add_field(name="Length", value=f"{self.length}s")
        )
        if position:
            embed = embed.add_field(name="Position", value="{:.2f}".format(position))
        if self.playlist_url:
            embed = embed.add_field(name="orginal playlist", value=self.playlist_url)

        if queue:
            embed = embed.add_field(
                name="Queue",
                value="\n".join(
                    [f"{i+1}. {track.title}" for i, track in enumerate(queue)]
                ),
            )

        return embed

    @override
    def __str__(self):
        return f"{self.title} requested by {self.requester.display_name if self.requester else 'Unknown'}"

    @override
    def __repr__(self):
        return f"{self.title} requested by {self.requester.display_name if self.requester else 'Unknown'}\n og_url : {self.original_url}"

    @override
    def __eq__(self, other: object):
        if isinstance(other, Track):
            return self.original_url == other.original_url

        return False

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        fetch_sts: bool,
        requester: discord.Member | None = None,
    ) -> Track:
        return cls(
            original_url=data.get("original_url", "Unknown"),  # pyright: ignore[reportAny]
            data_url=data["url"],  # pyright: ignore[reportAny]
            title=data.get("title", "Unknown"),  # pyright: ignore[reportAny]
            length=data.get("duration", 0),  # pyright: ignore[reportAny]
            thumbnail=data.get("thumbnail", None),  # pyright: ignore[reportAny]
            extractor=data.get("extractor", None),  # pyright: ignore[reportAny]
            playlist_url=data.get("playlist", None),
            fetched=fetch_sts,
            requester=requester,
        )

    async def fetch(self):
        print(f"fetch_called for {self.original_url} {self.data_url}")
        loop = asyncio.get_event_loop()
        with YoutubeDL(ytldl_single_url_options) as ytdl:
            if self.original_url is None or "" == self.original_url:
                data = await loop.run_in_executor(
                    None,
                    lambda: ytdl.extract_info(self.original_url, download=False),
                )
            elif self.data_url is None or "" == self.original_url:
                return None
            else:
                self.original_url = self.data_url
                data = await loop.run_in_executor(
                    None,
                    lambda: ytdl.extract_info(self.data_url, download=False),
                )
            if data is None:
                return
            if "enttries" in data:
                data = data["entries"][0]
            if isinstance(data, dict):
                self.original_url = data.get("original_url", self.original_url)  # pyright: ignore
                self.data_url = data["url"]  # pyright: ignore
                self.title = data.get("title", self.title)  # pyright: ignore
                self.length = data.get("duration", self.length)  # pyright: ignore
                self.thumbnail = data.get("thumbnail", self.thumbnail)  # pyright: ignore
                self.extractor = data.get("extractor", self.extractor)  # pyright: ignore
                self.playlist_url = data.get("playlist", self.playlist_url)  # pyright: ignore
                self.fetched = True
                self.requester = self.requester
                return True
        return False


class YTDLHandler:
    def __init__(
        self,
        bot: discord.ext.commands.Bot,
        voice_client: discord.VoiceClient | discord.VoiceProtocol,
    ):
        self.bot = bot

        self.voice_client = voice_client

        self.queue: SharedList[Track] = SharedList()

        self.active_track = None

        self.active_playback = None

        self.loop = False

    async def tracks_from_search(self, query: str):
        """
        Search for a query and return the first 5 results
        """

        loop = asyncio.get_event_loop()

        print("Searching for:", query)

        with YoutubeDL(ytdl_search_options) as ytdl:
            data: Any | dict[str, Any | list[Any]] = await loop.run_in_executor(
                None, lambda: ytdl.extract_info(f"ytsearch5:{query}", download=False)
            )
            if data and "entries" in data:
                return [
                    await self.create_track(track, fetch_sts=False)
                    for track in data["entries"]
                ]  # pyright: ignore[reportAny]

        return None

    @staticmethod
    async def create_track(dict_data: dict[str, Any], fetch_sts=True) -> Track | None:
        try:
            if not dict_data:
                return None
            # TODO: maybe need to more key checking
            if "duration" not in dict_data:
                return None
            new_trck = Track.from_dict(dict_data, fetch_sts=fetch_sts)
            print(f"{new_trck=}")
            return new_trck
        except Exception as e:
            print(
                f"Failed to get track info: probably its not a url: {dict_data} with error: {e}"
            )

    @staticmethod
    async def generate_track_or_que_urls(
        url: str,
    ) -> AsyncGenerator[tuple[Coroutine[Any, Any, Track | None], bool], None]:
        loop = asyncio.get_event_loop()
        secondary_plist_url: None | str = None
        secondary_plist_first_track = None

        with YoutubeDL(ytdl_glbl_format_options) as ytdl:
            data_of_urls: (
                Any | dict[str, str | list[Any] | dict[str, Any]]
            ) = await loop.run_in_executor(
                None,
                lambda: ytdl.extract_info(url, download=False),
            )
            if data_of_urls:
                extraction_type = data_of_urls.get("_type", None)
                print(f"{extraction_type=} on url {url=}")
                if "audio_ext" in data_of_urls:
                    print("i think its single file")
                    try:
                        if nw_track := YTDLHandler.create_track(
                            data_of_urls, fetch_sts=True
                        ):
                            yield nw_track, False
                    except Exception as e:
                        print(
                            f"Failed to get track info: probably its not a url: {url} with error: {e}"
                        )
                if "playlist" == extraction_type:
                    print("i think its plylist")
                    for entry in data_of_urls["entries"]:
                        try:
                            if not isinstance(
                                entry,
                                dict,
                            ):
                                continue
                            print(f"has entry {entry=}")
                            if nw_track := YTDLHandler.create_track(
                                entry, fetch_sts=False
                            ):
                                yield nw_track, True
                        except Exception as e:
                            print(
                                f"Failed to get track info: probably its not a url: {entry} with error: {e}"
                            )
                elif extraction_type == "url" and "playlist?" in data_of_urls.get(
                    "url", ""
                ):
                    print("i think its plylist from item url")
                    temp_url = data_of_urls.get("url", None)
                    if isinstance(temp_url, str):
                        secondary_plist_url = temp_url
                    secondary_plist_first_track = None
                    if "watch?v=" in data_of_urls.get("webpage_url", ""):
                        secondary_plist_first_track = data_of_urls.get(
                            "webpage_url", ""
                        )
                        if isinstance(secondary_plist_first_track, str):
                            secondary_plist_first_track = (
                                secondary_plist_first_track.split("&list")[0]
                            )

        if secondary_plist_url:
            results_for_single = None
            if isinstance(secondary_plist_first_track, str):
                results_for_single = (
                    result
                    async for result in YTDLHandler.generate_track_or_que_urls(
                        secondary_plist_first_track
                    )
                )
            for tasks in [
                results_for_single,
                YTDLHandler.generate_track_or_que_urls(secondary_plist_url),
            ]:
                if tasks:
                    for task in tasks:
                        yield task

    @staticmethod
    async def get_new_stream_url(original_url) -> str | None:
        loop = asyncio.get_event_loop()
        if any([invalid in original_url for invalid in ["Unknown"]]):
            return
        with YoutubeDL(ytldl_single_url_options) as ytdl:
            print(f"getting new stream for {original_url=}")
            data = await loop.run_in_executor(
                None,
                lambda: ytdl.extract_info(original_url, download=False),
            )
            if data is None:
                return
            if "enttries" in data:
                raise NotImplementedError("f")
            if isinstance(data, dict):
                new_url = data.get("url", None)
                if new_url:
                    if "Unkown" in new_url:
                        raise NotImplementedError("f")
                    if isinstance(new_url, str):
                        return new_url

    async def search_and_display_buttons(
        self, interaction: discord.Interaction, query: str
    ):
        tracks = await self.tracks_from_search(query)

        if tracks:
            view = PlayButtonView(ytdl_handler=self, tracks=filter(None, tracks))

            await interaction.edit_original_response(view=view)
        else:
            await interaction.edit_original_response(content="No results found.")

    async def handle_track(
        self, interaction: discord.Interaction, track: Track
    ) -> None:
        track.requester = interaction.user

        await self.queue.append(track)
        try:
            await interaction.response.send_message(
                content=f"Added to queue: {track.title} now queue has {len(self.queue)} tracks"
            )

        except discord.errors.InteractionResponded:
            await interaction.edit_original_response(
                content=f"Added to queue: {track.title} now queue has {len(self.queue)} tracks"
            )

        await self.play_next(interaction)

    async def handle_url(
        self,
        interaction: discord.Interaction,
        url: str,
    ) -> None:
        counter = 0

        added_trk_list: list[str | None] = []

        async for new_track_cr, is_plist in self.generate_track_or_que_urls(url):
            new_track = await new_track_cr

            if interaction.is_expired():
                return

            if not new_track:
                await interaction.edit_original_response(
                    content="Failed to get track info."
                )
                continue
            if is_plist:
                counter += 1

                if counter >= 100:
                    await interaction.edit_original_response(
                        content="Playlist is too large, only the first 100 tracks have been added."
                    )
                    break

            await self.handle_track(interaction, new_track)

            added_trk_list.append(new_track.title)

        if len(added_trk_list) > 1:
            await interaction.edit_original_response(
                content=" added tracks to que from playlist\n"
                + "\n".join(
                    f"{indx}. {title}" for indx, title in enumerate(added_trk_list)
                )
            )

            await self.play_next(interaction)

    async def play(
        self, interaction: discord.Interaction, query_or_url: str | None = None
    ) -> None:
        await interaction.edit_original_response(content="Loading...")

        if query_or_url:
            is_url = urlparse(query_or_url).scheme
            if is_url:
                await self.handle_url(interaction, query_or_url)
            else:
                await self.search_and_display_buttons(interaction, query_or_url)

        await self.resume_playback(interaction)

    async def resume_playback(self, interaction: discord.Interaction):
        self.paused = False

        if self.queue and not self.voice_client.is_playing():  # pyright: ignore[reportAttributeAccessIssue]
            await self.play_next(interaction)

    async def play_next(self, interaction: discord.Interaction) -> None:
        if not self.queue:
            print(f"{len(self.queue)=} and {self.queue=} is empty")

            await interaction.edit_original_response(content="Queue is empty.")
            return

        if not self.voice_client.is_connected():  # pyright: ignore[reportAttributeAccessIssue]
            await interaction.edit_original_response(
                content="Not connected to a voice channel."
            )
            return

        if self.voice_client.is_playing():  # pyright: ignore[reportAttributeAccessIssue]
            return

        self.active_track = await self.queue.pop(0)

        if not self.active_track:
            await interaction.edit_original_response(content="No track to play.")
            return
        if (
            self.active_track.data_url is None
            or "Unknown" in self.active_track.data_url
            or not self.active_track.fetched
        ):
            if not await self.active_track.fetch():
                raise NotADirectoryError("should throw some message")

        self.active_playback = discord.FFmpegPCMAudio(
            self.active_track.data_url,
            pipe=False,
            stderr=stderr.buffer,
            **ffmpeg_options,
        )
        try:
            self.voice_client.play(  # pyright: ignore[reportAttributeAccessIssue]
                self.active_playback, after=lambda e: self._play_next(interaction, e)
            )

            self.paused = False

            await interaction.edit_original_response(
                content=f"Playing: {self.active_track.title}"
            )

        except Exception as e:
            print(f"Failed to play track: {e}")

            if "http" in str(e):
                await self.active_track.fetch()
            try:
                self.voice_client.play(  # pyright: ignore[reportAttributeAccessIssue]
                    self.active_playback,
                    after=lambda e: self._play_next(interaction, e),
                )

                self.paused = False

                await interaction.edit_original_response(
                    content=f"Playing: {self.active_track.title}"
                )

            except Exception as e:
                print(f"Failed to play track after refreshing data URL: {e}")
            else:
                await interaction.edit_original_response(
                    content="Failed to play track."
                )

    def _play_next(self, interaction: discord.Interaction, error):
        if error:
            print(f"Player error: {error}")

        if self.loop and self.active_track:
            _ = asyncio.run_coroutine_threadsafe(
                self.queue.append(self.active_track), self.bot.loop
            )

        if self.queue:
            asyncio.run_coroutine_threadsafe(
                self.play_next(interaction=interaction), self.bot.loop
            )

    async def pause(self, interaction: discord.Interaction):
        if self.voice_client.is_playing():  # pyright: ignore[reportAttributeAccessIssue]
            self.voice_client.pause()  # pyright: ignore[reportAttributeAccessIssue]

            self.paused = True

            if self.active_track:
                await interaction.response.send_message(
                    f"Paused: {self.active_track.title}"
                )
            else:
                await interaction.response.send_message("Paused Queue")
        else:
            await interaction.response.send_message("Player is not playing.")

    async def resume(self, interaction: discord.Interaction):
        if self.voice_client.is_paused() or self.paused:  # pyright: ignore[reportAttributeAccessIssue]
            self.voice_client.resume()  # pyright: ignore[reportAttributeAccessIssue]

            self.paused = False

            if self.active_track:
                await interaction.response.send_message(
                    f"Resumed: {self.active_track.title}"
                )
            else:
                await interaction.response.send_message("Resumed Queue")
        else:
            await interaction.response.send_message("Player is not paused.")

    async def stop(self, interaction: discord.Interaction):
        if self.voice_client.is_playing() or self.voice_client.is_paused():  # pyright: ignore[reportAttributeAccessIssue]
            self.voice_client.stop()  # pyright: ignore[reportAttributeAccessIssue]

            await self.queue.clear()

            self.paused = True

            self.active_track = None

            await interaction.response.send_message("Stopped")
        else:
            await interaction.response.send_message("Player is not playing.")

    async def skip(self, interaction: discord.Interaction, count: int | None):
        if self.voice_client.is_playing():  # pyright: ignore[reportAttributeAccessIssue]
            self.voice_client.stop()  # pyright: ignore[reportAttributeAccessIssue]

            if count is None or count == 1:
                trk_title = "Unknown"

                if self.active_track:
                    trk_title = (
                        self.active_track.title
                        if self.active_track.title
                        else trk_title
                    )

                await interaction.response.send_message("Skipped: " + trk_title)
            else:
                trk_titles: list[str] = []

                if count > 0:
                    element_range = range(count - 1)
                else:
                    element_range = range(len(self.queue) - 1, count, -1)
                for indx in element_range:
                    skipped_trk = await self.queue.pop(indx)
                    if skipped_trk:
                        trk_titles.append(f"{indx}. {skipped_trk.title or 'Unkown'}")

                await interaction.response.send_message(
                    f"first {count} items skipped from queuee \n"
                    + "\n".join(trk_titles)
                )

            await self.play(interaction=interaction)
        else:
            await interaction.response.send_message("Player is not playing.")

    async def set_loop(self, interaction: discord.Interaction, loop: bool):
        self.loop = loop

        await interaction.response.send_message(
            f"Looping is {'enabled' if loop else 'disabled'}."
        )

    async def disconnect(self, interaction: discord.Interaction):
        await self.stop(interaction=interaction)

        await self.voice_client.disconnect()

    async def status(self, interaction: discord.Interaction):
        embd_title = "Status"

        embed_msg = discord.Embed(title=embd_title, color=discord.Color.blurple())

        if self.active_track and hasattr(self.voice_client, "timestamp"):
            pos = None
            try:
                pos = self.voice_client.timestamp / 1000000  # pyright: ignore[reportAttributeAccessIssue]
            except Exception as e:
                print(f"{e=} on timestamp calc")

            embed_msg = self.active_track.msg_embed(
                position=pos,
                title=embd_title,
                queue=self.queue,
            )
        else:
            embed_msg = embed_msg.add_field(name="Currently playing", value="Nothing")

        await interaction.response.send_message(embed=embed_msg)

    async def show_queue(
        self, interaction: discord.Interaction, is_followup: bool = False
    ) -> None:
        embed = discord.Embed(title="Queue", color=discord.Color.blurple())

        if self.queue:
            embed = embed.add_field(
                name="Currently playing",
                value=self.active_track.title if self.active_track else "Nothing",
            ).add_field(
                name="Queue",
                value="\n".join(
                    [f"{i+1}. {track.title}" for i, track in enumerate(self.queue)]
                ),
            )
        else:
            embed = embed.add_field(name="Queue", value="Empty")

        if is_followup:
            await interaction.followup.send(embed=embed)
            return

        await interaction.response.send_message(embed=embed)

    async def clear_queue(self, interaction: discord.Interaction) -> None:
        await self.queue.clear()

        await interaction.response.send_message("Queue cleared.")
