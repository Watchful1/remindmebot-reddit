#!/usr/bin/env python3

# =============================================================================
# IMPORTS
# =============================================================================

import praw
import sqlite3
import time
from datetime import datetime
from requests.exceptions import HTTPError, ConnectionError, Timeout
from praw.exceptions import APIException
from socket import timeout
from pytz import timezone

# =============================================================================
# GLOBALS
# =============================================================================

#Reddit info
reddit = praw.Reddit("RemindMeBot", user_agent="RemindMeBot user agent")

# =============================================================================
# CLASSES
# =============================================================================

class Connect(object):
	"""
	DB connection class
	"""
	connection = None
	cursor = None

	def __init__(self):
		self.connection = sqlite3.connect("database.db")
		self.cursor = self.connection.cursor()

class Reply(object):

	def __init__(self):
		self._queryDB = Connect()
		self._replyMessage =(
			"RemindMeBot private message here!" 
			"\n\n**The message:** \n\n>{message}"
			"\n\n**The original comment:** \n\n>{original}"
			"\n\n**The parent comment from the original comment or its submission:** \n\n>{parent}"
			"{origin_date_text}"
			"\n\n#Would you like to be reminded of the original comment again? Just set your time again after the RemindMe! command. [CLICK HERE]"
			"(http://np.reddit.com/message/compose/?to=RemindMeBot&subject=Reminder&message=[{original}]"
			"%0A%0ARemindMe!)"
			"\n\n_____\n\n"
			"|[^(FAQs)](http://np.reddit.com/r/RemindMeBot/comments/24duzp/remindmebot_info/)"
			"|[^(Custom)](http://np.reddit.com/message/compose/?to=RemindMeBot&subject=Reminder&message="
				"[LINK INSIDE SQUARE BRACKETS else default to FAQs]%0A%0A"
				"NOTE: Don't forget to add the time options after the command.%0A%0ARemindMe!)"
			"|[^(Your Reminders)](http://np.reddit.com/message/compose/?to=RemindMeBot&subject=List Of Reminders&message=MyReminders!)"
			"|[^(Feedback)](http://np.reddit.com/message/compose/?to=RemindMeBotWrangler&subject=Feedback)"
			"|[^(Code)](https://github.com/SIlver--/remindmebot-reddit)"
			"|[^(Browser Extensions)](https://np.reddit.com/r/RemindMeBot/comments/4kldad/remindmebot_extensions/)"
			"\n|-|-|-|-|-|-|"
			)

	def parent_comment(self, dbPermalink):
		"""
		Returns the parent comment or if it's a top comment
		return the original submission
		"""
		try:
			if dbPermalink.startswith("www"):
				dbPermalink = "https://"+dbPermalink
			commentObj = reddit.comment(url=dbPermalink)
			if commentObj.is_root:
				return commentObj.submission.permalink
			else:
				return commentObj.parent().permalink
		except IndexError as err:
			print("parrent_comment error")
			return "It seems your original comment was deleted, unable to return parent comment."
		# Catch any URLs that are not reddit comments
		except Exception  as err:
			print(err)
			print("HTTPError/PRAW parent comment")
			return "Parent comment not required for this URL."

	def time_to_reply(self):
		"""
		Checks to see through SQL if net_date is < current time
		"""

		# get current time to compare
		currentTime = datetime.now(timezone('UTC'))
		currentTime = format(currentTime, '%Y-%m-%d %H:%M:%S')
		cmd = "SELECT * FROM message_date WHERE new_date < ? order by new_date DESC"
		self._queryDB.cursor.execute(cmd, (currentTime,))

	def search_db(self):
		"""
		Loop through data looking for which comments are old
		"""

		data = self._queryDB.cursor.fetchall()
		alreadyCommented = []
		for row in data:
			# checks to make sure ID hasn't been commented already
			# For situtations where errors happened
			if row[0] not in alreadyCommented:
				flagDelete = False
				# MySQl- permalink, message, origin date, reddit user
				flagDelete = self.new_reply(row[1],row[2], row[4], row[5])
				# removes row based on flagDelete
				if flagDelete:
					cmd = "DELETE FROM message_date WHERE id = ?"
					self._queryDB.cursor.execute(cmd, (row[0],))
					self._queryDB.connection.commit()
					alreadyCommented.append(row[0])

		self._queryDB.connection.commit()
		self._queryDB.connection.close()

	def new_reply(self, permalink, message, origin_date, author):
		"""
		Replies a second time to the user after a set amount of time
		""" 
		"""
		print(self._replyMessage.format(
				message,
				permalink
			)
		"""
		print("---------------")
		print(author)
		print(permalink)

		origin_date_text = ""
		# Before feature was implemented, there are no origin dates stored
		if origin_date is not None:
			origin_date_text =  ("\n\nYou requested this reminder on: " 
								"[**" + str(origin_date) + " UTC**](http://www.wolframalpha.com/input/?i="
								+ str(origin_date) + " UTC To Local Time)")

		try:
			reddit.redditor(str(author)).message(
				subject='Hello, ' + str(author) + ' RemindMeBot Here!',
				message=self._replyMessage.format(
					message=str(message),
					original=str(permalink),
					parent= self.parent_comment(permalink),
					origin_date_text = origin_date_text
				))
			print("Did It")
			return True
		except APIException as err:
			print("APIException", err)
			return False
		except IndexError as err:
			print("IndexError", err)
			return False
		except (HTTPError, ConnectionError, Timeout, timeout) as err:
			print("HTTPError", err)
			time.sleep(10)
			return False


# =============================================================================
# MAIN
# =============================================================================

def main():
	while True:
		checkReply = Reply()
		checkReply.time_to_reply()
		checkReply.search_db()
		time.sleep(10)


# =============================================================================
# RUNNER
# =============================================================================
print("start")
if __name__ == '__main__':
	main()