import asyncio
from collections.abc import AsyncIterator

import discord
from discord import (Member, VoiceChannel, VoiceClient, VoiceProtocol,
                     app_commands)
from discord.ext import commands

from load_env import get_all_envs  # for bot token
from utils import SharedDict, get_voice_client, not_guild
from yt_dlp_streamer import Track, YTDLHandler

intents = discord.Intents.default()
intents.message_content = True

class MusicBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.musicHandlerPool : SharedDict[str, YTDLHandler] = SharedDict()

bot = MusicBot(
    command_prefix=commands.when_mentioned_or("!"),
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
    await interaction.response.send_message(message)


@bot.tree.command()
async def ping(interaction: discord.Interaction) -> None:
    """
    Pong!

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    """
    await interaction.response.send_message("Pong!" + str(bot.latency) + "ms")

async def join_vc(interaction: discord.Interaction, channel: discord.VoiceChannel | None, quiet=False) -> tuple[VoiceChannel,VoiceProtocol] | None:
    if await not_guild(interaction):
        return None

    if channel is None:
        if isinstance(interaction.user, Member):
            if interaction.user.voice is None:
                await interaction.response.send_message("You are not connected to a voice channel.")
                return None
            channel = interaction.user.voice.channel # type: ignore
    
    if not isinstance(channel, discord.VoiceChannel):
        await interaction.response.send_message("Please provide a valid voice channel.")
        return None
    if interaction.guild is None:
        await interaction.response.send_message("Bot currently only supports guilds")
        return None

    if interaction.guild.voice_client is not None:
        if interaction.guild.voice_client.channel == channel:
            return interaction.guild.voice_client.channel , interaction.guild.voice_client # type: ignore

        await interaction.guild.voice_client.disconnect(force=False)

    try:
        voice_client = await channel.connect()
        await interaction.response.send_message(f"Joined {channel.name}")
        return channel , voice_client
    except discord.errors.ClientException:
        await interaction.response.send_message("I'm already connected to a voice channel.")
        return None
    except discord.errors.Forbidden:
        await interaction.response.send_message("I don't have permission to join the voice channel.")
        return None
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}")
        return None
   
@bot.tree.command()
async def join(interaction: discord.Interaction, channel: discord.VoiceChannel | None) -> None:
    """
    Joins a voice channel.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    channel : discord.VoiceChannel | None
        The voice channel to join.
    """
    await join_vc(interaction, channel)

       
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
    await interaction.response.send_message("Left voice channel")


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

    embed = discord.Embed(title="Commands", description="List of all commands", color=discord.Color.green())
    for command in slash_commands:
        embed.add_field(name=command.name, value=command.description, inline=False)
    await interaction.response.send_message(embed=embed)




@bot.tree.command(name="ensure_voice", description="Ensure the bot is connected to a voice channel")
async def ensure_voice_cmd(interaction: discord.Interaction, voice_ch: VoiceChannel | None = None) -> VoiceProtocol | VoiceClient | None:
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
    group = app_commands.Group(name="manage",description="Manage commands")
    def __init__(self,bot:commands.Bot) -> None:
        self.bot = bot
        super().__init__()
    
    @group.command(name="clean",description="Cleans the chat")
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

        await interaction.response.send_message("I am trying to delete messages of this channel ...")
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.edit_original_response(content="This command only works in text channels.")
            return

        if limit > 100:
            await interaction.edit_original_response(content="You can only delete up to 100 messages at a time.")
            return
        if limit < 1:
            limit = 1

        messages :AsyncIterator[discord.Message]= interaction.channel.history(limit=limit)
        # make it snow flake iterable
        messages_snfl = [message async for message in messages]
        try:
            await interaction.channel.delete_messages(messages_snfl)
            await interaction.edit_original_response(content=f"Deleted {len(messages_snfl)} messages.")
        except (discord.errors.Forbidden, discord.errors.HTTPException, discord.errors.NotFound, discord.errors.ClientException) as e:
            # only response with the error type 
            await interaction.edit_original_response(content=f"An error occurred: {e}")



###########

@bot.tree.command(name="play", description="Play a song from url or search or resume the current song")
async def play_cmd(interaction: discord.Interaction, query_or_url: str|None = None
               ,voice_ch: discord.VoiceChannel|None = None) -> None:
    """
    Plays a song.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    query_or_url : str | None
        The query to search for or the URL of the song to play. If None, it will resume the current song.
    voice_ch : discord.VoiceChannel | None
        The voice channel to connect to if not specified it will try to connect to the voice channel of the user who invoked the command.
    """
    return await play(interaction, query_or_url=query_or_url, voice_ch=voice_ch)



async def play(interaction: discord.Interaction, query_or_url: str|None = None
               ,voice_ch: discord.VoiceChannel|None = None,edit_msg:bool=False) -> None:
    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id) # type: ignore
    
    voice_client = await get_voice_client(interaction, voice_ch, quiet=True)

    if voice_client is None:
        if not edit_msg:
            await interaction.response.send_message("I have issues connecting to the voice channel")
        await interaction.response.edit_message(content="I have issues connecting to the voice channel")
        return None
    
    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)
    query_or_url = query_or_url.strip() if query_or_url is not None else None
    
    #
    if query_or_url is None or query_or_url == "":
        if guild_music_hndlr is not None:
            await guild_music_hndlr.resume(interaction=interaction)
        else:
            if not edit_msg:
                await interaction.response.send_message("Nothing to play")
            await interaction.response.edit_message(content="Nothing to play")
        return None
    #
    
    #
    await interaction.response.defer()

    if guild_music_hndlr is None:
        try:
            guild_music_hndlr = YTDLHandler(bot=bot, voice_client=voice_client) # type: ignore
        except Exception:
            if not edit_msg:
                await interaction.response.send_message("Error initializing music handler")
            await interaction.response.edit_message(content="Error initializing music handler")
            return None
        await bot.musicHandlerPool.set(guild_id, guild_music_hndlr)
    #

    # from now on we edit the message instead responding
    try:
        await guild_music_hndlr.play(interaction=interaction, query_or_url=query_or_url)
    except Exception as e:
        print(e)
        await interaction.response.edit_message(content="Error playing the song")
        return None
    return None

@bot.tree.command(name="stop", description="stop song and clear the queue")
async def stop(interaction: discord.Interaction) -> None:
    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id) # type: ignore
    
    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)
    if guild_music_hndlr is None:
        await interaction.response.send_message("Nothing to stop")
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
        await interaction.response.send_message("Nothing to resume")
        return
    await guild_music_hndlr.resume(interaction=interaction)

@bot.tree.command(name="skip", description="skip the current song")
async def skip(interaction: discord.Interaction) -> None:
    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id)

    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)

    if guild_music_hndlr is None:
        await interaction.response.send_message("Nothing to skip")
        return
    await guild_music_hndlr.skip(interaction=interaction)

async def set_loop(interaction: discord.Interaction,loop:bool) -> None:
    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id)

    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)

    if guild_music_hndlr is None:
        await interaction.response.send_message("Nothing to set loop")
        return
    guild_music_hndlr.loop = loop
    await interaction.response.send_message(f"Loop set to {loop}")

@bot.tree.command(name="loop", description="loop the current song")
async def loop(interaction: discord.Interaction) -> None:
    await set_loop(interaction,loop=True)

@bot.tree.command(name="unloop", description="unloop the current song")
async def unloop(interaction: discord.Interaction) -> None:
    await set_loop(interaction,loop=False)

@bot.tree.command(name="queue", description="show the current queue")
async def queue(interaction: discord.Interaction) -> None:
    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id)

    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)

    if guild_music_hndlr is None:
        await interaction.response.send_message("Nothing in the queue")
        return
    await guild_music_hndlr.show_queue(interaction=interaction)

@bot.tree.command(name="disconnect", description="disconnect the bot from the voice channel")
async def disconnect(interaction: discord.Interaction) -> None:
    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id)

    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)

    if guild_music_hndlr is None:
        vc = await  get_voice_client(interaction, quiet=True)
        if vc is not None:
            await vc.disconnect()
        return
    await guild_music_hndlr.disconnect(interaction=interaction)

@bot.tree.command(name="status", description="show the current status of the bot")
async def status(interaction: discord.Interaction) -> None:
    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id)

    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)

    if guild_music_hndlr is None:
        await interaction.response.send_message("Nothing to show")
        return
    await guild_music_hndlr.status(interaction=interaction)

@bot.tree.command(name="clear", description="clear the current queue")
async def clear(interaction: discord.Interaction) -> None:
    if await not_guild(interaction):
        return None
    guild_id = str(interaction.guild_id)

    guild_music_hndlr = await bot.musicHandlerPool.get(guild_id)

    if guild_music_hndlr is None:
        await interaction.response.send_message("Nothing to clear")
        return
    await guild_music_hndlr.clear_queue(interaction=interaction)


@bot.event
async def on_ready():
    if bot.user is None:
        print("Bot is not logged in")
        exit(1)
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.tree.sync()
    print("Command tree synced with Discord")
    print("------ Bot is ready ------")
    print(" all commands")
    print(bot.commands)
    print("------")
    print(" all cogs")
    print(bot.cogs)
    print("------")

    print(" all slash commands")
    print(bot.all_commands)
    print("------")

@bot.event
async def on_error(event, *args, **kwargs):
    print(f"An error occurred in {event}: {args} {kwargs}")

async def main():
    bot_token = get_all_envs(".env")["BOT_TOKEN"]
    # activity_game = discord.Game(name="cool music")
    # activty = discord.Activity(status=discord.Status.idle, type=discord.ActivityType.playing, name="cool music")
    async with bot:
        await bot.add_cog(Manage(bot))
        await bot.start(bot_token)


if __name__ == "__main__":
    asyncio.run(main())
