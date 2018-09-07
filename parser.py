from bs4 import BeautifulSoup
import requests
import datetime
import regex as re
import unicodedata
from pyopenmensa import feed as op


class UnexpectedFormatError(AttributeError):
    pass


MAIN_MEAL_KEY = "mm"
ADDITION_KEY = "a"
PRICE_KEY = "p"
DATE_KEY = "d"
STUDENT_KEY = "stud"
EMPLOYEE_KEY = "bed"

canteen = op.LazyBuilder()
search_date = datetime.datetime(2018, 9, 7)  # TODO


def get_meals(date=None):
    result = requests.get("https://osnabrueck.my-mensa.de/essen.php?v=5121119&hyp=1&lang=de&mensa=westerberg")
    if result.status_code == 200:
        content = result.content
    else:
        raise ConnectionError
    b_soup = BeautifulSoup(content, "lxml")
    print(b_soup.prettify())
    # TODO change mensa name and year
    unparsed_meals = b_soup.find_all(
        href=lambda href: href and re.compile("mensa=westerberg#westerberg_tag_20\d{3,5}_essen").search(href))
    print(unparsed_meals)
    meals = []
    for meal in unparsed_meals:
        meal_info = meal.find_all(["h3", "p"])
        if len(meal_info) != 3:
            raise UnexpectedFormatError("More than 3 meal info")
        meal_info = [unicodedata.normalize("NFKD", info.text).replace("\xad", "") for info in meal_info]
        main_meal, additional, price = meal_info
        price_search = re.compile("((\d+,\d{2})|-)\D*((\d+,\d{2})|-)").search(price)
        if not price_search:
            raise UnexpectedFormatError(f"price formation error {price}")
        try:
            stud_price_str = price_search.group(2)
            emp_price_str = price_search.group(4)
            price = {STUDENT_KEY: float(stud_price_str.replace(",", ".")) if stud_price_str else None,
                     EMPLOYEE_KEY: float(emp_price_str.replace(",", ".")) if emp_price_str else None}
        except ValueError:
            raise UnexpectedFormatError(f"price formation error {price_search.groups()}")
        date_search = re.compile("tag_(\d{4})(\d{1,3})").search(meal["href"])
        if not date_search:
            raise UnexpectedFormatError(f"Date formation error{meal['href']}")
        try:
            year, day = [int(group) for group in date_search.groups()]
        except ValueError:
            raise UnexpectedFormatError(f"Date formation error {year}, {day}")
        if date:
            date_days = (date - datetime.datetime(date.year, 1, 1)).days
            if date_days != day or year != date.year:
                continue
        date = datetime.datetime(year, 1, 1) + datetime.timedelta(day)
        meals.append({MAIN_MEAL_KEY: main_meal, ADDITION_KEY: additional, PRICE_KEY: price, DATE_KEY: date})
    return meals


print(get_meals())

