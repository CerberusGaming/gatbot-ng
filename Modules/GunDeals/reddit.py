import datetime
import html

from requests import Session


class RedditPost:
    def __init__(self, post: dict):
        post = post['data']
        self.raw = post

        self.id = post['id']

        self.title = html.unescape(post['title'])
        self.author = post['author']

        self.post = "https://reddit.com{}".format(post['permalink'])
        self.posted_on = datetime.datetime.fromtimestamp(int(post['created_utc']))
        self.text = html.unescape(post['selftext'])

        self.link = post['url']
        self.flair = post['link_flair_text']
        self.thumb = post['thumbnail'] if str(post['thumbnail']).startswith("https") else None
        self.sticky = post['stickied']
        self.nsfw = post['over_18']

    def __str__(self):
        return "<RedditPost: {} - {}>".format(self.title, self.post)

    def __repr__(self):
        return self.__str__()


class Reddit:
    def __init__(self, subreddit: str = None, username: str = None):
        if username is None:
            raise ValueError("You must set a username for requests.")
        if subreddit is None:
            subreddit = ""
        else:
            subreddit = "r/{}".format(subreddit.lower().split('/')[-1])
        self._url = "https://www.reddit.com/{}.json?sort=new".format(subreddit)
        self._session = Session()
        self._session.headers.update({'Accept': 'application/json',
                                      "User-Agent": "server:discord.hook.bot:v0 (by /u/{})".format(username)})

    def get_posts(self, limit: int = 25):
        req = self._session.get(self._url + "&limit={}".format(str(limit)))
        if req.status_code == 200:
            return [RedditPost(x) for x in req.json()['data']['children']]
        else:
            return None
