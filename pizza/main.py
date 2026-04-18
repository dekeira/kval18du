import sys, os
import mysql.connector
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QDate


# ---------------- DATABASE ----------------
class Database:
    def __init__(self):
        self.conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="root",
            database="pizzeria"
        )
        self.cursor = self.conn.cursor(dictionary=True)

    def execute(self, q, p=None, fetch=False):
        self.cursor.execute(q, p or ())
        if fetch:
            return self.cursor.fetchall()
        self.conn.commit()


db = Database()
ICON_PATH = "images/icon.jpg"


# ---------------- AUTH ----------------
class AuthWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Вход")
        self.setWindowIcon(QIcon(ICON_PATH))
        self.resize(400, 250)

        l = QVBoxLayout()

        self.login = QLineEdit()
        self.passw = QLineEdit()
        self.passw.setEchoMode(QLineEdit.EchoMode.Password)

        btn_login = QPushButton("Войти")
        btn_guest = QPushButton("Гость")

        l.addWidget(QLabel("Логин"))
        l.addWidget(self.login)
        l.addWidget(QLabel("Пароль"))
        l.addWidget(self.passw)
        l.addWidget(btn_login)
        l.addWidget(btn_guest)

        self.setLayout(l)

        btn_login.clicked.connect(self.auth)
        btn_guest.clicked.connect(lambda: self.open_main({"role_id": 1, "user_id": None}))

    def auth(self):
        u = db.execute(
            "SELECT * FROM Users WHERE username=%s AND password_hash=%s",
            (self.login.text(), self.passw.text()), True
        )
        if u:
            self.open_main(u[0])
        else:
            QMessageBox.critical(self, "Ошибка", "Неверный логин")

    def open_main(self, user):
        self.m = MainWindow(user)
        self.m.show()
        self.close()


class CheckoutDialog(QDialog):
    def __init__(self, items):
        super().__init__()
        self.setWindowTitle("Оформление заказа")
        self.setWindowIcon(QIcon(ICON_PATH))
        self.resize(400, 300)

        self.items = items

        l = QVBoxLayout()

        self.delivery = QComboBox()
        self.delivery.addItems(["В зале", "Доставка"])

        self.address = QLineEdit()
        self.address.setPlaceholderText("Адрес (если доставка)")

        self.payment = QComboBox()
        self.payment.addItems(["Наличные", "Карта"])

        self.total_label = QLabel()

        total = sum(i["price"] * q.value() for _, q, i in items)
        self.total = total
        self.total_label.setText(f"Сумма: {total} ₽")

        btn = QPushButton("Подтвердить")

        l.addWidget(QLabel("Тип доставки"))
        l.addWidget(self.delivery)
        l.addWidget(self.address)
        l.addWidget(QLabel("Оплата"))
        l.addWidget(self.payment)
        l.addWidget(self.total_label)
        l.addWidget(btn)

        self.setLayout(l)

        btn.clicked.connect(self.accept)


# ---------------- MAIN ----------------
class MainWindow(QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.setWindowTitle("Pizzeria CRM")
        self.setWindowIcon(QIcon(ICON_PATH))
        self.resize(1200, 800)

        role = user["role_id"]

        if role == 1:
            self.setCentralWidget(ClientView(user, self))
        elif role == 2:
            self.setCentralWidget(OperatorView(self))
        elif role == 3:
            self.setCentralWidget(ManagerView(self))
        else:
            self.setCentralWidget(AdminView(self))

    def logout(self):
        self.auth = AuthWindow()
        self.auth.show()
        self.close()


# ---------------- CLIENT ----------------
class ClientView(QWidget):
    def __init__(self, user, main):
        super().__init__()
        self.user = user
        self.main = main

        l = QVBoxLayout()

        top = QHBoxLayout()
        btn_logout = QPushButton("Выйти")
        btn_orders = QPushButton("Мои заказы")
        top.addWidget(btn_orders)
        top.addStretch()
        top.addWidget(btn_logout)

        self.scroll = QScrollArea()
        self.box = QWidget()
        self.v = QVBoxLayout()

        self.items = []
        self.load()

        self.box.setLayout(self.v)
        self.scroll.setWidget(self.box)
        self.scroll.setWidgetResizable(True)

        btn_order = QPushButton("Оформить заказ")

        l.addLayout(top)
        l.addWidget(self.scroll)
        l.addWidget(btn_order)
        self.setLayout(l)

        btn_order.clicked.connect(self.make_order)
        btn_orders.clicked.connect(self.show_orders)
        btn_logout.clicked.connect(self.main.logout)

    def load(self):
        data = db.execute("SELECT * FROM MenuItems", fetch=True)

        for i in data:
            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.Box)

            h = QHBoxLayout()

            img = QLabel()
            path = f"images/{i['image']}.png"
            if not os.path.exists(path):
                path = "images/placeholder.png"

            img.setPixmap(QPixmap(path).scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio))

            text = QLabel(f"{i['name']} ({i['price']} ₽)")

            cb = QCheckBox()
            qty = QSpinBox()
            qty.setMinimum(1)

            self.items.append((cb, qty, i))

            h.addWidget(img)
            h.addWidget(text)
            h.addWidget(cb)
            h.addWidget(qty)

            frame.setLayout(h)
            self.v.addWidget(frame)

    def make_order(self):
        if not self.user.get("user_id"):
            QMessageBox.warning(self, "Ошибка", "Войдите в аккаунт")
            return

        sel = [x for x in self.items if x[0].isChecked()]
        if not sel:
            QMessageBox.warning(self, "Ошибка", "Выберите товары")
            return

        dlg = CheckoutDialog(sel)
        if not dlg.exec():
            return

        db.execute("""
            INSERT INTO Orders(user_id, order_date, total_amount, status,
            delivery_type, address, payment_method)
            VALUES(%s, NOW(), %s, 'Ожидает приготовления', %s, %s, %s)
        """, (
            self.user["user_id"],
            dlg.total,
            dlg.delivery.currentText(),
            dlg.address.text(),
            dlg.payment.currentText()
        ))

        oid = db.cursor.lastrowid

        for _, q, i in sel:
            db.execute(
                "INSERT INTO OrderItems(order_id, item_id, quantity) VALUES(%s, %s, %s)",
                (oid, i["item_id"], q.value())
            )

        QMessageBox.information(self, "Успех", "Заказ оформлен")

    def show_orders(self):
        self.w = OrdersWindow(self.user)
        self.w.show()


# ---------------- ORDERS ----------------
class OrdersWindow(QWidget):
    def __init__(self, user):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))
        self.user = user
        self.setWindowTitle("Мои заказы")
        self.resize(800, 500)

        l = QVBoxLayout()
        self.t = QTableWidget()
        l.addWidget(self.t)
        self.setLayout(l)

        self.load()

    def load(self):
        d = db.execute("SELECT * FROM Orders WHERE user_id=%s", (self.user["user_id"],), True)
        self.t.setRowCount(len(d))
        self.t.setColumnCount(4)
        self.t.setHorizontalHeaderLabels(["ID", "Дата", "Сумма", "Статус"])

        for i, r in enumerate(d):
            self.t.setItem(i, 0, QTableWidgetItem(str(r["order_id"])))
            self.t.setItem(i, 1, QTableWidgetItem(str(r["order_date"])))
            self.t.setItem(i, 2, QTableWidgetItem(f"{r['total_amount']} ₽"))
            self.t.setItem(i, 3, QTableWidgetItem(r["status"]))


# ---------------- OPERATOR ----------------
class OperatorView(QWidget):
    def __init__(self, main):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))
        self.main = main

        l = QVBoxLayout()

        top = QHBoxLayout()
        btn_logout = QPushButton("Выйти")

        self.filter = QComboBox()
        self.filter.addItems(["Все", "Ожидает приготовления", "Готово", "Доставляется"])

        self.bulk_status = QComboBox()
        self.bulk_status.addItems(["Ожидает приготовления", "Готово", "Доставляется"])

        btn_apply = QPushButton("Применить к выбранным")

        top.addWidget(self.filter)
        top.addWidget(self.bulk_status)
        top.addWidget(btn_apply)
        top.addStretch()
        top.addWidget(btn_logout)

        self.t = QTableWidget()
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.t.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)

        l.addLayout(top)
        l.addWidget(self.t)
        self.setLayout(l)

        self.filter.currentTextChanged.connect(self.load)
        btn_logout.clicked.connect(self.main.logout)
        btn_apply.clicked.connect(self.apply_bulk)

        self.load()

    def load(self):
        s = self.filter.currentText()

        if s == "Все":
            data = db.execute("SELECT * FROM Orders", fetch=True)
        else:
            data = db.execute("SELECT * FROM Orders WHERE status=%s", (s,), True)

        self.t.setRowCount(len(data))
        self.t.setColumnCount(4)
        self.t.setHorizontalHeaderLabels(["ID", "Дата", "Сумма", "Статус"])

        for i, r in enumerate(data):
            self.t.setItem(i, 0, QTableWidgetItem(str(r["order_id"])))
            self.t.setItem(i, 1, QTableWidgetItem(str(r["order_date"])))
            self.t.setItem(i, 2, QTableWidgetItem(f"{r['total_amount']} ₽"))

            combo = QComboBox()
            combo.addItems(["Ожидает приготовления", "Готово", "Доставляется"])
            combo.setCurrentText(r["status"])

            combo.currentTextChanged.connect(
                lambda status, row=i: self.update_status(row, status)
            )

            self.t.setCellWidget(i, 3, combo)

    def update_status(self, row, status):
        order_id = int(self.t.item(row, 0).text())
        db.execute("UPDATE Orders SET status=%s WHERE order_id=%s", (status, order_id))

    def apply_bulk(self):
        status = self.bulk_status.currentText()
        rows = set(i.row() for i in self.t.selectedIndexes())

        if not rows:
            QMessageBox.warning(self, "Ошибка", "Выберите строки")
            return

        for row in rows:
            order_id = int(self.t.item(row, 0).text())
            db.execute("UPDATE Orders SET status=%s WHERE order_id=%s", (status, order_id))

            combo = self.t.cellWidget(row, 3)
            if combo:
                combo.setCurrentText(status)

        QMessageBox.information(self, "Успех", "Статусы обновлены")


# ---------------- MANAGER ----------------
class ManagerView(QWidget):
    def __init__(self, main):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))
        self.main = main

        l = QVBoxLayout()

        top_bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Поиск по названию, описанию или категории...")
        btn_logout = QPushButton("Выйти")

        top_bar.addWidget(QLabel("Поиск:"))
        top_bar.addWidget(self.search)
        top_bar.addStretch()
        top_bar.addWidget(btn_logout)

        self.t = QTableWidget()
        self.t.setColumnCount(6)
        self.t.setHorizontalHeaderLabels(["ID", "Название", "Описание", "Цена", "Изображение", "Категория"])

        btn_add = QPushButton("Добавить")
        btn_del = QPushButton("Удалить")

        l.addLayout(top_bar)
        l.addWidget(self.t)
        l.addWidget(btn_add)
        l.addWidget(btn_del)
        self.setLayout(l)

        self.search.textChanged.connect(self.load)
        btn_add.clicked.connect(self.add)
        btn_del.clicked.connect(self.delete)
        btn_logout.clicked.connect(self.main.logout)
        self.t.itemChanged.connect(self.update)

        self.load()

    def load(self):
        search = self.search.text().strip()
        if search:
            data = db.execute(
                "SELECT * FROM MenuItems WHERE name LIKE %s OR description LIKE %s OR category LIKE %s",
                (f"%{search}%", f"%{search}%", f"%{search}%"), True
            )
        else:
            data = db.execute("SELECT * FROM MenuItems", fetch=True)

        self.t.setRowCount(0)
        self.t.setRowCount(len(data))
        for i, r in enumerate(data):
            self.t.setItem(i, 0, QTableWidgetItem(str(r["item_id"])))
            self.t.setItem(i, 1, QTableWidgetItem(r["name"]))
            self.t.setItem(i, 2, QTableWidgetItem(str(r["description"])))
            self.t.setItem(i, 3, QTableWidgetItem(f"{r['price']} ₽"))
            self.t.setItem(i, 4, QTableWidgetItem(r["image"]))
            self.t.setItem(i, 5, QTableWidgetItem(r.get("category", "")))

    def update(self, item):
        if item.column() == 0:
            return

        row_id = int(self.t.item(item.row(), 0).text())
        cols = ["name", "description", "price", "image", "category"]
        col_name = cols[item.column() - 1]

        val = item.text()
        if col_name == "price":
            val = val.replace("₽", "").strip()

        db.execute(f"UPDATE MenuItems SET {col_name}=%s WHERE item_id=%s", (val, row_id))

    def add(self):
        db.execute(
            "INSERT INTO MenuItems(name, description, price, category, image) VALUES('Новое блюдо', '-', 10, 'Пицца', '1')")
        self.load()

    def delete(self):
        r = self.t.currentRow()
        if r < 0:
            return
        row_id = int(self.t.item(r, 0).text())
        db.execute("DELETE FROM MenuItems WHERE item_id=%s", (row_id,))
        self.load()


# ---------------- ADMIN ----------------
class AdminView(QTabWidget):
    def __init__(self, main):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))
        self.addTab(ManagerView(main), "🍕 Управление меню")
        self.addTab(AdminOrdersView(main), "📦 Управление заказами")
        self.addTab(StatsView(), "📊 Аналитика")
        self.addTab(UserView(), "👥 Пользователи")


# ---------------- STATS ----------------
class StatsView(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))

        l = QVBoxLayout()
        l.setContentsMargins(15, 15, 15, 15)
        l.setSpacing(15)

        total_res = db.execute("SELECT COALESCE(SUM(total_amount), 0) s FROM Orders", fetch=True)[0]["s"]
        status_res = db.execute("SELECT status, COUNT(*) c FROM Orders GROUP BY status", fetch=True)
        popular_res = db.execute("""
            SELECT m.name, SUM(oi.quantity) c
            FROM OrderItems oi JOIN MenuItems m ON oi.item_id = m.item_id
            GROUP BY m.name ORDER BY c DESC LIMIT 5
        """, fetch=True)

        # Общая выручка
        gb_total = QGroupBox("💰 Общая выручка")
        gb_total.setStyleSheet("font-weight: bold;")
        vl_total = QVBoxLayout()
        lbl_total = QLabel(f"{total_res:,.2f} ₽")
        lbl_total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_total.setStyleSheet("font-size: 28px; color: #27ae60; margin: 10px;")
        vl_total.addWidget(lbl_total)
        gb_total.setLayout(vl_total)

        # Статусы
        gb_status = QGroupBox("📈 Статусы заказов")
        grid_status = QGridLayout()
        for idx, s in enumerate(status_res):
            lbl = QLabel(f"• {s['status']}")
            val = QLabel(f"{s['c']}")
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid_status.addWidget(lbl, idx, 0)
            grid_status.addWidget(val, idx, 1)
        gb_status.setLayout(grid_status)

        # Популярное
        gb_pop = QGroupBox("🏆 Топ-5 популярных блюд")
        vl_pop = QVBoxLayout()
        for p in popular_res:
            row = QHBoxLayout()
            name_lbl = QLabel(p['name'])
            count_lbl = QLabel(f"{p['c']} шт.")
            count_lbl.setStyleSheet("font-weight: bold;")
            row.addWidget(name_lbl)
            row.addStretch()
            row.addWidget(count_lbl)
            vl_pop.addLayout(row)
        gb_pop.setLayout(vl_pop)

        l.addWidget(gb_total)
        l.addWidget(gb_status)
        l.addWidget(gb_pop)
        self.setLayout(l)


# ---------------- ADMIN ORDERS ----------------
class AdminOrdersView(QWidget):
    def __init__(self, main):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))
        self.main = main

        l = QVBoxLayout()
        l.setContentsMargins(10, 10, 10, 10)

        # Фильтры
        filter_box = QGroupBox("🔎 Фильтры")
        fl = QGridLayout()

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-30))

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())

        self.status_filter = QComboBox()
        self.status_filter.addItems(["Все", "Ожидает приготовления", "Готово", "Доставляется", "Завершен"])

        self.client_filter = QLineEdit()
        self.client_filter.setPlaceholderText("Имя клиента...")

        btn_apply = QPushButton("Применить")
        btn_logout = QPushButton("Выйти")

        fl.addWidget(QLabel("С:"), 0, 0)
        fl.addWidget(self.date_from, 0, 1)
        fl.addWidget(QLabel("По:"), 0, 2)
        fl.addWidget(self.date_to, 0, 3)
        fl.addWidget(self.status_filter, 1, 0, 1, 2)
        fl.addWidget(self.client_filter, 1, 2, 1, 2)
        fl.addWidget(btn_apply, 2, 0, 1, 2)
        fl.addWidget(btn_logout, 2, 2, 1, 2, Qt.AlignmentFlag.AlignRight)
        filter_box.setLayout(fl)

        # Таблица
        self.t = QTableWidget()
        self.t.setColumnCount(6)
        self.t.setHorizontalHeaderLabels(["ID", "Клиент", "Дата", "Сумма", "Статус", "Адрес"])

        l.addWidget(filter_box)
        l.addWidget(self.t)
        self.setLayout(l)

        btn_apply.clicked.connect(self.load)
        btn_logout.clicked.connect(self.main.logout)
        self.t.itemChanged.connect(self.update)  # Подключаем сигнал
        self.load()

    def load(self):
        query = """
            SELECT o.order_id, u.username, o.order_date, o.total_amount, o.status, o.address
            FROM Orders o
            LEFT JOIN Users u ON o.user_id = u.user_id
            WHERE 1=1
        """
        params = []

        d1 = self.date_from.date().toString("yyyy-MM-dd")
        d2 = self.date_to.date().toString("yyyy-MM-dd")
        query += " AND DATE(o.order_date) BETWEEN %s AND %s"
        params.extend([d1, d2])

        if self.status_filter.currentText() != "Все":
            query += " AND o.status = %s"
            params.append(self.status_filter.currentText())

        if self.client_filter.text().strip():
            query += " AND u.username LIKE %s"
            params.append(f"%{self.client_filter.text().strip()}%")

        query += " ORDER BY o.order_date DESC"

        data = db.execute(query, params, True)

        self.t.setRowCount(len(data))
        for i, r in enumerate(data):
            self.t.setItem(i, 0, QTableWidgetItem(str(r["order_id"])))
            self.t.setItem(i, 1, QTableWidgetItem(str(r.get("username") or "Гость")))
            self.t.setItem(i, 2, QTableWidgetItem(str(r["order_date"])))
            self.t.setItem(i, 3, QTableWidgetItem(f"{r['total_amount']} ₽"))
            self.t.setItem(i, 4, QTableWidgetItem(r["status"]))  # Статус — редактируемый
            self.t.setItem(i, 5, QTableWidgetItem(str(r.get("address") or "-")))

            # Настраиваем флаги редактирования
            for col in range(6):
                item = self.t.item(i, col)
                if item:
                    if col in [3, 4, 5]:  # Сумма, Статус, Адрес — можно менять
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                    else:  # ID, Клиент, Дата — только чтение
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

    def update(self, item):
        """Обработка изменения ячейки в таблице заказов"""
        row = item.row()
        col = item.column()

        # Колонки: 0=ID, 1=Клиент, 2=Дата, 3=Сумма, 4=Статус, 5=Адрес
        if col in [0, 1, 2]:  # Эти поля не редактируются
            return

        order_id = int(self.t.item(row, 0).text())

        if col == 3:  # Сумма
            val = item.text().replace("₽", "").replace(",", ".").strip()
            db.execute("UPDATE Orders SET total_amount=%s WHERE order_id=%s", (val, order_id))

        elif col == 4:  # Статус ← ВАЖНО: меняется в БД
            db.execute("UPDATE Orders SET status=%s WHERE order_id=%s", (item.text(), order_id))

        elif col == 5:  # Адрес
            db.execute("UPDATE Orders SET address=%s WHERE order_id=%s", (item.text(), order_id))


# ---------------- USERS (ADMIN) ----------------
class UserView(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))

        l = QVBoxLayout()
        l.setContentsMargins(10, 10, 10, 10)

        # Поиск
        search_layout = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Поиск по имени или контактам...")
        search_layout.addWidget(self.search)
        l.addLayout(search_layout)

        # Таблица
        self.t = QTableWidget()
        self.t.setColumnCount(5)
        self.t.setHorizontalHeaderLabels(["ID", "Логин", "Пароль", "Роль", "Контакты"])
        l.addWidget(self.t)

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ Добавить")
        btn_del = QPushButton("🗑️ Удалить")
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_del)
        btn_layout.addStretch()
        l.addLayout(btn_layout)

        self.setLayout(l)

        self.search.textChanged.connect(self.load)
        btn_add.clicked.connect(self.add)
        btn_del.clicked.connect(self.delete)
        self.t.itemChanged.connect(self.update)

        self.load()

    def load(self):
        search = self.search.text().strip()
        if search:
            data = db.execute(
                "SELECT * FROM Users WHERE username LIKE %s OR contact_info LIKE %s",
                (f"%{search}%", f"%{search}%"), True
            )
        else:
            data = db.execute("SELECT * FROM Users", fetch=True)

        self.t.setRowCount(0)
        self.t.setRowCount(len(data))

        roles = {1: "Клиент", 2: "Оператор", 3: "Менеджер", 4: "Админ"}

        for i, r in enumerate(data):
            self.t.setItem(i, 0, QTableWidgetItem(str(r["user_id"])))
            self.t.setItem(i, 1, QTableWidgetItem(r["username"]))
            self.t.setItem(i, 2, QTableWidgetItem(r["password_hash"]))

            # Роль через ComboBox
            role_combo = QComboBox()
            role_combo.addItems(["Клиент", "Оператор", "Менеджер", "Админ"])
            role_combo.setCurrentIndex(r["role_id"] - 1)
            role_combo.currentTextChanged.connect(
                lambda val, row=i, uid=r["user_id"]: self.update_role(row, uid, val)
            )
            self.t.setCellWidget(i, 3, role_combo)

            self.t.setItem(i, 4, QTableWidgetItem(r.get("contact_info") or ""))

    def update_role(self, row, user_id, role_name):
        role_map = {"Клиент": 1, "Оператор": 2, "Менеджер": 3, "Админ": 4}
        new_role = role_map.get(role_name, 1)
        db.execute("UPDATE Users SET role_id=%s WHERE user_id=%s", (new_role, user_id))

    def update(self, item):
        if item.column() in [0, 3]:  # ID и роль обрабатываются отдельно
            return

        user_id = int(self.t.item(item.row(), 0).text())
        cols = [None, "username", "password_hash", None, "contact_info"]
        col_name = cols[item.column()]

        if col_name:
            db.execute(f"UPDATE Users SET {col_name}=%s WHERE user_id=%s", (item.text(), user_id))

    def add(self):
        db.execute("""
            INSERT INTO Users(username, password_hash, role_id, contact_info) 
            VALUES('new_user', '123', 1, 'email@example.com')
        """)
        self.load()

    def delete(self):
        r = self.t.currentRow()
        if r < 0:
            return
        user_id = int(self.t.item(r, 0).text())

        reply = QMessageBox.question(
            self, "Подтверждение",
            "Вы уверены, что хотите удалить этого пользователя?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            db.execute("DELETE FROM Users WHERE user_id=%s", (user_id,))
            self.load()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(ICON_PATH))

    w = AuthWindow()
    w.show()
    sys.exit(app.exec())