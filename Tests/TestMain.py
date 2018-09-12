# Copyright 2018 Google Inc. All Rights Reserved.
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

import main
import unittest
from bs4 import BeautifulSoup


class TestMain(unittest.TestCase):
    def setUp(self):
        main.app.testing = True
        self.client = main.app.test_client()

    def test_index(self):
        r = self.client.get('/')
        self.assertEquals(200, r.status_code)
        self.assertEquals(main.WARNING, r.data.decode('utf-8'))

    def test_westerberg(self):
        r = self.client.get('/westerberg')
        b_soup = BeautifulSoup(r.data, "lxml")
        category = b_soup.category
        self.assertEquals("Hauptgericht HK 2", category.attrs['name'].strip())
