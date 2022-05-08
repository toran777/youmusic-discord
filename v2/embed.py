from typing import Dict, List

from discord.embeds import Embed


class CustomEmbed(Embed):
    def __init__(self, title: str = ""):
        super().__init__(title=title, color=0x0099ff)
        self.set_footer(text='Created by toran777')


def song_queued(song: Dict):
    embed = CustomEmbed()
    embed.add_field(name='Queued', value=f'Queued [{song["title"]}]({song["url"]})')

    return embed


def alert(message: str):
    embed = CustomEmbed()
    msg = message if message else 'Looks like something went wrong with the request'
    embed.add_field(name='Info', value=msg)

    return embed


def now_playing(audio_data: Dict):
    embed = CustomEmbed(title=audio_data['title'])
    embed.set_author(name='Now Playing!')

    if audio_data['description']:
        description = audio_data['description'][:200] + '...' if len(audio_data['description']) > 200 else audio_data['description']
        embed.add_field(name='Description', value=description, inline=False)

    embed.add_field(name='Channel', value=f'[{audio_data["channel"]}]({audio_data["channel_url"]})', inline=False)
    embed.add_field(name='Video', value=audio_data['webpage_url'])
    embed.set_thumbnail(url=audio_data['thumbnail'])

    return embed


def show_queue(queue: List):
    embed = CustomEmbed()

    if len(queue) == 0:
        embed.add_field(name='Info', value='The queue is empty')
    else:
        embed.set_author(name='Songs queued')
        for i, song in enumerate(queue):
            if i == 0:
                embed.add_field(name=f'Now playing', value=song['name'], inline=False)
            else:
                embed.add_field(name=f'{i + 1})', value=song['name'], inline=False)
            embed.add_field(name='Duration', value=song['duration'], inline=True)

    return embed
