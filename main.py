# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START gae_python37_app]
from flask import Flask
from bs4 import BeautifulSoup
import requests
import datetime
import regex as re
import unicodedata
from pyopenmensa import feed as op
from lxml import etree


class UnexpectedFormatError(AttributeError):
    pass


WARNING = 'No Mensa path!'


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
    b_soup = BeautifulSoup(content, "html.parser")
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


def get_total_feed(mensa):
    canteen = op.LazyBuilder()
    meals = get_meals(mensa)
    for meal in meals:
        main_meal = meal[MAIN_MEAL_KEY]
        additional = meal[ADDITION_KEY]
        ing_reg = re.compile("\(((\d+|[a-n])(,(\d+|[a-n]))*)\)")
        # noinspection PyTypeChecker
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
    return canteen.toXMLFeed()


def validate(xml_data):
    # with open("open-mensa-v2.xsd", 'r') as schema_file:
    #     xml_schema_str = schema_file.read()
    #
    # xml_schema_doc = etree.parse(StringIO(xml_schema_str))
    # xml_schema = etree.XMLSchema(StringIO(xml_schema_doc))

    # parse xml
    try:
        xml_schema_doc = etree.parse("./open-mensa-v2.xsd")
        xml_schema = etree.XMLSchema(xml_schema_doc)
        # doc = etree.parse(xml_data.encode())
        print('XML well formed, syntax ok.')
        etree.fromstring(xml_data.encode(), parser=etree.XMLParser(schema=xml_schema))
        # xml_schema.assertValid(doc)
        print('XML valid, schema validation ok.')
    # check for XML syntax errors
    except etree.XMLSyntaxError as err:
        raise UnexpectedFormatError(err)
    except etree.DocumentInvalid as err:
        print('Schema validation error, see error_schema.log')
        raise UnexpectedFormatError(err)


# If `entrypoint` is not defined in app.yaml, App Engine will look for an app
# called `app` in `main.py`.
app = Flask(__name__)


@app.route(f'/<mensa>')
def mensa_feed(mensa):
    if mensa not in MENSAE:
        return WARNING
    feed = get_total_feed(mensa)
    validate(feed)
    return feed


@app.route('/')
@app.route('/index')
def mensa_list():
    mensae = "\n          ".join(["<list-item>" + mensa + "</list-item>" for mensa in MENSAE])
    response = f"""
    Status: 404 Not Found
    Content-Type: application/xml; charset=utf-8
    
    '<?xml version="1.0" encoding="UTF-8"?>'
    <error>
      <code>404</code>
        <message>Mensa not found</message>
        <debug-data>
        <list-desc>Valid filenames</list-desc>"
            {mensae}
        </debug-data>"
    </error>"""
    return response


if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
# [END gae_python37_app]
