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
from yt_dlp import YoutubeDL

from muscpy.utils import SharedList

try:
    # newer yt-dlp moved std_headers out of the top-level package
    from yt_dlp.utils.networking import std_headers as ytdl_headers
except ImportError:  # older yt-dlp
    from yt_dlp import std_headers as ytdl_headers  # pyright: ignore

from yt_dlp.utils.networking import random_user_agent


class PlayButton(discord.ui.Button["PlayButtonView"]):
    def __init__(self, ytdl_handler: YTDLHandler, track: Track, indx: int = 0):
        super().__init__(
            label=str(indx),
            style=discord.ButtonStyle.primary,
        )

        self.ytdl_handler = ytdl_handler

        self.track = track

    @override
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"from_query Playing: {self.track.title[:40] if self.track.title else "unknown"} \nurl: {self.track.original_url}",
            ephemeral=True,
        )

        if not hasattr(self.ytdl_handler, "handle_track"):
            await interaction.followup.send(
                "Internal error: Handler does not have handle_track method",
                ephemeral=True,
            )
            return

        await self.ytdl_handler.handle_track(interaction, self.track)


class PlayButtonView(discord.ui.View):
    def __init__(self, ytdl_handler: YTDLHandler, tracks: Iterable[Track]):
        super().__init__()

        self.tracks = tracks
        self.trk_list: list[str] = []

        for indx, track in enumerate(tracks, 0):
            # parenthesised: the index was dropped for untitled tracks
            _ = self.trk_list.append(
                f"{indx}. " + (track.title[:70] if track.title else "Unknown Title")
            )
            _ = self.add_item(PlayButton(ytdl_handler, track, indx))


ytdl_headers["User-Agent"] = random_user_agent()


common_ytdl_options = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "geo_bypass": True,
    "nocheckcertificate": False,
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


def format_queue(queue: Iterable[Track], limit: int = 1024) -> str:
    """Numbered queue listing that fits in one embed field (max 1024 chars)."""
    lines: list[str] = []
    tracks = list(queue)
    used = 0
    for i, track in enumerate(tracks):
        line = f"{i + 1}. {(track.title or 'Unknown')[:80]}"
        more = f"... and {len(tracks) - i} more"
        if used + len(line) + 1 + len(more) > limit:
            lines.append(more)
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines) or "Empty"


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
            embed = embed.add_field(name="Position", value=f"{position:.2f}")
        if self.playlist_url:
            embed = embed.add_field(name="orginal playlist", value=self.playlist_url)

        if queue:
            embed = embed.add_field(name="Queue", value=format_queue(queue))

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
        # prefer the page url: stream urls (data_url) expire
        if self.original_url and self.original_url != "Unknown":
            source_url = self.original_url
        elif self.data_url and self.data_url != "Unknown":
            source_url = self.data_url
        else:
            return False
        with YoutubeDL(ytldl_single_url_options) as ytdl:
            data = await loop.run_in_executor(
                None,
                lambda: ytdl.extract_info(source_url, download=False),
            )
            if data is None:
                return False
            if "entries" in data:
                entries = [e for e in data["entries"] if e]
                if not entries:
                    return False
                data = entries[0]
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

        self.paused = False

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
        except Exception as e:  # noqa: BLE001 - one bad track must not stop playback
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
                    except Exception as e:  # noqa: BLE001 - one bad track must not stop playback
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
                        except Exception as e:  # noqa: BLE001 - one bad track must not stop playback
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
            # watch?v=X&list=Y: first the video itself, then the playlist
            if isinstance(secondary_plist_first_track, str):
                async for result in YTDLHandler.generate_track_or_que_urls(
                    secondary_plist_first_track
                ):
                    yield result
            async for result in YTDLHandler.generate_track_or_que_urls(
                secondary_plist_url
            ):
                yield result

    @staticmethod
    async def get_new_stream_url(original_url) -> str | None:
        loop = asyncio.get_event_loop()
        if "Unknown" in original_url:
            return
        with YoutubeDL(ytldl_single_url_options) as ytdl:
            print(f"getting new stream for {original_url=}")
            data = await loop.run_in_executor(
                None,
                lambda: ytdl.extract_info(original_url, download=False),
            )
            if data is None:
                return
            if "entries" in data:
                entries = [e for e in data["entries"] if e]
                if not entries:
                    return None
                data = entries[0]
            if isinstance(data, dict):
                new_url = data.get("url", None)
                if new_url:
                    if "Unknown" in new_url:
                        raise NotImplementedError("f")
                    if isinstance(new_url, str):
                        return new_url

    async def search_and_display_buttons(
        self, interaction: discord.Interaction, query: str
    ):
        tracks = await self.tracks_from_search(query)

        if tracks:
            view = PlayButtonView(ytdl_handler=self, tracks=filter(None, tracks))
            content = "\n".join(view.trk_list)

            await interaction.edit_original_response(content=content, view=view)
        else:
            await interaction.edit_original_response(content="No results found.")

    async def handle_track(
        self, interaction: discord.Interaction, track: Track
    ) -> None:
        track.requester = interaction.user

        await self.queue.append(track)
        try:
            await interaction.response.send_message(
                content=f"Added to queue: {track.title} now queue has {len(self.queue)} tracks",
                ephemeral=True,
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

                if counter > 100:
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
        ) and not await self.active_track.fetch():
            await self._safe_edit(interaction, "have some struggles with youtube")
            # skip the broken track instead of feeding ffmpeg a bad url
            return await self.play_next(interaction)

        for attempt in range(2):
            try:
                # a fresh source each attempt: a failed one can't be reused
                self.active_playback = discord.FFmpegPCMAudio(
                    self.active_track.data_url,
                    pipe=False,
                    stderr=stderr.buffer,
                    **ffmpeg_options,
                )
                self.voice_client.play(  # pyright: ignore[reportAttributeAccessIssue]
                    self.active_playback,
                    after=lambda e: self._play_next(interaction, e),
                )
            except Exception as e:  # noqa: BLE001 - one bad track must not stop playback
                print(f"Failed to play track (attempt {attempt + 1}): {e}")
                if attempt == 0:
                    await self._safe_edit(
                        interaction, "have networking issue retrying"
                    )
                    await self.active_track.fetch()
                    continue
                await self._safe_edit(interaction, "Failed to play track.")
                return
            self.paused = False
            await self._safe_edit(
                interaction, f"Playing: {self.active_track.title}"
            )
            return

    @staticmethod
    async def _safe_edit(interaction: discord.Interaction, content: str) -> None:
        # interaction tokens expire after 15 minutes; a long queue outlives them
        try:
            await interaction.edit_original_response(content=content)
        except discord.HTTPException as e:
            print(f"could not edit interaction message: {e}")

    def _play_next(self, interaction: discord.Interaction, error):
        # called by discord.py from the audio player thread
        if error:
            print(f"Player error: {error}")
        asyncio.run_coroutine_threadsafe(
            self._after_track(interaction, error), self.bot.loop
        )

    async def _after_track(self, interaction: discord.Interaction, error) -> None:
        if error:
            await self._safe_edit(interaction, "probably networking (youtube) issue")
        # re-queue first, then check the queue, in one coroutine; before, the
        # emptiness check could run before the append and looping stopped
        if self.loop and self.active_track:
            await self.queue.append(self.active_track)
        if self.queue:
            await self.play_next(interaction=interaction)

    async def pause(self, interaction: discord.Interaction):
        if self.voice_client.is_playing():  # pyright: ignore[reportAttributeAccessIssue]
            self.voice_client.pause()  # pyright: ignore[reportAttributeAccessIssue]

            self.paused = True

            if self.active_track:
                await interaction.response.send_message(
                    f"Paused: {self.active_track.title}", ephemeral=True
                )
            else:
                await interaction.response.send_message("Paused Queue", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Player is not playing.", ephemeral=True
            )

    async def resume(self, interaction: discord.Interaction):
        if self.voice_client.is_paused() or self.paused:  # pyright: ignore[reportAttributeAccessIssue]
            self.voice_client.resume()  # pyright: ignore[reportAttributeAccessIssue]

            self.paused = False

            if self.active_track:
                await interaction.response.send_message(
                    f"Resumed: {self.active_track.title}", ephemeral=True
                )
            else:
                await interaction.response.send_message("Resumed Queue")
        else:
            await interaction.response.send_message(
                "Player is not paused.", ephemeral=True
            )

    async def stop(
        self,
        interaction: discord.Interaction | None = None,
    ):
        await self.queue.clear()
        if self.voice_client.is_playing() or self.voice_client.is_paused():  # pyright: ignore[reportAttributeAccessIssue]
            self.active_track = None
            self.paused = True
            self.voice_client.stop()  # pyright: ignore[reportAttributeAccessIssue]
            if interaction:
                await interaction.response.send_message("Stopped", ephemeral=True)
        else:
            if interaction:
                await interaction.response.send_message(
                    "Player is not playing.", ephemeral=True
                )

    async def skip(self, interaction: discord.Interaction, count: int | None):
        if self.voice_client.is_playing() or self.voice_client.is_paused():  # pyright: ignore[reportAttributeAccessIssue]
            if count is None or count == 1 or count == 0:
                trk_title = "Unknown"

                if self.active_track:
                    trk_title = (
                        self.active_track.title
                        if self.active_track.title
                        else trk_title
                    )

                await interaction.response.send_message(
                    "Skipped: " + trk_title, ephemeral=True
                )
            else:
                trk_titles: list[str] = []
                # positive: current track + next (count-1) from the front
                # negative: remove |count| tracks from the end of the queue
                pop_index = 0 if count > 0 else -1
                n_to_remove = count - 1 if count > 0 else -count
                for _ in range(n_to_remove):
                    skipped_trk = await self.queue.pop(pop_index)
                    if skipped_trk is None:
                        break
                    trk_titles.append(skipped_trk.title or "Unknown")

                where = "first" if count > 0 else "last"
                await interaction.response.send_message(
                    f"{where} {abs(count)} items skipped from queue\n"
                    + "\n".join(f"{i}. {t}" for i, t in enumerate(trk_titles, 1)),
                    ephemeral=True,
                )

            if count is None or count >= 0:
                # the after-callback of stop() starts the next track
                self.voice_client.stop()  # pyright: ignore[reportAttributeAccessIssue]
        else:
            await interaction.response.send_message(
                "Player is not playing.", ephemeral=True
            )

    async def set_loop(self, interaction: discord.Interaction, loop: bool):
        self.loop = loop

        await interaction.response.send_message(
            f"Looping is {'enabled' if loop else 'disabled'}.", ephemeral=True
        )

    async def disconnect(self, interaction: discord.Interaction | None = None):
        await self.stop(interaction=interaction)

        await self.voice_client.disconnect()
        self.voice_client.cleanup()

    async def status(self, interaction: discord.Interaction):
        embd_title = "Status"

        embed_msg = discord.Embed(title=embd_title, color=discord.Color.blurple())

        if self.active_track and hasattr(self.voice_client, "timestamp"):
            pos = None
            try:
                pos = self.voice_client.timestamp / 1000000  # pyright: ignore[reportAttributeAccessIssue]
            except (AttributeError, TypeError) as e:
                print(f"{e=} on timestamp calc")

            embed_msg = self.active_track.msg_embed(
                position=pos,
                title=embd_title,
                queue=self.queue,
            )
        else:
            embed_msg = embed_msg.add_field(name="Currently playing", value="Nothing")

        await interaction.response.send_message(embed=embed_msg, ephemeral=True)

    async def show_queue(
        self, interaction: discord.Interaction, is_followup: bool = False
    ) -> None:
        embed = discord.Embed(title="Queue", color=discord.Color.blurple())

        if self.queue:
            embed = embed.add_field(
                name="Currently playing",
                value=self.active_track.title if self.active_track else "Nothing",
            ).add_field(name="Queue", value=format_queue(self.queue))
        else:
            embed = embed.add_field(name="Queue", value="Empty")

        if is_followup:
            await interaction.followup.send(embed=embed)
            return

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def clear_queue(self, interaction: discord.Interaction) -> None:
        await self.queue.clear()

        await interaction.response.send_message("Queue cleared.", ephemeral=True)
