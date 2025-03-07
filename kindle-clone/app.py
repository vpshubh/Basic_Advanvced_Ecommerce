from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import requests
from bs4 import BeautifulSoup
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SECRET_KEY'] = 'your_secret_key_here'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class UserProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    favorite_books = db.Column(db.String(1000), default="")  # Comma-separated book titles

def fetch_books_from_gutendex(query=None):
    try:
        url = "https://gutendex.com/books/"
        params = {"search": query} if query else {}
        
        print(f"Fetching URL: {url}")  # Debug: Print the URL being fetched
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        books = []
        for book in data.get("results", [])[:6]:  # Limit to 6 results
            title = book.get("title", "Unknown Title")
            author = book.get("authors", [{"name": "Unknown Author"}])[0]["name"]
            formats = book.get("formats", {})
            
            # Get download links
            epub_url = formats.get("application/epub+zip", "#")
            pdf_url = formats.get("application/pdf", "#")
            text_url = formats.get("text/plain", "#")
            
            books.append({
                "title": title,
                "author": author,
                "epub_url": epub_url,
                "pdf_url": pdf_url,
                "text_url": text_url
            })
        
        print(f"Fetched {len(books)} books")  # Debug: Print the number of books fetched
        return books
    except Exception as e:
        print("Error fetching books:", e)
        return []
    
# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        user = User(username=username, password=password)
        try:
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except:
            flash('Username already exists!', 'error')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('library'))
        else:
            flash('Invalid username/password!',  'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully.', 'info')
    return redirect(url_for('home'))

@app.route('/library')
def library():
    if 'user_id' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
    
    search_query = request.args.get('search', '').strip()
    print(f"Search Query: {search_query}")  # Debug: Print the search query
    books = fetch_books_from_gutendex(query=search_query)
    print(f"Books: {books}")  # Debug: Print the fetched books
    
    return render_template('library.html', books=books, search_query=search_query)


@app.route('/save_favorite/<book_title>')
def save_favorite(book_title):
    if 'user_id' not in session:
        return "Unauthorized", 401
    
    profile = UserProfile.query.filter_by(user_id=session['user_id']).first()
    if not profile:
        profile = UserProfile(user_id=session['user_id'])
        db.session.add(profile)
    
    if book_title not in profile.favorite_books.split(','):
        profile.favorite_books += f"{book_title},"
        db.session.commit()
        flash('Book added to favorites!', 'success')
    else:
        flash('Book already in favorites!', 'info')
    
    return redirect(url_for('library'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
    
    profile = UserProfile.query.filter_by(user_id=session['user_id']).first()
    favorite_books = []
    
    if profile and profile.favorite_books:
        for book_title in profile.favorite_books.strip(',').split(','):
            books = fetch_books_from_hathitrust(query=book_title)
            if books:
                favorite_books.append(books[0])
    
    return render_template('profile.html', favorite_books=favorite_books)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)