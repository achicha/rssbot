### RSS Reader telegram bot.

dockerized container with Python3, PostgreSQL, python-telegram-bot onboard.


- Pre requirements:

	- installed docker: https://docs.docker.com/engine/installation/
	- installed docker-compose: https://docs.docker.com/compose/install/

- Install:

	- git clone https://github.com/achicha/rssbot.git rssbot
	- docker-compose stop && docker-compose rm -f && docker-compose build --no-cache project && docker-compose up -d
	- create Database:
		- outside of container with Pycharm (ssh needed)
		- or inside: (psql -h 127.0.0.1 -p 5432 -U postgres) and (CREATE DATABASE rsstelebot;)
	- add ./config.ini with valid data (see config-example.ini)

- Commands:

	 - /help
	 - /show -> show all added rss feeds
	 - /add <rss feed>  -> add one more rss feed
	 - /remove <rss feed id>  -> remove feed
	 - /get <rss feed id from /show> <number of posts> -> get recent rss posts from mentioned feed