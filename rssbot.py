from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, Job
from random import randint
import logging
import feedparser
import time
import postgresql
import configparser

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.ERROR)
logger = logging.getLogger(__name__)

# load config from file
config = configparser.ConfigParser()
config.read('./config.ini')
db_path = config['Database']['Path']
bot_access_token = config['Telegram']['access_token']


class RssParser(object):
    """ Class for parsing RSS Feed.
    We need just title, link and published date
    """

    def __init__(self, config_links):
        self.links = [config_links]
        self.news = []
        self.refresh()

    def refresh(self):
        self.news = []
        for i in self.links:
            data = feedparser.parse(i)
            self.news += [(i['title'], i['link'],
                           int(time.mktime(i['published_parsed']))) for i in data['entries']]


class Database:
    """
    Database Class
    """
    _db = None

    def __init__(self, chat_id):
        self._db = postgresql.open(db_path)
        self.char_id = chat_id
        # create feeds table
        try:
            self._db.query("SELECT * FROM feeds;")
            print('feeds init')
        except:
            self._db.execute("CREATE TABLE feeds (feed_id SERIAL PRIMARY KEY, "
                             "rssfeed CHAR(300), updated INT DEFAULT 0, custom_feed INT DEFAULT 0);")
            print('feeds table created')
        # create posts table
        try:
            self._db.query("SELECT * FROM posts;")
            print('posts init')
        except:
            self._db.execute("CREATE TABLE posts (feed_id INT REFERENCES feeds(feed_id), title CHAR(1000), "
                             "link CHAR(1000), post_time INT, publish_time INT DEFAULT 0);")
            print('posts table created')
        # create user_feeds
        try:
            self._db.query("SELECT * FROM user_feeds;")
            print('user_feeds init')
        except:
            self._db.execute("CREATE TABLE user_feeds (feed_id INT REFERENCES feeds(feed_id), chat_id INT);")
            print('user_feeds table created')

        print('DB init')

    def add_feed(self, feed):
        sel = self._db.prepare("SELECT * FROM feeds WHERE rssfeed=($1);")
        if len(sel(feed)) > 0:
            return 'already added'
        else:
            # check valid rss feed
            p = RssParser(feed)
            posts = p.news
            if len(posts) < 1:
                return 'Invalid rss feed. Please try again'
            # add feed to feeds table
            _ins_feed = self._db.prepare("INSERT INTO feeds (rssfeed) VALUES ($1);")
            _ins_feed(feed)
            return '{0} feed added. \n' \
                   'Get recent posts: /get {1} <number of posts>'.format(feed, int(sel(feed)[0][0]))

    def subscribe_feed(self, chat_id, feed):
        # add user_feed relations
        sel = self._db.prepare("SELECT feed_id, rssfeed FROM feeds WHERE rssfeed=($1);")
        feed_id = int(sel(feed)[0][0])
        p = self._db.prepare("SELECT * FROM user_feeds "
                             "WHERE chat_id = $1 AND feed_id = $2;")
        if len(p(chat_id, feed_id)) > 0:
            return 'this feed already added. \n' \
                   'Get recent posts: /get {0} <number of posts>'.format(int(sel(feed)[0][0]))

        _ins_uf = self._db.prepare("INSERT INTO user_feeds (feed_id, chat_id) VALUES ($1, $2);")
        _ins_uf(int(sel(feed)[0][0]), chat_id)
        return 'Subscribed to {}'.format((sel(feed)[0][1]))

    def unsubscribe_feed(self, feed_id):
        # remove user relation to this feed
        dd = self._db.prepare("DELETE FROM user_feeds WHERE feed_id = $1;")
        dd(int(feed_id))
        print(feed_id)
        s = self._db.prepare("SELECT trim(rssfeed) FROM feeds WHERE feed_id = $1;")
        return 'Unsubscribed from {}'.format(s(int(feed_id))[0][0])

    def show_all_feeds(self, chat_id):
        gaf = self._db.prepare("SELECT feeds.feed_id, feeds.rssfeed FROM feeds "
                               "INNER JOIN user_feeds ON feeds.feed_id = user_feeds.feed_id "
                               "WHERE chat_id = $1;")
        return gaf(chat_id)

    def get_posts(self, chat_id, feed_number, posts_quantity):
        """
        Get posts from DB

        :param chat_id:
        :param feed_number: feed id
        :param posts_quantity: number of posts, got from user
        :return: list with rss news
        """
        sel = self._db.prepare("SELECT * FROM posts WHERE feed_id = ($1) ORDER BY post_time DESC LIMIT ($2);")
        return sel(feed_number, posts_quantity)

    def update_all_feeds(self):
        # select feeds which were updated more than 450 second ago.
        rss_feeds = self._db.prepare("SELECT feed_id, trim(rssfeed) FROM feeds WHERE updated < $1 - 450;")
        feeds_to_update = rss_feeds(int(time.time()))

        # add new posts and update updated_time for every feed
        posts_upd = self._db.prepare("INSERT INTO posts (feed_id, title, link, post_time) VALUES ($1, $2, $3, $4);")
        feed_time_upd = self._db.prepare("UPDATE feeds SET updated = $1 WHERE feed_id = $2;")
        all_posts = self._db.prepare("SELECT trim(title), trim(link), post_time FROM posts WHERE feed_id = $1;")

        for _id, feed in feeds_to_update:
            p = RssParser(feed)
            new_posts = p.news
            _all = all_posts(_id)
            for post in new_posts:
                if post not in _all:
                    posts_upd(_id, post[0], post[1], post[2])
            feed_time_upd(int(time.time()), _id)
            print('updated {0} , total posts: {1}'.format(feed, len(all_posts(_id))))

    def not_published(self):
        """
        find all new posts and update published_time to current time
        :return: new posts
        """
        p = self._db.query("SELECT title, link, chat_id FROM posts "
                           "INNER JOIN feeds ON posts.feed_id = feeds.feed_id "
                           "INNER JOIN user_feeds ON feeds.feed_id = user_feeds.feed_id "
                           "WHERE publish_time = 0 ORDER BY  posts.post_time;")
        if len(p) > 0:
            mp = self._db.prepare("UPDATE posts SET publish_time = $1 "
                                  "WHERE publish_time = 0")
            mp(int(time.time()))
            print('new posts are published and published time was updated')
        return p

    def __del__(self):
        self._db.close


# ----------------------------------------------------------------------------------------------------
def start(bot, update):
    bot.sendMessage(update.message.chat_id,
                    text="""Hi! Use:
 /help
 /show -> show all added rss feeds
 /add <rss feed>  -> add one more rss feed
 /remove <rss feed id>  -> remove feed
 /get <rss feed id from /show> <number of posts> -> get recent rss posts from mentioned feed
""")


def get(bot, update, args):
    chat_id = update.message.chat_id
    d = Database(chat_id)
    try:
        # args[0] should contain positive numbers of posts
        feed_number = int(args[0])
        posts_number = int(args[1])
        if posts_number < 0 or feed_number < 0:
            bot.sendMessage(chat_id, text='should be a positive number!')
            return

        recent_posts = d.get_posts(chat_id, feed_number, posts_number)
        if len(recent_posts) < 1:
            bot.sendMessage(chat_id, text="looks like empty feed...")
            return
        for i in recent_posts:
            bot.sendMessage(chat_id, text=i[1] + ' ' + i[2])

    except (IndexError, ValueError):
        bot.sendMessage(chat_id, text='Usage: /get <number of posts>')


def show(bot, update):
    """
    Show all added feeds
    """
    chat_id = update.message.chat_id
    d = Database(chat_id)
    all_feeds = d.show_all_feeds(chat_id)
    if len(all_feeds) < 1:
        bot.sendMessage(chat_id, text=('Nothing here yet. \n'
                                       'Please add the first feed by command:\n'
                                       '/add <rss feed link>'))
    else:
        for f in all_feeds:
            bot.sendMessage(chat_id, text=str(f[0]) + ') ' + f[1])


def add(bot, update, job_queue, args):
    """
    add rss feed to DB.feeds
    """
    chat_id = update.message.chat_id
    try:
        feed = str(args[0])
        d = Database(chat_id)
        add_feed = d.add_feed(feed)
        if add_feed != 'Invalid rss feed. Please try again':
            subscribe = d.subscribe_feed(chat_id, feed)
            # update feeds
            job_updater = Job(upd, 1.0, repeat=False,
                              context=update.message.chat_id)
            job_queue.put(job_updater)

            bot.sendMessage(chat_id, text=subscribe)
    except (IndexError, ValueError):
        bot.sendMessage(chat_id, text='Usage: /add <rss feed string>')


def upd(bot, job, xz=0):
    """ update POSTS DB"""
    print(xz)
    chat_id = job.context
    d = Database(chat_id)
    d.update_all_feeds()
    # bot.sendMessage(chat_id=chat_id, text='all feeds updated')


def pub(bot, job):
    """ Publish new posts from DB to telegram user"""
    chat_id = job.context
    d = Database(chat_id)
    new_posts = d.not_published()
    if len(new_posts) < 1:
        # bot.sendMessage(chat_id=chat_id, text='could not find any new posts')
        return
    for i in new_posts:
        bot.sendMessage(chat_id=i[2], text=i[0] + ' ' + i[1])
        time.sleep(randint(1, 4))


def callback_timer(bot, update, job_queue):
    bot.sendMessage(chat_id=update.message.chat_id,
                    text='updater started!')
    job_updater = Job(upd, 300.0, repeat=True,
                      context=update.message.chat_id)
    job_publisher = Job(pub, 150.0, repeat=True,
                        context=update.message.chat_id)
    job_queue.put(job_updater, next_t=0.0)
    job_queue.put(job_publisher, next_t=0.0)


def remove(bot, update, args):
    chat_id = update.message.chat_id
    try:
        feed_id = str(args[0])
        d = Database(chat_id)
        rm_feed = d.unsubscribe_feed(feed_id)
        bot.sendMessage(chat_id, text=rm_feed)
    except (IndexError, ValueError):
        bot.sendMessage(chat_id, text='Usage: /add <rss feed string>')


def error(bot, update, error):
    logger.warn('Update "%s" caused error "%s"' % (update, error))


def main():
    updater = Updater(bot_access_token)
    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("help", start))
    dp.add_handler(CommandHandler("get", get, pass_args=True))
    dp.add_handler(CommandHandler("remove", remove, pass_args=True))
    dp.add_handler(CommandHandler("show", show))
    dp.add_handler(CommandHandler("add", add, pass_args=True, pass_job_queue=True))
    # on non command i.e message - error message
    dp.add_handler(MessageHandler([Filters.text], start))
    # posts auto updater
    dp.add_handler(CommandHandler('timer', callback_timer, pass_job_queue=True))
    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()
    # Block until the you presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
