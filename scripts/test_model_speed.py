#!/usr/bin/env python3
"""测试本地 API 和兼容 OpenAI 接口模型的速度。"""

import os
import time

from openai import OpenAI

LOCAL_API_KEY = os.environ.get("LOCAL_API_KEY", "test-key")
LOCAL_BASE_URL = os.environ.get("LOCAL_BASE_URL", "http://127.0.0.1:3003/v1")
LOCAL_MODELS = ["small", "gpt"]

SILICONFLOW_MODELS = [
    "Qwen/Qwen2.5-7B-Instruct",
    "THUDM/glm-4-9b-chat",
    "Qwen/Qwen3-8B",
]
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"

TEST_PROMPT = "请用一句话介绍人工智能。"


def test_model(client: OpenAI, model: str, prompt: str, max_tokens: int = 100):
    try:
        start = time.time()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        duration = time.time() - start
        content = response.choices[0].message.content
        return {
            "success": True,
            "duration": duration,
            "content": content,
            "tokens": response.usage.total_tokens if response.usage else None,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def test_models(client: OpenAI, models: list[str], api_name: str):
    print(f"\n{'=' * 60}")
    print(f"{api_name} 模型测试")
    print("=" * 60)
    print(f"测试提示: {TEST_PROMPT}")
    print("-" * 60)

    results = []
    for model in models:
        print(f"\n测试模型: {model}")
        result = test_model(client, model, TEST_PROMPT)
        results.append((model, result))

        if result["success"]:
            print("  成功")
            print(f"  耗时: {result['duration']:.2f}s")
            if result["tokens"]:
                print(f"  Tokens: {result['tokens']}")
            print(f"  回复: {result['content'][:80]}...")
        else:
            print(f"  失败: {result['error']}")

    return results


def print_summary(all_results: list):
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    successful = [(m, r, api) for m, r, api in all_results if r["success"]]
    if successful:
        successful.sort(key=lambda x: x[1]["duration"])
        print("\n速度排名 (快→慢):")
        for i, (model, result, api) in enumerate(successful, 1):
            print(f"  {i}. [{api}] {model}: {result['duration']:.2f}s")
    else:
        print("\n所有模型测试失败")


def main():
    all_results = []

    local_client = OpenAI(api_key=LOCAL_API_KEY, base_url=LOCAL_BASE_URL)
    local_results = test_models(local_client, LOCAL_MODELS, "本地 API")
    all_results.extend([(m, r, "本地") for m, r in local_results])

    sf_api_key = os.environ.get("SILICONFLOW_API_KEY")
    if sf_api_key:
        sf_client = OpenAI(api_key=sf_api_key, base_url=SILICONFLOW_BASE_URL)
        sf_results = test_models(sf_client, SILICONFLOW_MODELS, "硅基流动")
        all_results.extend([(m, r, "硅基流动") for m, r in sf_results])
    else:
        print("\n" + "-" * 60)
        print("提示: 设置 SILICONFLOW_API_KEY 环境变量可测试硅基流动免费模型")
        print("  export SILICONFLOW_API_KEY='your-api-key'")

    print_summary(all_results)


if __name__ == "__main__":
    main()
