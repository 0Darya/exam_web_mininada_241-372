import os
import hashlib
import bleach
import markdown
from flask import Flask, render_template, request, redirect, url_for, flash, current_app
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Role, Book, Genre, BookGenre, Cover, Review
from functools import wraps

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'  # Можно заменить на mysql+pymysql://...
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'super-secret-key-change-in-production'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Для выполнения данного действия необходимо пройти процедуру аутентификации'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- Декораторы прав ---
def roles_required(*roles):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if current_user.role.name not in roles:
                flash('У вас недостаточно прав для выполнения данного действия', 'danger')
                return redirect(url_for('index'))
            return fn(*args, **kwargs)

        return decorated_view

    return wrapper


# --- Маршруты ---
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)

    # Поиск (Вариант 3)
    search_title = request.args.get('title', '')
    search_author = request.args.get('author', '')
    search_genres = request.args.getlist('genre', type=int)
    search_years = request.args.getlist('year', type=int)
    pages_from = request.args.get('pages_from', type=int)
    pages_to = request.args.get('pages_to', type=int)

    query = Book.query

    if search_title:
        query = query.filter(Book.title.ilike(f'%{search_title}%'))
    if search_author:
        query = query.filter(Book.author.ilike(f'%{search_author}%'))
    if search_genres:
        query = query.join(BookGenre).filter(BookGenre.genre_id.in_(search_genres))
    if search_years:
        query = query.filter(Book.year.in_(search_years))
    if pages_from:
        query = query.filter(Book.pages >= pages_from)
    if pages_to:
        query = query.filter(Book.pages <= pages_to)

    # Сортировка по году (новые сначала)
    query = query.order_by(Book.year.desc())

    pagination = query.paginate(page=page, per_page=10, error_out=False)

    # Для формы поиска: доступные годы и жанры
    available_years = [r[0] for r in db.session.query(Book.year).distinct().order_by(Book.year.desc()).all()]
    all_genres = Genre.query.all()

    return render_template('index.html',
                           books=pagination.items,
                           pagination=pagination,
                           available_years=available_years,
                           all_genres=all_genres,
                           search_title=search_title, search_author=search_author,
                           search_genres=search_genres, search_years=search_years,
                           pages_from=pages_from, pages_to=pages_to)


@app.route('/book/<int:book_id>')
def view_book(book_id):
    book = Book.query.get_or_404(book_id)
    # Санитизация и рендер Markdown при отображении
    html_description = bleach.clean(markdown.markdown(book.description),
                                    tags=['p', 'b', 'i', 'u', 'a', 'ul', 'ol', 'li', 'h1', 'h2', 'h3'])

    user_review = None
    if current_user.is_authenticated:
        user_review = Review.query.filter_by(book_id=book_id, user_id=current_user.id).first()

    return render_template('book_view.html', book=book, html_description=html_description, user_review=user_review)


@app.route('/book/add', methods=['GET', 'POST'])
@login_required
@roles_required('администратор')
def add_book():
    return handle_book_form(None)


@app.route('/book/edit/<int:book_id>', methods=['GET', 'POST'])
@login_required
@roles_required('администратор', 'модератор')
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)
    return handle_book_form(book)


def handle_book_form(book):
    genres = Genre.query.all()
    if request.method == 'POST':
        try:
            title = request.form['title']
            description = request.form['description']
            year = int(request.form['year'])
            publisher = request.form['publisher']
            author = request.form['author']
            pages = int(request.form['pages'])
            genre_ids = request.form.getlist('genres', type=int)

            # Санитизация описания
            clean_description = bleach.clean(description,
                                             tags=['p', 'b', 'i', 'u', 'a', 'ul', 'ol', 'li', 'h1', 'h2', 'h3'])

            if not book:
                book = Book(title=title, description=clean_description, year=year, publisher=publisher, author=author,
                            pages=pages)
                db.session.add(book)
            else:
                # Обновляем поля существующей книги
                book.title = title
                book.description = clean_description
                book.year = year
                book.publisher = publisher
                book.author = author
                book.pages = pages

            # Flush чтобы получить ID книги для обложки
            db.session.flush()

            # Обработка обложки (только при создании)
            if not book.cover and 'cover' in request.files:
                file = request.files['cover']
                if file and file.filename != '':
                    file_content = file.read()
                    file.seek(0)

                    md5_hash = hashlib.md5(file_content).hexdigest()
                    existing_cover = Cover.query.filter_by(md5_hash=md5_hash).first()

                    if existing_cover:
                        book.cover = existing_cover
                    else:
                        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
                        new_filename = f"cover_{book.id}.{ext}"
                        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], new_filename)
                        file.save(filepath)

                        new_cover = Cover(
                            filename=new_filename,
                            mime_type=file.content_type or 'image/jpeg',
                            md5_hash=md5_hash,
                            book_id=book.id
                        )
                        db.session.add(new_cover)

            # Обновление жанров
            book.genres = Genre.query.filter(Genre.id.in_(genre_ids)).all()

            db.session.commit()
            flash('Книга успешно сохранена', 'success')
            return redirect(url_for('view_book', book_id=book.id))

        except Exception as e:
            db.session.rollback()
            flash('При сохранении данных возникла ошибка. Проверьте корректность введённых данных.', 'danger')
            print(e)

    return render_template('book_form.html', book=book, genres=genres)


@app.route('/book/delete/<int:book_id>', methods=['POST'])
@login_required
@roles_required('администратор')
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)
    title = book.title

    try:
        # Удаляем файл обложки из ФС, если он есть и не используется другими книгами
        if book.cover:
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], book.cover.filename)
            if os.path.exists(filepath):
                # Проверяем, не используется ли этот хэш другой книгой (на всякий случай, хотя cascade удалит запись)
                if Cover.query.filter_by(md5_hash=book.cover.md5_hash).count() == 1:
                    os.remove(filepath)

        db.session.delete(book)
        db.session.commit()
        flash(f'Книга "{title}" успешно удалена', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при удалении книги', 'danger')

    return redirect(url_for('index'))


@app.route('/review/add/<int:book_id>', methods=['GET', 'POST'])
@login_required
def add_review(book_id):
    book = Book.query.get_or_404(book_id)
    if Review.query.filter_by(book_id=book_id, user_id=current_user.id).first():
        flash('Вы уже оставляли рецензию на эту книгу', 'warning')
        return redirect(url_for('view_book', book_id=book_id))

    if request.method == 'POST':
        try:
            rating = int(request.form['rating'])
            text = request.form['text']

            clean_text = bleach.clean(markdown.markdown(text), tags=['p', 'b', 'i', 'u', 'a', 'ul', 'ol', 'li'])

            review = Review(
                book_id=book_id,
                user_id=current_user.id,
                rating=rating,
                text=clean_text
            )
            db.session.add(review)
            db.session.commit()
            flash('Рецензия успешно добавлена', 'success')
            return redirect(url_for('view_book', book_id=book_id))
        except Exception as e:
            db.session.rollback()
            flash('При сохранении рецензии возникла ошибка', 'danger')

    return render_template('review_form.html', book=book)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        login_str = request.form['login']
        password = request.form['password']
        user = User.query.filter_by(login=login_str).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember='remember' in request.form)
            return redirect(request.args.get('next') or url_for('index'))
        else:
            flash('Невозможно аутентифицироваться с указанными логином и паролем', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы успешно вышли из системы', 'info')
    return redirect(request.args.get('next') or url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)