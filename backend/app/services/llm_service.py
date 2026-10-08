"""LLM服务模块 - 支持双模型(Fast + Pro)"""

import os
from hello_agents import HelloAgentsLLM
from ..config import get_settings

_flash_llm_instance = None
_pro_llm_instance = None


def _create_llm(model_id: str):
    """创建指定模型的LLM实例"""
    settings = get_settings()
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("LLM_BASE_URL") or settings.openai_base_url

    os.environ["LLM_MODEL_ID"] = model_id
    os.environ["LLM_API_KEY"] = api_key
    os.environ["LLM_BASE_URL"] = base_url

    return HelloAgentsLLM()


def get_flash_llm() -> HelloAgentsLLM:
    """获取快速LLM实例(用于景点/天气/酒店等简单检索)"""
    global _flash_llm_instance
    if _flash_llm_instance is None:
        settings = get_settings()
        model = os.getenv("LLM_FLASH_MODEL") or settings.llm_flash_model
        _flash_llm_instance = _create_llm(model)
        print(f"✅ Flash LLM: {_flash_llm_instance.model}")
    return _flash_llm_instance


def get_pro_llm() -> HelloAgentsLLM:
    """获取专业LLM实例(用于行程规划生成)"""
    global _pro_llm_instance
    if _pro_llm_instance is None:
        settings = get_settings()
        model = os.getenv("LLM_PRO_MODEL") or settings.llm_pro_model
        _pro_llm_instance = _create_llm(model)
        print(f"✅ Pro LLM: {_pro_llm_instance.model}")
    return _pro_llm_instance


def get_llm() -> HelloAgentsLLM:
    """获取LLM实例(向后兼容,默认使用Pro模型)"""
    return get_pro_llm()


def reset_llm():
    global _flash_llm_instance, _pro_llm_instance
    _flash_llm_instance = None
    _pro_llm_instance = None
