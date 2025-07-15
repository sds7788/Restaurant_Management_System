# backend/database.py
import mysql.connector
from mysql.connector import Error
import bcrypt  # 用于密码哈希
from backend.db_config import DB_CONFIG  # 引入数据库配置


# --- 数据库连接辅助函数 ---
def create_connection():
    """创建并返回一个数据库连接对象"""
    connection = None
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        # print("成功连接到MySQL数据库") # 开发时可以取消注释
    except Error as e:
        print(f"连接MySQL时发生错误: '{e}'")
    return connection

# 请用这段代码替换 database.py 中已有的同名函数

def update_order_payment_status(order_id, new_status):
    """
    更新指定订单的支付状态和支付时间。
    (已修正：使用项目中已有的 execute_query 函数，更简洁、更安全)
    
    Args:
        order_id (int): 要更新的订单ID。
        new_status (str): 新的支付状态 (例如 'paid')。
        
    Returns:
        bool: 如果操作成功执行返回 True，否则返回 False。
    """
    # SQL UPDATE语句，同时更新支付状态和支付时间
    sql = "UPDATE orders SET payment_status = %s WHERE id = %s"
    
    try:
        # 直接调用项目中已有的通用函数 execute_query 来执行更新
        # 这会自动处理数据库连接、游标、提交/回滚和关闭，非常方便
        affected_rows = execute_query(
            query=sql, 
            params=(new_status, order_id), 
            is_modify=True, 
            dictionary_cursor=False  # 更新操作不需要返回字典
        )
        
        # execute_query 在执行修改操作(is_modify=True)时，
        # 成功则返回受影响的行数(>=0)，出错则返回 None。
        if affected_rows is not None:
            print(f"数据库日志：订单 {order_id} 支付状态更新操作完成，影响行数: {affected_rows}")
            return True
        else:
            # 如果 execute_query 内部出错，它会打印错误并返回 None
            print(f"数据库错误：更新订单 {order_id} 支付状态失败。")
            return False

    except Exception as e:
        # 捕获意外的程序错误
        print(f"在 update_order_payment_status 函数中发生意外错误: {e}")
        return False

def execute_query(query, params=None, fetch_one=False, fetch_all=False, is_modify=False, dictionary_cursor=True):
    """
    通用查询执行函数
    :param query: SQL查询语句
    :param params: 查询参数 (元组)
    :param fetch_one: 是否获取单条记录
    :param fetch_all: 是否获取所有记录
    :param is_modify: 是否为修改操作 (INSERT, UPDATE, DELETE)
    :param dictionary_cursor: 是否使用字典类型的游标 (True 表示结果为字典列表, False 表示结果为元组列表)
    :return: 根据操作类型返回结果
    """
    connection = create_connection()
    if not connection:
        return None if is_modify or fetch_one else []

    cursor = None
    if dictionary_cursor:
        cursor = connection.cursor(dictionary=True)
    else:
        cursor = connection.cursor()

    result = None
    try:
        cursor.execute(query, params or ())
        if is_modify:
            connection.commit()
            last_row_id = cursor.lastrowid
            row_count = cursor.rowcount
            # print(f"修改查询执行成功，影响行数: {row_count}, 最后插入ID: {last_row_id}")
            result = last_row_id if query.strip().upper().startswith("INSERT") else row_count
        elif fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
    except Error as e:
        print(f"执行查询 '{query[:100]}...' 时发生错误: '{e}'")
        if is_modify and connection.is_connected():
            connection.rollback()
    finally:
        if connection.is_connected():
            if cursor:
                cursor.close()
            connection.close()
    return result


# --- 用户管理函数 ---
def create_user(username, password, role='customer', full_name=None, email=None, phone=None):
    """创建新用户，密码会自动哈希处理"""
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    query = """
    INSERT INTO users (username, password_hash, role, full_name, email, phone)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    params = (username, hashed_password, role, full_name, email, phone)
    return execute_query(query, params, is_modify=True)


def get_user_by_username(username):
    """根据用户名获取用户信息"""
    query = "SELECT id, username, password_hash, role, full_name, email, phone, created_at, last_login FROM users WHERE username = %s"
    return execute_query(query, (username,), fetch_one=True, dictionary_cursor=True)


def get_user_by_id(user_id):
    """根据用户ID获取用户信息"""
    query = "SELECT id, username, password_hash, role, full_name, email, phone, created_at, last_login FROM users WHERE id = %s"
    return execute_query(query, (user_id,), fetch_one=True, dictionary_cursor=True)


def verify_password(plain_password, hashed_password):
    """验证明文密码是否与哈希密码匹配"""
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password)


def update_user_last_login(user_id):
    """更新用户最后登录时间"""
    query = "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s"
    return execute_query(query, (user_id,), is_modify=True)


# --- 菜品管理函数 ---
def get_all_menu_items(include_unavailable=False):
    """获取所有菜品信息，并包含分类名称。管理员可获取所有菜品。"""
    query_base = """
    SELECT mi.id, mi.name, mi.description, mi.price, mi.category_id, mi.image_url, mi.is_available, c.name as category_name
    FROM menu_items mi
    LEFT JOIN categories c ON mi.category_id = c.id
    """
    params = []

    if not include_unavailable:
        query_base += " WHERE mi.is_available = TRUE"

    query_base += " ORDER BY c.display_order, mi.name"

    return execute_query(query_base, tuple(params), fetch_all=True, dictionary_cursor=True)


def get_menu_item_by_id(item_id):
    """根据ID获取单个菜品信息，并包含分类名称"""
    query = """
    SELECT mi.id, mi.name, mi.description, mi.price, mi.category_id, mi.image_url, mi.is_available, c.name as category_name
    FROM menu_items mi
    LEFT JOIN categories c ON mi.category_id = c.id
    WHERE mi.id = %s
    """
    return execute_query(query, (item_id,), fetch_one=True, dictionary_cursor=True)


def add_menu_item(name, description, price, category_id, image_url=None, is_available=True):
    """添加新菜品"""
    query = """
    INSERT INTO menu_items (name, description, price, category_id, image_url, is_available)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    params = (name, description, price, category_id, image_url, is_available)
    return execute_query(query, params, is_modify=True)


def update_menu_item(item_id, name, description, price, category_id, image_url, is_available):
    """更新现有菜品信息"""
    query = """
    UPDATE menu_items
    SET name = %s,
        description = %s,
        price = %s,
        category_id = %s,
        image_url = %s,
        is_available = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s
    """
    params = (name, description, price, category_id, image_url, is_available, item_id)
    affected_rows = execute_query(query, params, is_modify=True, dictionary_cursor=False)
    return affected_rows


# ========== 代码修改部分 ==========
def delete_menu_item(item_id):
    """
    软删除菜品（通过将其is_available设置为False）。
    这是推荐的做法，以保留历史订单的完整性。
    真正的删除（硬删除）可能会导致外键约束错误，此实现避免了该问题。
    
    返回: 
        受影响的行数 (成功时通常为1), 如果出错则返回0。
    """
    # SQL UPDATE 语句将菜品标记为不可用，实现软删除
    query = "UPDATE menu_items SET is_available = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
    try:
        # 使用通用的 execute_query 函数执行更新
        affected_rows = execute_query(
            query=query, 
            params=(item_id,), 
            is_modify=True, 
            dictionary_cursor=False
        )
        
        # is_modify=True 时，成功返回受影响的行数(>=0)，出错返回 None
        if affected_rows is not None:
            print(f"数据库日志：菜品ID {item_id} 已被软删除（设置为不可用）。")
            return affected_rows
        else:
            print(f"数据库错误：软删除菜品ID {item_id} 失败。")
            return 0 # 表示操作失败或未找到行
            
    except Exception as e:
        print(f"软删除菜品ID {item_id} 时发生未知错误: {e}")
        return 0 # 表示操作失败
# ========== 代码修改结束 ==========


# --- 订单管理函数 ---
def create_order(total_amount, items_data, user_id=None, customer_name="匿名用户", payment_method=None,
                 delivery_address=None, notes=None):
    """创建新订单"""
    connection = create_connection()
    if not connection:
        return None

    cursor = connection.cursor()
    order_id = None
    try:
        order_query = """
        INSERT INTO orders (user_id, customer_name, total_amount, payment_method, delivery_address, notes, status, payment_status)
        VALUES (%s, %s, %s, %s, %s, %s, 'pending', 'unpaid') 
        """
        actual_customer_name = customer_name
        if user_id:
            user_info_dict = get_user_by_id(user_id)
            if user_info_dict:
                actual_customer_name = user_info_dict.get('full_name') or user_info_dict.get(
                    'username') or customer_name

        order_params = (user_id, actual_customer_name, total_amount, payment_method, delivery_address, notes)
        cursor.execute(order_query, order_params)
        order_id = cursor.lastrowid

        if not order_id:
            raise Exception("创建订单失败，未能获取订单ID")

        item_query = """
        INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, subtotal, special_requests)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        order_items_to_insert = []
        for item in items_data:
            order_items_to_insert.append((
                order_id,
                item['menu_item_id'],
                item['quantity'],
                item['unit_price'],
                item['subtotal'],
                item.get('special_requests', None)
            ))

        cursor.executemany(item_query, order_items_to_insert)

        connection.commit()
        # print(f"订单 {order_id} 创建成功，包含 {len(order_items_to_insert)} 个订单项。")
        return order_id
    except Error as e:
        print(f"创建订单时发生数据库错误: '{e}'")
        if connection.is_connected():
            connection.rollback()
        return None
    except Exception as ex:
        print(f"创建订单时发生一般错误: '{ex}'")
        if connection.is_connected():
            connection.rollback()
        return None
    finally:
        if connection.is_connected():
            if cursor:
                cursor.close()
            connection.close()


def get_order_details_by_id(order_id):
    """获取单个订单的详细信息，包括订单项和用户信息(如果存在)"""
    order_query = """
    SELECT o.*, u.username as user_username, u.full_name as user_full_name, u.email as user_email, u.phone as user_phone
    FROM orders o
    LEFT JOIN users u ON o.user_id = u.id
    WHERE o.id = %s
    """
    order_data = execute_query(order_query, (order_id,), fetch_one=True, dictionary_cursor=True)

    if not order_data:
        return None

    items_query = """
    SELECT oi.quantity, oi.unit_price, oi.subtotal, oi.special_requests, mi.name as item_name, mi.image_url as item_image_url
    FROM order_items oi
    JOIN menu_items mi ON oi.menu_item_id = mi.id
    WHERE oi.order_id = %s
    """
    order_items = execute_query(items_query, (order_id,), fetch_all=True, dictionary_cursor=True)

    order_data['items'] = order_items
    return order_data


def get_orders_by_user_id(user_id, page=1, per_page=10):
    """获取特定用户的所有订单（分页）"""
    offset = (page - 1) * per_page
    query = """
    SELECT o.id, o.order_time, o.total_amount, o.status, o.payment_status
    FROM orders o
    WHERE o.user_id = %s
    ORDER BY o.order_time DESC
    LIMIT %s OFFSET %s
    """
    orders = execute_query(query, (user_id, per_page, offset), fetch_all=True, dictionary_cursor=True)

    count_query = "SELECT COUNT(*) as total_orders FROM orders WHERE user_id = %s"
    total_orders_result = execute_query(count_query, (user_id,), fetch_one=True, dictionary_cursor=True)
    total_orders = total_orders_result['total_orders'] if total_orders_result else 0

    return {"orders": orders, "total_orders": total_orders, "page": page, "per_page": per_page}


def get_all_orders_admin(page=1, per_page=10, status_filter=None, user_id_filter=None, sort_by='order_time',
                         sort_order='DESC'):
    """管理员获取所有订单（分页，可筛选，可排序）"""
    offset = (page - 1) * per_page
    base_query = """
    SELECT o.id, o.order_time, o.total_amount, o.status, o.payment_status, o.customer_name, 
           u.username as user_username, u.id as user_id_from_user_table
    FROM orders o
    LEFT JOIN users u ON o.user_id = u.id
    """
    count_base_query = "SELECT COUNT(*) as total_orders FROM orders o LEFT JOIN users u ON o.user_id = u.id"

    conditions = []
    params_for_main_query = []
    params_for_count_query = []

    if status_filter:
        conditions.append("o.status = %s")
        params_for_main_query.append(status_filter)
        params_for_count_query.append(status_filter)
    if user_id_filter:
        try:
            user_id_val = int(user_id_filter)
            conditions.append("o.user_id = %s")
            params_for_main_query.append(user_id_val)
            params_for_count_query.append(user_id_val)
        except ValueError:
            print(f"警告: 无效的用户ID筛选值 '{user_id_filter}', 已忽略。")
            pass

    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)
        base_query += where_clause
        count_base_query += where_clause

    allowed_sort_by = ['order_time', 'total_amount', 'status', 'id']
    db_sort_by = 'o.order_time'
    if sort_by in allowed_sort_by:
        db_sort_by = f"o.{sort_by}"
    elif sort_by == 'user_username':
        db_sort_by = "u.username"
    else:
        print(f"警告: 不允许的排序字段 '{sort_by}', 使用默认排序 'o.order_time'.")

    if sort_order.upper() not in ['ASC', 'DESC']:
        sort_order_safe = 'DESC'
    else:
        sort_order_safe = sort_order.upper()

    base_query += f" ORDER BY {db_sort_by} {sort_order_safe} LIMIT %s OFFSET %s"
    params_for_main_query.extend([per_page, offset])

    orders = execute_query(base_query, tuple(params_for_main_query), fetch_all=True, dictionary_cursor=True)

    total_orders_result = execute_query(count_base_query, tuple(params_for_count_query), fetch_one=True,
                                        dictionary_cursor=True)
    total_orders = total_orders_result['total_orders'] if total_orders_result else 0

    return {"orders": orders, "total_orders": total_orders, "page": page, "per_page": per_page}


def update_order_status_admin(order_id, new_status, admin_user_id):
    """管理员更新订单状态，并记录到历史表"""
    connection = create_connection()
    if not connection:
        return False

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
        order = cursor.fetchone()
        if not order:
            return False
        old_status = order['status']

        if old_status == new_status:
            return True

        cursor.execute("UPDATE orders SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                       (new_status, order_id))

        history_query = """
        INSERT INTO order_status_history (order_id, previous_status, new_status, changed_by_user_id, notes)
        VALUES (%s, %s, %s, %s, %s)
        """
        notes_for_history = f"管理员 (ID: {admin_user_id}) 将状态从 '{old_status}' 修改为 '{new_status}'."
        cursor.execute(history_query, (order_id, old_status, new_status, admin_user_id, notes_for_history))

        connection.commit()
        return True
    except Error as e:
        print(f"管理员更新订单 {order_id} 状态时发生数据库错误: '{e}'")
        if connection.is_connected():
            connection.rollback()
        return False
    finally:
        if connection.is_connected():
            if cursor:
                cursor.close()
            connection.close()

# --- 分类管理函数 ---
def get_all_categories():
    """获取所有菜品分类"""
    query = "SELECT id, name, description, display_order FROM categories ORDER BY display_order, name"
    return execute_query(query, fetch_all=True)


def get_category_by_id(category_id):
    """根据ID获取单个分类信息"""
    query = "SELECT id, name, description, display_order FROM categories WHERE id = %s"
    return execute_query(query, (category_id,), fetch_one=True)

def create_category(name, description=None, display_order=0):
    """创建新分类"""
    query = "INSERT INTO categories (name, description, display_order) VALUES (%s, %s, %s)"
    return execute_query(query, (name, description, display_order), is_modify=True)

def update_category(category_id, name, description, display_order):
    """更新分类信息"""
    query = "UPDATE categories SET name = %s, description = %s, display_order = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
    affected_rows = execute_query(query, (name, description, display_order, category_id), is_modify=True, dictionary_cursor=False)
    return affected_rows is not None and affected_rows > 0

def delete_category(category_id):
    """
    删除分类。
    返回: 1 (成功), 0 (分类不存在), -1 (被菜品使用), -2 (数据库错误)
    """
    try:
        if not get_category_by_id(category_id):
            return 0

        item_check_query = "SELECT COUNT(*) as count FROM menu_items WHERE category_id = %s"
        item_count = execute_query(item_check_query, (category_id,), fetch_one=True)
        if item_count and item_count['count'] > 0:
            return -1
        
        delete_query = "DELETE FROM categories WHERE id = %s"
        affected_rows = execute_query(delete_query, (category_id,), is_modify=True, dictionary_cursor=False)
        return 1 if affected_rows is not None and affected_rows > 0 else 0
    except Error as e:
        print(f"删除分类 {category_id} 时发生数据库错误: {e}")
        return -2

## --- 管理员用户管理函数 ---
def get_all_users(page=1, per_page=10):
    """
    管理员获取所有用户信息（分页）。
    查询的字段与 aql `users` 表结构完全对应。
    """
    offset = (page - 1) * per_page
    query = """
        SELECT id, username, full_name, email, phone, role, created_at, last_login 
        FROM users 
        ORDER BY created_at DESC 
        LIMIT %s OFFSET %s
    """
    users = execute_query(query, (per_page, offset), fetch_all=True)
    
    count_query = "SELECT COUNT(*) as total FROM users"
    total_result = execute_query(count_query, fetch_one=True)
    total_users = total_result['total'] if total_result else 0
    
    return {"users": users, "total_users": total_users, "page": page, "per_page": per_page}

def update_user_role(user_id, new_role):
    """管理员更新用户角色"""
    query = "UPDATE users SET role = %s WHERE id = %s"
    affected_rows = execute_query(query, (new_role, user_id), is_modify=True, dictionary_cursor=False)
    return affected_rows is not None and affected_rows > 0

def delete_user(user_id):
    """
    管理员删除用户。
    返回: 1 (成功), 0 (用户不存在), -1 (有关联订单), -2 (数据库错误)
    """
    try:
        if not get_user_by_id(user_id):
            return 0 

        order_check_query = "SELECT COUNT(*) as count FROM orders WHERE user_id = %s"
        order_count = execute_query(order_check_query, (user_id,), fetch_one=True)
        if order_count and order_count['count'] > 0:
            print(f"警告：用户 {user_id} 存在关联订单，删除用户后，这些订单的 user_id 将变为 NULL。")

        delete_query = "DELETE FROM users WHERE id = %s"
        affected_rows = execute_query(delete_query, (user_id,), is_modify=True, dictionary_cursor=False)
        return 1 if affected_rows is not None and affected_rows > 0 else 0
    except Error as e:
        print(f"删除用户 {user_id} 时发生数据库错误: {e}")
        return -2

# --- 分类管理函数 ---
def get_all_categories():
    """获取所有菜品分类"""
    query = "SELECT id, name, description, display_order FROM categories ORDER BY display_order, name"
    return execute_query(query, fetch_all=True, dictionary_cursor=True)


def get_category_by_id(category_id):
    """根据ID获取单个分类信息"""
    query = "SELECT id, name, description, display_order FROM categories WHERE id = %s"
    return execute_query(query, (category_id,), fetch_one=True, dictionary_cursor=True)


if __name__ == '__main__':
    # print("测试数据库模块 (database.py)...")
    pass
