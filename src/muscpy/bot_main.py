import asyncio
from collections.abc import Iterable
from typing import Any

import discord
from discord import (
    Intents,
    Member,
    VoiceChannel,
    VoiceClient,
    VoiceProtocol,
    app_commands,
)
from discord.abc import Connectable
from discord.ext import commands
from discord.shard import EventItem

from muscpy.idle_checker import IdleChecker
from muscpy.load_env import get_env
from muscpy.utils import SharedDict, get_voice_client, not_guild
from muscpy.yt_dlp_streamer import YTDLHandler

intents = discord.Intents.default()
intents.message_content = True


class MusicBot(commands.Bot):
    def __init__(
        self,
        description: str,
        intents: Intents,
        *args: Iterable[Any],
        **kwargs: dict[str, Any],
    ):
        super().__init__(
            command_prefix="!0_",
            description=description,
            intents=intents,
            *args,
            **kwargs,
        )
        self.musicHandlerPool: SharedDict[str, YTDLHandler] = SharedDict()
        self.idleChecker = IdleChecker()
        self.idle_task: asyncio.Task[None] | None = None
        self.tree_synced = False


bot = MusicBot(
    description="Relatively simple music bot example",
    intents=intents,
)


@bot.tree.command()
async def echo(interaction: discord.Interaction, message: str) -> None:
    """
    Echoes a message.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    message : str
        The message to echo.
    """
    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command()
async def ping(interaction: discord.Interaction) -> None:
    """
    Pong!

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    """
    # bot.latency is in seconds
    await interaction.response.send_message(f"Pong! {bot.latency * 1000:.0f}ms")


async def join_vc(
    interaction: discord.Interaction,
    channel: discord.VoiceChannel | None,
) -> tuple[VoiceChannel | Connectable, VoiceProtocol] | None:
    if await not_guild(interaction):
        return None

    if channel is None:
        if isinstance(interaction.user, Member):
            if interaction.user.voice is None:
                await interaction.response.send_message(
                    "You are not connected to a voice channel.", ephemeral=True
                )
                return None
            if isinstance(interaction.user.voice.channel, VoiceChannel):
                channel = interaction.user.voice.channel

    if not isinstance(channel, discord.VoiceChannel):
        await interaction.response.send_message(
            "Please provide a valid voice channel.", ephemeral=True
        )
        return None
    if interaction.guild is None:
        await interaction.response.send_message(
            "Bot currently only supports guilds", ephemeral=True
        )
        return None

    if interaction.guild.voice_client is not None:
        if interaction.guild.voice_client.channel == channel:
            # every interaction must be answered, or Discord shows "did not respond"
            await interaction.response.send_message(
                f"Already in {channel.name}", ephemeral=True
            )
            if isinstance(interaction.channel, discord.TextChannel):
                await bot.idleChecker.init_idle_state_for_client(
                    str(interaction.guild.id),
                    interaction.guild.voice_client,
                    interaction.channel,
                    None,
                )
            return (
                interaction.guild.voice_client.channel,
                interaction.guild.voice_client,
            )  # type: ignore

        await interaction.guild.voice_client.disconnect(force=False)

    try:
        voice_client = await channel.connect()
        await interaction.response.send_message(
            f"Joined {channel.name}", ephemeral=True
        )
        if isinstance(interaction.channel, discord.TextChannel):
            await bot.idleChecker.init_idle_state_for_client(
                str(interaction.guild.id), voice_client, interaction.channel, None
            )
        return channel, voice_client
    except discord.errors.ClientException:
        await interaction.response.send_message(
            "I'm already connected to a voice channel.", ephemeral=True
        )
        return None
    except discord.errors.Forbidden:
        await interaction.response.send_message(
            "I don't have permission to join the voice channel.", ephemeral=True
        )
        return None
    except Exception as e:
        await interaction.response.send_message(
            f"An error occurred: {e}", ephemeral=True
        )
        return None


@bot.tree.command()
async def join(
    interaction: discord.Interaction, channel: discord.VoiceChannel | None
) -> None:
    """
    Joins a voice channel.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    channel : discord.VoiceChannel | None
        The voice channel to join.
    """
    _ = await join_vc(interaction, channel)


@bot.tree.command()
async def leave(interaction: discord.Interaction) -> None:
    """
    Leaves the voice channel.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    """
    if interaction.guild is None:
        await interaction.response.send_message("Bot currently only supports guilds")
        return
    if interaction.guild.voice_client is not None:
        await interaction.guild.voice_client.disconnect(force=False)
    await bot.idleChecker.deinit_idlestate_of_client(guild_id=str(interaction.guild.id))
    await interaction.response.send_message("Left voice channel", ephemeral=True)


@bot.tree.command()
async def help(interaction: discord.Interaction) -> None:
    """
    Shows the help message.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    """
    slash_commands = await bot.tree.fetch_commands()
    # create a embed message

    embed = discord.Embed(
        title="Commands",
        description="List of all commands",
        color=discord.Color.green(),
    )
    for command in slash_commands:
        embed = embed.add_field(
            name=command.name, value=command.description, inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(
    name="ensure_voice", description="Ensure the bot is connected to a voice channel"
)
async def ensure_voice_cmd(
    interaction: discord.Interaction, voice_ch: VoiceChannel | None = None
) -> VoiceProtocol | VoiceClient | None:
    """
    Ensures the bot is connected to a voice channel.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    voice_ch : VoiceChannel | None, optional
        The voice channel to join, by default None.

    Returns
    -------
    VoiceChannel | None
        The voice channel the bot is connected to. If the bot is not connected to a voice channel, returns None.
    """
    if await not_guild(interaction):
        return None
    voice_cl = await get_voice_client(interaction, voice_ch, quiet=False)
    if voice_ch is None or voice_cl is None:
        return None
    return voice_cl


class Manage(commands.Cog):
    # hidden from / unusable by members without Manage Messages by default
    group = app_commands.Group(
        name="manage",
        description="Manage commands",
        default_permissions=discord.Permissions(manage_messages=True),
        guild_only=True,
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @group.command(name="clean", description="Cleans the chat")
    async def clean(self, interaction: discord.Interaction, limit: int) -> None:
        """
        cleans the chat

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        limit : int
            The number of messages to delete.
        """

        # server admins can override default_permissions per channel/role,
        # so check the caller's real permissions here too
        if (
            not isinstance(interaction.user, Member)
            or not interaction.permissions.manage_messages
        ):
            await interaction.response.send_message(
                "You need the Manage Messages permission to use this.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "I am trying to delete messages of this channel ...", ephemeral=True
        )

        if not isinstance(interaction.channel, discord.TextChannel):
            _ = await interaction.edit_original_response(
                content="This command only works in text channels."
            )
            return

        if limit > 100:
            _ = await interaction.edit_original_response(
                content="You can only delete up to 100 messages at a time."
            )
            return
        if limit < 1:
            limit = 1

        try:
            # purge() handles bulk-delete limits (e.g. messages older than 14 days)
            messages_snfl = await interaction.channel.purge(limit=limit)
            _ = await interaction.edit_original_response(
                content=f"Deleted {len(messages_snfl)} messages."
            )
        except (
            discord.errors.Forbidden,
            discord.errors.HTTPException,
            discord.errors.NotFound,
            discord.errors.ClientException,
        ) as e:
            # only response with the error type
            _ = await interaction.edit_original_response(
                content=f"An error occurred: {e}"
            )


###########


@bot.tree.command(name="play", description="Play a song from url or search")
async def play_cmd(
    interaction: discord.Interaction,
    query_or_url: str,
    voice_ch: discord.VoiceChannel | None = None,
) -> None:
    """
    Plays a song | songs.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    query_or_url : str
        The query to search for or the URL of the song to play.
    voice_ch : discord.VoiceChannel | None
        The voice channel to connect to if not specified it will try to connect to the voice channel of the user who invoked the command.
    """
    return await play(interaction, query_or_url=query_or_url, voice_ch=voice_ch)


async def play(
    interaction: discord.Interaction,
    query_or_url: str | None = None,
    voice_ch: discord.VoiceChannel | None = None,
    edit_msg: bool = False,
) -> None:
    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id)  # type: ignore

    # Defer before anything slow (voice connect, yt-dlp). After this the
    # interaction is answered, so only edit_original_response may be used;
    # response.send_message / response.edit_message would raise InteractionResponded.
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        voice_client = await get_voice_client(interaction, voice_ch, quiet=True)
    except Exception as e:
        print(f"voice connect error: {e!r}")
        voice_client = None

    if voice_client is None:
        await interaction.edit_original_response(
            content="I have issues connecting to the voice channel"
        )
        return None

    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)
    query_or_url = query_or_url.strip() if query_or_url is not None else None

    if guild_music_hndlr is None:
        try:
            guild_music_hndlr = YTDLHandler(bot=bot, voice_client=voice_client)  # type: ignore
        except Exception:
            await interaction.edit_original_response(
                content="Error initializing music handler"
            )
            return None
        await bot.musicHandlerPool.set(guild_id, guild_music_hndlr)

    if not guild_music_hndlr.voice_client.is_connected():  # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType]
        guild_music_hndlr.voice_client.cleanup()
        guild_music_hndlr.voice_client = voice_client

    if isinstance(interaction.channel, discord.TextChannel):
        await bot.idleChecker.init_idle_state_for_client(
            guild_id,
            voice_client,
            interaction.channel,
            guild_music_hndlr,
        )

    # from now on we edit the message instead responding
    try:
        await guild_music_hndlr.play(interaction=interaction, query_or_url=query_or_url)
    except Exception as e:
        print(f"play error: {e!r}")
        await interaction.edit_original_response(content="Error playing the song")
        return None
    return None


@bot.tree.command(name="stop", description="stop song and clear the queue")
async def stop(interaction: discord.Interaction) -> None:
    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id)  # type: ignore

    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)
    if guild_music_hndlr is None:
        await interaction.response.send_message("Nothing to stop", ephemeral=True)
        return
    await guild_music_hndlr.stop(interaction=interaction)


@bot.tree.command(name="pause", description="pause the current song")
async def pause(interaction: discord.Interaction) -> None:
    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id)

    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)

    if guild_music_hndlr is None:
        await interaction.response.send_message("Nothing to pause")
        return
    await guild_music_hndlr.pause(interaction=interaction)


@bot.tree.command(name="resume", description="resume the current song")
async def resume(interaction: discord.Interaction) -> None:
    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id)

    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)

    if guild_music_hndlr is None:
        await interaction.response.send_message("Nothing to resume", ephemeral=True)
        return
    await guild_music_hndlr.resume(interaction=interaction)


@bot.tree.command(name="skip", description="skip the current song or songs")
async def skip(interaction: discord.Interaction, count: int | None) -> None:
    """
    Skips a song | songs.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    count : int | None
        count of skipped objects, starts from first elements of queue if positive
    """

    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id)

    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)

    if guild_music_hndlr is None:
        await interaction.response.send_message("Nothing to skip", ephemeral=True)
        return
    await guild_music_hndlr.skip(interaction=interaction, count=count)


async def set_loop(interaction: discord.Interaction, loop: bool) -> None:
    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id)

    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)

    if guild_music_hndlr is None:
        await interaction.response.send_message("Nothing to set loop", ephemeral=True)
        return
    guild_music_hndlr.loop = loop
    await interaction.response.send_message(f"Loop set to {loop}", ephemeral=True)


@bot.tree.command(name="loop", description="loop the current song")
async def loop(interaction: discord.Interaction) -> None:
    await set_loop(interaction, loop=True)


@bot.tree.command(name="unloop", description="unloop the current song")
async def unloop(interaction: discord.Interaction) -> None:
    await set_loop(interaction, loop=False)


@bot.tree.command(name="queue", description="show the current queue")
async def queue(interaction: discord.Interaction) -> None:
    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id)

    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)

    if guild_music_hndlr is None:
        await interaction.response.send_message("Nothing in the queue", ephemeral=True)
        return
    await guild_music_hndlr.show_queue(interaction=interaction)


@bot.tree.command(
    name="disconnect", description="disconnect the bot from the voice channel"
)
async def disconnect(interaction: discord.Interaction) -> None:
    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id)

    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)

    if guild_music_hndlr is None:
        # don't use get_voice_client here: it would *connect* first
        vc = interaction.guild.voice_client if interaction.guild else None
        if vc is not None:
            await vc.disconnect(force=False)
            await interaction.response.send_message("Disconnected", ephemeral=True)
        else:
            await interaction.response.send_message(
                "I'm not in a voice channel", ephemeral=True
            )
        return
    await guild_music_hndlr.disconnect(interaction=interaction)
    await bot.musicHandlerPool.delete(guild_id)
    await bot.idleChecker.deinit_idlestate_of_client(guild_id)


@bot.tree.command(name="status", description="show the current status of the bot")
async def status(interaction: discord.Interaction) -> None:
    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id)

    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)

    if guild_music_hndlr is None:
        await interaction.response.send_message("Nothing to show", ephemeral=True)
        return
    await guild_music_hndlr.status(interaction=interaction)


@bot.tree.command(name="clear", description="clear the current queue")
async def clear(interaction: discord.Interaction) -> None:
    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id)

    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)

    if guild_music_hndlr is None:
        await interaction.response.send_message("Nothing to clear", ephemeral=True)
        return
    await guild_music_hndlr.clear_queue(interaction=interaction)


@bot.event
async def on_ready():
    if bot.user is None:
        print("Bot is not logged in")
        exit(1)
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    # on_ready fires again after reconnects; only sync / start the loop once.
    # (a 2nd idle loop made idle timers count down twice as fast)
    if not bot.tree_synced:
        bot_commands = await bot.tree.sync()
        bot.tree_synced = True
        print("Command tree synced with Discord")
        print(" all commands")
        print(bot_commands)
    print("------ Bot is ready ------")

    game = discord.Game("with the variables and processes")
    await bot.change_presence(status=discord.Status.idle, activity=game)

    if bot.idle_task is None or bot.idle_task.done():
        bot.idle_task = asyncio.create_task(bot.idleChecker.run_idle_loop())


@bot.event
async def on_error(event: EventItem, *args: Iterable[Any], **kwargs: dict[Any, Any]):
    print(f"An error occurred in {event}: {args} {kwargs}")


async def main():
    bot_token = get_env("DCBOT_TOKEN", ".env")
    if not bot_token:
        raise SystemExit(
            "DCBOT_TOKEN is not set (environment variable or .env file)"
        )
    async with bot:
        await bot.add_cog(Manage(bot))
        await bot.start(bot_token)


if __name__ == "__main__":
    asyncio.run(main())
