# backend/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import backend.database as db # 使用相对导入
import backend.llm_service as llm # 使用相对导入
from datetime import datetime, timedelta 
import jwt 
import bcrypt 
from functools import wraps
import logging

# --- 应用配置 ---
app = Flask(__name__)
CORS(app) 

app.config['SECRET_KEY'] = 'your-very-secret-and-strong-key' 
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)

# --- 辅助函数：JWT 和 权限装饰器 ---
def token_required(f):
    """装饰器：检查请求头中是否包含有效的JWT"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"message": "Token is missing!"}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = db.get_user_by_id(data['user_id'])
            if not current_user:
                return jsonify({"message": "Token is invalid, user not found!"}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token has expired!"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Token is invalid!"}), 401
        
        return f(current_user, *args, **kwargs)
    return decorated

def admin_required(f):
    """装饰器：检查用户是否为管理员"""
    @wraps(f)
    @token_required 
    def decorated(current_user, *args, **kwargs):
        if current_user['role'] != 'admin':
            return jsonify({"message": "Admin privilege required!"}), 403
        return f(current_user, *args, **kwargs)
    return decorated

# --- API 端点 ---

@app.route('/')
def home():
    return "欢迎来到餐饮管理系统后端API！ (v2)"

# == 用户认证API ==
@app.route('/api/auth/register', methods=['POST'])
def register_user():
    """用户注册"""
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "用户名和密码不能为空"}), 400

    username = data['username']
    password = data['password']
    role = data.get('role', 'customer') 
    full_name = data.get('full_name')
    email = data.get('email')
    phone = data.get('phone')

    if db.get_user_by_username(username):
        return jsonify({"error": "用户名已存在"}), 409
    if email and db.execute_query("SELECT id FROM users WHERE email = %s", (email,), fetch_one=True):
        return jsonify({"error": "邮箱已被注册"}), 409

    user_id = db.create_user(username, password, role, full_name, email, phone)
    if user_id:
        return jsonify({"message": "用户注册成功", "user_id": user_id}), 201
    else:
        app.logger.error(f"用户注册失败: {username}")
        return jsonify({"error": "用户注册失败，请稍后再试"}), 500

@app.route('/api/auth/login', methods=['POST'])
def login_user():
    """用户登录，成功则返回JWT"""
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "请输入用户名和密码"}), 400

    username = data['username']
    password = data['password']
    
    user = db.get_user_by_username(username)

    if not user or not db.verify_password(password, user['password_hash']):
        return jsonify({"error": "用户名或密码错误"}), 401

    db.update_user_last_login(user['id'])

    token_payload = {
        'user_id': user['id'],
        'username': user['username'],
        'role': user['role'],
        'exp': datetime.utcnow() + app.config['JWT_ACCESS_TOKEN_EXPIRES']
    }
    access_token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm="HS256")
    
    return jsonify({
        "message": "登录成功",
        "access_token": access_token,
        "user": { 
            "id": user['id'],
            "username": user['username'],
            "role": user['role'],
            "full_name": user.get('full_name')
        }
    }), 200

@app.route('/api/auth/me', methods=['GET'])
@token_required
def get_current_user_profile(current_user):
    """获取当前登录用户的个人信息 (需要Token)"""
    profile_data = {key: value for key, value in current_user.items() if key != 'password_hash'}
    return jsonify(profile_data), 200


# == 菜品和分类API (公开部分) ==
@app.route('/api/categories', methods=['GET'])
def get_categories():
    """获取所有菜品分类"""
    try:
        categories = db.get_all_categories()
        return jsonify(categories), 200
    except Exception as e:
        app.logger.error(f"获取分类失败: {e}")
        return jsonify({"error": "获取分类失败", "message": str(e)}), 500

@app.route('/api/menu', methods=['GET'])
def get_menu():
    """获取所有菜品，管理员可获取包括不可用的菜品"""
    try:
        include_unavailable_str = request.args.get('include_unavailable', 'false').lower()
        include_unavailable = include_unavailable_str == 'true'
        
        menu_items = db.get_all_menu_items(include_unavailable=include_unavailable)
        return jsonify(menu_items), 200
    except Exception as e:
        app.logger.error(f"获取菜单失败: {e}")
        return jsonify({"error": "获取菜单失败", "message": str(e)}), 500

@app.route('/api/menu/<int:item_id>', methods=['GET'])
def get_menu_item(item_id):
    """获取单个菜品详情"""
    try:
        item = db.get_menu_item_by_id(item_id)
        if item:
            return jsonify(item), 200
        else:
            return jsonify({"error": "菜品未找到"}), 404
    except Exception as e:
        app.logger.error(f"获取菜品 {item_id} 失败: {e}")
        return jsonify({"error": f"获取菜品 {item_id} 失败", "message": str(e)}), 500

# == 管理员菜品管理API ==
@app.route('/api/admin/menu', methods=['POST'])
@admin_required 
def admin_add_new_menu_item(current_admin_user):
    """管理员添加新菜品"""
    try:
        data = request.get_json()
        required_fields = ['name', 'price', 'category_id']
        if not data or not all(k in data for k in required_fields):
            return jsonify({"error": f"缺少必要参数: {', '.join(required_fields)}"}), 400
        
        name = data['name']
        description = data.get('description', '')
        price = data['price']
        category_id = data['category_id']
        image_url = data.get('image_url')
        is_available = data.get('is_available', True)

        try:
            price = float(price)
            if price <= 0:
                raise ValueError("价格必须为正数")
            category_id = int(category_id)
        except ValueError as ve:
            return jsonify({"error": "价格或分类ID格式无效", "message": str(ve)}), 400

        if not db.get_category_by_id(category_id):
            return jsonify({"error": f"分类ID {category_id} 不存在"}), 404

        item_id = db.add_menu_item(name, description, price, category_id, image_url, is_available)
        if item_id:
            app.logger.info(f"管理员 {current_admin_user['username']} 添加菜品成功, ID: {item_id}")
            return jsonify({"message": "菜品添加成功", "item_id": item_id}), 201
        else:
            return jsonify({"error": "添加菜品失败"}), 500
    except Exception as e:
        app.logger.error(f"管理员 {current_admin_user.get('username', 'N/A')} 添加菜品失败: {e}", exc_info=True)
        return jsonify({"error": "添加菜品时发生服务器错误", "message": str(e)}), 500

@app.route('/api/admin/menu/<int:item_id>', methods=['PUT'])
@admin_required
def admin_update_menu_item(current_admin_user, item_id):
    """管理员修改现有菜品"""
    try:
        existing_item = db.get_menu_item_by_id(item_id)
        if not existing_item:
            app.logger.warning(f"管理员 {current_admin_user['username']} 尝试更新不存在的菜品ID: {item_id}")
            return jsonify({"error": "菜品未找到，无法更新"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "请求体不能为空"}), 400

        name = data.get('name', existing_item['name'])
        description = data.get('description', existing_item['description'])
        price_str = data.get('price')
        category_id_str = data.get('category_id')
        image_url = data.get('image_url', existing_item['image_url'])
        is_available = data.get('is_available', existing_item['is_available'])

        if not name:
            return jsonify({"error": "菜品名称不能为空"}), 400
        
        try:
            price = float(price_str)
            if price <= 0:
                raise ValueError("价格必须为正数")
        except (ValueError, TypeError):
            return jsonify({"error": "价格格式无效或未提供", "message": "价格必须是正数。"}), 400

        try:
            category_id = int(category_id_str)
            if not db.get_category_by_id(category_id):
                return jsonify({"error": f"分类ID {category_id} 不存在"}), 404
        except (ValueError, TypeError):
            return jsonify({"error": "分类ID格式无效或未提供", "message": "分类ID必须是整数。"}), 400

        if not isinstance(is_available, bool):
             if str(is_available).lower() == 'true':
                 is_available = True
             elif str(is_available).lower() == 'false':
                 is_available = False
             else:
                return jsonify({"error": "is_available 字段必须是布尔值 (true/false)"}), 400

        affected_rows = db.update_menu_item(item_id, name, description, price, category_id, image_url, is_available)

        if affected_rows is not None and affected_rows > 0:
            app.logger.info(f"管理员 {current_admin_user['username']} 成功更新菜品ID: {item_id}")
            updated_item = db.get_menu_item_by_id(item_id)
            return jsonify({"message": "菜品更新成功", "item": updated_item}), 200
        elif affected_rows == 0:
            app.logger.warning(f"管理员 {current_admin_user['username']} 更新菜品ID: {item_id} 时，数据未发生变化或未找到。")
            return jsonify({"message": "菜品数据未发生变化", "item": existing_item}), 200
        else:
            app.logger.error(f"管理员 {current_admin_user['username']} 更新菜品ID: {item_id} 时发生数据库错误。")
            return jsonify({"error": "更新菜品失败，数据库操作错误"}), 500

    except Exception as e:
        app.logger.error(f"管理员 {current_admin_user.get('username', 'N/A')} 更新菜品ID {item_id} 时发生服务器内部错误: {e}", exc_info=True)
        return jsonify({"error": "更新菜品时发生服务器内部错误", "message": str(e)}), 500

@app.route('/api/admin/menu/<int:item_id>', methods=['DELETE'])
@admin_required
def admin_delete_menu_item(current_admin_user, item_id):
    """管理员删除菜品"""
    try:
        item = db.get_menu_item_by_id(item_id)
        if not item:
            app.logger.warning(f"管理员 {current_admin_user['username']} 尝试删除不存在的菜品ID: {item_id}")
            return jsonify({"error": "菜品未找到"}), 404

        deleted_rows = db.delete_menu_item(item_id)

        if deleted_rows == -1:
            app.logger.warning(f"管理员 {current_admin_user['username']} 尝试删除的菜品ID {item_id} 因被订单引用而无法删除")
            return jsonify({"error": "无法删除菜品，该菜品可能已被订单引用。"}), 409
        elif deleted_rows and deleted_rows > 0:
            app.logger.info(f"管理员 {current_admin_user['username']} 成功删除菜品ID: {item_id}")
            return jsonify({"message": f"菜品ID {item_id} 已成功删除"}), 200
        elif deleted_rows == 0:
            app.logger.warning(f"管理员 {current_admin_user['username']} 尝试删除菜品ID {item_id}，但未找到或未删除任何行")
            return jsonify({"error": "删除菜品失败，菜品可能已被删除或不存在"}), 404
        else:
            app.logger.error(f"管理员 {current_admin_user['username']} 删除菜品ID {item_id} 时发生未知数据库错误")
            return jsonify({"error": "删除菜品时发生未知错误"}), 500

    except Exception as e:
        app.logger.error(f"管理员 {current_admin_user.get('username', 'N/A')} 删除菜品ID {item_id} 时发生服务器错误: {e}", exc_info=True)
        return jsonify({"error": "删除菜品时发生服务器错误", "message": str(e)}), 500

# == 订单API ==
@app.route('/api/orders/<int:order_id>/pay', methods=['POST'])
@token_required
def pay_for_order(current_user, order_id):
    """用户支付订单"""
    try:
        order = db.get_order_details_by_id(order_id)
        if not order:
            return jsonify({"error": "订单未找到"}), 404

        if order.get('user_id') != current_user['id']:
            return jsonify({"error": "无权操作此订单"}), 403

        if order.get('payment_status') == 'paid':
            return jsonify({"message": "此订单已支付，无需重复操作"}), 200

        success = db.update_order_payment_status(order_id, 'paid')

        if success:
            app.logger.info(f"用户 {current_user['username']} (ID: {current_user['id']}) 成功支付订单 {order_id}")
            return jsonify({"message": f"订单 #{order_id} 支付成功"}), 200
        else:
            app.logger.error(f"用户 {current_user['username']} 支付订单 {order_id} 时数据库更新失败")
            return jsonify({"error": "支付失败，请稍后再试"}), 500

    except Exception as e:
        app.logger.error(f"支付订单 {order_id} 时发生服务器错误 (用户: {current_user['username']}): {e}", exc_info=True)
        return jsonify({"error": "处理支付请求时发生服务器错误", "message": str(e)}), 500

@app.route('/api/orders', methods=['POST'])
@token_required 
def place_order(current_user):
    """创建新订单 (用户必须登录)"""
    try:
        data = request.get_json()
        if not data or not data.get('items'): 
            return jsonify({"error": "缺少必要参数 (items)"}), 400

        order_items_data_frontend = data['items'] 
        
        if not isinstance(order_items_data_frontend, list) or not order_items_data_frontend:
            return jsonify({"error": "订单项目(items)必须是非空列表"}), 400

        detailed_items_for_db = []
        total_amount = 0
        for item_data in order_items_data_frontend:
            if not isinstance(item_data, dict) or not all(k in item_data for k in ('menu_item_id', 'quantity')):
                return jsonify({"error": "订单项目中缺少 menu_item_id 或 quantity"}), 400
            
            menu_item_id = item_data['menu_item_id']
            quantity = item_data['quantity']
            special_requests = item_data.get('special_requests')

            try:
                quantity = int(quantity)
                if quantity <= 0:
                     return jsonify({"error": f"菜品ID {menu_item_id} 的数量必须为正整数"}), 400
            except ValueError:
                return jsonify({"error": f"菜品ID {menu_item_id} 的数量格式无效"}), 400

            menu_item_db = db.get_menu_item_by_id(menu_item_id) 
            if not menu_item_db or not menu_item_db['is_available']:
                return jsonify({"error": f"菜品 '{menu_item_db.get('name', menu_item_id)}' 未找到或不可用"}), 404
            
            unit_price = menu_item_db['price'] 
            subtotal = unit_price * quantity
            total_amount += subtotal
            
            detailed_items_for_db.append({
                'menu_item_id': menu_item_id,
                'quantity': quantity,
                'unit_price': unit_price,
                'subtotal': subtotal,
                'special_requests': special_requests
            })

        order_id = db.create_order(
            user_id=current_user['id'], 
            customer_name=current_user.get('full_name', current_user['username']), 
            total_amount=total_amount,
            items_data=detailed_items_for_db,
            payment_method=data.get('payment_method'),
            delivery_address=data.get('delivery_address'),
            notes=data.get('notes')
        )

        if order_id:
            app.logger.info(f"用户 {current_user['username']} (ID: {current_user['id']}) 创建订单成功, 订单ID: {order_id}")
            return jsonify({"message": "订单创建成功", "order_id": order_id, "total_amount": total_amount}), 201
        else:
            app.logger.error(f"用户 {current_user['username']} 创建订单失败")
            return jsonify({"error": "创建订单失败"}), 500
    except Exception as e:
        app.logger.error(f"用户 {current_user.get('username', 'N/A')} 创建订单时发生服务器错误: {e}", exc_info=True)
        return jsonify({"error": "创建订单时发生服务器错误", "message": str(e)}), 500

@app.route('/api/orders/my', methods=['GET'])
@token_required
def get_my_orders(current_user):
    """获取当前登录用户的历史订单 (分页)"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        if page < 1: page = 1
        if per_page < 1: per_page = 1
        if per_page > 100: per_page = 100 

        orders_data = db.get_orders_by_user_id(current_user['id'], page, per_page)
        return jsonify(orders_data), 200
    except Exception as e:
        app.logger.error(f"用户 {current_user['username']} 获取历史订单失败: {e}", exc_info=True)
        return jsonify({"error": "获取历史订单失败", "message": str(e)}), 500

@app.route('/api/orders/<int:order_id>', methods=['GET'])
@token_required 
def get_single_order(current_user, order_id):
    """获取单个订单详情 (用户只能查看自己的，除非是管理员)"""
    try:
        order = db.get_order_details_by_id(order_id)
        if not order:
            return jsonify({"error": "订单未找到"}), 404
        
        if current_user['role'] != 'admin' and order.get('user_id') != current_user['id']:
            return jsonify({"error": "无权访问此订单"}), 403
            
        return jsonify(order), 200
    except Exception as e:
        app.logger.error(f"获取订单 {order_id} 失败 (请求者: {current_user['username']}): {e}", exc_info=True)
        return jsonify({"error": f"获取订单 {order_id} 失败", "message": str(e)}), 500

# == 管理员订单管理API ==
@app.route('/api/admin/orders', methods=['GET'])
@admin_required
def admin_get_all_orders(current_admin_user):
    """管理员获取所有订单 (分页, 可筛选, 可排序)"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status_filter = request.args.get('status')
        user_id_filter = request.args.get('user_id', type=int)
        sort_by = request.args.get('sort_by', 'order_time')
        sort_order = request.args.get('sort_order', 'DESC')

        if page < 1: page = 1
        if per_page < 1: per_page = 1
        if per_page > 100: per_page = 100

        orders_data = db.get_all_orders_admin(page, per_page, status_filter, user_id_filter, sort_by, sort_order)
        return jsonify(orders_data), 200
    except Exception as e:
        app.logger.error(f"管理员 {current_admin_user['username']} 获取所有订单失败: {e}", exc_info=True)
        return jsonify({"error": "获取所有订单失败", "message": str(e)}), 500

@app.route('/api/admin/orders/<int:order_id>/status', methods=['PUT'])
@admin_required
def admin_update_order_status(current_admin_user, order_id):
    """管理员更新订单状态"""
    data = request.get_json()
    new_status = data.get('status')
    if not new_status:
        return jsonify({"error": "缺少新状态 (status) 参数"}), 400
    
    valid_statuses = ['pending', 'confirmed', 'preparing', 'completed', 'cancelled', 'delivered']
    if new_status not in valid_statuses:
        return jsonify({"error": f"无效的订单状态: {new_status}. 合法状态为: {', '.join(valid_statuses)}"}), 400

    try:
        success = db.update_order_status_admin(order_id, new_status, current_admin_user['id'])
        if success:
            app.logger.info(f"管理员 {current_admin_user['username']} 更新订单 {order_id} 状态为 {new_status} 成功")
            return jsonify({"message": f"订单 {order_id} 状态已更新为 {new_status}"}), 200
        else:
            return jsonify({"error": f"更新订单 {order_id} 状态失败，订单可能不存在或数据库错误"}), 404 
    except Exception as e:
        app.logger.error(f"管理员 {current_admin_user['username']} 更新订单 {order_id} 状态失败: {e}", exc_info=True)
        return jsonify({"error": "更新订单状态时发生服务器错误", "message": str(e)}), 500


# ============================================
# == 管理员用户管理API (User Management) ==
# ============================================

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_all_users(current_admin_user):
    """
    管理员获取所有用户信息 (分页)
    此接口返回的数据字段与 `users` 表结构对应。
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        if page < 1: page = 1
        if per_page < 1 or per_page > 100: per_page = 10
        
        users_data = db.get_all_users(page=page, per_page=per_page)
        return jsonify(users_data), 200
    except Exception as e:
        app.logger.error(f"管理员 {current_admin_user['username']} 获取用户列表失败: {e}", exc_info=True)
        return jsonify({"error": "获取用户列表失败", "message": str(e)}), 500

@app.route('/api/admin/users/<int:user_id>/role', methods=['PUT'])
@admin_required
def admin_update_user_role(current_admin_user, user_id):
    """管理员修改用户角色"""
    data = request.get_json()
    new_role = data.get('role')

    # 验证传入的角色是否合法
    valid_roles = ['customer', 'admin', 'staff']
    if not new_role or new_role not in valid_roles:
        return jsonify({"error": f"无效的角色，角色必须是 {', '.join(valid_roles)} 之一"}), 400
    
    # 防止管理员误操作修改自己的角色
    if user_id == current_admin_user['id']:
        return jsonify({"error": "无法修改自己的角色"}), 403

    try:
        if not db.get_user_by_id(user_id):
            return jsonify({"error": "用户未找到"}), 404
        
        success = db.update_user_role(user_id, new_role)
        if success:
            app.logger.info(f"管理员 {current_admin_user['username']} 将用户 {user_id} 的角色修改为 {new_role}")
            return jsonify({"message": "用户角色更新成功"}), 200
        else:
            return jsonify({"error": "用户角色更新失败"}), 500
    except Exception as e:
        app.logger.error(f"管理员 {current_admin_user['username']} 修改用户 {user_id} 角色失败: {e}", exc_info=True)
        return jsonify({"error": "更新角色时发生服务器错误", "message": str(e)}), 500

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(current_admin_user, user_id):
    """管理员删除用户"""
    # 防止管理员删除自己
    if user_id == current_admin_user['id']:
        return jsonify({"error": "无法删除自己的账户"}), 403
    
    try:
        # 数据库函数会处理检查逻辑
        result_code = db.delete_user(user_id)

        if result_code == 1: # 删除成功
            app.logger.info(f"管理员 {current_admin_user['username']} 成功删除用户 {user_id}")
            return jsonify({"message": f"用户 {user_id} 已被删除"}), 200
        elif result_code == 0: # 用户不存在
            return jsonify({"error": "用户未找到"}), 404
        elif result_code == -1: # 用户有关联订单
            return jsonify({"error": "无法删除该用户，因为该用户存在关联订单"}), 409
        else: # 其他数据库错误 (-2)
            return jsonify({"error": "删除用户时发生数据库错误"}), 500

    except Exception as e:
        app.logger.error(f"管理员 {current_admin_user['username']} 删除用户 {user_id} 时发生错误: {e}", exc_info=True)
        return jsonify({"error": "删除用户时发生服务器错误", "message": str(e)}), 500

# ====================================================
# == 新增：管理员分类管理API (Category Management) ==
# ====================================================
@app.route('/api/admin/categories', methods=['POST'])
@admin_required
def admin_create_category(current_admin_user):
    """管理员创建新分类"""
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({"error": "分类名称不能为空"}), 400
    
    description = data.get('description')
    display_order = data.get('display_order', 0)

    try:
        category_id = db.create_category(name, description, display_order)
        if category_id:
            app.logger.info(f"管理员 {current_admin_user['username']} 创建新分类 '{name}' (ID: {category_id})")
            new_category = db.get_category_by_id(category_id)
            return jsonify({"message": "分类创建成功", "category": new_category}), 201
        else:
            return jsonify({"error": "创建分类失败"}), 500
    except Exception as e:
        app.logger.error(f"管理员 {current_admin_user['username']} 创建分类失败: {e}", exc_info=True)
        return jsonify({"error": "创建分类时发生服务器错误", "message": str(e)}), 500

@app.route('/api/admin/categories/<int:category_id>', methods=['PUT'])
@admin_required
def admin_update_category(current_admin_user, category_id):
    """管理员更新分类信息"""
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({"error": "分类名称不能为空"}), 400

    description = data.get('description')
    display_order = data.get('display_order', 0)

    try:
        success = db.update_category(category_id, name, description, display_order)
        if success:
            app.logger.info(f"管理员 {current_admin_user['username']} 更新了分类 {category_id}")
            updated_category = db.get_category_by_id(category_id)
            return jsonify({"message": "分类更新成功", "category": updated_category}), 200
        else:
            return jsonify({"error": "分类更新失败，可能未找到该分类"}), 404
    except Exception as e:
        app.logger.error(f"管理员 {current_admin_user['username']} 更新分类 {category_id} 失败: {e}", exc_info=True)
        return jsonify({"error": "更新分类时发生服务器错误", "message": str(e)}), 500


@app.route('/api/admin/categories/<int:category_id>', methods=['DELETE'])
@admin_required
def admin_delete_category(current_admin_user, category_id):
    """管理员删除分类"""
    try:
        # 数据库函数将处理检查逻辑
        result_code = db.delete_category(category_id)
        
        if result_code == 1: # 删除成功
            app.logger.info(f"管理员 {current_admin_user['username']} 删除了分类 {category_id}")
            return jsonify({"message": "分类删除成功"}), 200
        elif result_code == 0: # 分类不存在
            return jsonify({"error": "分类未找到"}), 404
        elif result_code == -1: # 分类正在被使用
            return jsonify({"error": "无法删除，该分类下仍有菜品"}), 409
        else: # 其他数据库错误
            return jsonify({"error": "删除分类时发生数据库错误"}), 500
            
    except Exception as e:
        app.logger.error(f"管理员 {current_admin_user['username']} 删除分类 {category_id} 失败: {e}", exc_info=True)
        return jsonify({"error": "删除分类时发生服务器错误", "message": str(e)}), 500


# == LLM 餐谱建议API ==
@app.route('/api/recipe-suggestion', methods=['POST'])
@token_required
def get_recipe_suggestion(current_user):
    """
    获取基于当前菜单和用户偏好的智能餐谱建议。
    """
    try:
        data = request.get_json()
        current_dishes = data.get('current_dishes', []) 
        preferences = data.get('preferences', "")    

        if not isinstance(current_dishes, list):
            return jsonify({"error": "current_dishes 必须是一个列表"}), 400
        
        all_available_items = db.get_all_menu_items(include_unavailable=False)
        menu_context = [
            f"{item['name']} (分类: {item['category_name']}, 描述: {item['description'] or '无'})" 
            for item in all_available_items
        ]
        
        suggestion = llm.get_recipe_suggestion_from_qwen(
            current_dishes=current_dishes, 
            preferences=preferences,
            full_menu=menu_context
        )
        return jsonify({"suggestion": suggestion}), 200
        
    except Exception as e:
        app.logger.error(f"获取餐谱建议失败: {e}", exc_info=True)
        return jsonify({"error": "获取餐谱建议时发生服务器错误", "message": str(e)}), 500


if __name__ == '__main__':
    # 配置日志
    app_logger = logging.getLogger() 
    app_logger.setLevel(logging.INFO)

    # 避免重复添加handler
    if not app_logger.handlers: 
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        file_handler = logging.FileHandler('restaurant_app.log', encoding='utf-8') 
        file_handler.setLevel(logging.INFO)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)')
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        app_logger.addHandler(console_handler)
        app_logger.addHandler(file_handler)
    
    app.logger.info("餐饮管理系统后端API启动...") 
    app.run(host='0.0.0.0', port=5000, debug=True)
