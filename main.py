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
            database="real_estate_agency"
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
        self.setWindowTitle("Вход в систему")
        self.setWindowIcon(QIcon(ICON_PATH))
        self.resize(400, 280)

        l = QVBoxLayout()
        l.addStretch()

        title = QLabel("🏠 Агентство недвижимости")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 20px;")
        l.addWidget(title)

        self.login = QLineEdit()
        self.login.setPlaceholderText("Логин")
        self.passw = QLineEdit()
        self.passw.setPlaceholderText("Пароль")
        self.passw.setEchoMode(QLineEdit.EchoMode.Password)

        btn_login = QPushButton("Войти")
        btn_guest = QPushButton("Войти как Гость")

        l.addWidget(QLabel("Логин:"))
        l.addWidget(self.login)
        l.addWidget(QLabel("Пароль:"))
        l.addWidget(self.passw)
        l.addWidget(btn_login)
        l.addWidget(btn_guest)
        l.addStretch()

        self.setLayout(l)

        btn_login.clicked.connect(self.auth)
        btn_guest.clicked.connect(lambda: self.open_main({"role_id": 1, "user_id": None, "username": "Гость"}))

    def auth(self):
        u = db.execute(
            "SELECT u.user_id, u.username, u.role_id, r.role_name, u.contact_info "
            "FROM Users u "
            "JOIN Roles r ON u.role_id = r.role_id "
            "WHERE u.username=%s AND u.password_hash=%s",
            (self.login.text(), self.passw.text()), True
        )
        if u:
            self.open_main(u[0])
        else:
            QMessageBox.critical(self, "Ошибка", "Неверный логин или пароль")

    def open_main(self, user):
        self.m = MainWindow(user)
        self.m.show()
        self.close()


class RequestDialog(QDialog):
    def __init__(self, properties, user):
        super().__init__()
        self.setWindowTitle("Создание заявки")
        self.setWindowIcon(QIcon(ICON_PATH))
        self.resize(450, 400)

        self.properties = properties
        self.user = user

        l = QVBoxLayout()

        l.addWidget(QLabel("📋 Выбранные объекты:"))
        self.selected_list = QListWidget()
        for cb, _, prop in properties:
            if cb.isChecked():
                self.selected_list.addItem(f"{prop['name']} — {prop['price']:,.2f} ₽")
        l.addWidget(self.selected_list)

        l.addWidget(QLabel("🎯 Тип сделки:"))
        self.deal_type = QComboBox()
        self.deal_type.addItems(["покупка", "аренда"])
        l.addWidget(self.deal_type)

        l.addWidget(QLabel("💬 Комментарий к заявке:"))
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        self.notes.setPlaceholderText("Ваши пожелания по объектам...")
        l.addWidget(self.notes)

        l.addWidget(QLabel("📞 Контакт для связи:"))
        self.contact = QLineEdit()
        self.contact.setText(user.get("contact_info", "").split(",")[0] if user.get("contact_info") else "")
        self.contact.setPlaceholderText("Телефон или email")
        l.addWidget(self.contact)

        # FIX: Correct variable names in sum calculation
        total = sum(p["price"] for cb, _, p in properties if cb.isChecked())
        self.total_label = QLabel(f"💰 Ориентировочная сумма: {total:,.2f} ₽")
        self.total_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        l.addWidget(self.total_label)

        btn = QPushButton("✅ Отправить заявку")
        l.addWidget(btn)

        self.setLayout(l)
        btn.clicked.connect(self.accept)


# ---------------- MAIN ----------------
class MainWindow(QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.setWindowTitle(f"🏠 Агентство недвижимости — {user.get('role_name', '')}")
        self.setWindowIcon(QIcon(ICON_PATH))
        self.resize(1300, 850)

        role = user["role_id"]

        if role == 1:
            self.setCentralWidget(GuestView(user, self))
        elif role == 2:
            self.setCentralWidget(ClientView(user, self))
        elif role == 3:
            self.setCentralWidget(AgentView(self))
        elif role == 4:
            self.setCentralWidget(ManagerView(self))
        else:
            self.setCentralWidget(AdminView(self))

    def logout(self):
        self.auth = AuthWindow()
        self.auth.show()
        self.close()


# ---------------- GUEST (NO FILTERS, NO DETAILS BUTTON) ----------------
class GuestView(QWidget):
    def __init__(self, user, main):
        super().__init__()
        self.user = user
        self.main = main

        l = QVBoxLayout()

        # Верхняя панель
        top = QHBoxLayout()
        top.addWidget(QLabel("👋 Вы вошли как Гость"))
        top.addStretch()
        btn_login = QPushButton("Войти в аккаунт")
        btn_logout = QPushButton("Выйти")
        top.addWidget(btn_login)
        top.addWidget(btn_logout)
        l.addLayout(top)

        # NO FILTERS for guest - just a simple label
        info_label = QLabel("📋 Каталог объектов недвижимости")
        info_label.setStyleSheet("font-size: 14px; font-weight: bold; margin: 10px 0;")
        l.addWidget(info_label)

        # Список объектов
        self.scroll = QScrollArea()
        self.box = QWidget()
        self.v = QVBoxLayout()
        self.properties = []
        self.load()
        self.box.setLayout(self.v)
        self.scroll.setWidget(self.box)
        self.scroll.setWidgetResizable(True)
        l.addWidget(self.scroll)

        self.setLayout(l)

        btn_logout.clicked.connect(self.main.logout)
        btn_login.clicked.connect(
            lambda: QMessageBox.information(self, "Вход", "Выйдите и войдите через форму авторизации"))

    def load(self):
        # Очищаем список
        for item in self.properties:
            item[0].deleteLater()
        self.properties = []
        while self.v.count():
            child = self.v.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # NO FILTERS - just load all properties for sale/rent
        data = db.execute("SELECT * FROM Properties", fetch=True)

        for prop in data:
            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.Box)
            frame.setStyleSheet("padding: 10px; margin: 5px;")

            h = QHBoxLayout()

            # Изображение
            img = QLabel()
            photos = db.execute("SELECT image_path FROM PropertyPhotos WHERE property_id=%s LIMIT 1",
                                (prop["property_id"],), fetch=True)
            path = photos[0]["image_path"] if photos else "images/placeholder.png"
            if not os.path.exists(path):
                path = "images/placeholder.png"
            pixmap = QPixmap(path).scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
            img.setPixmap(pixmap)

            # Полная информация как в оригинале
            info = QVBoxLayout()
            info.addWidget(QLabel(f"<b>{prop['name']}</b>"))
            info.addWidget(QLabel(f"📍 {prop['address']}"))
            info.addWidget(QLabel(f"📐 Площадь: {prop['area']} м²"))
            info.addWidget(QLabel(f"🏷️ Тип: {prop['type']}"))
            info.addWidget(QLabel(f"💰 {prop['price']:,.2f} ₽"))
            status_badge = QLabel(f"● {prop['status'].upper()}")
            status_badge.setStyleSheet(
                "color: green; font-weight: bold;" if prop['status'] == 'продажа' else "color: blue;")
            info.addWidget(status_badge)
            if prop.get('description'):
                info.addWidget(QLabel(f"📝 {prop['description'][:50]}{'...' if len(prop['description']) > 50 else ''}"))

            h.addWidget(img)
            h.addLayout(info)
            h.addStretch()

            # NO DETAILS BUTTON for guest

            frame.setLayout(h)
            self.properties.append((frame, prop))
            self.v.addWidget(frame)


# ---------------- CLIENT (SAME CARDS AS GUEST, WITH FILTERS) ----------------
class ClientView(QWidget):
    def __init__(self, user, main):
        super().__init__()
        self.user = user
        self.main = main
        self.client_id = None

        client_data = db.execute("SELECT client_id FROM Clients WHERE user_id=%s",
                                 (user["user_id"],), fetch=True)
        if client_data:
            self.client_id = client_data[0]["client_id"]

        l = QVBoxLayout()

        # Верхняя панель
        top = QHBoxLayout()
        lbl_welcome = QLabel(f"👋 {user['username']} (Клиент)")
        btn_orders = QPushButton("📋 Мои заявки")
        btn_deals = QPushButton("💼 Мои сделки")
        btn_logout = QPushButton("🚪 Выйти")

        top.addWidget(lbl_welcome)
        top.addStretch()
        top.addWidget(btn_orders)
        top.addWidget(btn_deals)
        top.addWidget(btn_logout)
        l.addLayout(top)

        # Фильтры для клиента
        filter_box = QGroupBox("🔍 Поиск объектов")
        fl = QGridLayout()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по названию или адресу...")

        self.type_filter = QComboBox()
        self.type_filter.addItems(
            ["Все типы", "квартира", "студия", "дом", "таунхаус", "коммерция", "гараж", "участок"])

        self.status_filter = QComboBox()
        self.status_filter.addItems(["Все", "продажа", "аренда"])

        self.price_min = QLineEdit()
        self.price_min.setPlaceholderText("Мин. цена")
        self.price_max = QLineEdit()
        self.price_max.setPlaceholderText("Макс. цена")

        fl.addWidget(QLabel("Поиск:"), 0, 0)
        fl.addWidget(self.search, 0, 1, 1, 3)
        fl.addWidget(QLabel("Тип:"), 1, 0)
        fl.addWidget(self.type_filter, 1, 1)
        fl.addWidget(QLabel("Статус:"), 1, 2)
        fl.addWidget(self.status_filter, 1, 3)
        fl.addWidget(QLabel("Цена:"), 2, 0)
        fl.addWidget(self.price_min, 2, 1)
        fl.addWidget(QLabel("—"), 2, 2)
        fl.addWidget(self.price_max, 2, 3)
        filter_box.setLayout(fl)
        l.addWidget(filter_box)

        # Список объектов с чекбоксами (КАК У ГОСТЯ - полная информация)
        self.scroll = QScrollArea()
        self.box = QWidget()
        self.v = QVBoxLayout()
        self.items = []
        self.prop_group = QButtonGroup(self)
        self.prop_group.setExclusive(True)
        self.load_properties()
        self.box.setLayout(self.v)
        self.scroll.setWidget(self.box)
        self.scroll.setWidgetResizable(True)
        l.addWidget(self.scroll)

        # Кнопка заявки
        btn_layout = QHBoxLayout()
        btn_request = QPushButton("📝 Создать заявку на выбранные объекты")
        btn_layout.addWidget(btn_request)
        btn_layout.addStretch()
        l.addLayout(btn_layout)

        self.setLayout(l)

        self.search.textChanged.connect(self.load_properties)
        self.type_filter.currentTextChanged.connect(self.load_properties)
        self.status_filter.currentTextChanged.connect(self.load_properties)
        btn_request.clicked.connect(self.make_request)
        btn_orders.clicked.connect(self.show_requests)
        btn_deals.clicked.connect(self.show_deals)
        btn_logout.clicked.connect(self.main.logout)

    def load_properties(self):
        # Очищаем
        for btn in self.prop_group.buttons():
            self.prop_group.removeButton(btn)

        for item in self.items:
            item[0].deleteLater()
        self.items = []
        while self.v.count():
            child = self.v.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        query = "SELECT * FROM Properties WHERE 1=1"
        params = []

        search = self.search.text().strip()
        if search:
            query += " AND (name LIKE %s OR address LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])

        if self.type_filter.currentText() != "Все типы":
            query += " AND type = %s"
            params.append(self.type_filter.currentText())

        if self.status_filter.currentText() != "Все":
            query += " AND status = %s"
            params.append(self.status_filter.currentText())

        if self.price_min.text().strip():
            query += " AND price >= %s"
            params.append(float(self.price_min.text()))
        if self.price_max.text().strip():
            query += " AND price <= %s"
            params.append(float(self.price_max.text()))

        data = db.execute(query, params, fetch=True)

        for prop in data:
            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.Box)
            frame.setStyleSheet("padding: 10px; margin: 5px;")
            h = QHBoxLayout()

            img = QLabel()
            photos = db.execute("SELECT image_path FROM PropertyPhotos WHERE property_id=%s LIMIT 1",
                                (prop["property_id"],), fetch=True)
            path = photos[0]["image_path"] if photos else "images/placeholder.png"
            if not os.path.exists(path):
                path = "images/placeholder.png"
            pixmap = QPixmap(path).scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
            img.setPixmap(pixmap)

            # Полная информация как у гостя
            info = QVBoxLayout()
            info.addWidget(QLabel(f"<b>{prop['name']}</b>"))
            info.addWidget(QLabel(f"📍 {prop['address']}"))
            info.addWidget(QLabel(f"📐 Площадь: {prop['area']} м²"))
            info.addWidget(QLabel(f"🏷️ Тип: {prop['type']}"))
            info.addWidget(QLabel(f"💰 {prop['price']:,.2f} ₽"))
            status_badge = QLabel(f"● {prop['status'].upper()}")
            status_badge.setStyleSheet(
                "color: green; font-weight: bold;" if prop['status'] == 'продажа' else "color: blue;")
            info.addWidget(status_badge)

            cb = QCheckBox()
            self.prop_group.addButton(cb)  # Добавляем в группу взаимного исключения
            self.items.append((cb, None, prop))

            h.addWidget(img)
            h.addLayout(info)
            h.addWidget(cb)
            h.addStretch()

            frame.setLayout(h)
            self.v.addWidget(frame)

    def make_request(self):
        if not self.client_id:
            QMessageBox.warning(self, "Ошибка", "Сначала заполните профиль клиента")
            return

        selected = [x for x in self.items if x[0].isChecked()]
        if len(selected) != 1:
            QMessageBox.warning(self, "Ошибка", "Выберите ровно один объект для заявки")
            return

        dlg = RequestDialog(selected, self.user)
        if not dlg.exec():
            return

        try:
            # Создаем заявку
            total = sum(p["price"] for cb, _, p in selected if cb.isChecked())
            # FIX: Convert Decimal to float before multiplication
            commission = float(total) * 0.03

            db.execute("""
                INSERT INTO Requests(client_id, agent_id, request_date, total_commission, status)
                VALUES(%s, NULL, CURDATE(), %s, 'Ожидает обработки')
            """, (self.client_id, commission))

            request_id = db.cursor.lastrowid

            # Добавляем объекты в заявку
            for cb, _, prop in selected:
                if cb.isChecked():
                    db.execute("""
                        INSERT INTO RequestProperties(request_id, property_id, notes)
                        VALUES(%s, %s, %s)
                    """, (request_id, prop["property_id"], dlg.notes.toPlainText()))

            # Обновляем контакт клиента
            if dlg.contact.text():
                db.execute("UPDATE Clients SET phone=%s WHERE client_id=%s",
                           (dlg.contact.text(), self.client_id))

            db.conn.commit()
            QMessageBox.information(self, "Успех", "Заявка создана! Агент свяжется с вами.")
        except Exception as e:
            db.conn.rollback()
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать заявку: {str(e)}")

    def show_requests(self):
        self.w = RequestsWindow(self.user, self.client_id)
        self.w.show()

    def show_deals(self):
        self.w = DealsWindow(self.user, self.client_id)
        self.w.show()


# ---------------- REQUESTS WINDOW ----------------
class RequestsWindow(QWidget):
    def __init__(self, user, client_id):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))
        self.user = user
        self.client_id = client_id
        self.setWindowTitle("📋 Мои заявки")
        self.resize(900, 550)

        l = QVBoxLayout()
        self.t = QTableWidget()
        l.addWidget(self.t)

        btn_delete = QPushButton("🗑️ Удалить выбранную заявку")
        btn_delete.clicked.connect(self.delete_request)
        l.addWidget(btn_delete)

        self.setLayout(l)
        self.load()

    def delete_request(self):
        """Удаление заявки только со статусом 'Ожидает обработки'"""
        selected_rows = self.t.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, "Ошибка", "Выберите заявку для удаления")
            return

        # Получаем ID выбранной заявки (первая колонка)
        row = selected_rows[0].row()
        request_id = int(self.t.item(row, 0).text())
        status = self.t.item(row, 2).text()

        # 👇 ПРОВЕРКА: можно удалять только "Ожидает обработки"
        if status != "Ожидает обработки":
            QMessageBox.warning(
                self,
                "Нельзя удалить",
                "Можно удалять только заявки со статусом «Ожидает обработки»"
            )
            return

        # Подтверждение
        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            "Вы уверены, что хотите удалить эту заявку?\nЭто действие нельзя отменить.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Сначала удаляем связанные записи в RequestProperties (внешний ключ)
                db.execute("DELETE FROM RequestProperties WHERE request_id=%s", (request_id,))
                # Затем удаляем саму заявку
                db.execute("DELETE FROM Requests WHERE request_id=%s", (request_id,))
                db.conn.commit()

                QMessageBox.information(self, "Успех", "Заявка удалена")
                self.load()  # Перезагружаем таблицу
            except Exception as e:
                db.conn.rollback()
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить заявку: {str(e)}")

    def load(self):
        data = db.execute("""
            SELECT r.request_id, r.request_date, r.status, r.total_commission,
                   GROUP_CONCAT(p.name SEPARATOR '; ') as properties
            FROM Requests r
            LEFT JOIN RequestProperties rp ON r.request_id = rp.request_id
            LEFT JOIN Properties p ON rp.property_id = p.property_id
            WHERE r.client_id = %s
            GROUP BY r.request_id
            ORDER BY r.request_date DESC
        """, (self.client_id,), fetch=True)

        self.t.setRowCount(len(data))
        self.t.setColumnCount(5)
        self.t.setHorizontalHeaderLabels(["ID", "Дата", "Статус", "Комиссия", "Объекты"])

        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        for i, r in enumerate(data):
            self.t.setItem(i, 0, QTableWidgetItem(str(r["request_id"])))
            self.t.setItem(i, 1, QTableWidgetItem(str(r["request_date"])))
            self.t.setItem(i, 2, QTableWidgetItem(r["status"]))
            self.t.setItem(i, 3, QTableWidgetItem(f"{r['total_commission']:,.2f} ₽"))
            self.t.setItem(i, 4, QTableWidgetItem(r["properties"] or "—"))


# ---------------- DEALS WINDOW ----------------
class DealsWindow(QWidget):
    def __init__(self, user, client_id):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))
        self.user = user
        self.client_id = client_id
        self.setWindowTitle("💼 Мои сделки")
        self.resize(800, 400)

        l = QVBoxLayout()
        self.t = QTableWidget()
        l.addWidget(self.t)
        self.setLayout(l)
        self.load()

    def load(self):
        data = db.execute("""
            SELECT d.deal_id, d.deal_date, d.amount, d.deal_type, r.status as request_status
            FROM Deals d
            JOIN Requests r ON d.request_id = r.request_id
            WHERE r.client_id = %s
            ORDER BY d.deal_date DESC
        """, (self.client_id,), fetch=True)

        self.t.setRowCount(len(data))
        self.t.setColumnCount(4)
        self.t.setHorizontalHeaderLabels(["ID сделки", "Дата", "Сумма", "Тип"])

        for i, r in enumerate(data):
            self.t.setItem(i, 0, QTableWidgetItem(str(r["deal_id"])))
            self.t.setItem(i, 1, QTableWidgetItem(str(r["deal_date"])))
            self.t.setItem(i, 2, QTableWidgetItem(f"{r['amount']:,.2f} ₽"))
            self.t.setItem(i, 3, QTableWidgetItem(r["deal_type"]))


# ---------------- AGENT (WITH CREATE REQUEST FUNCTIONALITY) ----------------
class AgentView(QWidget):
    def __init__(self, main):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))
        self.main = main

        l = QVBoxLayout()

        top = QHBoxLayout()
        btn_logout = QPushButton("🚪 Выйти")
        btn_create = QPushButton("➕ Создать заявку")
        self.filter = QComboBox()
        self.filter.addItems(["Все", "Ожидает обработки", "Запланирован просмотр", "Ожидает просмотра", "Закрыта"])
        self.bulk_status = QComboBox()
        self.bulk_status.addItems(["Ожидает обработки", "Запланирован просмотр", "Ожидает просмотра", "Закрыта"])
        btn_apply = QPushButton("🔄 Применить статус к выбранным")

        top.addWidget(self.filter)
        top.addWidget(self.bulk_status)
        top.addWidget(btn_apply)
        top.addStretch()
        top.addWidget(btn_create)
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
        btn_create.clicked.connect(self.create_request)

        self.load()

    def load(self):
        status = self.filter.currentText()
        agent_id = self.main.user["user_id"]

        query = """
            SELECT r.request_id, u.username as client_name, r.request_date, 
                   r.total_commission, r.status, c.phone, c.preferences,
                   GROUP_CONCAT(p.name SEPARATOR '; ') as properties
            FROM Requests r
            JOIN Clients c ON r.client_id = c.client_id
            JOIN Users u ON c.user_id = u.user_id
            LEFT JOIN RequestProperties rp ON r.request_id = rp.request_id
            LEFT JOIN Properties p ON rp.property_id = p.property_id
            WHERE (r.agent_id = %s OR r.agent_id IS NULL)
        """
        params = [agent_id]

        if status != "Все":
            query += " AND r.status = %s"
            params.append(status)

        query += " GROUP BY r.request_id ORDER BY r.request_date DESC"

        data = db.execute(query, params, fetch=True)

        self.t.setRowCount(len(data))
        self.t.setColumnCount(7)
        self.t.setHorizontalHeaderLabels(["ID", "Клиент", "Дата", "Комиссия", "Статус", "Телефон", "Объекты"])

        for i, r in enumerate(data):
            self.t.setItem(i, 0, QTableWidgetItem(str(r["request_id"])))
            self.t.setItem(i, 1, QTableWidgetItem(r["client_name"] or "Аноним"))
            self.t.setItem(i, 2, QTableWidgetItem(str(r["request_date"])))
            self.t.setItem(i, 3, QTableWidgetItem(f"{r['total_commission']:,.2f} ₽"))

            combo = QComboBox()
            combo.addItems(["Ожидает обработки", "Запланирован просмотр", "Ожидает просмотра", "Закрыта"])
            combo.setCurrentText(r["status"])
            # Block signal during programmatic update to avoid recursion
            combo.currentTextChanged.disconnect() if combo.signalsBlocked() else None
            combo.currentTextChanged.connect(
                lambda s, row=i: self.update_status(row, s)
            )
            self.t.setCellWidget(i, 4, combo)

            self.t.setItem(i, 5, QTableWidgetItem(r["phone"] or "—"))
            self.t.setItem(i, 6, QTableWidgetItem(r["properties"] or "—"))

    def update_status(self, row, status):
        request_id = int(self.t.item(row, 0).text())
        db.execute("UPDATE Requests SET status=%s WHERE request_id=%s", (status, request_id))

        if status == "Закрыта":
            req_data = db.execute("SELECT total_commission FROM Requests WHERE request_id=%s",
                                  (request_id,), fetch=True)
            if req_data:
                db.execute("""
                    INSERT INTO Deals(request_id, deal_date, amount, deal_type)
                    VALUES(%s, CURDATE(), %s, 'продажа')
                """, (request_id, req_data[0]["total_commission"] * 30))

    def apply_bulk(self):
        status = self.bulk_status.currentText()
        rows = set(i.row() for i in self.t.selectedIndexes())

        if not rows:
            QMessageBox.warning(self, "Ошибка", "Выберите заявки")
            return

        for row in rows:
            request_id = int(self.t.item(row, 0).text())
            db.execute("UPDATE Requests SET status=%s WHERE request_id=%s", (status, request_id))
            combo = self.t.cellWidget(row, 4)
            if combo:
                combo.blockSignals(True)
                combo.setCurrentText(status)
                combo.blockSignals(False)

        QMessageBox.information(self, "Успех", "Статусы обновлены")

    def create_request(self):
        """Создание новой заявки агентом с выбором клиента, даты, объектов"""
        dlg = AgentCreateRequestDialog(self.main.user["user_id"])
        if dlg.exec():
            self.load()
            QMessageBox.information(self, "Успех", "Заявка создана!")


class AgentCreateRequestDialog(QDialog):
    def __init__(self, agent_id):
        super().__init__()
        self.agent_id = agent_id
        self.setWindowTitle("➕ Создание заявки")
        self.setWindowIcon(QIcon(ICON_PATH))
        self.resize(600, 500)

        l = QVBoxLayout()

        # Выбор клиента
        client_group = QGroupBox("👤 Клиент")
        cl = QFormLayout()
        self.client_combo = QComboBox()
        self.client_combo.addItem("Выберите клиента...")
        clients = db.execute("""
            SELECT c.client_id, u.username, c.phone 
            FROM Clients c 
            JOIN Users u ON c.user_id = u.user_id
        """, fetch=True)
        for c in clients:
            self.client_combo.addItem(f"{c['username']} ({c['phone']})", c["client_id"])
        cl.addRow("Клиент:", self.client_combo)
        client_group.setLayout(cl)
        l.addWidget(client_group)

        # Выбор объектов
        prop_group = QGroupBox("🏠 Объекты")
        pl = QVBoxLayout()
        self.prop_list = QListWidget()
        self.prop_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        props = db.execute("SELECT property_id, name, price, type FROM Properties", fetch=True)
        self.props_data = {}
        for p in props:
            item = QListWidgetItem(f"{p['name']} — {p['price']:,.2f} ₽ ({p['type']})")
            item.setData(Qt.ItemDataRole.UserRole, p["property_id"])
            self.prop_list.addItem(item)
            self.props_data[p["property_id"]] = p
        pl.addWidget(self.prop_list)
        prop_group.setLayout(pl)
        l.addWidget(prop_group)

        # Параметры заявки
        params_group = QGroupBox("📋 Параметры")
        pfl = QFormLayout()
        self.request_date = QDateEdit()
        self.request_date.setCalendarPopup(True)
        self.request_date.setDate(QDate.currentDate())
        self.deal_type = QComboBox()
        self.deal_type.addItems(["покупка", "аренда"])
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(60)
        self.commission = QLineEdit()
        pfl.addRow("Дата:", self.request_date)
        pfl.addRow("Тип сделки:", self.deal_type)
        pfl.addRow("Комиссия (₽):", self.commission)
        pfl.addRow("Комментарий:", self.notes)
        params_group.setLayout(pfl)
        l.addWidget(params_group)

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Отмена")
        btn_create = QPushButton("✅ Создать")
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_create)
        l.addLayout(btn_layout)

        self.setLayout(l)
        btn_cancel.clicked.connect(self.reject)
        btn_create.clicked.connect(self.create)

    def create(self):
        if self.client_combo.currentIndex() == 0:
            QMessageBox.warning(self, "Ошибка", "Выберите клиента")
            return

        selected_items = self.prop_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Ошибка", "Выберите хотя бы один объект")
            return

        client_id = self.client_combo.currentData()
        commission = float(self.commission.text().replace(",", ".") or "0")
        request_date = self.request_date.date().toString("yyyy-MM-dd")

        try:
            db.execute("""
                INSERT INTO Requests(client_id, agent_id, request_date, total_commission, status)
                VALUES(%s, %s, %s, %s, 'Ожидает обработки')
            """, (client_id, self.agent_id, request_date, commission))

            request_id = db.cursor.lastrowid

            for item in selected_items:
                prop_id = item.data(Qt.ItemDataRole.UserRole)
                db.execute("""
                    INSERT INTO RequestProperties(request_id, property_id, notes)
                    VALUES(%s, %s, %s)
                """, (request_id, prop_id, self.notes.toPlainText()))

            db.conn.commit()
            self.accept()
        except Exception as e:
            db.conn.rollback()
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать заявку: {str(e)}")


# ---------------- MANAGER (FIXED CRASH) ----------------
class ManagerView(QWidget):
    def __init__(self, main):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))
        self.main = main
        self._loading = False  # Flag to prevent recursive updates

        l = QVBoxLayout()

        top_bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Поиск по названию, адресу или типу...")
        btn_logout = QPushButton("🚪 Выйти")

        top_bar.addWidget(QLabel("Поиск:"))
        top_bar.addWidget(self.search)
        top_bar.addStretch()
        top_bar.addWidget(btn_logout)

        self.t = QTableWidget()
        self.t.setColumnCount(7)  # Reduced columns to avoid issues
        self.t.setHorizontalHeaderLabels(["ID", "Название", "Тип", "Площадь", "Цена", "Адрес", "Статус"])
        # Disable editing on ID column
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)

        btn_add = QPushButton("➕ Добавить объект")
        btn_del = QPushButton("🗑️ Удалить")

        l.addLayout(top_bar)
        l.addWidget(self.t)
        l.addWidget(btn_add)
        l.addWidget(btn_del)
        self.setLayout(l)

        self.search.textChanged.connect(self.load)
        btn_add.clicked.connect(self.add_property)
        btn_del.clicked.connect(self.delete_property)
        btn_logout.clicked.connect(self.main.logout)
        # Connect itemChanged but handle carefully to avoid recursion
        self.t.itemChanged.connect(self.on_item_changed)

        self.load()

    def load(self):
        self._loading = True
        search = self.search.text().strip()
        if search:
            data = db.execute(
                "SELECT * FROM Properties WHERE name LIKE %s OR address LIKE %s OR type LIKE %s",
                (f"%{search}%", f"%{search}%", f"%{search}%"), fetch=True
            )
        else:
            data = db.execute("SELECT * FROM Properties", fetch=True)

        self.t.setRowCount(0)
        self.t.setRowCount(len(data))
        for i, r in enumerate(data):
            self.t.setItem(i, 0, QTableWidgetItem(str(r["property_id"])))
            self.t.item(i, 0).setFlags(self.t.item(i, 0).flags() & ~Qt.ItemFlag.ItemIsEditable)  # ID read-only
            self.t.setItem(i, 1, QTableWidgetItem(r["name"]))
            self.t.setItem(i, 2, QTableWidgetItem(r["type"]))
            self.t.setItem(i, 3, QTableWidgetItem(f"{r['area']}"))
            self.t.setItem(i, 4, QTableWidgetItem(f"{r['price']}"))
            self.t.setItem(i, 5, QTableWidgetItem(r["address"]))
            self.t.setItem(i, 6, QTableWidgetItem(r["status"]))
        self._loading = False

    def on_item_changed(self, item):
        """Handle cell edits safely without recursion"""
        if self._loading or item.column() == 0:  # Skip during load or ID column
            return

        property_id = int(self.t.item(item.row(), 0).text())
        cols = ["name", "type", "area", "price", "address", "status"]
        col_name = cols[item.column() - 1] if item.column() > 0 else None

        if col_name:
            val = item.text()
            if col_name in ["price", "area"]:
                val = val.replace("₽", "").replace("м²", "").replace(",", ".").strip()
            # Use parameterized query - col_name is from safe list
            db.execute(f"UPDATE Properties SET {col_name}=%s WHERE property_id=%s", (val, property_id))

    def add_property(self):
        db.execute("""
            INSERT INTO Properties(name, description, price, type, area, address, status) 
            VALUES('Новый объект', '-', 0, 'квартира', 0, '', 'продажа')
        """)
        self.load()

    def delete_property(self):
        r = self.t.currentRow()
        if r < 0:
            return
        property_id = int(self.t.item(r, 0).text())
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Удалить этот объект? Все связанные заявки будут затронуты!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            db.execute("DELETE FROM Properties WHERE property_id=%s", (property_id,))
            self.load()


# ---------------- ADMIN ----------------
class AdminView(QTabWidget):
    def __init__(self, main):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))
        self.addTab(PropertyManagerView(), "🏠 Объекты")
        self.addTab(RequestsAdminView(), "📋 Заявки")
        self.addTab(StatsView(), "📊 Аналитика")
        self.addTab(UserAdminView(), "👥 Пользователи")
        self.addTab(DealsAdminView(), "💼 Сделки")


# ---------------- STATS (FIXED INDENTATION) ----------------
class StatsView(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))

        l = QVBoxLayout()
        l.setContentsMargins(15, 15, 15, 15)
        l.setSpacing(15)

        # Общая выручка
        total_res = db.execute("SELECT COALESCE(SUM(amount), 0) s FROM Deals", fetch=True)[0]["s"]
        gb_total = QGroupBox("💰 Общая выручка по сделкам")
        gb_total.setStyleSheet("font-weight: bold;")
        vl_total = QVBoxLayout()
        lbl_total = QLabel(f"{total_res:,.2f} ₽")
        lbl_total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_total.setStyleSheet("font-size: 28px; color: #27ae60; margin: 10px;")
        vl_total.addWidget(lbl_total)
        gb_total.setLayout(vl_total)

        # Статусы заявок (FIXED INDENTATION)
        status_res = db.execute("SELECT status, COUNT(*) c FROM Requests GROUP BY status", fetch=True)
        gb_status = QGroupBox("📈 Статусы заявок")
        grid_status = QGridLayout()
        for idx, s in enumerate(status_res):
            lbl = QLabel(f"• {s['status']}")
            val = QLabel(f"{s['c']}")  # FIXED: proper indentation
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid_status.addWidget(lbl, idx, 0)
            grid_status.addWidget(val, idx, 1)
        gb_status.setLayout(grid_status)

        # Популярные объекты (FIXED INDENTATION)
        popular_res = db.execute("""
            SELECT p.name, COUNT(rp.req_prop_id) c
            FROM RequestProperties rp 
            JOIN Properties p ON rp.property_id = p.property_id
            GROUP BY p.name ORDER BY c DESC LIMIT 5
        """, fetch=True)
        gb_pop = QGroupBox("🏆 Топ-5 востребованных объектов")
        vl_pop = QVBoxLayout()
        for p in popular_res:
            row = QHBoxLayout()
            name_lbl = QLabel(p['name'])  # FIXED: proper indentation
            count_lbl = QLabel(f"{p['c']} запросов")
            count_lbl.setStyleSheet("font-weight: bold;")
            row.addWidget(name_lbl)
            row.addStretch()
            row.addWidget(count_lbl)
            vl_pop.addLayout(row)  # FIXED: proper indentation
        gb_pop.setLayout(vl_pop)

        # Статистика по типам (FIXED INDENTATION)
        type_res = db.execute("SELECT type, COUNT(*) c, AVG(price) avg_price FROM Properties GROUP BY type", fetch=True)
        gb_types = QGroupBox("📊 Статистика по типам объектов")
        grid_types = QGridLayout()
        grid_types.addWidget(QLabel("Тип"), 0, 0)
        grid_types.addWidget(QLabel("Кол-во"), 0, 1)
        grid_types.addWidget(QLabel("Сред. цена"), 0, 2)
        for idx, t in enumerate(type_res, 1):
            grid_types.addWidget(QLabel(t['type']), idx, 0)
            grid_types.addWidget(QLabel(str(t['c'])), idx, 1)  # FIXED: proper indentation
            grid_types.addWidget(QLabel(f"{t['avg_price']:,.0f} ₽"), idx, 2)  # FIXED: proper indentation
        gb_types.setLayout(grid_types)

        l.addWidget(gb_total)
        l.addWidget(gb_status)
        l.addWidget(gb_pop)
        l.addWidget(gb_types)
        self.setLayout(l)


# ---------------- PROPERTY MANAGER (ADMIN) ----------------
class PropertyManagerView(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))
        l = QVBoxLayout()

        search_layout = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Поиск...")
        self.type_filter = QComboBox()
        self.type_filter.addItems(["Все", "квартира", "студия", "дом", "таунхаус", "коммерция"])
        search_layout.addWidget(self.search)
        search_layout.addWidget(self.type_filter)
        l.addLayout(search_layout)

        self.t = QTableWidget()
        self.t.setColumnCount(7)
        self.t.setHorizontalHeaderLabels(["ID", "Название", "Тип", "Площадь", "Цена", "Адрес", "Статус"])
        l.addWidget(self.t)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ Добавить")
        btn_del = QPushButton("🗑️ Удалить")
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_del)
        btn_layout.addStretch()
        l.addLayout(btn_layout)

        self.setLayout(l)
        self.search.textChanged.connect(self.load)
        self.type_filter.currentTextChanged.connect(self.load)
        btn_add.clicked.connect(self.add)
        btn_del.clicked.connect(self.delete)
        self.t.itemChanged.connect(self.update)
        self.load()

    def load(self):
        query = "SELECT * FROM Properties WHERE 1=1"
        params = []
        if self.search.text().strip():
            query += " AND (name LIKE %s OR address LIKE %s)"
            params.extend([f"%{self.search.text()}%", f"%{self.search.text()}%"])
        if self.type_filter.currentText() != "Все":
            query += " AND type = %s"
            params.append(self.type_filter.currentText())

        data = db.execute(query, params, fetch=True)
        self.t.setRowCount(len(data))
        for i, r in enumerate(data):
            self.t.setItem(i, 0, QTableWidgetItem(str(r["property_id"])))
            self.t.setItem(i, 1, QTableWidgetItem(r["name"]))
            self.t.setItem(i, 2, QTableWidgetItem(r["type"]))
            self.t.setItem(i, 3, QTableWidgetItem(f"{r['area']}"))
            self.t.setItem(i, 4, QTableWidgetItem(f"{r['price']}"))
            self.t.setItem(i, 5, QTableWidgetItem(r["address"]))
            self.t.setItem(i, 6, QTableWidgetItem(r["status"]))

    def update(self, item):
        if item.column() == 0:
            return
        prop_id = int(self.t.item(item.row(), 0).text())
        cols = ["name", "type", "area", "price", "address", "status"]
        col = cols[item.column() - 1]
        val = item.text().replace("₽", "").replace("м²", "").strip()
        db.execute(f"UPDATE Properties SET {col}=%s WHERE property_id=%s", (val, prop_id))

    def add(self):
        db.execute("""
            INSERT INTO Properties(name, description, price, type, area, address, status) 
            VALUES('Новый объект', '-', 0, 'квартира', 0, '', 'продажа')
        """)
        self.load()

    def delete(self):
        r = self.t.currentRow()
        if r < 0:
            return
        prop_id = int(self.t.item(r, 0).text())
        if QMessageBox.question(self, "Подтверждение", "Удалить объект?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            db.execute("DELETE FROM Properties WHERE property_id=%s", (prop_id,))
            self.load()


# ---------------- REQUESTS ADMIN (NO FILTERS - SHOW ALL) ----------------
class RequestsAdminView(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))
        l = QVBoxLayout()

        # NO FILTERS - just a title
        title = QLabel("📋 Все заявки")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px 0;")
        l.addWidget(title)

        # Таблица
        self.t = QTableWidget()
        self.t.setColumnCount(6)
        self.t.setHorizontalHeaderLabels(["ID", "Клиент", "Агент", "Дата", "Статус", "Комиссия"])
        l.addWidget(self.t)
        self.setLayout(l)

        self.load()

    def load(self):
        # NO FILTERS - show ALL requests
        query = """
            SELECT r.request_id, u.username as client, a.username as agent, 
                   r.request_date, r.status, r.total_commission
            FROM Requests r
            JOIN Clients c ON r.client_id = c.client_id
            JOIN Users u ON c.user_id = u.user_id
            LEFT JOIN Users a ON r.agent_id = a.user_id
            ORDER BY r.request_date DESC
        """
        data = db.execute(query, fetch=True)
        self.t.setRowCount(len(data))
        for i, r in enumerate(data):
            self.t.setItem(i, 0, QTableWidgetItem(str(r["request_id"])))
            self.t.setItem(i, 1, QTableWidgetItem(r["client"] or "Гость"))
            self.t.setItem(i, 2, QTableWidgetItem(r["agent"] or "Не назначен"))
            self.t.setItem(i, 3, QTableWidgetItem(str(r["request_date"])))

            combo = QComboBox()
            combo.addItems(["Ожидает обработки", "Запланирован просмотр", "Ожидает просмотра", "Закрыта"])
            combo.setCurrentText(r["status"])
            combo.currentTextChanged.connect(lambda s, row=i: self.update_status(row, s))
            self.t.setCellWidget(i, 4, combo)

            self.t.setItem(i, 5, QTableWidgetItem(f"{r['total_commission']:,.2f} ₽"))

    def update_status(self, row, status):
        request_id = int(self.t.item(row, 0).text())
        db.execute("UPDATE Requests SET status=%s WHERE request_id=%s", (status, request_id))


# ---------------- DEALS ADMIN ----------------
class DealsAdminView(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))
        l = QVBoxLayout()
        self.t = QTableWidget()
        self.t.setColumnCount(5)
        self.t.setHorizontalHeaderLabels(["ID", "Дата", "Сумма", "Тип", "Заявка"])
        l.addWidget(self.t)
        self.setLayout(l)
        self.load()

    def load(self):
        data = db.execute("""
            SELECT d.deal_id, d.deal_date, d.amount, d.deal_type, r.request_id
            FROM Deals d
            JOIN Requests r ON d.request_id = r.request_id
            ORDER BY d.deal_date DESC
        """, fetch=True)
        self.t.setRowCount(len(data))
        for i, r in enumerate(data):
            self.t.setItem(i, 0, QTableWidgetItem(str(r["deal_id"])))
            self.t.setItem(i, 1, QTableWidgetItem(str(r["deal_date"])))
            self.t.setItem(i, 2, QTableWidgetItem(f"{r['amount']:,.2f} ₽"))
            self.t.setItem(i, 3, QTableWidgetItem(r["deal_type"]))
            self.t.setItem(i, 4, QTableWidgetItem(str(r["request_id"])))


# ---------------- USER ADMIN ----------------
class UserAdminView(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))
        l = QVBoxLayout()

        search_layout = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Поиск по имени или контактам...")
        search_layout.addWidget(self.search)
        l.addLayout(search_layout)

        self.t = QTableWidget()
        self.t.setColumnCount(5)
        self.t.setHorizontalHeaderLabels(["ID", "Логин", "Пароль", "Роль", "Контакты"])
        l.addWidget(self.t)

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
                (f"%{search}%", f"%{search}%"), fetch=True
            )
        else:
            data = db.execute("SELECT * FROM Users", fetch=True)

        self.t.setRowCount(len(data))
        roles = {1: "Гость", 2: "Клиент", 3: "Агент", 4: "Менеджер", 5: "Администратор"}

        for i, r in enumerate(data):
            self.t.setItem(i, 0, QTableWidgetItem(str(r["user_id"])))
            self.t.setItem(i, 1, QTableWidgetItem(r["username"]))
            self.t.setItem(i, 2, QTableWidgetItem("••••••••"))

            role_combo = QComboBox()
            role_combo.addItems(["Гость", "Клиент", "Агент", "Менеджер", "Администратор"])
            role_combo.setCurrentIndex(r["role_id"] - 1)
            role_combo.currentTextChanged.connect(
                lambda val, row=i, uid=r["user_id"]: self.update_role(row, uid, val)
            )
            self.t.setCellWidget(i, 3, role_combo)
            self.t.setItem(i, 4, QTableWidgetItem(r.get("contact_info") or ""))

    def update_role(self, row, user_id, role_name):
        role_map = {"Гость": 1, "Клиент": 2, "Агент": 3, "Менеджер": 4, "Администратор": 5}
        db.execute("UPDATE Users SET role_id=%s WHERE user_id=%s",
                   (role_map.get(role_name, 1), user_id))

    def update(self, item):
        if item.column() in [0, 2, 3]:
            return
        user_id = int(self.t.item(item.row(), 0).text())
        cols = [None, "username", None, None, "contact_info"]
        col = cols[item.column()]
        if col:
            db.execute(f"UPDATE Users SET {col}=%s WHERE user_id=%s", (item.text(), user_id))

    def add(self):
        db.execute("""
            INSERT INTO Users(username, password_hash, role_id, contact_info) 
            VALUES('new_user', '123', 2, 'email@example.com')
        """)
        self.load()

    def delete(self):
        r = self.t.currentRow()
        if r < 0:
            return
        user_id = int(self.t.item(r, 0).text())
        if QMessageBox.question(self, "Подтверждение", "Удалить пользователя?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            db.execute("DELETE FROM Users WHERE user_id=%s", (user_id,))
            self.load()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(ICON_PATH))

    w = AuthWindow()
    w.show()
    sys.exit(app.exec())