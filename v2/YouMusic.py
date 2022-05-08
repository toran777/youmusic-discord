import asyncio
import logging

import discord
import youtube_dl
from discord.ext import commands

from v2 import embed
from v2.utility import to_string_time

youtube_dl.utils.bug_reports_message = lambda: ''
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}
ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

logging.basicConfig(format='%(levelname)s %(name)s %(asctime)s %(message)s', datefmt='%d/%m/%Y %H:%M:%S',
                    filename='logfile.log', encoding='utf-8', level=logging.INFO)


class Timer:
    def __init__(self) -> None:
        self.timer = 0

    def update(self) -> None:
        self.timer += 1

    def reset(self) -> None:
        self.timer = 0

    def get_timer(self) -> int:
        return self.timer


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data), data


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def play(self, ctx, *, url):
        global processing

        if processing:
            message = embed.alert('Slow down cavrón')
            return await ctx.message.channel.send(embed=message)

        processing = True
        async with ctx.typing():
            try:
                player, audio_data = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
                processing = False
                logging.info('User [%s] requested [%s]', ctx.author, audio_data['id'])
                print(f'User {ctx.author} requested {audio_data["id"]}')
                audio_data['ctx'] = ctx
                audio_data['player'] = player

                clean_data = {'name': audio_data['title'], 'duration': to_string_time(audio_data['duration'])}
                titles_queue.append(clean_data)
                await queue.put(audio_data)

                if ctx.voice_client.is_playing():
                    message = embed.song_queued(audio_data)
                    await ctx.message.channel.send(embed=message)
            except Exception as e:
                message = embed.alert(str(e))
                processing = False
                await ctx.message.channel.send(embed=message)

    @commands.command(help='Shows the queue')
    async def queue(self, ctx):
        message = embed.show_queue(titles_queue)
        await ctx.message.channel.send(embed=message)

    @commands.command()
    async def volume(self, ctx, volume: int):
        ctx.voice_client.source.volume = volume / 100
        logging.info('User [%s] changed volume to [%s]', ctx.author, volume)
        print(f'User {ctx.author} changed volume to {volume}')
        message = embed.alert(f'Changed volume to {volume}%.')
        await ctx.message.channel.send(embed=message)

    @commands.command(help='Skips the current song')
    async def skip(self, ctx):
        ctx.voice_client.stop()
        logging.info('User [%s] skipped', ctx.author)
        print(f'User {ctx.author} skipped')
        message = embed.alert('Song skipped.')
        await ctx.message.channel.send(embed=message)

    @commands.command(help='Resumes the audio')
    async def resume(self, ctx):
        if ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            logging.info('User [%s] resumed', ctx.author)
            print(f'User {ctx.author} resumed')
            message = embed.alert('Resumed.')
        elif ctx.voice_client.is_playing():
            message = embed.alert("I'm already playing")
        else:
            message = embed.alert('No songs are currently being played.')

        await ctx.message.channel.send(embed=message)

    @commands.command(help='Pauses the audio')
    async def pause(self, ctx):
        if ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            logging.info('User [%s] paused', ctx.author)
            print(f'User {ctx.author} paused')
            message = embed.alert('Paused.')
        elif ctx.voice_client.is_paused():
            message = embed.alert("I'm already paused.")
        else:
            message = embed.alert('No songs are currently being played.')

        await ctx.message.channel.send(embed=message)

    @commands.command(help='Disconnects the bot from the voice chat')
    async def disconnect(self, ctx):
        await ctx.voice_client.disconnect()
        logging.info('User [%s] disconnected', ctx.author)
        print(f'User {ctx.author} disconnected')
        for _ in range(queue.qsize()):
            queue.get_nowait()
            queue.task_done()

    @play.before_invoke
    @volume.before_invoke
    @skip.before_invoke
    @pause.before_invoke
    @resume.before_invoke
    @disconnect.before_invoke
    async def ensure_voice(self, ctx):
        timer.reset()
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                message = embed.alert('You are not connected to a voice channel.')
                await ctx.message.channel.send(embed=message)
        elif ctx.voice_client.channel != ctx.author.voice.channel:
            message = embed.alert('You are in a different voice channel.')
            await ctx.message.channel.send(embed=message)


async def start_playing() -> None:
    while not bot.is_closed():
        play_next_song.clear()
        audio_data = await queue.get()
        logging.info('Now playing [%s]', audio_data["title"])
        print(f'Now playing {audio_data["title"]}')
        ctx = audio_data['ctx']
        player = audio_data['player']

        ctx.voice_client.play(player, after=play_next)
        message = embed.now_playing(audio_data)
        await ctx.message.channel.send(embed=message)
        await play_next_song.wait()


async def run_timer() -> None:
    while not bot.is_closed():
        for voice_client in bot.voice_clients:
            if not voice_client.is_playing():
                if timer.get_timer() == 30:
                    await voice_client.disconnect()
                else:
                    timer.update()
        await asyncio.sleep(1)


def play_next(_):
    bot.loop.call_soon_threadsafe(play_next_song.set)
    titles_queue.pop(0)


bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"), description='Gramola Magica')


@bot.event
async def on_ready():
    print(f'Ready {bot.description}')


queue = asyncio.Queue()
titles_queue = []
play_next_song = asyncio.Event()
timer = Timer()
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
processing = False

DISCORD_TOKEN = ''

bot.add_cog(Music(bot))
bot.loop.create_task(start_playing())
bot.loop.create_task(run_timer())
bot.run(DISCORD_TOKEN)
