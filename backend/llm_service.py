# backend/llm_service.py
import os  # 导入os模块以支持从环境变量读取API密钥
from openai import OpenAI, APIConnectionError, RateLimitError, APIStatusError  # 导入OpenAI库和相关异常

# DeepSeek API 配置
# 强烈建议将API密钥存储在环境变量中，而不是硬编码在代码里。
# 例如: DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
# 在运行前，请确保设置了名为 DEEPSEEK_API_KEY 的环境变量。
# 或者，为了快速测试，您可以临时在此处直接替换下面的占位符：
DEEPSEEK_API_KEY = "sk-303f28a8f16e4326ad72a7898f0b076f"  # <--- 请替换为您的真实 DeepSeek API Key
DEEPSEEK_BASE_URL = "https://api.deepseek.com"    # DeepSeek API 的基础 URL

# 为了保持与 app.py 的兼容性，函数名暂时不变
def get_recipe_suggestion_from_qwen(current_dishes, preferences=""):
    """
    从 DeepSeek 大模型获取餐谱搭配建议。
    (函数名保持为 get_recipe_suggestion_from_qwen 以兼容 app.py, 但内部已改为调用 DeepSeek)

    :param current_dishes: 当前已点菜品列表 (例如: ['宫保鸡丁', '米饭'])
    :param preferences: 用户偏好 (例如: '不吃辣', '素食者')
    :return: 大模型返回的建议文本，或者错误信息。
    """
    print(f"准备向 DeepSeek 请求餐谱建议。当前菜品: {current_dishes}, 用户偏好: {preferences}")

    # 检查API密钥是否已配置
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "sk-your-deepseek-api-key":
        print("警告: DeepSeek API Key 未配置或仍为占位符。请在 llm_service.py 中设置正确的 DEEPSEEK_API_KEY。")
        return "抱歉，餐谱建议服务未正确配置API密钥。"

    # 1. 构建用户Prompt
    if current_dishes:
        user_prompt = f"我正在点餐，已经选择了以下菜品：{', '.join(current_dishes)}。\n"
    else:
        user_prompt = "我正在点餐，但还没有选择任何菜品。\n"

    if preferences:
        user_prompt += f"我的饮食偏好是：{preferences}。\n"
    user_prompt += "请根据这些信息，为我推荐一些搭配的菜品或饮品，并简要说明理由。请以友好和专业的餐厅顾问口吻回答。"
    
    # 打印构建好的Prompt，便于调试
    # print(f"构建的用户Prompt: {user_prompt}")

    try:
        # 初始化 DeepSeek API 客户端
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

        # 构建发送给API的消息体
        messages = [
            {"role": "system", "content": "你是一个友好的餐厅顾问，擅长根据顾客已选菜品和饮食偏好推荐搭配菜品和饮品。你的回答应该专业、简洁且直接针对用户的点餐需求。"},
            {"role": "user", "content": user_prompt}
        ]
        
        # print(f"发送请求到 DeepSeek API (模型: deepseek-chat)") # 日志信息
        # 调用 DeepSeek API
        response = client.chat.completions.create(
            model="deepseek-chat",  # 使用 "deepseek-chat" 模型
            messages=messages,
            stream=False, # 设置为 False 以获取完整响应
            # max_tokens=250, # 可选：限制回复的最大长度，根据需要调整
            # temperature=0.7 # 可选：调整回复的创造性，0.0 (最确定) 到 2.0 (最随机)
        )

        #提取建议内容
        suggestion = response.choices[0].message.content
        # print(f"从 DeepSeek API 获取到响应: {suggestion}") # 日志信息
        return suggestion

    except APIConnectionError as e:
        print(f"错误: 无法连接到 DeepSeek API: {e}")
        return "抱歉，连接餐谱建议服务时出现网络问题，请稍后再试。"
    except RateLimitError as e:
        print(f"错误: DeepSeek API 请求超过速率限制: {e}")
        return "抱歉，请求过于频繁，请稍后再试。"
    except APIStatusError as e:
        print(f"错误: DeepSeek API 返回错误状态码 {e.status_code}: {e.response}")
        return f"抱歉，餐谱建议服务暂时不可用 (API 错误代码: {e.status_code})。"
    except Exception as e: # 捕获其他潜在错误
        print(f"错误: 调用 DeepSeek API 时发生未知错误: {e}")
        return "抱歉，获取餐谱建议时出现内部错误，请稍后再试。"


if __name__ == '__main__':
    print("测试LLM服务模块 (已切换到DeepSeek API)...")
    
    # 在运行测试前，请务必替换上面的 DEEPSEEK_API_KEY 为一个有效的密钥
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "sk-your-deepseek-api-key":
        print("\n跳过API调用测试，因为DeepSeek API Key未设置或仍为占位符。")
        print("请在 llm_service.py 文件顶部修改 DEEPSEEK_API_KEY 为您的真实密钥以进行测试。")
        print("推荐通过环境变量设置API密钥。")
    else:
        print(f"\n准备使用 API Key: ...{DEEPSEEK_API_KEY[-4:]}") # 打印部分密钥以供确认（注意安全）
        
        # 测试用例1: 有菜品，无偏好
        dishes1 = ["宫保鸡丁", "米饭"]
        print(f"\n测试1 - 菜品: {dishes1}, 偏好: 无")
        suggestion1 = get_recipe_suggestion_from_qwen(dishes1)
        print(f"建议1:\n{suggestion1}")

        # 测试用例2: 有菜品，有偏好
        dishes2 = ["麻婆豆腐"]
        prefs2 = "不吃辣，喜欢清淡" # 这个偏好和麻婆豆腐有点冲突，看模型怎么处理
        print(f"\n测试2 - 菜品: {dishes2}, 偏好: {prefs2}")
        suggestion2 = get_recipe_suggestion_from_qwen(dishes2, prefs2)
        print(f"建议2:\n{suggestion2}")
        
        # 测试用例3: 无菜品，无偏好
        dishes3 = []
        print(f"\n测试3 - 菜品: 无, 偏好: 无")
        suggestion3 = get_recipe_suggestion_from_qwen(dishes3)
        print(f"建议3:\n{suggestion3}")

        # 测试用例4: 无菜品，有偏好
        dishes4 = []
        prefs4 = "我想吃点辣的开胃菜，并且希望是素食。"
        print(f"\n测试4 - 菜品: 无, 偏好: {prefs4}")
        suggestion4 = get_recipe_suggestion_from_qwen(dishes4, prefs4)
        print(f"建议4:\n{suggestion4}")

        # 测试用例5: 多个菜品，复杂偏好
        dishes5 = ["北京烤鸭", "扬州炒饭"]
        prefs5 = "对海鲜过敏，希望搭配一些解腻的饮品"
        print(f"\n测试5 - 菜品: {dishes5}, 偏好: {prefs5}")
        suggestion5 = get_recipe_suggestion_from_qwen(dishes5, prefs5)
        print(f"建议5:\n{suggestion5}")