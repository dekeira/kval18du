import sys
import os
import mysql.connector
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt


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

    def execute(self, query, params=None, fetch=False):
        self.cursor.execute(query, params or ())
        return self.cursor.fetchall() if fetch else self.conn.commit()


db = Database()
ICON = "images/icon.jpg"


# ---------------- AUTH ----------------
class AuthWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Вход")
        self.setWindowIcon(QIcon(ICON))
        self.resize(350, 250)

        layout = QVBoxLayout()
        layout.addStretch()

        title = QLabel("🏠 Агентство недвижимости")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.login_input = QLineEdit(placeholderText="Логин")
        self.pass_input = QLineEdit(placeholderText="Пароль", echoMode=QLineEdit.EchoMode.Password)

        btn_login = QPushButton("Войти")
        btn_guest = QPushButton("Гость")

        for widget in [self.login_input, self.pass_input, btn_login, btn_guest]:
            layout.addWidget(widget)

        layout.addStretch()
        self.setLayout(layout)

        btn_login.clicked.connect(self.auth)
        btn_guest.clicked.connect(self.login_as_guest)

    def login_as_guest(self):
        guest_data = {
            "role_id": 1,
            "user_id": None,
            "username": "Гость",
            "role_name": "Гость"
        }
        self.open_main(guest_data)

    def auth(self):
        result = db.execute(
            """SELECT u.user_id, u.username, u.role_id, r.role_name, u.contact_info 
               FROM Users u 
               JOIN Roles r ON u.role_id = r.role_id 
               WHERE u.username = %s AND u.password_hash = %s""",
            (self.login_input.text(), self.pass_input.text()),
            fetch=True
        )
        if result:
            self.open_main(result[0])
        else:
            QMessageBox.critical(self, "Ошибка", "Неверные данные")

    def open_main(self, user):
        self.main_window = MainWindow(user)
        self.main_window.show()
        self.hide()

# ---------------- MAIN WINDOW ----------------
class MainWindow(QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.setWindowTitle(f"🏠 Агентство — {user.get('role_name', '')}")
        self.setWindowIcon(QIcon(ICON))
        self.resize(1100, 700)

        role = user["role_id"]
        views = {
            1: GuestView,
            2: ClientView,
            3: AgentView,
            4: ManagerView,
            5: AdminView
        }

        if role <= 2:
            self.setCentralWidget(views[role](user, self))
        else:
            self.setCentralWidget(views[role](self))

    def logout(self):
        self.auth_window = AuthWindow()
        self.auth_window.show()
        self.close()

# ---------------- GUEST ----------------
class GuestView(QWidget):
    def __init__(self, user, main):
        super().__init__()
        self.main = main

        layout = QVBoxLayout()

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("👋 Гость"))
        header.addStretch()
        btn_logout = QPushButton("Выйти")
        header.addWidget(btn_logout)
        layout.addLayout(header)

        # Properties list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.properties_layout = QVBoxLayout()

        properties = db.execute("SELECT * FROM Properties", fetch=True)
        for prop in properties:
            frame = self.create_property_card(prop)
            self.properties_layout.addWidget(frame)

        container.setLayout(self.properties_layout)
        scroll.setWidget(container)
        layout.addWidget(scroll)
        self.setLayout(layout)

        btn_logout.clicked.connect(self.main.logout)

    def create_property_card(self, prop):
        frame = QFrame(frameShape=QFrame.Shape.Box)
        frame.setStyleSheet("padding: 8px; margin: 4px;")
        layout = QHBoxLayout()

        # Image
        img_label = QLabel()
        photos = db.execute(
            "SELECT image_path FROM PropertyPhotos WHERE property_id = %s LIMIT 1",
            (prop["property_id"],),
            fetch=True
        )
        path = photos[0]["image_path"] if photos and os.path.exists(
            photos[0]["image_path"]) else "images/placeholder.png"
        img_label.setPixmap(QPixmap(path).scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio))

        # Info
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel(f"<b>{prop['name']}</b>"))
        info_layout.addWidget(QLabel(f"📍 {prop['address']}"))
        info_layout.addWidget(QLabel(f"📐 {prop['area']} м²"))
        info_layout.addWidget(QLabel(f"💰 {prop['price']:,.0f} ₽"))

        layout.addWidget(img_label)
        layout.addLayout(info_layout)
        layout.addStretch()
        frame.setLayout(layout)
        return frame


# ---------------- CLIENT ----------------
class ClientView(QWidget):
    def __init__(self, user, main):
        super().__init__()
        self.user = user
        self.main = main
        self.client_id = self._get_client_id()
        self.selected_properties = {}  # {checkbox: property_id}

        layout = QVBoxLayout()

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel(f"👋 {user['username']}"))
        header.addStretch()

        btn_requests = QPushButton("📋 Заявки")
        btn_requests.clicked.connect(self.show_requests)

        btn_logout = QPushButton("🚪 Выйти")
        btn_logout.clicked.connect(self.main.logout)

        header.addWidget(btn_requests)
        header.addWidget(btn_logout)
        layout.addLayout(header)

        # Filters
        filter_group = QGroupBox("🔍 Фильтры")
        filter_layout = QGridLayout()

        self.search_input = QLineEdit(placeholderText="Поиск...")
        self.type_filter = QComboBox()
        self.type_filter.addItems(["Все", "квартира", "дом", "студия", "коммерция"])
        self.status_filter = QComboBox()
        self.status_filter.addItems(["Все", "продажа", "аренда"])

        filter_layout.addWidget(QLabel("Поиск:"), 0, 0)
        filter_layout.addWidget(self.search_input, 0, 1)
        filter_layout.addWidget(QLabel("Тип:"), 1, 0)
        filter_layout.addWidget(self.type_filter, 1, 1)
        filter_layout.addWidget(QLabel("Статус:"), 2, 0)
        filter_layout.addWidget(self.status_filter, 2, 1)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # Connect filters
        self.search_input.textChanged.connect(self.load_properties)
        self.type_filter.currentTextChanged.connect(self.load_properties)
        self.status_filter.currentTextChanged.connect(self.load_properties)

        # Properties list
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.properties_layout = QVBoxLayout()
        self.container.setLayout(self.properties_layout)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

        # Request button
        btn_request = QPushButton("📝 Заявка на выбранное")
        btn_request.clicked.connect(self.make_request)
        layout.addWidget(btn_request)

        self.setLayout(layout)
        self.load_properties()

    def _get_client_id(self):
        result = db.execute(
            "SELECT client_id FROM Clients WHERE user_id = %s",
            (self.user["user_id"],),
            fetch=True
        )
        return result[0]["client_id"] if result else None

    def load_properties(self):
        # Clear old items
        for i in reversed(range(self.properties_layout.count())):
            widget = self.properties_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        self.selected_properties.clear()

        # Build query
        query = "SELECT * FROM Properties WHERE 1=1"
        params = []

        if self.search_input.text().strip():
            query += " AND (name LIKE %s OR address LIKE %s)"
            params += [f"%{self.search_input.text()}%"] * 2

        if self.type_filter.currentText() != "Все":
            query += " AND type = %s"
            params.append(self.type_filter.currentText())

        if self.status_filter.currentText() != "Все":
            query += " AND status = %s"
            params.append(self.status_filter.currentText())

        properties = db.execute(query, params, fetch=True)

        for prop in properties:
            frame = QFrame(frameShape=QFrame.Shape.Box)
            frame.setStyleSheet("padding: 8px; margin: 4px;")
            layout = QHBoxLayout()

            # Image
            img_label = QLabel()
            photos = db.execute(
                "SELECT image_path FROM PropertyPhotos WHERE property_id = %s LIMIT 1",
                (prop["property_id"],),
                fetch=True
            )
            path = photos[0]["image_path"] if photos and os.path.exists(
                photos[0]["image_path"]) else "images/placeholder.png"
            img_label.setPixmap(QPixmap(path).scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio))

            # Info
            info_layout = QVBoxLayout()
            info_layout.addWidget(QLabel(f"<b>{prop['name']}</b>"))
            info_layout.addWidget(QLabel(f"📍 {prop['address']}"))
            info_layout.addWidget(QLabel(f"💰 {prop['price']:,.0f} ₽"))

            # Checkbox with property_id binding
            checkbox = QCheckBox()
            checkbox.setProperty("property_id", prop["property_id"])
            self.selected_properties[checkbox] = prop["property_id"]

            layout.addWidget(img_label)
            layout.addLayout(info_layout)
            layout.addWidget(checkbox)
            layout.addStretch()
            frame.setLayout(layout)
            self.properties_layout.addWidget(frame)

    def make_request(self):
        if not self.client_id:
            QMessageBox.warning(self, "Ошибка", "Сначала заполните профиль клиента")
            return

        selected = [cb for cb in self.selected_properties if cb.isChecked()]
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите хотя бы один объект")
            return

        try:
            # Create request
            db.execute(
                """INSERT INTO Requests(client_id, request_date, total_commission, status) 
                   VALUES(%s, CURDATE(), %s, 'Ожидает обработки')""",
                (self.client_id, 0)
            )
            request_id = db.cursor.lastrowid

            # Add selected properties
            for checkbox in selected:
                prop_id = self.selected_properties[checkbox]
                db.execute(
                    "INSERT INTO RequestProperties(request_id, property_id) VALUES(%s, %s)",
                    (request_id, prop_id)
                )

            db.conn.commit()
            QMessageBox.information(self, "Успех", "Заявка создана!")

        except Exception as e:
            db.conn.rollback()
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать заявку: {e}")

    def show_requests(self):
        # FIX: Keep reference to window
        self.requests_window = RequestsWindow(self.client_id)
        self.requests_window.show()


class RequestsWindow(QWidget):
    def __init__(self, client_id):
        super().__init__()
        self.setWindowTitle("📋 Мои заявки")
        self.resize(600, 400)
        self.setWindowIcon(QIcon(ICON))

        layout = QVBoxLayout()
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["ID", "Дата", "Статус"])

        data = db.execute(
            "SELECT request_id, request_date, status FROM Requests WHERE client_id = %s",
            (client_id,),
            fetch=True
        )
        table.setRowCount(len(data))

        for i, row in enumerate(data):
            table.setItem(i, 0, QTableWidgetItem(str(row["request_id"])))
            table.setItem(i, 1, QTableWidgetItem(str(row["request_date"])))
            table.setItem(i, 2, QTableWidgetItem(row["status"]))

        layout.addWidget(table)
        self.setLayout(layout)


# ---------------- AGENT ----------------
class AgentView(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main

        layout = QVBoxLayout()

        # Header
        header = QHBoxLayout()
        self.status_filter = QComboBox()
        self.status_filter.addItems(["Все", "Ожидает обработки", "Запланирован просмотр", "Закрыта"])
        self.status_filter.currentTextChanged.connect(self.load_requests)

        btn_refresh = QPushButton("🔄 Обновить")
        btn_refresh.clicked.connect(self.load_requests)
        btn_logout = QPushButton("🚪 Выйти")
        btn_logout.clicked.connect(self.main.logout)

        header.addWidget(self.status_filter)
        header.addWidget(btn_refresh)
        header.addStretch()
        header.addWidget(btn_logout)
        layout.addLayout(header)

        # Table
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Клиент", "Дата", "Статус", "Телефон"])
        layout.addWidget(self.table)

        self.setLayout(layout)
        self.load_requests()

    def load_requests(self):
        query = """
            SELECT r.request_id, u.username, r.request_date, r.status, c.phone 
            FROM Requests r
            JOIN Clients c ON r.client_id = c.client_id
            JOIN Users u ON c.user_id = u.user_id
            WHERE 1=1
        """
        params = []

        if self.status_filter.currentText() != "Все":
            query += " AND r.status = %s"
            params.append(self.status_filter.currentText())

        data = db.execute(query, params, fetch=True)
        self.table.setRowCount(len(data))

        for i, row in enumerate(data):
            self.table.setItem(i, 0, QTableWidgetItem(str(row["request_id"])))
            self.table.setItem(i, 1, QTableWidgetItem(row["username"] or "?"))
            self.table.setItem(i, 2, QTableWidgetItem(str(row["request_date"])))

            # Status combo
            status_combo = QComboBox()
            status_combo.addItems(["Ожидает обработки", "Запланирован просмотр", "Закрыта"])
            status_combo.setCurrentText(row["status"])
            status_combo.currentTextChanged.connect(
                lambda status, r=i: self.update_status(r, status)
            )
            self.table.setCellWidget(i, 3, status_combo)

            self.table.setItem(i, 4, QTableWidgetItem(row["phone"] or "-"))

    def update_status(self, row, status):
        request_id = int(self.table.item(row, 0).text())
        db.execute("UPDATE Requests SET status = %s WHERE request_id = %s", (status, request_id))


# ---------------- MANAGER ----------------
class ManagerView(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main

        layout = QVBoxLayout()

        # Header
        header = QHBoxLayout()
        search = QLineEdit(placeholderText="🔍 Поиск...")
        search.textChanged.connect(self.load_properties)

        btn_add = QPushButton("➕ Добавить")
        btn_add.clicked.connect(self.add_property)
        btn_delete = QPushButton("🗑️ Удалить")
        btn_delete.clicked.connect(self.delete_property)
        btn_logout = QPushButton("🚪 Выйти")
        btn_logout.clicked.connect(self.main.logout)

        header.addWidget(search)
        header.addWidget(btn_add)
        header.addWidget(btn_delete)
        header.addStretch()
        header.addWidget(btn_logout)
        layout.addLayout(header)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Название", "Тип", "Площадь", "Цена", "Статус"])
        self.table.itemChanged.connect(self.update_property)
        layout.addWidget(self.table)

        self.setLayout(layout)
        self.load_properties()

    def load_properties(self):
        data = db.execute("SELECT * FROM Properties", fetch=True)
        self.table.setRowCount(len(data))

        columns = ["property_id", "name", "type", "area", "price", "status"]
        for i, row in enumerate(data):
            for j, col in enumerate(columns):
                item = QTableWidgetItem(str(row[col]))
                if j == 0:  # ID read-only
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i, j, item)

    def update_property(self, item):
        if item.column() == 0:
            return
        prop_id = int(self.table.item(item.row(), 0).text())
        columns = ["name", "type", "area", "price", "status"]
        col_name = columns[item.column() - 1]
        db.execute(f"UPDATE Properties SET {col_name} = %s WHERE property_id = %s", (item.text(), prop_id))

    def add_property(self):
        db.execute("""
            INSERT INTO Properties(name, type, area, price, address, status) 
            VALUES('Новый объект', 'квартира', 50, 5000000, '', 'продажа')
        """)
        self.load_properties()

    def delete_property(self):
        row = self.table.currentRow()
        if row < 0:
            return
        prop_id = int(self.table.item(row, 0).text())
        if QMessageBox.question(self, "Подтверждение", "Удалить объект?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            db.execute("DELETE FROM Properties WHERE property_id = %s", (prop_id,))
            self.load_properties()


# ---------------- ADMIN ----------------
class AdminView(QTabWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.addTab(AdminUsers(self.main), "👥 Роли")
        self.addTab(AdminStats(), "📊 Статистика")
        self.addTab(AdminProps(self.main), "🏠 Объекты")


class AdminUsers(QWidget):
    def __init__(self, main_window):
        super().__init__()
        layout = QVBoxLayout()

        btn_logout = QPushButton("🚪 Выйти")
        btn_logout.clicked.connect(main_window.logout)  # FIX: прямой вызов выхода
        layout.addWidget(btn_logout)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Логин", "Роль", "Контакты"])
        layout.addWidget(self.table)

        self.setLayout(layout)
        self.load_users()

    def load_users(self):
        data = db.execute("SELECT * FROM Users", fetch=True)
        self.table.setRowCount(len(data))

        roles = ["Гость", "Клиент", "Агент", "Менеджер", "Администратор"]
        for i, row in enumerate(data):
            self.table.setItem(i, 0, QTableWidgetItem(str(row["user_id"])))
            self.table.setItem(i, 1, QTableWidgetItem(row["username"]))

            role_combo = QComboBox()
            role_combo.addItems(roles)
            role_combo.setCurrentIndex(row["role_id"] - 1)
            role_combo.currentTextChanged.connect(
                lambda val, uid=row["user_id"]: self.update_role(uid, val)
            )
            self.table.setCellWidget(i, 2, role_combo)
            self.table.setItem(i, 3, QTableWidgetItem(row.get("contact_info") or ""))

    def update_role(self, user_id, role_name):
        role_map = {"Гость": 1, "Клиент": 2, "Агент": 3, "Менеджер": 4, "Администратор": 5}
        db.execute("UPDATE Users SET role_id = %s WHERE user_id = %s", (role_map[role_name], user_id))

class AdminStats(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        # FIX: используем алиас 'total' и безопасное извлечение из словаря
        try:
            rev_data = db.execute("SELECT COALESCE(SUM(amount), 0) as total FROM Deals", fetch=True)
            revenue = rev_data[0]["total"] if rev_data else 0
        except Exception:
            revenue = 0  # На случай если таблица пуста или не существует

        rev_group = QGroupBox("💰 Выручка")
        rev_layout = QVBoxLayout()
        rev_layout.addWidget(QLabel(f"{revenue:,.0f} ₽"), alignment=Qt.AlignmentFlag.AlignCenter)
        rev_group.setLayout(rev_layout)
        layout.addWidget(rev_group)

        # FIX: аналогично для заявок
        try:
            req_data = db.execute("SELECT COUNT(*) as total FROM Requests", fetch=True)
            count = req_data[0]["total"] if req_data else 0
        except Exception:
            count = 0

        req_group = QGroupBox("📋 Заявок")
        req_layout = QVBoxLayout()
        req_layout.addWidget(QLabel(f"{count} шт."), alignment=Qt.AlignmentFlag.AlignCenter)
        req_group.setLayout(req_layout)
        layout.addWidget(req_group)

        self.setLayout(layout)


class AdminProps(QWidget):
    def __init__(self, main_window):
        super().__init__()
        layout = QVBoxLayout()

        btn_logout = QPushButton("🚪 Выйти")
        btn_logout.clicked.connect(main_window.logout)
        layout.addWidget(btn_logout)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Название", "Тип", "Цена", "Статус"])
        self.table.itemChanged.connect(self.update_property)
        layout.addWidget(self.table)

        self.setLayout(layout)
        self.load_properties()

    def load_properties(self):
        data = db.execute("SELECT property_id, name, type, price, status FROM Properties", fetch=True)
        self.table.setRowCount(len(data))

        columns = ["property_id", "name", "type", "price", "status"]
        for i, row in enumerate(data):
            for j, col in enumerate(columns):
                item = QTableWidgetItem(str(row[col]))
                if j == 0:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i, j, item)

    def update_property(self, item):
        if item.column() == 0:
            return
        prop_id = int(self.table.item(item.row(), 0).text())
        columns = ["name", "type", "price", "status"]
        col_name = columns[item.column() - 1]
        db.execute(f"UPDATE Properties SET {col_name} = %s WHERE property_id = %s", (item.text(), prop_id))


# ---------------- MAIN ----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AuthWindow()
    window.show()
    sys.exit(app.exec())