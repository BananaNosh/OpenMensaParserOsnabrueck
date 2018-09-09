from bs4 import BeautifulSoup
import requests
import datetime
import regex as re
import unicodedata
from pyopenmensa import feed as op


class UnexpectedFormatError(AttributeError):
    pass


CATEGORY_KEY = "cat"
MAIN_MEAL_KEY = "mm"
ADDITION_KEY = "a"
PRICE_KEY = "p"
DATE_KEY = "d"
STUDENT_KEY = "student"
EMPLOYEE_KEY = "employee"
MENSAE = ["westerberg", "mschlossg", "mhaste", "mvechta"]


def get_meals(_mensa, date=None):
    result = requests.get(f"https://osnabrueck.my-mensa.de/essen.php?v=5121119&hyp=1&lang=de&mensa={_mensa}")
    if result.status_code == 200:
        content = result.content
    else:
        raise ConnectionError
    b_soup = BeautifulSoup(content, "lxml")
    print(b_soup.prettify())
    unparsed_meals = b_soup.find_all(
        href=lambda href: href and re.compile(f"mensa={_mensa}#{_mensa}_tag_20\d{{3,5}}_essen").search(href))
    _meals = []
    for meal in unparsed_meals:
        category = meal.parent.previous_sibling.previous_sibling.text
        meal_info = meal.find_all(["h3", "p"])
        if len(meal_info) != 3:
            raise UnexpectedFormatError("More than 3 meal info")
        meal_info = [unicodedata.normalize("NFKD", info.text).replace("\xad", "") for info in meal_info]
        _main_meal, _additional, price = meal_info
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
        meal_date = datetime.datetime(year, 1, 1) + datetime.timedelta(day)
        _meals.append({CATEGORY_KEY: category, MAIN_MEAL_KEY: _main_meal,
                      ADDITION_KEY: _additional, PRICE_KEY: price, DATE_KEY: meal_date.date()})
    return _meals


if __name__ == '__main__':
    for mensa in MENSAE[:1]:
        canteen = op.LazyBuilder()
        meals = get_meals(mensa)
        for meal in meals:
            main_meal = meal[MAIN_MEAL_KEY]
            additional = meal[ADDITION_KEY]
            ing_reg = re.compile("\(((\d+|[a-n])(,(\d+|[a-n]))*)\)")
            ingredients_match = ing_reg.findall(main_meal + " " + additional)
            ingredients = list(set(",".join([ingred[0] for ingred in ingredients_match]).split(",")))
            ingredients.sort()
            ingredients = ",".join(ingredients)
            main_meal = ing_reg.sub("", main_meal)
            additional = ing_reg.sub("", additional)
            notes = [note for note in [additional, ingredients] if len(note) > 0]
            prices = {role: price for role, price in meal[PRICE_KEY].items() if price}
            canteen.addMeal(meal[DATE_KEY], meal[CATEGORY_KEY], main_meal,
                            notes if len(notes) > 0 else None, prices)
        print(canteen.toXMLFeed())
