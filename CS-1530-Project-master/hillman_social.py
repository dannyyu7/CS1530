from models import db, User, Book, Update
import sqlalchemy
import time
import os
from hashlib import md5
from datetime import datetime
from flask import Flask, request, session, url_for, redirect, render_template, abort, g, flash, _app_ctx_stack
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# configuration
PER_PAGE = 30
DEBUG = True
SECRET_KEY = '123456'

SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(app.root_path, 'hillman_social.db')

app.config.from_object(__name__)
app.config.from_envvar('HILLMAN_SOCIAL_SETTINGS', silent=True)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False #here to silence deprecation warning

db.init_app(app)

@app.cli.command('initdb')
def initdb_command():
	"""Creates the database tables."""
	db.create_all()

	# add admin as the first owner
	owner = User('admin', generate_password_hash('admin'))
	db.session.add(owner)
	db.session.commit()
	print('Initialized the database.')

@app.route("/")
def default():
	return redirect(url_for("login"))

@app.route("/login/", methods=["GET", "POST"])
def login():
	error = None
	user = None
	if 'username' in session: # You can't login twice, go to your main page
		return redirect(url_for('timeline'))
	if request.method == "POST":
		if not request.form['username']:
			error = 'You have to enter a username'
		elif not request.form['password']:
			error = 'You have to enter a password'
		else:
			user = User.query.filter_by(username=request.form['username']).first()
			if user == None:
				error = "Invalid username"
			if user != None:
				error = login(user, request.form["password"])
				if error == None:
					return redirect(url_for('timeline'))

	return render_template('login.html', error=error)

def login(user, password):
	if not check_password_hash(user.pw_hash, password):
		return "Invalid password"
	session['username'] = user.username
	return None

@app.route("/register/",  methods=["POST", "GET"])
def register():
	error = None
	if request.method == "POST":
		if not request.form['username']:
			error = 'You have to enter a username'
		elif not request.form['password']:
			error = 'You have to enter a password'
		else:
			user = User(request.form['username'], generate_password_hash(request.form['password']))
			db.session.add(user)
			db.session.commit()
			db.session.flush()

			flash("Welcome " + request.form['username'] + "! ")
			flash("You have successfully registered for an account!")
			session['username'] = user.username # Allows the session to remember user is logged in
	return render_template('register.html', error=error)

@app.route("/logout/",  methods=["GET"])
def logout():
	flash("You have been logged out.")
	session.pop('username', None)
	return redirect(url_for('login'))

@app.route("/books/",  methods=["POST", "GET"])
def books():
	error = None
	if 'username' not in session:
		abort(401) # Not authorized
	# Get the user
	user = User.query.filter_by(username=session['username']).first()
	books = Book.query.order_by(Book.title.asc()).all()
	if not user:
		abort(404)
	return render_template("books.html", error=error, user_name=user.username, books=books)

@app.route("/suggested_books/",  methods=["POST", "GET"])
def suggested_books():
	error = None
	if 'username' not in session:
		abort(401) # Not authorized
	# Get the user
	user = User.query.filter_by(username=session['username']).first()
	if not user:
		abort(404)

	# get user's prefered genre & validate
	if user.reading is None:
		flash('Start reading a book to get more recommendations')
		return redirect(url_for('books'))

	pref_genre = Book.query.filter_by(title=user.reading).first().genre

	if pref_genre is None:
		flash('Something went wrong')
		return redirect(url_for('books'))

	print(pref_genre)

	books = Book.query.order_by(Book.rating.desc()).all()

	for book in books:
		print(book.title + ': ' + book.genre)
		if book.genre != pref_genre or book.title == user.reading:
			print('removing')
			books.remove(book)

	return render_template("books.html", error=error, user_name=user.username, books=books)

@app.route("/timeline/",  methods=["POST", "GET"])
def timeline():
	error = None
	if 'username' not in session:
		abort(401) # Not authorized
	# Get the user
	user = User.query.filter_by(username=session['username']).first()
	updates = Update.query.order_by(Update.timestamp.desc()).limit(PER_PAGE).all()
	if not user:
		abort(404)
	return render_template("timeline.html", error=error, user_name=user.username, updates=updates)

@app.route("/review/<book_title>", methods=["POST", "GET"])
def review(book_title):
	if 'username' not in session:
		abort(401)
	error = None
	if request.method == 'POST':
		if not request.form['rating']:
			error = 'Please give this book a rating from 1 - 10'
		else:
			# update rating for book
			book = Book.query.filter_by(title=book_title).first()
			old_rating = book.rating
			if old_rating == 0:
				book.rating = request.form['rating']
				book.num_ratings = 1
			else:
				book.rating = round(((old_rating * book.num_ratings) + int(request.form['rating'])) / (book.num_ratings + 1), 1)
				book.num_ratings += 1

			db.session.add(Update('review', session['username'], book_title, request.form['content'], request.form['rating'], time.time()))
			db.session.commit()
			db.session.flush()
			flash("Submission successful")
			return redirect(url_for('timeline'))
	return render_template('review.html', book=Book.query.filter_by(title=book_title).first(), error=error)

@app.route("/begin/<book_title>/", methods=['GET', 'POST'])
def begin(book_title):
	if 'username' not in session:
		abort(401)
	error = None
	user = User.query.filter_by(username=session['username']).first()
	book = Book.query.filter_by(title=book_title).first()
	if not user:
		abort(404)
	user.reading = book_title
	db.session.add(Update('reading', session['username'], book_title, None, None, time.time()))
	db.session.commit()
	db.session.flush()
	flash('Enjoy \"' + book_title + '\"!')
	return redirect(url_for('timeline'))

@app.route("/book/<book_title>/", methods=['GET', 'POST'])
def book(book_title):
	if 'username' not in session:
		abort(401)
	error = None
	user = User.query.filter_by(username=session['username']).first()
	book = Book.query.filter_by(title=book_title).first()
	if not user:
		abort(404)
	return render_template("book.html", error=error, user_name=user.username, book=book)

@app.route("/manage/", methods=['POST', 'GET'])
def manage():
	error = None
	if session['username'] == 'admin':
		if request.method == 'POST':
			if not request.form['username']:
				error = 'You have to enter a username'
			elif not request.form['password']:
				error = 'You have to enter a password'
			elif User.query.filter_by(username=request.form['username']).first() is not None:
				error = 'User already exists'
			else:
				user = User(request.form['username'], generate_password_hash(request.form['password']))
				db.session.add(user)
				db.session.commit()
				db.session.flush()

				flash("New user " + request.form['username'] + " successfully registered")
		return render_template('manage.html', users=User.query.order_by(User.username.asc()).all(), error=error)
	else:
		flash("You do not have administrative priveleges")
		return redirect(url_for('timeline'))

@app.route("/remove/<username>/", methods=['POST', 'GET'])
def remove(username):
	error = None
	if session['username'] == 'admin':
		user = User.query.filter_by(username=username).first()
		db.session.delete(user)
		db.session.commit()
		db.session.flush()
		flash("User " + username + " successfully removed")
		return render_template('manage.html', users=User.query.order_by(User.username.asc()).all(), error=error)
	else:
		flash("You do not have administrative priveleges")
		return redirect(url_for('timeline'))

@app.route("/remove_update/<update_id>/", methods=['POST', 'GET'])
def remove_update(update_id):
	error = None
	update = Update.query.filter_by(update_id=update_id).first()
	db.session.delete(update)
	db.session.commit()
	db.session.flush()
	flash("Update successfully removed")
	return redirect(url_for('timeline'))

@app.route("/showbooks/")
def showbooks():
	if session['username'] == 'admin':
		return render_template('showbooks.html', books=Book.query.all())
	else:
		flash("You do not have administrative priveleges")
		return redirect(url_for('timeline'))

@app.route("/showusers/")
def showusers():
	if session['username'] == 'admin':
		return render_template('showusers.html', users=User.query.all())
	else:
		flash("You do not have administrative priveleges")
		return redirect(url_for('timeline'))

@app.route("/loadusers/")
def loadusers():
	if session['username'] == 'admin':
		file1 = open('users.txt', 'r')
		Lines = file1.readlines()

		# Strips the newline character
		for line in Lines:
			elems = line.split('|')
			db.session.add(User(elems[0], generate_password_hash('p')))
			db.session.commit()
			db.session.flush()
		file1.close()

		return redirect(url_for('manage'))
	else:
		flash("You do not have administrative priveleges")
		return redirect(url_for('timeline'))

@app.route("/loadbooks/")
def loadbooks():
	if session['username'] == 'admin':
		file1 = open('users.txt', 'r')
		Lines = file1.readlines()

		# add books to the db
		file1 = open('books.txt', 'r')
		Lines = file1.readlines()
		# Strips the newline character
		for line in Lines:
			elems = line.split('|')
			db.session.add(Book(elems[0], elems[1], elems[2], elems[3], 0))
			db.session.commit()
			db.session.flush()
		file1.close()

		return redirect(url_for('manage'))
	else:
		flash("You do not have administrative priveleges")
		return redirect(url_for('timeline'))

@app.route("/clearbooks/")
def clearbooks():
	if session['username'] == 'admin':

		Book.query.delete()
		db.session.commit()
		db.session.flush()

		return redirect(url_for('manage'))
	else:
		flash("You do not have administrative priveleges")
		return redirect(url_for('timeline'))

if __name__ == '__main__':
	app.run()
