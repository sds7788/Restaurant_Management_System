# backend/llm_service.py
import os
from openai import OpenAI, APIConnectionError, RateLimitError, APIStatusError

# DeepSeek API 配置
DEEPSEEK_API_KEY = ""  # <--- 请替换为您的真实 DeepSeek API Key
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

def get_recipe_suggestion_from_qwen(current_dishes, preferences="", full_menu=None):
    """
    从 DeepSeek 大模型获取基于本店菜单的、经过优化的餐谱搭配建议。

    :param current_dishes: 当前已点菜品列表。
    :param preferences: 用户偏好。
    :param full_menu: 餐厅当前所有可用菜品的列表 (包含名称、分类和描述)。
    :return: 大模型返回的建议文本，或者错误信息。
    """
    if full_menu is None:
        full_menu = []
    
    print(f"准备向 DeepSeek 请求优化后的餐谱建议。当前菜品: {current_dishes}, 用户偏好: {preferences}")

    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "sk-your-deepseek-api-key":
        print("警告: DeepSeek API Key 未配置。")
        return "抱歉，餐谱建议服务未正确配置API密钥。"

    # 1. 优化系统提示词 (System Prompt)
    system_prompt = """
你是一位顶级的中餐主厨和餐厅顾问。你的任务是帮助顾客搭配出一套完美、均衡且美味的餐点。
你的回答必须遵循以下结构和要求：
1.  **分析现状**: 首先，简要分析顾客已选菜品的口味特点（例如：这道菜是香辣开胃的）。如果顾客未选菜，则直接根据其偏好进行推荐。
2.  **提出推荐**: 根据你的分析和顾客的个人偏好，清晰地推荐1-3个可以形成良好互补的菜品、汤或饮品。
3.  **解释理由**: 为每一项推荐提供充分的理由。
4.  **专业口吻**: 始终保持专业、友好的专家口吻。
5.  **核心原则**: 你的所有推荐【必须】从下面用户提供的“今日菜单”中选择。严禁推荐任何不在菜单中的菜品。
6.  **格式要求**: 请使用Markdown格式进行排版，让回答清晰易读。
"""

    # 2. 构建包含完整菜单的用户指令 (User Prompt)
    if not full_menu:
        # 如果菜单为空，直接返回提示信息，避免无效调用
        return "抱歉，餐厅今天没有可用的菜单，无法为您提供建议。"
        
    menu_list_str = "\n".join(f"- {item}" for item in full_menu)
    user_prompt_content = f"这是我们餐厅今天的完整菜单：\n---\n{menu_list_str}\n---\n\n"

    # 根据用户是否已点餐，组织不同的提问方式
    if not current_dishes:
        user_prompt_content += "一位顾客只告诉了我他的口味偏好，还没有点任何菜。"
    else:
        dish_list_str = "\n".join(f"- {dish}" for dish in current_dishes)
        user_prompt_content += f"这位顾客目前已经选了这些菜：\n{dish_list_str}\n"

    if preferences:
        user_prompt_content += f"\n顾客的个人口味和要求是：'{preferences}'。\n"
    
    user_prompt_content += "\n请根据以上信息，为顾客提供搭配建议。"

    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt_content}
        ]
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=False,
            max_tokens=1000,
            temperature=0.7
        )

        suggestion = response.choices[0].message.content
        return suggestion

    except APIConnectionError as e:
        print(f"错误: 无法连接到 DeepSeek API: {e}")
        return "抱歉，连接餐谱建议服务时出现网络问题，请稍后再试。"
    except Exception as e:
        print(f"错误: 调用 DeepSeek API 时发生未知错误: {e}")
        return "抱歉，获取餐谱建议时出现内部错误，请稍后再试。"

if __name__ == '__main__':
    print("测试菜单感知增强版的LLM服务模块...")
    
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "sk-your-deepseek-api-key":
        print("\n跳过API调用测试，因为DeepSeek API Key未设置。")
    else:
        # 模拟从数据库获取的完整菜单
        mock_menu = [
            "宫保鸡丁 (分类: 热菜, 描述: 香辣口味，鸡丁鲜嫩，花生香脆)",
            "麻婆豆腐 (分类: 热菜, 描述: 麻辣烫，非常下饭)",
            "扬州炒饭 (分类: 主食, 描述: 粒粒分明，配料丰富)",
            "西湖牛肉羹 (分类: 汤羹, 描述: 口感滑嫩，味道鲜美)",
            "拍黄瓜 (分类: 凉菜, 描述: 爽口解腻)",
            "酸梅汤 (分类: 饮品, 描述: 解暑解辣)"
        ]

        # --- 测试场景1: 已点菜，有偏好 ---
        dishes1 = ["扬州炒饭"]
        prefs1 = "我想搭配一个辣一点的菜，再来个爽口的凉菜。"
        print("\n--- 测试场景1 ---")
        print(f"完整菜单: {len(mock_menu)} 道菜")
        print(f"已选菜品: {dishes1}")
        print(f"个人偏好: {prefs1}")
        suggestion1 = get_recipe_suggestion_from_qwen(dishes1, prefs1, mock_menu)
        print(f"\n模型返回的建议:\n{suggestion1}")
        
        # --- 测试场景2: 未点菜，只有偏好 ---
        dishes2 = []
        prefs2 = "我想吃点开胃的，最好有个汤。"
        print("\n--- 测试场景2 ---")
        print(f"完整菜单: {len(mock_menu)} 道菜")
        print(f"已选菜品: (无)")
        print(f"个人偏好: {prefs2}")
        suggestion2 = get_recipe_suggestion_from_qwen(dishes2, prefs2, mock_menu)
        print(f"\n模型返回的建议:\n{suggestion2}")

