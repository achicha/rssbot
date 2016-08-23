-- delete old tables
DROP TABLE IF EXISTS user_feeds, posts, feeds;

-- feeds table
CREATE TABLE IF NOT EXISTS feeds (feed_id SERIAL PRIMARY KEY, rssfeed CHAR(300), updated INT DEFAULT 0, custom_feed INT DEFAULT 0);
-- posts table
CREATE TABLE IF NOT EXISTS posts (feed_id INT REFERENCES feeds(feed_id), title CHAR(1000),link CHAR(1000), post_time INT, publish_time INT DEFAULT 0);
-- user_feeds table
CREATE TABLE IF NOT EXISTS user_feeds (feed_id INT REFERENCES feeds(feed_id), chat_id INT);
