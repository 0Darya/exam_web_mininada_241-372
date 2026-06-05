from app import app, db
from models import Role, User, Genre
from werkzeug.security import generate_password_hash

with app.app_context():
    db.create_all()

    # Создание ролей
    roles_data = [
        ('администратор', 'Суперпользователь, имеет полный доступ к системе'),
        ('модератор', 'Может редактировать данные книг и производить модерацию рецензий'),
        ('пользователь', 'Может оставлять рецензии')
    ]

    for name, desc in roles_data:
        if not Role.query.filter_by(name=name).first():
            db.session.add(Role(name=name, description=desc))

    # Получаем роли
    admin_role = Role.query.filter_by(name='администратор').first()
    moderator_role = Role.query.filter_by(name='модератор').first()
    user_role = Role.query.filter_by(name='пользователь').first()

    # Создание тестового админа
    if not User.query.filter_by(login='admin').first():
        user = User(
            login='admin',
            password_hash=generate_password_hash('admin'),
            last_name='Минина',
            first_name='Дарья',
            middle_name='Андреевна',
            role_id=admin_role.id
        )
        db.session.add(user)

    # Создание тестового модератора
    if not User.query.filter_by(login='moderator').first():
        user = User(
            login='moderator',
            password_hash=generate_password_hash('moderator'),
            last_name='Петров',
            first_name='Петр',
            middle_name='Петрович',
            role_id=moderator_role.id
        )
        db.session.add(user)

    # Создание тестового пользователя
    if not User.query.filter_by(login='user').first():
        user = User(
            login='user',
            password_hash=generate_password_hash('user'),
            last_name='Васильев',
            first_name='Василий',
            role_id=user_role.id
        )
        db.session.add(user)

    # Создание тестовых жанров
    genres_data = ['Фантастика', 'Детектив', 'Роман', 'Научная литература', 'Учебник']
    for g in genres_data:
        if not Genre.query.filter_by(name=g).first():
            db.session.add(Genre(name=g))

    db.session.commit()
    print("База данных инициализирована!")
    print("Доступные пользователи:")
    print("  Администратор: логин 'admin', пароль 'admin'")
    print("  Модератор:     логин 'moderator', пароль 'moderator'")
    print("  Пользователь:  логин 'user', пароль 'user'")