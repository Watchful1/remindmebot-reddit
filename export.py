import MySQLdb
import sqlite3

sqliteConn = sqlite3.connect("database.db")
sqliteCur = sqliteConn.cursor()

sqliteCur.execute("drop table if exists comment_list")
sqliteCur.execute('''
	CREATE TABLE IF NOT EXISTS comment_list (
		list longtext,
		id INTEGER PRIMARY KEY AUTOINCREMENT
	)
	''')
sqliteCur.execute("drop table if exists message_date")
sqliteCur.execute('''
	CREATE TABLE IF NOT EXISTS message_date (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		permalink varchar(400) NOT NULL DEFAULT '',
		message varchar(11000) DEFAULT NULL,
		new_date datetime DEFAULT NULL,
		origin_date datetime DEFAULT NULL,
		userID varchar(50) DEFAULT NULL
	)
	''')


mysqlConn = MySQLdb.connect(host="localhost", user="root", passwd="x", db="bot")
mysqlCur = mysqlConn.cursor()



mysqlCur.execute("SELECT list, id FROM comment_list")

i = 0
for row in mysqlCur.fetchall():
	try:
		sqliteCur.execute("INSERT INTO comment_list (list, id) VALUES (?, ?)", (
				row[0],
				row[1]
			))
	except Exception as err:
		print(err)
		print(row[0])
		print(row[1])
		print("-----------------------------------------------")

	if i % 10000 == 0:
		print(str(i))
	i += 1



mysqlCur.execute("SELECT id, permalink, message, new_date, origin_date, userID FROM message_date")

i = 0
for row in mysqlCur.fetchall():
	try:
		sqliteCur.execute("INSERT INTO message_date (id, permalink, message, new_date, origin_date, userID) VALUES (?, ?, ?, ?, ?, ?)", (
				row[0],
				row[1].decode('utf-8', 'replace'),
				row[2].decode('utf-8', 'replace'),
				str(row[3]),
				str(row[4]),
				row[5]
			))
	except Exception as err:
		print(err)
		print(row[0])
		print(row[1])
		print(row[2])
		print("-----------------------------------------------")

	if i % 10000 == 0:
		print(str(i))
	i += 1

sqliteConn.commit()
sqliteConn.close()
