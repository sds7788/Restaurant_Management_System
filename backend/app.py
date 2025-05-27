# backend/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import backend.database as db # 使用相对导入
import backend.llm_service as llm # 使用相对导入
from datetime import datetime, timedelta 
import jwt 
import bcrypt 
from functools import wraps

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


# == 菜品和分类API ==
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
        # MODIFIED: 检查 include_unavailable 参数，主要为管理后台服务
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

# TODO: 实现管理员修改菜品 (@admin_required PUT /api/admin/menu/<item_id>)
# TODO: 实现管理员删除菜品 (@admin_required DELETE /api/admin/menu/<item_id>)

# == 订单API ==
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
        user_id_filter = request.args.get('user_id', type=int) # 如果传来非数字会是None
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


# == LLM 餐谱建议API ==
@app.route('/api/recipe-suggestion', methods=['POST'])
def get_recipe_suggestion():
    try:
        data = request.get_json()
        current_dishes = data.get('current_dishes', []) 
        preferences = data.get('preferences', "")    

        if not isinstance(current_dishes, list):
            return jsonify({"error": "current_dishes 必须是一个列表"}), 400
        
        suggestion = llm.get_recipe_suggestion_from_qwen(current_dishes, preferences)
        return jsonify({"suggestion": suggestion}), 200
    except Exception as e:
        app.logger.error(f"获取餐谱建议失败: {e}", exc_info=True)
        return jsonify({"error": "获取餐谱建议时发生服务器错误", "message": str(e)}), 500


if __name__ == '__main__':
    import logging
    app_logger = logging.getLogger() 
    app_logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    file_handler = logging.FileHandler('restaurant_app.log', encoding='utf-8') 
    file_handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)')
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    if not app_logger.handlers: 
        app_logger.addHandler(console_handler)
        app_logger.addHandler(file_handler)
    
    app.logger.info("餐饮管理系统后端API启动...") 
    app.run(host='0.0.0.0', port=5000, debug=True)
