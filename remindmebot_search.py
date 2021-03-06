#!/usr/bin/env python3

# =============================================================================
# IMPORTS
# =============================================================================
import traceback
import praw
import re
import sqlite3
import ast
import time
import requests
import parsedatetime.parsedatetime as pdt
from datetime import datetime
from praw.exceptions import APIException
from prawcore.exceptions import Forbidden
from pytz import timezone
from threading import Thread

# =============================================================================
# GLOBALS
# =============================================================================

#Reddit info
reddit = praw.Reddit("RemindMeBot", user_agent="RemindMeBot user agent")

# Time when program was started
START_TIME = time.time()
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

class Search(object):
	commented = [] # comments already replied to
	subId = [] # reddit threads already replied in
	
	# Fills subId with previous threads. Helpful for restarts
	database = Connect()
	cmd = "SELECT id FROM comment_list"
	database.cursor.execute(cmd)
	data = database.cursor.fetchall()
	if len(data):
		for row in data:
			subId.append(row[0])
	database.connection.commit()
	database.connection.close()

	endMessage = (
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

	def __init__(self, comment):
		self._addToDB = Connect()
		self.comment = comment # Reddit comment Object
		self._permalink = None
		self._messageInput = '"Hello, I\'m here to remind you to see the parent comment!"'
		self._storeTime = None
		self._replyMessage = ""
		self._replyDate = None
		self._originDate = datetime.fromtimestamp(comment.created_utc)
		self._privateMessage = False
		
	def run(self, privateMessage=False):
		self._privateMessage = privateMessage
		self.parse_comment()
		self.save_to_db()
		self.build_message(privateMessage)
		self.reply()
		if self._privateMessage == True:
			# Makes sure to marks as read, even if the above doesn't work
			self.comment.mark_read()
			self.find_bot_child_comment()
		self._addToDB.connection.close()

	def parse_comment(self):
		"""
		Parse comment looking for the message and time
		"""

		if self._privateMessage:
			print("----")
			self._permalink = "https://www.reddit.com/message/messages/" + self.comment.id
			print(self._permalink)
		else:
			print("----")
			self._permalink = "https://www.reddit.com" + self.comment.permalink
			print(self._permalink)

		# remove RemindMe! or !RemindMe (case insenstive)
		match = re.search(r'(?i)(!*)RemindMe(!*)[^bot]', self.comment.body)
		# and everything before
		try:
			tempString = self.comment.body[match.start():]
		except Exception as err:
			tempString = "' '"

		# remove all format breaking characters IE: [ ] ( ) newline
		tempString = tempString.split("\n")[0]
		# adds " at the end if only 1 exists
		if (tempString.count('"') == 1):
			tempString = tempString + '"'

		# Use message default if not found
		messageInputTemp = re.search('(["].{0,9000}["])', tempString)
		if messageInputTemp:
			self._messageInput = messageInputTemp.group()
		# Fix issue with dashes for parsedatetime lib
		tempString = tempString.replace('-', "/")
		# Remove RemindMe!
		self._storeTime = re.sub('(["].{0,9000}["])', '', tempString)[9:]
	
	def save_to_db(self):
		"""
		Saves the permalink comment, the time, and the message to the DB
		"""

		cal = pdt.Calendar()
		try:
			holdTime = cal.parse(self._storeTime, datetime.now(timezone('UTC')))
		except (ValueError, OverflowError):
			# year too long
			holdTime = cal.parse("9999-12-31")
		if holdTime[1] == 0:
			# default time
			holdTime = cal.parse("1 day", datetime.now(timezone('UTC')))
			self._replyMessage = "**Defaulted to one day.**\n\n"
		# Converting time
		#9999/12/31 HH/MM/SS
		self._replyDate = time.strftime('%Y-%m-%d %H:%M:%S', holdTime[0])
		cmd = "INSERT INTO message_date (permalink, message, new_date, origin_date, userID) VALUES (?, ?, ?, ?, ?)"
		self._addToDB.cursor.execute(cmd, (
						self._permalink.encode('utf-8'),
						self._messageInput.encode('utf-8'),
						self._replyDate,
						self._originDate.strftime('%Y-%m-%d %H:%M:%S'),
						self.comment.author.name))
		self._addToDB.connection.commit()
		# Info is added to DB, user won't be bothered a second time
		self.commented.append(self.comment.id)

	def build_message(self, privateMessage=False):
		"""
		Buildng message for user
		"""
		self._replyMessage +=(
			"I will be messaging you on [**{0} UTC**](http://www.wolframalpha.com/input/?i={0} UTC To Local Time)"
			" to remind you of [**this link.**]({commentPermalink})"
			"{remindMeMessage}")

		try:
			self.sub = self.comment.submission
		except Exception as err:
			print("link had http")
		if self._privateMessage == False and self.sub.id not in self.subId:
			remindMeMessage = (
				"\n\n[**CLICK THIS LINK**](http://np.reddit.com/message/compose/?to=RemindMeBot&subject=Reminder&message="
				"[{permalink}]%0A%0ARemindMe! {time}) to send a PM to also be reminded and to reduce spam."
				"\n\n^(Parent commenter can ) [^(delete this message to hide from others.)]"
				"(http://np.reddit.com/message/compose/?to=RemindMeBot&subject=Delete Comment&message=Delete! ____id____)").format(
					permalink=self._permalink,
					time=self._storeTime.replace('\n', '')
				)
		else:
			remindMeMessage = ""

		self._replyMessage = self._replyMessage.format(
				self._replyDate,
				remindMeMessage=remindMeMessage,
				commentPermalink=self._permalink)
		self._replyMessage += Search.endMessage

	def reply(self):
		"""
		Messages the user letting as a confirmation
		"""

		author = self.comment.author
		def send_message():
			author.message('Hello, ' + author.name + ' RemindMeBot Confirmation Sent', self._replyMessage)

		try:
			if self._privateMessage == False:
				# First message will be a reply in a thread
				# afterwards are PM in the same thread
				if (self.sub.id not in self.subId):
					newcomment = self.comment.reply(self._replyMessage)
					self.subId.append(self.sub.id)
					# adding it to database as well
					database = Connect()
					cmd = 'insert into comment_list (id) values (?)'
					database.cursor.execute(cmd, (self.sub.id,))
					database.connection.commit()
					database.connection.close()
					# grabbing comment just made
					reddit.comment(
							str(newcomment.id)
							# edit comment with self ID so it can be deleted
						).edit(self._replyMessage.replace('____id____', str(newcomment.id))) 
				else:
					send_message()
			else:
				print(str(author))
				send_message()
		except Forbidden as err:
			send_message()
		except APIException as err: # Catch any less specific API errors
			print(err)
		#else:
			#print(self._replyMessage

	def find_bot_child_comment(self):
		"""
		Finds the remindmebot comment in the child
		"""
		try:
			# Grabbing all child comments
			replies = reddit.submission(url=self._permalink).comments[0].replies
			# Look for bot's reply
			commentfound = ""
			if replies:
				for comment in replies:
					if str(comment.author) == "RemindMeBot":
						commentfound = comment
				self.comment_count(commentfound)
		except Exception as err:
			pass
			
	def comment_count(self, commentfound):
		"""
		Posts edits the count if found
		"""
		query = "SELECT count(DISTINCT userid) FROM message_date WHERE permalink = ?"
		self._addToDB.cursor.execute(query, (self._permalink,))
		data = self._addToDB.cursor.fetchall()
		# Grabs the tuple within the tuple, a number/the dbcount
		dbcount = count = str(data[0][0])
		comment = reddit.comment(str(commentfound.id))
		body = comment.body

		pattern = r'(\d+ OTHERS |)CLICK(ED|) THIS LINK'
		# Compares to see if current number is bigger
		# Useful for after some of the reminders are sent, 
		# a smaller number doesnt overwrite bigger
		try:
			currentcount = int(re.search(r'\d+', re.search(pattern, body).group(0)).group())
		# for when there is no number
		except AttributeError as err:
			currentcount = 0
		if currentcount > int(dbcount):
			count = str(currentcount + 1)
		# Adds the count to the post
		body = re.sub(
			pattern, 
			count + " OTHERS CLICKED THIS LINK", 
			body)
		comment.edit(body)
def grab_list_of_reminders(username):
	"""
	Grabs all the reminders of the user
	"""
	database = Connect()
	query = "SELECT permalink, message, new_date, id FROM message_date WHERE userid = ? ORDER BY new_date"
	database.cursor.execute(query, (username,))
	data = database.cursor.fetchall()
	table = (
			"[**Click here to delete all your reminders at once quickly.**]"
			"(http://np.reddit.com/message/compose/?to=RemindMeBot&subject=Reminder&message=RemoveAll!)\n\n"
			"|Permalink|Message|Date|Remove|\n"
			"|-|-|-|:-:|")
	for row in data:
		if isinstance(row[0], (bytes, bytearray)):
			permalink = row[0].decode("utf-8")
		else:
			permalink = row[0]
		if isinstance(row[1], (bytes, bytearray)):
			message = row[1].decode("utf-8")
		else:
			message = str(row[1])
		if isinstance(row[2], (bytes, bytearray)):
			date = row[2].decode("utf-8")
		else:
			date = str(row[2])
		if isinstance(row[3], (bytes, bytearray)):
			id = row[3].decode("utf-8")
		else:
			id = str(row[3])
		table += (
			"\n|" + permalink + "|" + message + "|" +
			"[" + date + " UTC](http://www.wolframalpha.com/input/?i=" + str(row[2]) + " UTC to local time)|"
			"[[X]](https://np.reddit.com/message/compose/?to=RemindMeBot&subject=Remove&message=Remove!%20"+ id + ")|"
			)
	if len(data) == 0: 
		table = "Looks like you have no reminders. Click the **[Custom]** button below to make one!"
	elif len(table) > 9000:
		table = "Sorry the comment was too long to display. Message /u/RemindMeBotWrangler as this was his lazy error catching."
	table += Search.endMessage
	return table

def remove_reminder(username, idnum):
	"""
	Deletes the reminder from the database
	"""
	database = Connect()
	# only want userid to confirm if owner
	query = "SELECT userid FROM message_date WHERE id = ?"
	database.cursor.execute(query, (idnum,))
	data = database.cursor.fetchall()
	deleteFlag = False
	for row in data:
		userid = str(row[0])
		# If the wrong ID number is given, item isn't deleted
		if userid == username:
			cmd = "DELETE FROM message_date WHERE id = ?"
			database.cursor.execute(cmd, (idnum,))
			deleteFlag = True

	
	database.connection.commit()
	return deleteFlag

def remove_all(username):
	"""
	Deletes all reminders at once
	"""
	database = Connect()
	query = "SELECT * FROM message_date where userid = ?"
	database.cursor.execute(query, (username,))
	count = len(database.cursor.fetchall())
	cmd = "DELETE FROM message_date WHERE userid = ?"
	database.cursor.execute(cmd, (username,))
	database.connection.commit()

	return count

def read_pm():
	try:
		for message in reddit.inbox.unread(limit=100):
			# checks to see as some comments might be replys and non PMs
			prawobject = isinstance(message, praw.models.Message)
			if (("remindme" in message.body.lower() or 
				"remindme!" in message.body.lower() or 
				"!remindme" in message.body.lower()) and prawobject):
				redditPM = Search(message)
				redditPM.run(privateMessage=True)
				message.mark_read()
			elif (("delete!" in message.body.lower() or "!delete" in message.body.lower()) and prawobject):  
				ids = re.findall(r'delete!\s(.*?)$', message.body.lower())
				if len(ids):
					givenid = ids[0]
					comment = reddit.comment(givenid)
					try:
						parentcomment = comment.parent()
						if message.author.name == parentcomment.author.name:
							comment.delete()
					except ValueError as err:
						# comment wasn't inside the list
						pass
					except AttributeError as err:
						# comment might be deleted already
						pass
				message.mark_read()
			elif (("myreminders!" in message.body.lower() or "!myreminders" in message.body.lower()) and prawobject):
				listOfReminders = grab_list_of_reminders(message.author.name)
				message.reply(listOfReminders)
				message.mark_read()
			elif (("remove!" in message.body.lower() or "!remove" in message.body.lower()) and prawobject):
				givenid = re.findall(r'remove!\s(.*?)$', message.body.lower())[0]
				deletedFlag = remove_reminder(message.author.name, givenid)
				listOfReminders = grab_list_of_reminders(message.author.name)
				# This means the user did own that reminder
				if deletedFlag == True:
					message.reply("Reminder deleted. Your current Reminders:\n\n" + listOfReminders)
				else:
					message.reply("Try again with the current IDs that belong to you below. Your current Reminders:\n\n" + listOfReminders)
				message.mark_read()
			elif (("removeall!" in message.body.lower() or "!removeall" in message.body.lower()) and prawobject):
				count = str(remove_all(message.author.name))
				listOfReminders = grab_list_of_reminders(message.author.name)
				message.reply("I have deleted all **" + count + "** reminders for you.\n\n" + listOfReminders)
				message.mark_read()
			message.mark_read()
	except Exception as err:
		print(traceback.format_exc())

def check_comment(comment):
	"""
	Checks the body of the comment, looking for the command
	"""
	redditCall = Search(comment)
	if (("remindme!" in comment.body.lower() or
		"!remindme" in comment.body.lower()) and 
		redditCall.comment.id not in redditCall.commented and
		'RemindMeBot' != str(comment.author) and
		START_TIME < redditCall.comment.created_utc):
			print("in")
			t = Thread(target=redditCall.run())
			t.start()

def check_own_comments():
	user = reddit.redditor("RemindMeBot")
	for comment in user.comments.new(limit=None):
		if comment.score <= -5:
			print("COMMENT DELETED")
			print(comment)
			comment.delete()
# =============================================================================
# MAIN
# =============================================================================

def main():
	print("start")
	checkcycle = 0
	while True:
		try:
			# grab the request
			request = requests.get('https://api.pushshift.io/reddit/search?q=%22RemindMe%22&limit=100', 
				headers = {'User-Agent': 'RemindMeBot-Agent'})
			json = request.json()
			comments =  json["data"]

			if checkcycle % 5 == 0:
				read_pm()

			for rawcomment in comments:
				# object constructor requires empty attribute
				rawcomment['_replies'] = ''
				comment = reddit.comment(rawcomment['id'])
				check_comment(comment)

			# Only check periodically 
			if checkcycle >= 1000:
				check_own_comments()
				checkcycle = 0
			else:
				checkcycle += 1

			print("----")
			time.sleep(5)
		except Exception as err:
			print(traceback.format_exc())
			time.sleep(10)
		"""
		Will add later if problem with api.pushshift
		hence why check_comment is a function
		try:
			for comment in praw.helpers.comment_stream(reddit, 'all', limit = 1, verbosity = 0):
				check_comment(comment)
		except Exception as err:
		   print(err
		"""
# =============================================================================
# RUNNER
# =============================================================================

if __name__ == '__main__':
	main()
