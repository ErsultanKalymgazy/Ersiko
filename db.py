import aiosqlite
from errors import CleanBasketError, MakeOrderError, NotEnoughMoneyError


class Database:
    def __init__(self, db_path='bot_db.sqlite'):
        self.db_path = db_path

    async def create_tables(self):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL UNIQUE,
                    username TEXT
                )
            ''')
            await cursor.close()

            cursor = await db.execute('''
                CREATE TABLE IF NOT EXISTS baskets (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    item_name TEXT NOT NULL,
                    price REAL, 
                    quantity INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            await cursor.close()

            cursor = await db.execute('''
                            CREATE TABLE IF NOT EXISTS user_wallet (
                                id INTEGER PRIMARY KEY,
                                user_id INTEGER NOT NULL,
                                cash REAL DEFAULT 10000.0,
                                FOREIGN KEY (user_id) REFERENCES users (user_id)
                            )
                        ''')
            await cursor.close()

            cursor = await db.execute('''
                                        CREATE TABLE IF NOT EXISTS user_order (
                                            id INTEGER PRIMARY KEY,
                                            user_id INTEGER NOT NULL,
                                            order_sum REAL,
                                            status TEXT, 
                                            FOREIGN KEY (user_id) REFERENCES users (user_id)
                                        )
                                    ''')
            await cursor.close()

            cursor = await db.execute('''
                                            CREATE TABLE IF NOT EXISTS order_item (
                                                id INTEGER PRIMARY KEY,
                                                order_id INTEGER NOT NULL,
                                                item_name TEXT,
                                                quantity INTEGER,
                                                price REAl,
                                                FOREIGN KEY (order_id) REFERENCES user_order (id)
                                            )
                                                ''')
            await cursor.close()

    async def add_user(self, user_id, username=None):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)',
                                      (user_id, username))
            rows_affected = cursor.rowcount
            await db.commit()
            return rows_affected

    async def add_user_wallet(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('INSERT OR IGNORE INTO user_wallet (user_id) VALUES (?)', (user_id,))
            await db.commit()

    async def get_user_wallet(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT cash FROM user_wallet WHERE user_id = ?', (user_id,))
            rows = await cursor.fetchall()
            await cursor.close()
            cash_num = rows[0][0]
            return cash_num

    async def add_item_to_basket(self, user_id, item_name, price, quantity=1):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('INSERT INTO baskets (user_id, item_name, quantity, price) VALUES (?, ?, ?, ?)',
                             (user_id, item_name, price, quantity))
            await db.commit()

    async def get_basket(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT item_name, quantity, price FROM baskets WHERE user_id = ?', (user_id,))
            rows = await cursor.fetchall()
            await cursor.close()
            basket = {}
            for item_name, quantity, price in rows:
                if basket.get(item_name) is not None:
                    basket[item_name]["quantity"] += 1
                    basket[item_name]["price"] += price
                else:
                    basket[item_name] = {
                        "quantity": 1,
                        "price": price,
                    }

            return basket

    async def get_orders(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT id, order_sum, status FROM user_order WHERE user_id = ?', (user_id,))
            rows = await cursor.fetchall()
            await cursor.close()
            return rows

    async def get_order_items(self, order_id):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT item_name, quantity, price FROM order_item WHERE order_id = ?', (order_id,))
            rows = await cursor.fetchall()
            await cursor.close()
            return rows

    async def clean_basket(self, user_id):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('DELETE FROM baskets WHERE baskets.user_id = ?', (user_id,))
                await db.commit()
                await cursor.close()
        except Exception as e:
            print(f"Error cleaning basket: {e}")
            raise CleanBasketError(f"Error cleaning basket: {e}")

    async def make_order(self, user_id):
        try:
            basket = await self.get_basket(user_id)
            basket_items_sum = 0.0
            for item_name, item_info in basket.items():
                basket_items_sum += item_info["price"]
            async with aiosqlite.connect(self.db_path) as db:
                order_cursor = await db.execute(
                    'INSERT INTO user_order (user_id, order_sum, status) VALUES (?, ?, "Принят в обработку") RETURNING id',
                    (user_id, basket_items_sum,))
                rows = await order_cursor.fetchall()
                order_id = rows[0][0]
                print(order_id)
                await db.commit()
            async with aiosqlite.connect(self.db_path) as db:
                for item_name, item_info in basket.items():
                    await db.execute(
                        'INSERT INTO order_item (order_id, item_name, quantity, price) VALUES (?, ?, ?, ?)',
                        (order_id, item_name, item_info["quantity"], item_info["price"]))
                await db.commit()
            await self.clean_basket(user_id)
            async with aiosqlite.connect(self.db_path) as db:
                cash_cur = await db.execute('select cash from user_wallet WHERE user_id = ?',
                                 (user_id,))
                rows = await cash_cur.fetchall()
                cash = rows[0][0]
                await db.commit()
                if cash - basket_items_sum < 0:
                    raise NotEnoughMoneyError("Не достаточно средств на кошельке")
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('update user_wallet set cash = cash - ? WHERE user_id = ?',
                                 (basket_items_sum, user_id,))
                await db.commit()
        except NotEnoughMoneyError as e:
            raise NotEnoughMoneyError(f"Error cleaning basket: {e}")
        except Exception as e:
            print(f"Error cleaning basket: {e}")
            raise MakeOrderError(f"Error cleaning basket: {e}")
