-- database_setup.sql
-- 创建数据库 (如果不存在)
CREATE DATABASE IF NOT EXISTS restaurant_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE restaurant_db;

-- 用户表 (核心表，用于存储用户信息和角色)
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,         -- 用户名，唯一
    password_hash VARCHAR(255) NOT NULL,          -- 哈希后的密码
    role VARCHAR(20) DEFAULT 'customer' CHECK (role IN ('customer', 'admin', 'staff')), -- 角色: customer, admin, staff
    full_name VARCHAR(100),                       -- 真实姓名
    phone VARCHAR(20) UNIQUE,                     -- 电话号码，唯一 (可选)
    email VARCHAR(100) UNIQUE,                    -- 邮箱，唯一 (可选)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 注册时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, -- 信息更新时间
    last_login TIMESTAMP NULL                     -- 上次登录时间
);

-- 分类表 (用于菜品分类)
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,             -- 分类名称
    description TEXT,                             -- 分类描述
    display_order INT DEFAULT 0                   -- 显示顺序 (用于前端排序)
);

-- 菜品表
CREATE TABLE IF NOT EXISTS menu_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,            -- 菜品名称
    description TEXT,                             -- 描述
    price DECIMAL(10, 2) NOT NULL,                -- 价格
    category_id INT,                              -- 外键，关联 categories 表
    image_url VARCHAR(255),                       -- 图片链接 (可选)
    is_available BOOLEAN DEFAULT TRUE,            -- 是否可供应
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL -- 如果分类被删除，菜品分类ID置空
);

-- 订单表 (核心表，关联用户)
CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,                             -- 外键，关联 users 表 (允许匿名用户下单，所以为NULL)
    customer_name VARCHAR(100),                   -- 顾客名称 (主要用于匿名用户或备用)
    order_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 下单时间
    total_amount DECIMAL(10, 2) NOT NULL,         -- 总金额
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'preparing', 'completed', 'cancelled', 'delivered')), -- 订单状态
    payment_method VARCHAR(50),                   -- 支付方式
    payment_status VARCHAR(20) DEFAULT 'unpaid' CHECK (payment_status IN ('unpaid', 'paid', 'failed', 'refunded')), -- 支付状态
    delivery_address TEXT,                        -- 配送地址 (如果需要外送)
    notes TEXT,                                   -- 订单备注
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL -- 如果用户被删除，订单中的user_id置空
);

-- 订单详情表 (一个订单可以包含多个菜品)
CREATE TABLE IF NOT EXISTS order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,                        -- 外键，关联 orders 表
    menu_item_id INT NOT NULL,                    -- 外键，关联 menu_items 表
    quantity INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,           -- 下单时的单价 (重要，防止菜品价格变动影响历史订单)
    subtotal DECIMAL(10, 2) NOT NULL,             -- 小计金额 (quantity * unit_price)
    special_requests TEXT,                        -- 特殊要求
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE, -- 如果订单被删除，相关订单项也删除
    FOREIGN KEY (menu_item_id) REFERENCES menu_items(id) ON DELETE RESTRICT -- 如果菜品存在于订单项中，则不允许删除该菜品 (或改为SET NULL，但需处理菜品信息展示)
);

-- 订单状态历史表 (用于追踪订单状态变更，高级功能)
CREATE TABLE IF NOT EXISTS order_status_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    previous_status VARCHAR(20),
    new_status VARCHAR(20) NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by_user_id INT NULL,                  -- 操作变更的用户ID (可能是管理员或系统)
    notes TEXT,                                   -- 变更备注或原因
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (changed_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 示例：会话变量，用于触发器中获取当前操作用户ID (需要在应用层面设置)
-- SET @current_user_id = 1; -- 假设当前操作用户是ID为1的管理员

-- 触发器：当订单状态更新时，自动记录到 order_status_history
DELIMITER //
CREATE TRIGGER IF NOT EXISTS after_order_status_update
AFTER UPDATE ON orders
FOR EACH ROW
BEGIN
    IF OLD.status <> NEW.status THEN
        -- 尝试获取会话变量 @current_user_id，如果未设置则为NULL
        -- 注意：这种方式依赖于应用在执行UPDATE前正确设置了@current_user_id
        -- 更可靠的方式可能是在应用逻辑中直接插入历史记录
        INSERT INTO order_status_history (order_id, previous_status, new_status, changed_by_user_id, notes)
        VALUES (NEW.id, OLD.status, NEW.status, IFNULL(@current_user_id, NULL), CONCAT('Status changed from ', OLD.status, ' to ', NEW.status));
    END IF;
END //
DELIMITER ;


-- --- 插入初始数据 ---

-- 插入分类数据
INSERT IGNORE INTO categories (id, name, description, display_order) VALUES
(1, '主菜', '各种主要菜品', 1),
(2, '汤品', '各种汤类', 2),
(3, '主食', '米饭、面条等', 3),
(4, '饮品', '各种饮料', 4),
(5, '小吃', '开胃小食', 5);

-- 插入菜品数据 (使用 IGNORE 避免重复插入导致错误)
INSERT IGNORE INTO menu_items (name, description, price, category_id, image_url, is_available) VALUES
('宫保鸡丁', '经典川菜，鸡肉丁、花生米、辣椒段等炒制而成，酸甜微辣。', 38.00, 1, 'https://www.butiao.com/static/images/2022/11/12/7672f22f0d284f938e7fe56fb3ab3b06~noop_ezhvlmduv4n.jpg', TRUE),
('鱼香肉丝', '经典川菜，猪里脊肉丝与木耳、笋丝等炒制，咸甜酸辣兼备，姜葱蒜味突出。', 35.00, 1, 'https://pic.nximg.cn/file/20230331/33857552_193519175105_2.jpg', TRUE),
('麻婆豆腐', '经典川菜，豆腐、牛肉末（或猪肉末）、豆瓣酱、豆豉等烧制，麻辣鲜香。', 28.00, 1, 'https://th.bing.com/th/id/R.2842ebed1c91a3e4747b6ebbdda2026a?rik=xnQWE1sPxNrOjw&riu=http%3a%2f%2fi2.hdslb.com%2fbfs%2farchive%2f0a7daed5e4a52ca5dbf1aa18cbffd5362719fe81.jpg&ehk=6gRq1RhQbYRigMuzPv7lfASg%2b1W4shKPdJa6llOY5x8%3d&risl=&pid=ImgRaw&r=0', TRUE),
('酸辣汤', '传统汤品，以肉丝、豆腐、冬笋、木耳等为原料，酸辣开胃。', 18.00, 2, 'https://th.bing.com/th/id/R.d654e39ce10eb060da2b25c9e90d723d?rik=fsEIk5UMUsjsVQ&riu=http%3a%2f%2fcp1.douguo.net%2fupload%2fcaiku%2f3%2fc%2fc%2fyuan_3cf096f91b5702cc7e5f9167f369410c.jpg&ehk=0JLABhI%2fXgyohGAn3p9CgJYYxX7j3NvFSEAfPhEyWN8%3d&risl=&pid=ImgRaw&r=0', TRUE),
('米饭', '优质大米蒸煮而成。', 3.00, 3, 'https://pic.nximg.cn/file/20230722/34599220_175523740108_2.jpg', TRUE),
('可乐', '经典碳酸饮料。', 5.00, 4, 'https://image2.suning.cn/b2c/catentries/000000000155267597_3_800x800.jpg', TRUE),
('扬州炒饭', '包含虾仁、鸡蛋、火腿丁、青豆、玉米等多种食材的炒饭。', 25.00, 3, 'https://th.bing.com/th/id/R.aead032af4b8a74ca8f6b40d59d6d040?rik=v7hzE7XxeQ9oZQ&riu=http%3a%2f%2fcp1.douguo.net%2fupload%2fcaiku%2f8%2f4%2f6%2fyuan_8435c1f7b9e8a9656c9dad11ee6aaa86.jpg&ehk=UbLEvuz8lVWTPCOwA%2bJ4w%2fSRcHYYjQXbpQfIasjFuhQ%3d&risl=&pid=ImgRaw&r=0', TRUE),
('番茄鸡蛋汤', '家常汤品，番茄与鸡蛋的完美结合，营养美味。', 15.00, 2, 'https://th.bing.com/th/id/R.8426db50a9fe8eb852aba0ea5ef2d412?rik=y%2fSK2alygGke1g&riu=http%3a%2f%2fn.sinaimg.cn%2fsinacn23%2fw1193h802%2f20180314%2f2f39-fyscsmv7444782.jpg&ehk=rT7RpKoCCKyKfhG%2b3GRWIT1nDJST%2fgudeHDpZ8xmq4s%3d&risl=&pid=ImgRaw&r=0', TRUE);

-- 插入示例用户 (密码是 'password123' 的bcrypt哈希值, 实际应由后端生成)
-- 使用 bcrypt.hashpw('password123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8') 生成
-- $2b$12$E0CMTTz57m564zWl.mRk6u231y0yX0f2uQzLq7gE7f7gH3rX0mQ.S  (for 'customerpass')
-- $2b$12$gZ2N3Y4vQW.Z9e8X7kF6cO.rY2uW.iO9uT3xJ.pZ5sL8vD0qR1eI.  (for 'adminpass')

INSERT IGNORE INTO users (username, password_hash, role, full_name, email, phone) VALUES
('customer1', '$2b$12$0usU2x4Gnr8qCVSO5VsK.OuSY61CL8R371RQjOTvh9.tF4Fr9D1WW', 'customer', '张三', 'zhangsan@example.com', '13800138000'),
('adminuser', '$2b$12$0usU2x4Gnr8qCVSO5VsK.OuSY61CL8R371RQjOTvh9.tF4Fr9D1WW', 'admin', '李四管理员', 'admin@example.com', '13900139000'),
('staffuser', '$2b$12$0usU2x4Gnr8qCVSO5VsK.OuSY61CL8R371RQjOTvh9.tF4Fr9D1WW', 'staff', '王五员工', 'staff@example.com', '13700137000');


COMMIT;

-- 注意：开发初期，如果需要完全重置数据库和表，可以取消以下注释并执行
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS order_status_history;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS menu_items;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS users;
SET FOREIGN_KEY_CHECKS = 1;
DROP DATABASE IF EXISTS restaurant_db;
