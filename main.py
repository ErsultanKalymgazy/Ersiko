import logging
import asyncio
from aiogram import Bot, Router, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db import Database

from errors import CleanBasketError, MakeOrderError, NotEnoughMoneyError

from consts import API_TOKEN, menu_photos, menu_dishes, menu_subdishes

logging.basicConfig(level=logging.INFO)

router = Router()

bot = Bot(token=API_TOKEN)
db = Database()


async def main():
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


@router.message(CommandStart())
async def start(message: types.Message):
    buttons = [[KeyboardButton(text="Меню 📝")],
               [KeyboardButton(text="Корзина 🗑")],
               [KeyboardButton(text="Информация 🌍")],
               [KeyboardButton(text="Кошелёк 💰")],
               [KeyboardButton(text="Заказы 🛎")]]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await db.create_tables()
    await message.answer("Привет! Чем я могу помочь?", reply_markup=keyboard)
    is_new_user = await db.add_user(message.from_user.id, message.from_user.username)
    if is_new_user:
        await db.add_user_wallet(message.from_user.id)


@router.message(lambda message: message.text == "Меню 📝")
async def menu(message: types.Message):
    menu_list = []
    for dish, photo_url in menu_photos.items():
        button = InlineKeyboardButton(text=dish, callback_data=f"menu_item_{dish}")
        menu_list.append(button)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[menu_list], row_width=2)

    await message.answer("Выберите меню: ✍️", reply_markup=keyboard)


@router.message(lambda message: message.text == "Корзина 🗑")
async def basket(message: types.Message):
    user_id = message.from_user.id
    basket = await db.get_basket(user_id)

    if basket:
        # basket_text = "\n".join([f"{item_name}: {quantity}" for item_name, quantity in basket.items()])
        # button = InlineKeyboardButton(text="Очистить корзину", callback_data="clean_basket")
        # keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]], row_width=2)
        # await message.answer(basket_text, reply_markup=keyboard)
        basket_item_row = []
        title_row = [
            InlineKeyboardButton(text="Блюдо", callback_data=f"d"),
            InlineKeyboardButton(text=str("Количество"), callback_data=f"d"),
            InlineKeyboardButton(text=str("Цена"), callback_data=f"d")
        ]
        basket_item_row.append(title_row)
        basket_items_sum = 0.0
        for item_name, item_info in basket.items():
            basket_items_sum += item_info["price"]
            row = [
                InlineKeyboardButton(text=item_name, callback_data=f"d"),
                InlineKeyboardButton(text=str(item_info["quantity"]), callback_data=f"d"),
                InlineKeyboardButton(text=str(item_info["price"]), callback_data=f"d")
            ]
            basket_item_row.append(row)
        total_button = InlineKeyboardButton(text=f"Общая сумма корзины:{str(basket_items_sum)}", callback_data="d")
        basket_item_row.append([total_button])
        clean_basket_button = InlineKeyboardButton(text="Очистить корзину", callback_data="clean_basket")
        make_order_button = InlineKeyboardButton(text="Сделать заказ", callback_data="make_order")
        basket_item_row.append([make_order_button, clean_basket_button])
        keyboard = InlineKeyboardMarkup(inline_keyboard=basket_item_row, row_width=3)
        await message.answer("Корзина покупок: 💸", reply_markup=keyboard)
    else:
        basket_text = "Корзина пуста ❌"
        await message.answer(basket_text)

@router.message(lambda message: message.text == "Заказы 🛎")
async def orders(message: types.Message):
    user_id = message.from_user.id
    orders = await db.get_orders(user_id)
    basket_item_row = []
    title_row = [
        InlineKeyboardButton(text="Номер заказа", callback_data=f"d"),
        InlineKeyboardButton(text=str("Сумма заказа"), callback_data=f"d"),
        InlineKeyboardButton(text=str("Статус"), callback_data=f"d"),
        InlineKeyboardButton(text=str("Подробнее"), callback_data=f"d")
    ]
    basket_item_row.append(title_row)
    if len(orders) > 0:
        for order_id, order_sum, status in orders:
            row = [
                InlineKeyboardButton(text=str(order_id), callback_data=f"d"),
                InlineKeyboardButton(text=str(order_sum), callback_data=f"d"),
                InlineKeyboardButton(text=str(status), callback_data=f"d"),
                InlineKeyboardButton(text="Подробнее", callback_data=f"get_order_{order_id}")
            ]
            basket_item_row.append(row)
        keyboard = InlineKeyboardMarkup(inline_keyboard=basket_item_row, row_width=3)
        await message.answer("Список заказов: 📃", reply_markup=keyboard)
    else:
        orders_text = "Заказов нет ❌"
        await message.answer(orders_text)


@router.callback_query(lambda c: c.data.startswith('get_order_'))
async def process_callback(callback_query: types.CallbackQuery):
    order_id = callback_query.data.replace('get_order_', '')
    order_items = await db.get_order_items(order_id)
    basket_text = "\n".join([f"Блюдо: {item_name}, Кол.: {quantity}, Цена: {price}" for item_name, quantity, price in order_items])
    await callback_query.message.answer(basket_text)


@router.callback_query(lambda c: c.data == "clean_basket")
async def clean_basket(message: types.Message):
    user_id = message.from_user.id
    try:
        await db.clean_basket(user_id)
        await message.answer("Корзина очищена ✅")
    except CleanBasketError as e:
        await message.answer(f"Произошла ошибка, корзина не очищена 🔴 !")


@router.callback_query(lambda c: c.data == "make_order")
async def make_order(message: types.Message):
    user_id = message.from_user.id
    try:
        await db.make_order(user_id)
        await message.answer("Заказ создан ✅ ")
    except NotEnoughMoneyError as e:
        await message.answer(f"Недостаточно средств на кошельке 💢 ")
    except MakeOrderError as e:
        await message.answer(f"Произошла ошибка, заказ не создался 🔴 !")


@router.message(lambda message: message.text == "Кошелёк 💰")
async def basket(message: types.Message):
    user_id = message.from_user.id
    cash_num = await db.get_user_wallet(user_id)
    print()
    await message.answer(f"Ваш остаток средств кошелька: {str(cash_num)} тенге")


@router.message(lambda message: message.text == "Информация 🌍")
async def info(message: types.Message):
    await message.answer("""Мы расположены по адресу:

Астана, 1-я Экспо улица, 55

🕛 Время работы:

С 8:00 до 22:00 без выходных """)


@router.callback_query(lambda c: c.data.startswith('menu_item_'))
async def process_callback(callback_query: types.CallbackQuery):
    menu = callback_query.data.replace('menu_item_', '')
    with open(menu_photos[menu], "rb") as photo_file:
        photo_bytes = photo_file.read()

    menu_list = []
    i = 0
    row_menu_list = []
    for menu_dish in menu_dishes[menu]:
        if i % 2 == 0:
            list_copy = row_menu_list.copy()
            menu_list.append(list_copy)
            row_menu_list = []
        if isinstance(menu_subdishes[menu_dish], dict):
            button = InlineKeyboardButton(text=f"{menu_dish} - {menu_subdishes[menu_dish]['price']} тенге",
                                          callback_data=f"dish_item_{menu_dish}")
        else:
            button = InlineKeyboardButton(text=menu_dish, callback_data=f"dish_item_{menu_dish}")
        row_menu_list.append(button)
        i += 1
    if len(row_menu_list) > 0:
        menu_list.append(row_menu_list)
    keyboard = InlineKeyboardMarkup(inline_keyboard=menu_list, row_width=1)
    await bot.send_photo(chat_id=callback_query.from_user.id,
                         photo=BufferedInputFile(file=photo_bytes, filename=menu_photos[menu]),
                         caption=f"Вы выбрали {menu}. Выберите блюдо из этого меню")
    await callback_query.message.answer("Выберите тип блюда или блюдо:", reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith('dish_item_'))
async def process_callback(callback_query: types.CallbackQuery):
    dish = callback_query.data.replace('dish_item_', '')
    if isinstance(menu_subdishes[dish], list):
        subdishes_list = []
        i = 0
        row_subdishes_list = []
        for subdish in menu_subdishes[dish]:
            if i % 1 == 0:
                list_copy = row_subdishes_list.copy()
                subdishes_list.append(list_copy)
                row_subdishes_list = []
            button = InlineKeyboardButton(text=f"{subdish['title']} - {subdish['price']} тенге",
                                          callback_data=f"dish_price_item_{dish}:{i}")
            row_subdishes_list.append(button)
            i += 1
        if len(row_subdishes_list) > 0:
            subdishes_list.append(row_subdishes_list)

        keyboard = InlineKeyboardMarkup(inline_keyboard=subdishes_list, row_width=4)
        await callback_query.message.answer("Выберите блюдо:", reply_markup=keyboard)
    else:
        quantity = 1  # Количество блюд
        user_id = callback_query.from_user.id
        await db.add_item_to_basket(user_id, dish, quantity, menu_subdishes[dish]["price"])
        await callback_query.message.answer(f"Спасибо {dish} добавлен в корзину!")


@router.callback_query(lambda c: c.data.startswith('dish_price_item_'))
async def process_callback(callback_query: types.CallbackQuery):
    dish = callback_query.data.replace('dish_price_item_', '')
    dish_tmp = dish.split(':')  # Бурито:0
    last_dish = menu_subdishes[dish_tmp[0]][int(dish_tmp[1])]
    quantity = 1  # Количество блюд
    user_id = callback_query.from_user.id
    await db.add_item_to_basket(user_id, last_dish["title"], quantity, last_dish["price"])
    await callback_query.message.answer(f"Спасибо {last_dish['title']} добавлен в корзину!")


@router.callback_query(lambda c: c.data.startswith('subdish_item_'))
async def process_callback(callback_query: types.CallbackQuery):
    dish = callback_query.data.replace('subdish_item_', '')
    quantity = 1  # Количество блюд
    user_id = callback_query.from_user.id
    await db.add_item_to_basket(user_id, dish, quantity)
    await callback_query.message.answer(f"Спасибо {dish} добавлен в корзину!")


if __name__ == '__main__':
    asyncio.run(main())
