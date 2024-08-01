import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any
import discord

from yt_dlp_streamer import YTDLHandler

from discord import Member, VoiceChannel, VoiceClient, VoiceProtocol, VoiceState, app_commands
from discord.ext import commands

from load_env import get_all_envs  # for bot token

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("!"),
    description="Relatively simple music bot example",
    intents=intents,
)

command_tree = bot.tree

# TODO : rewrite try except blocks for better error handling


async def not_guild_response(interaction:discord.Interaction) -> bool:
    # if the interaction is not from a guild
    if interaction.guild is None:
        await interaction.response.send_message("Bot currently only supports guilds")
        return True
    return False

# TODO: somekind of decorator to check if the interaction is from a guild (not works because of type hinting nature of discord.py)
# find a way to make it work
# if await not_guild_response(interaction):
#     await interaction.followup.send("because of the error i can't leave the voice channel")
#     return

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
    if await not_guild_response(interaction):
        return None

    if channel is None:
        if isinstance(interaction.user, Member):
            if interaction.user.voice is None:
                await interaction.response.send_message("You are not connected to a voice channel.")
                return None
            channel = interaction.user.voice.channel
    
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
    help_message = "Commands:\n"
    for command in bot.commands:
        help_message += f"{command.name}: {command.description}\n"
    await interaction.response.send_message(help_message)
class Music(commands.Cog):
    group = app_commands.Group(name="music", description="Music commands")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.music_handler_pool: dict[str, YTDLHandler] = {}  # guild_id: music_controller

    @group.command(name="join", description="Join the voice channel")
    async def join(self, interaction: discord.Interaction, channel: discord.VoiceChannel | None) -> None:
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

    @group.command(name="leave", description="Leave the voice channel")
    async def leave(self, interaction: discord.Interaction) -> None:
        """
        Leaves the voice channel.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        if await not_guild_response(interaction):
            return None
        if interaction.guild.voice_client is not None:
            await interaction.guild.voice_client.disconnect(force=False)
        await interaction.response.send_message("Left voice channel")

    @group.command(name="play", description="Play a song")
    async def play(self, interaction: discord.Interaction, url: str) -> None:
        """
        Plays a song.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        url : str
            The URL of the song to play.
        """
        if await not_guild_response(interaction):
            return None
        print("play command before ensure_voice")

        _, voice_client = await self.ensure_voice(interaction)
        if voice_client is None:
            await interaction.response.send_message("i can't join the voice channel or related error")
            return

        print("play command after ensure_voice")
        if url == "":
            await interaction.response.send_message("Please provide a URL.")
            return

        # Send the "searching" message
        await interaction.response.defer()
        if str(interaction.guild.id) not in self.music_handler_pool:
            print("play command before YTDL_Player")
            if voice_client is None:
                await interaction.followup.send("I'm not connected to a voice channel.")
                return
            try:
                self.music_handler_pool[str(interaction.guild.id)] = YTDLHandler(bot=bot, voice_client=voice_client)
            except discord.errors.ClientException:
                await interaction.followup.send("I'm not connected to a voice channel.")
                return
            except Exception as e:
                await interaction.followup.send(f"An error occurred: {e}")
                return

        music_controller = self.music_handler_pool[str(interaction.guild.id)]
        try:
            await interaction.followup.send("Searching for the song...")
            await music_controller.play(interaction=interaction, url=url)
            await interaction.followup.send(f"Now playing: {url}")
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}")
            return

    @group.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction) -> None:
        """
        Pauses the current song.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        if await not_guild_response(interaction):
            return None
        await self.ensure_voice(interaction)
        if str(interaction.guild.id) not in self.music_handler_pool:
            await interaction.response.send_message("I'm not playing anything.")
            return
        music_controller = self.music_handler_pool[str(interaction.guild.id)]
        await music_controller.pause(interaction)

    @group.command(name="resume", description="Resume the current song")
    async def resume(self, interaction: discord.Interaction) -> None:
        """
        Resumes the current song.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        if await not_guild_response(interaction):
            return None
        await self.ensure_voice(interaction)
        if str(interaction.guild.id) not in self.music_handler_pool:
            await interaction.response.send_message("I'm not playing anything.")
            return
        music_controller = self.music_handler_pool[str(interaction.guild.id)]
        await music_controller.resume(interaction)

    @group.command(name="stop", description="Stop the current song")
    async def stop(self, interaction: discord.Interaction) -> None:
        """
        Stops the current song.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        if await not_guild_response(interaction):
            return None
        await self.ensure_voice(interaction)
        if str(interaction.guild.id) not in self.music_handler_pool:
            await interaction.response.send_message("I'm not playing anything.")
            return
        music_controller = self.music_handler_pool[str(interaction.guild.id)]
        await music_controller.stop(interaction)

    @group.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction) -> None:
        """
        Skips the current song.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        if await not_guild_response(interaction):
            return None
        await self.ensure_voice(interaction)
        if str(interaction.guild.id) not in self.music_handler_pool:
            await interaction.response.send_message("I'm not playing anything.")
            return
        music_controller = self.music_handler_pool[str(interaction.guild.id)]
        await music_controller.skip(interaction)

    @group.command(name="set_loop", description="Set the loop status")
    async def set_loop(self, interaction: discord.Interaction, loop: bool) -> None:
        """
        Sets the loop status.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        loop : bool
            The loop status.
        """
        if await not_guild_response(interaction):
            return None
        await self.ensure_voice(interaction)
        if str(interaction.guild.id) not in self.music_handler_pool:
            await interaction.response.send_message("queue is empty not possible to loop")
            return
        music_controller = self.music_handler_pool[str(interaction.guild.id)]
        await music_controller.set_loop(interaction,loop)

    @group.command(name="disconnect", description="Disconnect from the voice channel")
    async def disconnect(self, interaction: discord.Interaction) -> None:
        """
        Disconnects from the voice channel.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        if await not_guild_response(interaction):
            return None
        await self.ensure_voice(interaction)
        if str(interaction.guild.id) not in self.music_handler_pool:
            await interaction.response.send_message("I'm not playing anything.")
            return
        music_controller = self.music_handler_pool[str(interaction.guild.id)]
        await music_controller.disconnect(interaction)

    @group.command(name="status", description="Get the current status")
    async def status(self, interaction: discord.Interaction) -> None:
        """
        Gets the current status.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        if await not_guild_response(interaction):
            return None
        if str(interaction.guild.id) not in self.music_handler_pool:
            await interaction.response.send_message("I'm not playing anything.")
            return
        music_controller = self.music_handler_pool[str(interaction.guild.id)]
        await music_controller.status(interaction)

    @group.command(name="ensure_voice", description="Ensure the bot is connected to a voice channel")
    async def ensure_voice_cmd(self, interaction: discord.Interaction, voice_ch: VoiceChannel | None = None) -> tuple[VoiceChannel,VoiceProtocol] | None:
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
        if await not_guild_response(interaction):
            return None
        voice_ch , voice_cl = await self.ensure_voice(interaction, voice_ch, quiet=False)
        if voice_ch is None or voice_cl is None:
            return None
        return voice_ch , voice_cl

    async def ensure_voice(self, interaction: discord.Interaction, voice_ch: VoiceChannel | None = None, quiet: bool = True) -> tuple[VoiceChannel,VoiceProtocol] | tuple[None,None]:
        """
        Ensures the bot is connected to a user's voice channel or specified voice channel.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        voice_ch : VoiceChannel | None, optional
            The voice channel to join, by default None.
        quiet : bool, optional
            Whether to send a message if the bot is not connected to a voice channel, by default True.

        Returns
        -------
        VoiceChannel | None
            The voice channel the bot is connected to. If the bot is not connected to a voice channel, returns None.
        """
        if voice_ch is None:
            if isinstance(interaction.user, Member):
                if isinstance(interaction.user.voice, VoiceState):
                    voice_ch = interaction.user.voice.channel

        if voice_ch is None:
            if not quiet:
                await interaction.response.send_message("You are not connected to a voice channel.")
            return None,None
        # if already connected to the same channel then return the channel
        if interaction.guild is None:
            if not quiet:
                await interaction.response.send_message("Bot currently only supports guilds")
            return None,None
        if interaction.guild.voice_client is not None and interaction.guild.voice_client.channel == voice_ch:
            if not quiet:
                await interaction.response.send_message(f"Already connected to {voice_ch.name}")
            return voice_ch , interaction.guild.voice_client
        try:
            voice_client = await voice_ch.connect()
            if not quiet:
                await interaction.response.send_message(f"Joined {voice_ch.name}")
            return voice_ch , voice_client
        except Exception as e:
            if not quiet:
                await interaction.response.send_message("An error occurred while connecting to the voice channel")
            return None,None

    


class Manage(commands.Cog):
    group = app_commands.Group(name="manage",description="Manage commands")
    def __init__(self,bot:commands.Bot) -> None:
        self.bot = bot
        super().__init__()
    
    @group.command(name="clean",description="Cleans the chat")
    @commands.has_permissions(manage_messages=True)
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

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("I can only delete messages in text channels.")
            return

        if limit > 100:
            await interaction.response.send_message("You can only delete up to 100 messages at a time.")
            return
        if limit < 1:
            limit = 1

        messages :AsyncIterator[discord.Message]= interaction.channel.history(limit=limit)
        # make it snow flake iterable
        messages_snfl = [message async for message in messages]
        try:
            await interaction.channel.delete_messages(messages_snfl)
            await interaction.response.send_message(f"must have deleted last {limit} messages in this channel")
        except (discord.errors.Forbidden, discord.errors.HTTPException, discord.errors.NotFound, discord.errors.ClientException) as e:
            # only response with the error type 
            await interaction.response.send_message(f"An error occurred: type {type(e).__name__}")




@bot.event
async def on_ready():
    if bot.user is None:
        print("Bot is not logged in")
        exit(1)
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await command_tree.sync()
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


async def main():
    bot_token = get_all_envs(".env")["BOT_TOKEN"]
    async with bot:
        await bot.add_cog(Music(bot))
        await bot.add_cog(Manage(bot))
        await bot.start(bot_token)


if __name__ == "__main__":
    asyncio.run(main())
