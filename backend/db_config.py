# backend/db_config.py
# 数据库连接配置
# 请根据你的MySQL实际情况修改这些配置
DB_CONFIG = {
    'host': 'localhost',        # MySQL服务器地址
    'user': 'root',    # MySQL用户名
    'password': 'sds205322',# MySQL密码
    'database': 'restaurant_db',# 数据库名称
    'port': 3306                # MySQL端口号, 默认3306
}

# 强烈建议: 不要将敏感信息（如密码）直接硬编码在代码中。
# 在生产环境中，应使用环境变量、配置文件或密钥管理服务来存储这些信息。
# 例如, 可以从环境变量读取:
# import os
# DB_CONFIG = {
#     'host': os.environ.get('DB_HOST', 'localhost'),
#     'user': os.environ.get('DB_USER'),
#     'password': os.environ.get('DB_PASSWORD'),
#     'database': os.environ.get('DB_NAME', 'restaurant_db'),
#     'port': int(os.environ.get('DB_PORT', 3306))
# }
