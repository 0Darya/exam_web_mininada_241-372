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

    # Создание тестового админа (логин: admin, пароль: admin)
    if not User.query.filter_by(login='admin').first():
        admin_role = Role.query.filter_by(name='администратор').first()
        user = User(
            login='admin',
            password_hash=generate_password_hash('admin'),
            last_name='Минина',
            first_name='Дарья',
            middle_name='Андреевна',
            role_id=admin_role.id
        )
        db.session.add(user)

    # Создание тестовых жанров
    genres_data = ['Фантастика', 'Детектив', 'Роман', 'Научная литература', 'Учебник']
    for g in genres_data:
        if not Genre.query.filter_by(name=g).first():
            db.session.add(Genre(name=g))

    db.session.commit()
    print("База данных инициализирована!")