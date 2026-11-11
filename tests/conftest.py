import pytest

from app import create_app
from app.extensions import db


@pytest.fixture()
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "WTF_CSRF_ENABLED": False,
        "SESSION_COOKIE_SECURE": False,
    })
    with app.app_context():
        db.create_all()
    # Konteks aplikasi tidak boleh dibiarkan terbuka: `g` (tempat Flask-Login
    # menyimpan user) akan dipakai bersama oleh semua request dan membocorkan login.
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, name="budi", email="budi@example.com", password="password123"):
    return client.post("/auth/register", data={
        "username": name, "email": email,
        "password": password, "confirm": password,
    }, follow_redirects=True)


@pytest.fixture()
def user_client(client):
    register(client)
    return client
