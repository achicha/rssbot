### RSS Reader telegram bot.

dockerized container with Python3, PostgreSQL, python-telegram-bot onboard.


- Pre requirements:

	- installed docker: https://docs.docker.com/engine/installation/
	- installed docker-compose: https://docs.docker.com/compose/install/

- Install:

	- git clone https://github.com/achicha/rssbot.git rssbot
	- docker-compose stop && docker-compose rm -f && docker-compose build --no-cache project && docker-compose up -d
	- add ./config.ini with valid data (see config-example.ini)

- Commands:

	 - /help
	 - /show -> show all added rss feeds
	 - /add <rss feed>  -> add one more rss feed
	 - /remove <rss feed id>  -> remove feed
	 - /get <rss feed id from /show> <number of posts> -> get recent rss posts from mentioned feed