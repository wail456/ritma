from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional

from .models import CATEGORIES


def _strip(value):
    return value.strip() if isinstance(value, str) else value


def _lower(value):
    return value.lower() if isinstance(value, str) else value


class RegisterForm(FlaskForm):
    username = StringField(
        "Nama panggilan",
        filters=[_strip],
        validators=[
            DataRequired("Nama panggilan wajib diisi."),
            Length(min=2, max=50, message="Nama panggilan 2 sampai 50 karakter."),
        ],
    )
    email = StringField(
        "Email",
        filters=[_strip, _lower],
        validators=[
            DataRequired("Email wajib diisi."),
            Email("Format email tidak valid."),
            Length(max=120, message="Email maksimal 120 karakter."),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired("Password wajib diisi."),
            Length(min=8, max=128, message="Password minimal 8 karakter."),
        ],
    )
    confirm = PasswordField(
        "Ulangi password",
        validators=[DataRequired("Ulangi password kamu."), EqualTo("password", "Password tidak sama.")],
    )


class LoginForm(FlaskForm):
    # Sengaja tanpa validator format email: login cukup mencocokkan ke database.
    email = StringField("Email", filters=[_strip, _lower], validators=[DataRequired("Email wajib diisi.")])
    password = PasswordField("Password", validators=[DataRequired("Password wajib diisi.")])
    remember = BooleanField("Ingat saya")


class HabitForm(FlaskForm):
    name = StringField(
        "Nama habit",
        filters=[_strip],
        validators=[
            DataRequired("Nama habit wajib diisi."),
            Length(max=80, message="Nama habit maksimal 80 karakter."),
        ],
    )
    description = TextAreaField(
        "Catatan",
        filters=[_strip],
        validators=[Optional(), Length(max=300, message="Catatan maksimal 300 karakter.")],
    )
    category = SelectField("Kategori", choices=list(CATEGORIES), default="General")
