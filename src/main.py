import asyncio
import discord

from yt_dlp_streamer import YTDL_Player

from discord import app_commands
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


# this methods are create music controller and add it to the pool based of guild id


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

async def join_vc(interaction: discord.Interaction, channel: discord.VoiceChannel | None,quiet=False) -> bool:
    """
    Joins a voice channel.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    channel : discord.VoiceChannel | None
        The voice channel to join.
    """
    if channel is None:
        if interaction.user.voice is None:
            if not quiet:
                await interaction.response.send_message("You are not connected to a voice channel. if you want me to join a specific channel, please provide the channel.")
            return False
        channel = interaction.user.voice.channel

    if interaction.guild.voice_client is not None:
        # If the bot is already connected to a voice channel, move to the new channel

        if channel:
            await interaction.guild.voice_client.connect(reconnect=True)
            if not quiet:
                await interaction.response.send_message(f"Moved to {channel.name}")
            return True
    await channel.connect(reconnect=True)
    if not quiet:
        await interaction.response.send_message(f"Joined {channel.name}")
    return True

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
    group = app_commands.Group(name="music",description="Music commands")
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.music_player_pool : dict[str,YTDL_Player]  = {}  # guild_id: music_controller

    @group.command(name="join",description="Join the voice channel")
    async def join(self,interaction: discord.Interaction, channel: discord.VoiceChannel | None) -> None:
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


    @group.command(name="leave",description="Leave the voice channel")
    async def leave(self,interaction: discord.Interaction) -> None:
        """
        Leaves the voice channel.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
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
        print("play command")
        if await join_vc(interaction, None,quiet=True) is False:
            await interaction.response.send_message("I have issues joining the voice channel.")
            return

        print("play command after join_vc")
        if url == "":
            await interaction.response.send_message("Please provide a URL.")
            return

        # Send the "searching" message
        await interaction.response.defer()
        if str(interaction.guild.id) not in self.music_player_pool:
            print("play command before YTDL_Player")
            try:
                self.music_player_pool[str(interaction.guild.id)] = YTDL_Player(bot, interaction, interaction.guild.voice_client)
            except discord.errors.ClientException:
                await interaction.followup.send("I'm not connected to a voice channel.")
                return
            except Exception as e:
                await interaction.followup.send(f"An error occurred: {e}")
                return

        music_controller = self.music_player_pool[str(interaction.guild.id)]
        try:
            await interaction.followup.send("Searching for the song...")
            await music_controller.play(url)
            await interaction.followup.send(f"Now playing: {url}")
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}")
            return


    @group.command(name="pause",description="Pause the current song")
    async def pause(self,interaction: discord.Interaction) -> None:
        """
        Pauses the current song.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        await self.ensure_voice(interaction)
        if str(interaction.guild.id) not in self.music_player_pool:
            await interaction.response.send_message("I'm not playing anything.")
            return
        music_controller = self.music_player_pool[str(interaction.guild.id)]
        await music_controller.pause()

    @group.command(name="resume",description="Resume the current song")
    async def resume(self,interaction: discord.Interaction) -> None:
        """
        Resumes the current song.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        await self.ensure_voice(interaction)
        if str(interaction.guild.id) not in self.music_player_pool:
            await interaction.response.send_message("I'm not playing anything.")
            return
        music_controller = self.music_player_pool[str(interaction.guild.id)]
        await music_controller.resume()

    @group.command(name="stop",description="Stop the current song")
    async def stop(self,interaction: discord.Interaction) -> None:
        """
        Stops the current song.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        await self.ensure_voice(interaction)
        if str(interaction.guild.id) not in self.music_player_pool:
            await interaction.response.send_message("I'm not playing anything.")
            return
        music_controller = self.music_player_pool[str(interaction.guild.id)]
        await music_controller.stop()

    @group.command(name="skip",description="Skip the current song")
    async def skip(self,interaction: discord.Interaction) -> None:
        """
        Skips the current song.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        await self.ensure_voice(interaction)
        if str(interaction.guild.id) not in self.music_player_pool:
            await interaction.response.send_message("I'm not playing anything.")
            return
        music_controller = self.music_player_pool[str(interaction.guild.id)]
        await music_controller.skip()

    @group.command(name="set_loop",description="Set the loop status")
    async def set_loop(self,interaction: discord.Interaction, loop: bool) -> None:
        """
        Sets the loop status.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        loop : bool
            The loop status.
        """
        await self.ensure_voice(interaction)
        if str(interaction.guild.id) not in self.music_player_pool:
            await interaction.response.send_message("queue is empty not possible to loop")
            return
        music_controller = self.music_player_pool[str(interaction.guild.id)]
        await music_controller.set_loop(loop)

    @group.command(name="disconnect",description="Disconnect from the voice channel")
    async def disconnect(self,interaction: discord.Interaction) -> None:
        """
        Disconnects from the voice channel.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        await self.ensure_voice(interaction)
        if str(interaction.guild.id) not in self.music_player_pool:
            await interaction.response.send_message("I'm not playing anything.")
            return
        music_controller = self.music_player_pool[str(interaction.guild.id)]
        await music_controller.disconnect()

    @group.command(name="status",description="Get the current status")
    async def status(self,interaction: discord.Interaction) -> None:
        """
        Gets the current status.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        await self.ensure_voice(interaction)
        if str(interaction.guild.id) not in self.music_player_pool:
            await interaction.response.send_message("I'm not playing anything.")
            return
        music_controller = self.music_player_pool[str(interaction.guild.id)]
        await music_controller.status()

    
    @group.command(name="ensure_voice",description="Ensure the bot is connected to a voice channel")
    async def ensure_voice_cmd(self,interaction: discord.Interaction) -> None:
        """
        Ensures the bot is connected to a voice channel.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        await self.ensure_voice(interaction,False)

    async def ensure_voice(self,interaction: discord.Interaction,quiet=True) -> None:
        """
        Ensures the bot is connected to a voice channel.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        if interaction.guild.voice_client is None:
            if not quiet:
                await interaction.response.send_message("I'm not connected to a voice channel.")
            return
        if str(interaction.guild.id) not in self.music_player_pool:
            await interaction.response.send_message("I'm connected to a voice channel.")


    


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
        await interaction.channel.delete_messages(interaction.channel.history(limit=limit))
        await interaction.response.send_message(f"Deleted {limit} messages")



@bot.event
async def on_ready():
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
