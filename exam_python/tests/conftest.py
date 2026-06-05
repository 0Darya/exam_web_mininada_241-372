import os
import sys
import io
import pytest
import shutil

# Автоматически добавляем корневую папку проекта в PATH, чтобы импорты работали из папки tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db
from models import Role, User, Genre
from werkzeug.security import generate_password_hash


@pytest.fixture(scope='function')
def test_client():
    """Создает тестовый клиент Flask без управления контекстом БД."""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'test_uploads')

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    with app.test_client() as client:
        yield client

    # Очистка папки с тестовыми файлами
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        shutil.rmtree(app.config['UPLOAD_FOLDER'])


@pytest.fixture(scope='function')
def init_db(test_client):
    """Инициализирует БД и тестовые данные для каждого теста в своем контексте."""
    with app.app_context():
        db.create_all()

        # Создание ролей
        roles = [
            Role(name='администратор', description='Суперпользователь'),
            Role(name='модератор', description='Модерация'),
            Role(name='пользователь', description='Обычный пользователь')
        ]
        db.session.add_all(roles)

        # Создание жанров
        genres = [Genre(name='Фантастика'), Genre(name='Детектив'), Genre(name='Наука')]
        db.session.add_all(genres)

        # Создание пользователей
        admin_role = Role.query.filter_by(name='администратор').first()
        user_role = Role.query.filter_by(name='пользователь').first()

        # Пароли: admin123 и user123
        admin = User(login='admin', password_hash=generate_password_hash('admin123'),
                     last_name='Минина', first_name='Дарья', middle_name='Андреевна', role_id=admin_role.id)
        user = User(login='user', password_hash=generate_password_hash('user123'),
                    last_name='Петров', first_name='Петр', role_id=user_role.id)
        db.session.add_all([admin, user])
        db.session.commit()

        yield {
            'admin': admin,
            'user': user,
            'genres': genres
        }

        # Очистка после теста
        db.session.remove()
        db.drop_all()


def login(client, login_str, password):
    """Хелпер для входа в систему."""
    return client.post('/login', data=dict(
        login=login_str,
        password=password,
        remember=True
    ), follow_redirects=True)


def create_test_image():
    """Создает фейковый файл изображения для тестов."""
    return (io.BytesIO(b"fake image content for md5 test"), 'test_cover.jpg')