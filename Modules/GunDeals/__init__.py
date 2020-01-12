import asyncio
import datetime
import json

from discord import Embed
from discord.ext import commands
from sqlalchemy import Boolean, Column, DateTime, Integer, String

from .reddit import Reddit


class GunDeals(commands.Cog):
    deps = ['Storage', 'Settings']

    def __init__(self, bot):
        self.bot = bot
        self.bot.config.init_module(self.qualified_name,
                                    defaults={'reddit_user': '',
                                              'reddit_refresh': '60',
                                              'reddit_posts': '100'})

        self.storage = bot.get_cog('Storage')
        self.settings = bot.get_cog('Settings')
        self.options = ["subreddit", "username"]

        self.model = self.__gen_model__()
        self.storage.model_base.metadata.create_all()

        self.bot.loop.create_task(self.store_task())

    def __gen_model__(self):
        class Model(self.storage.model_base):
            __tablename__ = "feed_entries"
            id = Column(Integer, primary_key=True, autoincrement=True)
            subreddit = Column(String(24))
            post_id = Column(String(24), unique=True)
            title = Column(String(2048))
            author = Column(String(2048))
            post = Column(String(2048))
            posted_on = Column(DateTime, default=datetime.datetime.utcnow())
            text = Column(String(4096))
            link = Column(String(2048))
            flair = Column(String(2048))
            thumb = Column(String(2048))
            sticky = Column(Boolean, default=False)
            nsfw = Column(Boolean, default=False)

        return Model

    @commands.command("gdstatus")
    @commands.has_permissions(administrator=True)
    async def status(self, ctx):
        ctx: commands.Context = ctx
        settings = self.settings.get(self.qualified_name, str(ctx.channel.id))
        if settings is not None and len(settings) != 1:
            await ctx.send("This channel has not been set up")
        else:
            embed = Embed(title="Settings for: #{}".format(str(ctx.channel.name)))
            for key, value in json.loads(settings[0].value).items():
                embed.add_field(name=key, value=value, inline=False)
            await ctx.send(embed=embed)

    @commands.command("gdsetup")
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx):
        ctx: commands.Context = ctx
        settings = self.settings.get(self.qualified_name, str(ctx.channel.id))
        if settings is not None and len(settings) == 1:
            await ctx.send("This channel is already set up")
        else:
            default = {}
            self.settings.set(self.qualified_name, str(ctx.channel.id), json.dumps(default))
            await ctx.send("#{} has been initialized. Please add a subreddit to begin feed.".format(ctx.channel.name))

    @commands.command("gdoption")
    @commands.has_permissions(administrator=True)
    async def option(self, ctx, option: str = "", value: str = ""):
        ctx: commands.Context = ctx
        settings = json.loads(self.settings.get(self.qualified_name, str(ctx.channel.id))[0].value)
        option = option.lower()
        if len(option) == 0 or option not in self.options:
            option = "_None_" if len(option) == 0 else option
            await ctx.send("Invalid Option: {}".format(option))
            await  ctx.send("Command Use: `!gdset <option> [<value>, Empty to clear]`")
        else:
            settings.update({option: value})
            self.settings.set(self.qualified_name, str(ctx.channel.id), json.dumps(settings))

            settings = json.loads(self.settings.get(self.qualified_name, str(ctx.channel.id))[0].value)
            embed = Embed(title="Settings for: #{}".format(str(ctx.channel.name)))
            for key, value in settings.items():
                embed.add_field(name=key, value=value, inline=False)
            await ctx.send(embed=embed)

    async def store_task(self):
        while True:
            try:
                if not self.bot.loop.is_running():
                    await asyncio.sleep(30)
                else:
                    self.store_entries()
                    await asyncio.sleep(60)
            except Exception as E:
                print(E)
                continue

    def store_entries(self):
        ses = self.storage.gen_session()
        settings = self.settings.get(self.qualified_name)
        settings = [] if settings is None else settings

        subreddits = {}
        for setting in settings:
            setting = json.loads(setting.value)

            s = setting['subreddit'] if 'subreddit' in setting.keys() else None
            s = s.split(";") if ";" in str(s) else s

            u = self.bot.config.get_setting(self.qualified_name, 'reddit_user', 'REDDIT_USER', default=None)
            u = setting['username'] if 'username' in setting.keys() else u

            subreddits = {}
            if isinstance(s, list):
                for item in s:
                    if s not in subreddits.keys():
                        subreddits.update({item: u})
            else:
                subreddits.update({s: u})

        for subreddit, username in subreddits.items():
            if username is None or subreddit is None:
                pass
            else:
                reddit = Reddit(subreddit, username)
                posts = self.bot.config.get_setting(self.qualified_name, 'reddit_posts', 'REDDIT_POSTS', default=100)
                entries = reddit.get_posts(int(posts))
                entries = [] if entries is None else entries
                for entry in entries:
                    exists = ses.query(self.model).filter(self.model.post_id == entry.id).count() > 0
                    if not exists and not entry.sticky:
                        print("Stored: {}".format(entry))
                        ses.add(self.model(post_id=entry.id,
                                           subreddit=subreddit,
                                           title=entry.title,
                                           author=entry.author,
                                           post=entry.post,
                                           posted_on=entry.posted_on,
                                           text=entry.text,
                                           link=entry.link,
                                           thumb=entry.thumb,
                                           sticky=entry.sticky,
                                           nsfw=entry.nsfw,
                                           flair=entry.flair))
                        ses.commit()
                ses.close()

    async def post_task(self):
        while True:
            try:
                if not self.bot.loop.is_running():
                    await asyncio.sleep(30)
                else:
                    self.post_entries()
                    await asyncio.sleep(60)
            except Exception as E:
                print(E)
                continue

    def post_entries(self):
        ses = self.storage.gen_session()

        ses.query(self.model)
