import os
import pytest
from app import db
from models import Book, Review, Cover, BookGenre
from conftest import login, create_test_image


# ==========================================
# 1. Аутентификация и авторизация (4 теста)
# ==========================================

def test_login_success(test_client, init_db):
    response = login(test_client, 'admin', 'admin123')
    data = response.data.decode('utf-8')
    assert 'Минина Дарья Андреевна' in data
    assert 'администратор' in data


def test_login_failure(test_client, init_db):
    response = login(test_client, 'admin', 'wrongpassword')
    data = response.data.decode('utf-8')
    assert 'Невозможно аутентифицироваться' in data


def test_unauthenticated_access_restriction(test_client, init_db):
    response = test_client.get('/book/add', follow_redirects=True)
    data = response.data.decode('utf-8')
    assert 'Для выполнения данного действия необходимо пройти процедуру аутентификации' in data


def test_insufficient_privileges(test_client, init_db):
    login(test_client, 'user', 'user123')
    response = test_client.get('/book/add', follow_redirects=True)
    data = response.data.decode('utf-8')
    assert 'У вас недостаточно прав для выполнения данного действия' in data


# ==========================================
# 2. Управление книгами: Создание и Чтение (4 теста)
# ==========================================

def test_add_book_success(test_client, init_db):
    login(test_client, 'admin', 'admin123')
    genre = init_db['genres'][0]

    response = test_client.post('/book/add', data={
        'title': 'Тестовая книга',
        'author': 'Тестовый Автор',
        'year': 2023,
        'pages': 300,
        'publisher': 'Тест Издат',
        'description': 'Описание книги',
        'genres': [genre.id]
    }, follow_redirects=True)

    data = response.data.decode('utf-8')
    assert 'Книга успешно сохранена' in data
    book = Book.query.filter_by(title='Тестовая книга').first()
    assert book is not None
    assert book.genres[0].name == 'Фантастика'


def test_add_book_sanitization(test_client, init_db):
    login(test_client, 'admin', 'admin123')
    genre = init_db['genres'][0]

    malicious_desc = '<script>alert("xss")</script><b>Жирный текст</b>'
    test_client.post('/book/add', data={
        'title': 'Книга с XSS',
        'author': 'Автор',
        'year': 2023,
        'pages': 100,
        'publisher': 'Издательство',
        'description': malicious_desc,
        'genres': [genre.id]
    })

    book = Book.query.filter_by(title='Книга с XSS').first()
    assert '<script>' not in book.description
    assert '<b>Жирный текст</b>' in book.description


def test_view_book_markdown_rendering(test_client, init_db):
    login(test_client, 'admin', 'admin123')
    genre = init_db['genres'][0]
    test_client.post('/book/add', data={
        'title': 'Markdown Книга',
        'author': 'Автор',
        'year': 2023,
        'pages': 100,
        'publisher': 'Издательство',
        'description': '# Заголовок\n**Жирный**',
        'genres': [genre.id]
    })

    book = Book.query.filter_by(title='Markdown Книга').first()
    response = test_client.get(f'/book/{book.id}')
    data = response.data.decode('utf-8')
    assert '<h1' in data and 'Заголовок' in data


def test_cover_upload_and_deduplication(test_client, init_db):
    login(test_client, 'admin', 'admin123')
    genre = init_db['genres'][0]

    test_client.post('/book/add', data={
        'title': 'Книга 1', 'author': 'Автор', 'year': 2023, 'pages': 100,
        'publisher': 'Изд', 'description': 'Опис', 'genres': [genre.id],
        'cover': create_test_image()
    }, content_type='multipart/form-data')

    test_client.post('/book/add', data={
        'title': 'Книга 2', 'author': 'Автор', 'year': 2023, 'pages': 100,
        'publisher': 'Изд', 'description': 'Опис', 'genres': [genre.id],
        'cover': create_test_image()
    }, content_type='multipart/form-data')

    covers = Cover.query.all()
    assert len(covers) == 1, "Должна быть только одна запись обложки из-за совпадения MD5"


# ==========================================
# 3. Управление книгами: Обновление и Удаление (4 теста)
# ==========================================

def test_edit_book_moderator(test_client, init_db):
    login(test_client, 'admin', 'admin123')
    genre = init_db['genres'][0]
    test_client.post('/book/add', data={
        'title': 'Книга для редактирования', 'author': 'Автор', 'year': 2020,
        'pages': 100, 'publisher': 'Изд', 'description': 'Опис', 'genres': [genre.id]
    })
    book = Book.query.filter_by(title='Книга для редактирования').first()

    test_client.post(f'/book/edit/{book.id}', data={
        'title': 'Измененная книга', 'author': 'Автор', 'year': 2021,
        'pages': 150, 'publisher': 'Изд', 'description': 'Опис', 'genres': [genre.id]
    }, follow_redirects=True)

    updated_book = db.session.get(Book, book.id)
    assert updated_book.title == 'Измененная книга'
    assert updated_book.year == 2021


def test_delete_book_admin(test_client, init_db):
    login(test_client, 'admin', 'admin123')
    genre = init_db['genres'][0]
    test_client.post('/book/add', data={
        'title': 'Книга для удаления', 'author': 'Автор', 'year': 2020,
        'pages': 100, 'publisher': 'Изд', 'description': 'Опис', 'genres': [genre.id]
    })
    book = Book.query.filter_by(title='Книга для удаления').first()

    response = test_client.post(f'/book/delete/{book.id}', follow_redirects=True)
    data = response.data.decode('utf-8')
    # Проверяем просто наличие текста об успешном удалении
    assert 'успешно удалена' in data
    assert db.session.get(Book, book.id) is None


def test_delete_book_cascade(test_client, init_db):
    login(test_client, 'admin', 'admin123')
    genre = init_db['genres'][0]
    test_client.post('/book/add', data={
        'title': 'Книга с рецензией', 'author': 'Автор', 'year': 2020,
        'pages': 100, 'publisher': 'Изд', 'description': 'Опис', 'genres': [genre.id]
    })
    book = Book.query.filter_by(title='Книга с рецензией').first()

    test_client.post(f'/review/add/{book.id}', data={'rating': 5, 'text': 'Супер'})
    test_client.post(f'/book/delete/{book.id}', follow_redirects=True)

    assert Review.query.filter_by(book_id=book.id).count() == 0
    assert BookGenre.query.filter_by(book_id=book.id).count() == 0


def test_delete_book_file_cleanup(test_client, init_db):
    login(test_client, 'admin', 'admin123')
    genre = init_db['genres'][0]
    test_client.post('/book/add', data={
        'title': 'Книга с уникальной обложкой', 'author': 'Автор', 'year': 2020,
        'pages': 100, 'publisher': 'Изд', 'description': 'Опис', 'genres': [genre.id],
        'cover': create_test_image()
    }, content_type='multipart/form-data')

    book = Book.query.filter_by(title='Книга с уникальной обложкой').first()
    cover_filename = book.cover.filename
    filepath = os.path.join(test_client.application.config['UPLOAD_FOLDER'], cover_filename)
    assert os.path.exists(filepath)

    test_client.post(f'/book/delete/{book.id}', follow_redirects=True)
    assert not os.path.exists(filepath)


# ==========================================
# 4. Рецензии (4 теста)
# ==========================================

def test_add_review_success(test_client, init_db):
    login(test_client, 'admin', 'admin123')
    genre = init_db['genres'][0]
    test_client.post('/book/add', data={
        'title': 'Книга для рецензии', 'author': 'Автор', 'year': 2020,
        'pages': 100, 'publisher': 'Изд', 'description': 'Опис', 'genres': [genre.id]
    })
    book = Book.query.filter_by(title='Книга для рецензии').first()

    response = test_client.post(f'/review/add/{book.id}', data={
        'rating': 4, 'text': 'Хорошая книга'
    }, follow_redirects=True)

    data = response.data.decode('utf-8')
    assert 'Рецензия успешно добавлена' in data
    assert Review.query.filter_by(book_id=book.id, user_id=init_db['admin'].id).first() is not None


def test_add_review_sanitization(test_client, init_db):
    # Сначала админ создает книгу
    login(test_client, 'admin', 'admin123')
    genre = init_db['genres'][0]
    test_client.post('/book/add', data={
        'title': 'Книга для XSS рецензии', 'author': 'Автор', 'year': 2020,
        'pages': 100, 'publisher': 'Изд', 'description': 'Опис', 'genres': [genre.id]
    })
    book = Book.query.filter_by(title='Книга для XSS рецензии').first()

    # Теперь обычный пользователь пишет рецензию
    test_client.get('/logout')
    login(test_client, 'user', 'user123')

    test_client.post(f'/review/add/{book.id}', data={
        'rating': 1, 'text': '<img src=x onerror=alert(1)>'
    })

    review = Review.query.filter_by(book_id=book.id).first()
    assert '<img' not in review.text


def test_add_review_duplicate_prevention(test_client, init_db):
    # Сначала админ создает книгу
    login(test_client, 'admin', 'admin123')
    genre = init_db['genres'][0]
    test_client.post('/book/add', data={
        'title': 'Книга с одной рецензией', 'author': 'Автор', 'year': 2020,
        'pages': 100, 'publisher': 'Изд', 'description': 'Опис', 'genres': [genre.id]
    })
    book = Book.query.filter_by(title='Книга с одной рецензией').first()

    # Теперь обычный пользователь пишет рецензию
    test_client.get('/logout')
    login(test_client, 'user', 'user123')

    test_client.post(f'/review/add/{book.id}', data={'rating': 5, 'text': 'Первая'})
    response = test_client.post(f'/review/add/{book.id}', data={'rating': 1, 'text': 'Вторая'}, follow_redirects=True)

    data = response.data.decode('utf-8')
    assert 'Вы уже оставляли рецензию на эту книгу' in data
    assert Review.query.filter_by(book_id=book.id, user_id=init_db['user'].id).count() == 1


def test_book_average_rating(test_client, init_db):
    login(test_client, 'admin', 'admin123')
    genre = init_db['genres'][0]
    test_client.post('/book/add', data={
        'title': 'Книга для рейтинга', 'author': 'Автор', 'year': 2020,
        'pages': 100, 'publisher': 'Изд', 'description': 'Опис', 'genres': [genre.id]
    })
    book = Book.query.filter_by(title='Книга для рейтинга').first()

    test_client.post(f'/review/add/{book.id}', data={'rating': 5, 'text': 'Отлично'})

    test_client.get('/logout')
    login(test_client, 'user', 'user123')
    test_client.post(f'/review/add/{book.id}', data={'rating': 3, 'text': 'Норм'})

    response = test_client.get('/')
    data = response.data.decode('utf-8')
    assert '4.0' in data


# ==========================================
# 5. Поиск и Пагинация (Вариант 3) (4 теста)
# ==========================================

def test_search_by_title_partial(test_client, init_db):
    login(test_client, 'admin', 'admin123')
    genre = init_db['genres'][0]
    test_client.post('/book/add', data={
        'title': 'Война и Мир', 'author': 'Толстой', 'year': 1869,
        'pages': 1000, 'publisher': 'Классика', 'description': 'Роман', 'genres': [genre.id]
    })

    response = test_client.get('/?title=Война')
    data = response.data.decode('utf-8')
    assert 'Война и Мир' in data

    response_fail = test_client.get('/?title=Преступление')
    data_fail = response_fail.data.decode('utf-8')
    assert 'Война и Мир' not in data_fail


def test_search_by_multiple_genres(test_client, init_db):
    login(test_client, 'admin', 'admin123')
    g1 = init_db['genres'][0]
    g2 = init_db['genres'][1]

    test_client.post('/book/add', data={
        'title': 'Дюна', 'author': 'Герберт', 'year': 1965,
        'pages': 700, 'publisher': 'Sci-Fi', 'description': 'Опис', 'genres': [g1.id, g2.id]
    })

    response = test_client.get(f'/?genre={g1.id}&genre={g2.id}')
    data = response.data.decode('utf-8')
    assert 'Дюна' in data


def test_search_by_pages_range(test_client, init_db):
    login(test_client, 'admin', 'admin123')
    genre = init_db['genres'][0]
    test_client.post('/book/add', data={
        'title': 'Короткая книга', 'author': 'Автор', 'year': 2020,
        'pages': 150, 'publisher': 'Изд', 'description': 'Опис', 'genres': [genre.id]
    })
    test_client.post('/book/add', data={
        'title': 'Длинная книга', 'author': 'Автор', 'year': 2021,
        'pages': 500, 'publisher': 'Изд', 'description': 'Опис', 'genres': [genre.id]
    })

    response = test_client.get('/?pages_from=100&pages_to=200')
    data = response.data.decode('utf-8')
    assert 'Короткая книга' in data
    assert 'Длинная книга' not in data


def test_pagination_preserves_search_params(test_client, init_db):
    login(test_client, 'admin', 'admin123')
    genre = init_db['genres'][0]

    for i in range(12):
        test_client.post('/book/add', data={
            'title': f'Книга {i}', 'author': 'Поиск Автор', 'year': 2020,
            'pages': 100, 'publisher': 'Изд', 'description': 'Опис', 'genres': [genre.id]
        })

    response = test_client.get('/?author=Поиск+Автор&page=2')
    data = response.data.decode('utf-8')

    assert 'Книга 10' in data
    # Проверяем наличие параметра author в URL (он будет URL-encoded)
    assert 'author=' in data and 'page=2' in data