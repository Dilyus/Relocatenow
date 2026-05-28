import csv
import json
import os
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from database import DATA_DIR, db_session, engine
from models import Attraction, Base, City, CityStats, Favorite, SearchHistory, User


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CITIES_FILE = os.path.join(DATA_DIR, "cities.csv")
USERS_FILE = os.path.join(DATA_DIR, "users.csv")
HISTORY_FILE = os.path.join(DATA_DIR, "history.csv")
FAVORITES_FILE = os.path.join(DATA_DIR, "favorites.csv")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "student-secret-key-change-me")

# Ключи внешних API не хранятся в коде. Для запуска задайте переменные окружения.
app.config["YANDEX_MAPS_API_KEY"] = os.environ.get(
    "YANDEX_MAPS_API_KEY", "YOUR_YANDEX_MAPS_API_KEY"
)
USD_TO_RUB = 90


@app.template_filter("rub")
def format_rub(value):
    amount = to_float(value) * USD_TO_RUB
    return f"{int(round(amount)):,}".replace(",", " ") + " ₽"


@app.template_filter("rub_number")
def format_rub_number(value):
    return int(round(to_float(value) * USD_TO_RUB))


def rub_to_usd(value):
    return to_float(value) / USD_TO_RUB


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def parse_datetime(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return datetime.now()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return datetime.now()


def split_text_items(value):
    return [item.strip() for item in str(value or "").split(";") if item.strip()]


def to_float(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def build_default_city_details(row):
    rent = to_float(row.get("avg_rent_usd"))
    infrastructure = to_float(row.get("infrastructure_score"))
    ecology = to_float(row.get("ecology_score"))
    sea = to_float(row.get("sea_score"))
    city_name = row.get("name", "город")
    region = row.get("region", "регион")

    pros = ["доступная аренда" if rent <= 350 else "развитый рынок жилья"]
    if infrastructure >= 8:
        pros.append("развитая инфраструктура")
    if ecology >= 6:
        pros.append("приятная городская среда")
    if sea >= 7:
        pros.append("близость к морю или крупной воде")

    cons = []
    if rent >= 500:
        cons.append("аренда выше среднего")
    if ecology < 5:
        cons.append("есть экологические вопросы")
    if infrastructure < 7:
        cons.append("инфраструктура развита неравномерно")
    if not cons:
        cons.append("в популярных районах возможны пробки")

    return {
        "pros": "; ".join(pros),
        "cons": "; ".join(cons),
        "attractions": "центральная площадь; городская набережная или парк; исторический центр",
        "transport_info": f"{city_name} имеет городские маршруты и связь с другими населенными пунктами региона {region}.",
        "education_info": "Есть школы, колледжи и образовательные центры; в крупных городах доступны вузы.",
        "healthcare_info": "Работают поликлиники, больницы и частные медицинские центры.",
        "job_info": "Возможности зависят от сферы: услуги, торговля, образование, IT и промышленность.",
        "monthly_budget_usd": max(int(rent + 420), int(rent * 1.8)),
        "suitable_for": "студентам, молодым специалистам, семьям и тем, кто подбирает город по балансу цены и качества жизни",
        "relocation_summary": f"{city_name} стоит рассмотреть для переезда, если вам подходят его цены, климат и инфраструктура.",
    }


def fill_city_details(row):
    defaults = build_default_city_details(row)
    for field, value in defaults.items():
        if not row.get(field):
            row[field] = value
    return row


def crime_level_by_safety(score):
    if score >= 7.5:
        return "низкий"
    if score >= 6.7:
        return "средний"
    return "повышенный"


def safety_level_by_score(score):
    if score >= 7.5:
        return "высокий"
    if score >= 6.7:
        return "средний"
    return "требует внимания к району"


def seed_database_from_csv():
    """CSV используется только для первичного импорта в SQLite."""
    db = db_session()
    try:
        if db.scalar(select(City.id).limit(1)) is None:
            for row in read_csv(CITIES_FILE):
                row = fill_city_details(dict(row))
                city = City(
                    id=to_int(row.get("id")),
                    name=row["name"],
                    region=row["region"],
                    population=to_int(row.get("population")),
                    latitude=to_float(row.get("latitude")),
                    longitude=to_float(row.get("longitude")),
                    avg_rent_usd=to_float(row.get("avg_rent_usd")),
                    climate_score=to_float(row.get("climate_score")),
                    sea_score=to_float(row.get("sea_score")),
                    internet_score=to_float(row.get("internet_score")),
                    safety_score=to_float(row.get("safety_score")),
                    ecology_score=to_float(row.get("ecology_score")),
                    infrastructure_score=to_float(row.get("infrastructure_score")),
                    description=row.get("description", ""),
                    pros=row.get("pros", ""),
                    cons=row.get("cons", ""),
                    transport_info=row.get("transport_info", ""),
                    education_info=row.get("education_info", ""),
                    healthcare_info=row.get("healthcare_info", ""),
                    job_info=row.get("job_info", ""),
                    monthly_budget_usd=to_int(row.get("monthly_budget_usd")),
                    suitable_for=row.get("suitable_for", ""),
                    relocation_summary=row.get("relocation_summary", ""),
                )
                db.add(city)
                for attraction_name in split_text_items(row.get("attractions")):
                    db.add(Attraction(city=city, name=attraction_name))
            db.commit()

        if db.scalar(select(User.id).limit(1)) is None:
            for row in read_csv(USERS_FILE):
                if row.get("username") and row.get("password_hash"):
                    db.add(
                        User(
                            id=to_int(row.get("id")),
                            username=row["username"],
                            password_hash=row["password_hash"],
                            created_at=parse_datetime(row.get("created_at")),
                        )
                    )
            db.commit()

        if db.scalar(select(CityStats.id).limit(1)) is None:
            for city in db.scalars(select(City)).all():
                avg_rent = float(city.avg_rent_usd)
                db.add(
                    CityStats(
                        city_id=city.id,
                        avg_rent_price=avg_rent,
                        avg_buy_price_m2=round(avg_rent * 155, 2),
                        crime_level=crime_level_by_safety(city.safety_score),
                        safety_level=safety_level_by_score(city.safety_score),
                        source_name="Учебная оценка",
                        source_url="",
                        updated_at=datetime.now(),
                    )
                )
            db.commit()

        if db.scalar(select(SearchHistory.id).limit(1)) is None:
            for row in read_csv(HISTORY_FILE):
                if row.get("user_id"):
                    db.add(
                        SearchHistory(
                            id=to_int(row.get("id")),
                            user_id=to_int(row.get("user_id")),
                            created_at=parse_datetime(row.get("created_at")),
                            max_rent_usd=to_float(row.get("max_rent_usd")),
                            climate_preference=row.get("climate_preference", ""),
                            sea_preference=row.get("sea_preference", ""),
                            safety_important=row.get("safety_important", "нет"),
                            internet_important=row.get("internet_important", "нет"),
                            ecology_important=row.get("ecology_important", "нет"),
                            infrastructure_important=row.get("infrastructure_important", "нет"),
                            best_city=row.get("best_city", ""),
                            best_score=to_float(row.get("best_score")),
                        )
                    )
            db.commit()

        if db.scalar(select(Favorite.id).limit(1)) is None:
            for row in read_csv(FAVORITES_FILE):
                if row.get("user_id") and row.get("city_id"):
                    db.add(
                        Favorite(
                            id=to_int(row.get("id")),
                            user_id=to_int(row.get("user_id")),
                            city_id=to_int(row.get("city_id")),
                            created_at=parse_datetime(row.get("created_at")),
                        )
                    )
            db.commit()
    except Exception:
        db.rollback()
        raise


Base.metadata.create_all(bind=engine)
seed_database_from_csv()


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Для доступа к этой странице нужно войти в аккаунт.", "error")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Для доступа к этой странице нужно войти в аккаунт.", "error")
            return redirect(url_for("login"))
        admin_username = os.environ.get("ADMIN_USERNAME", "admin")
        if session.get("username") != admin_username:
            flash("Справочник доступен только администратору.", "error")
            return redirect(url_for("index"))
        return view_func(*args, **kwargs)

    return wrapper


@app.context_processor
def inject_user():
    return {
        "current_user": {
            "id": session.get("user_id"),
            "username": session.get("username"),
        }
        if session.get("user_id")
        else None
    }


def find_user_by_username(username):
    db = db_session()
    return db.scalar(select(User).where(User.username == username.strip()))


def load_cities():
    db = db_session()
    return db.scalars(select(City).order_by(City.name)).all()


def get_city_by_id(city_id):
    db = db_session()
    return db.get(City, int(city_id))


def get_latest_city_stats(city_id):
    db = db_session()
    return db.scalar(
        select(CityStats)
        .where(CityStats.city_id == int(city_id))
        .order_by(CityStats.updated_at.desc(), CityStats.id.desc())
        .limit(1)
    )


def get_crime_data(city_name):
    db = db_session()
    city = db.scalar(select(City).where(City.name == city_name))
    if not city:
        return None
    return get_latest_city_stats(city.id)


def get_housing_data(city_name):
    db = db_session()
    city = db.scalar(select(City).where(City.name == city_name))
    if not city:
        return None
    return get_latest_city_stats(city.id)


def get_weather(city_name):
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    if not api_key:
        print("OpenWeather: переменная OPENWEATHER_API_KEY не задана")
        return None

    query = urllib.parse.urlencode(
        {
            "q": f"{city_name},RU",
            "appid": api_key,
            "units": "metric",
            "lang": "ru",
        }
    )
    url = f"https://api.openweathermap.org/data/2.5/weather?{query}"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        print(f"OpenWeather: ошибка {error.code} для города {city_name}")
        return None
    except urllib.error.URLError as error:
        print(f"OpenWeather: ошибка сети для города {city_name}: {error.reason}")
        return None
    except Exception:
        print(f"OpenWeather: не удалось получить погоду для города {city_name}")
        return None

    try:
        return {
            "temperature": round(float(data["main"]["temp"])),
            "feels_like": round(float(data["main"]["feels_like"])),
            "description": data["weather"][0]["description"],
            "humidity": int(data["main"]["humidity"]),
            "wind_speed": float(data["wind"]["speed"]),
        }
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def city_to_dict(city):
    return {
        "id": city.id,
        "name": city.name,
        "region": city.region,
        "population": city.population,
        "latitude": city.latitude,
        "longitude": city.longitude,
        "avg_rent_usd": city.avg_rent_usd,
        "climate_score": city.climate_score,
        "sea_score": city.sea_score,
        "internet_score": city.internet_score,
        "safety_score": city.safety_score,
        "ecology_score": city.ecology_score,
        "infrastructure_score": city.infrastructure_score,
        "description": city.description,
        "pros": city.pros,
        "cons": city.cons,
        "transport_info": city.transport_info,
        "education_info": city.education_info,
        "healthcare_info": city.healthcare_info,
        "job_info": city.job_info,
        "monthly_budget_usd": city.monthly_budget_usd,
        "suitable_for": city.suitable_for,
        "relocation_summary": city.relocation_summary,
    }


def city_to_map_item(city, score=None):
    item = city_to_dict(city)
    item["detail_url"] = url_for("city_detail", city_id=city.id)
    if score is not None:
        item["score"] = score
    return item


def get_user_favorite_city_ids(user_id):
    db = db_session()
    return {
        city_id
        for (city_id,) in db.execute(
            select(Favorite.city_id).where(Favorite.user_id == int(user_id))
        ).all()
    }


def is_city_favorite(user_id, city_id):
    return int(city_id) in get_user_favorite_city_ids(user_id)


def calculate_city_score(user_criteria, city):
    """
    Возвращает рейтинг города от 0 до 100.
    Вес каждого критерия фиксированный, чтобы логика была простой для защиты.
    """
    max_rent = user_criteria["max_rent_usd"]
    rent = city.avg_rent_usd
    if rent <= max_rent:
        rent_score = 10
    else:
        rent_score = max(0, 10 - ((rent - max_rent) / max_rent) * 10)

    climate_targets = {
        "cold": 4,
        "moderate": 7,
        "warm": 9,
    }
    target = climate_targets[user_criteria["climate_preference"]]
    climate_match = max(0, 10 - abs(city.climate_score - target) * 1.7)

    if user_criteria["sea_preference"] == "yes":
        climate_match = climate_match * 0.75 + city.sea_score * 0.25

    safety_score = city.safety_score if user_criteria["safety_important"] else 10
    internet_score = city.internet_score if user_criteria["internet_important"] else 10
    ecology_score = city.ecology_score if user_criteria["ecology_important"] else 10
    infrastructure_score = (
        city.infrastructure_score if user_criteria["infrastructure_important"] else 10
    )

    total = (
        rent_score / 10 * 25
        + climate_match / 10 * 20
        + safety_score / 10 * 20
        + internet_score / 10 * 15
        + ecology_score / 10 * 10
        + infrastructure_score / 10 * 10
    )
    return round(max(0, min(total, 100)), 1)


def parse_bool(value):
    return value == "yes"


def get_search_criteria(form):
    max_rent_raw = form.get("max_rent_usd", "").strip()
    if not max_rent_raw:
        raise ValueError("Укажите максимальный бюджет аренды.")
    try:
        max_rent = rub_to_usd(max_rent_raw)
    except ValueError as exc:
        raise ValueError("Бюджет аренды должен быть числом.") from exc
    if max_rent <= 0:
        raise ValueError("Бюджет аренды должен быть больше нуля.")

    climate = form.get("climate_preference")
    sea = form.get("sea_preference")
    if climate not in ["cold", "moderate", "warm"]:
        raise ValueError("Выберите желаемый климат.")
    if sea not in ["yes", "no", "any"]:
        raise ValueError("Выберите отношение к близости моря.")

    return {
        "max_rent_usd": max_rent,
        "climate_preference": climate,
        "sea_preference": sea,
        "safety_important": parse_bool(form.get("safety_important")),
        "internet_important": parse_bool(form.get("internet_important")),
        "ecology_important": parse_bool(form.get("ecology_important")),
        "infrastructure_important": parse_bool(form.get("infrastructure_important")),
    }


def label_by_score(score):
    if score >= 80:
        return "Отлично подходит"
    if score >= 60:
        return "Хорошо подходит"
    if score >= 40:
        return "Средне подходит"
    return "Слабо подходит"


def score_badge_class(score):
    if score >= 80:
        return "excellent"
    if score >= 60:
        return "good"
    if score >= 40:
        return "medium"
    return "low"


def climate_label(value):
    return {"cold": "холодный", "moderate": "умеренный", "warm": "теплый"}[value]


def sea_label(value):
    return {"yes": "да", "no": "нет", "any": "неважно"}[value]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    db = db_session()
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        password_repeat = request.form.get("password_repeat", "")

        if not username or not password or not password_repeat:
            flash("Заполните все поля регистрации.", "error")
            return render_template("register.html")
        if len(username) < 3:
            flash("Имя пользователя должно быть не короче 3 символов.", "error")
            return render_template("register.html")
        if len(password) < 5:
            flash("Пароль должен быть не короче 5 символов.", "error")
            return render_template("register.html")
        if password != password_repeat:
            flash("Пароли не совпадают.", "error")
            return render_template("register.html")
        if find_user_by_username(username):
            flash("Пользователь с таким именем уже существует.", "error")
            return render_template("register.html")

        user = User(username=username, password_hash=generate_password_hash(password))
        db.add(user)
        db.commit()
        flash("Регистрация прошла успешно. Теперь можно войти.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Введите имя пользователя и пароль.", "error")
            return render_template("login.html")

        user = find_user_by_username(username)
        if not user or not check_password_hash(user.password_hash, password):
            flash("Неверное имя пользователя или пароль.", "error")
            return render_template("login.html")

        session["user_id"] = user.id
        session["username"] = user.username
        flash("Вы вошли в аккаунт.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из аккаунта.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/results", methods=["POST"])
@login_required
def results():
    db = db_session()
    try:
        criteria = get_search_criteria(request.form)
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("dashboard"))

    ranked_cities = []
    for city in db.scalars(select(City)).all():
        score = calculate_city_score(criteria, city)
        city_item = city_to_dict(city)
        city_item["score"] = score
        city_item["score_label"] = label_by_score(score)
        city_item["score_class"] = score_badge_class(score)
        city_item["detail_url"] = url_for("city_detail", city_id=city.id)
        ranked_cities.append(city_item)

    ranked_cities.sort(key=lambda item: item["score"], reverse=True)
    best_city = ranked_cities[0] if ranked_cities else None

    db.add(
        SearchHistory(
            user_id=int(session["user_id"]),
            max_rent_usd=criteria["max_rent_usd"],
            climate_preference=climate_label(criteria["climate_preference"]),
            sea_preference=sea_label(criteria["sea_preference"]),
            safety_important="да" if criteria["safety_important"] else "нет",
            internet_important="да" if criteria["internet_important"] else "нет",
            ecology_important="да" if criteria["ecology_important"] else "нет",
            infrastructure_important="да"
            if criteria["infrastructure_important"]
            else "нет",
            best_city=best_city["name"] if best_city else "",
            best_score=best_city["score"] if best_city else 0,
        )
    )
    db.commit()

    return render_template(
        "results.html",
        cities=ranked_cities,
        criteria=criteria,
        climate_label=climate_label,
        sea_label=sea_label,
        map_cities=ranked_cities,
        favorite_city_ids=get_user_favorite_city_ids(session["user_id"]),
    )


@app.route("/city/<int:city_id>")
def city_detail(city_id):
    city = get_city_by_id(city_id)
    if not city:
        flash("Город не найден.", "error")
        return redirect(url_for("index"))

    favorite = False
    if session.get("user_id"):
        favorite = is_city_favorite(session["user_id"], city_id)

    weather = get_weather(city.name)
    city_stats = get_latest_city_stats(city.id)
    crime_data = get_crime_data(city.name)
    housing_data = get_housing_data(city.name)

    return render_template(
        "city.html",
        city=city,
        pros=split_text_items(city.pros),
        cons=split_text_items(city.cons),
        attractions=city.attractions,
        is_favorite=favorite,
        map_cities=[city_to_map_item(city)],
        weather=weather,
        city_stats=city_stats,
        crime_data=crime_data,
        housing_data=housing_data,
    )


@app.route("/favorites")
@login_required
def favorites():
    db = db_session()
    cities = db.scalars(
        select(City)
        .join(Favorite)
        .where(Favorite.user_id == int(session["user_id"]))
        .order_by(City.name)
    ).all()
    return render_template("favorites.html", cities=cities)


@app.route("/favorite/add/<int:city_id>", methods=["POST"])
@login_required
def add_favorite(city_id):
    db = db_session()
    city = db.get(City, city_id)
    if not city:
        flash("Город не найден.", "error")
        return redirect(url_for("dashboard"))

    favorite = Favorite(user_id=int(session["user_id"]), city_id=city_id)
    db.add(favorite)
    try:
        db.commit()
        flash(f"{city.name} добавлен в избранное.", "success")
    except IntegrityError:
        db.rollback()
        flash("Этот город уже есть в избранном.", "error")

    return redirect(request.referrer or url_for("city_detail", city_id=city_id))


@app.route("/favorite/remove/<int:city_id>", methods=["POST"])
@login_required
def remove_favorite(city_id):
    db = db_session()
    favorite = db.scalar(
        select(Favorite).where(
            Favorite.user_id == int(session["user_id"]),
            Favorite.city_id == city_id,
        )
    )
    if favorite:
        db.delete(favorite)
        db.commit()
        flash("Город удален из избранного.", "success")
    return redirect(request.referrer or url_for("favorites"))


@app.route("/history")
@login_required
def history():
    db = db_session()
    rows = db.scalars(
        select(SearchHistory)
        .where(SearchHistory.user_id == int(session["user_id"]))
        .order_by(SearchHistory.created_at.desc())
    ).all()
    return render_template("history.html", history_rows=rows)


@app.route("/admin/city-stats", methods=["GET", "POST"])
@admin_required
def admin_city_stats():
    db = db_session()
    if request.method == "POST":
        stat_id = request.form.get("stat_id")
        city_id = to_int(request.form.get("city_id"))
        updated_at = parse_datetime(request.form.get("updated_at"))

        if not city_id:
            flash("Выберите город.", "error")
            return redirect(url_for("admin_city_stats"))

        if stat_id:
            stat = db.get(CityStats, to_int(stat_id))
            if not stat:
                flash("Запись не найдена.", "error")
                return redirect(url_for("admin_city_stats"))
        else:
            stat = CityStats(city_id=city_id)
            db.add(stat)

        stat.city_id = city_id
        stat.avg_rent_price = rub_to_usd(request.form.get("avg_rent_price"))
        stat.avg_buy_price_m2 = rub_to_usd(request.form.get("avg_buy_price_m2"))
        stat.crime_level = request.form.get("crime_level", "").strip() or "не указано"
        stat.safety_level = request.form.get("safety_level", "").strip() or "не указано"
        stat.source_name = request.form.get("source_name", "").strip() or "Учебные данные"
        stat.source_url = request.form.get("source_url", "").strip()
        stat.updated_at = updated_at
        db.commit()
        flash("Показатели города сохранены.", "success")
        return redirect(url_for("admin_city_stats"))

    edit_id = request.args.get("edit")
    edit_stat = db.get(CityStats, to_int(edit_id)) if edit_id else None
    cities = db.scalars(select(City).order_by(City.name)).all()
    stats = db.scalars(
        select(CityStats).join(City).order_by(City.name, CityStats.updated_at.desc())
    ).all()
    return render_template(
        "admin_city_stats.html",
        cities=cities,
        stats=stats,
        edit_stat=edit_stat,
    )


@app.route("/admin/city-stats/delete/<int:stat_id>", methods=["POST"])
@admin_required
def delete_city_stats(stat_id):
    db = db_session()
    stat = db.get(CityStats, stat_id)
    if stat:
        db.delete(stat)
        db.commit()
        flash("Запись удалена.", "success")
    return redirect(url_for("admin_city_stats"))


if __name__ == "__main__":
    app.run(debug=True)
