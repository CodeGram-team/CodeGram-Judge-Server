import asyncio
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dotenv import load_dotenv

from judge import grading_code_challenge

from db import get_db, engine as db_engine

load_dotenv()

# example problem 4999 solution
CODE="""
import math

def main():
    b, k, g = map(int, input().split())
    groups = a // b 
    days = math.ceil((b - 1) / groups)
    print(days)

if __name__ == "__main__":
    main()
"""

MOCK_JOB_DATA = {
    "submission_id": "test-submission-12345",
    "problem_id": 4990, # 테스트하려는 문제의 ID
    "language": "python",
    "code": CODE
}
async def main():
    print("온라인 저지 로직 테스트를 시작합니다...")
    print(f"문제 ID: {MOCK_JOB_DATA['problem_id']}, 언어: {MOCK_JOB_DATA['language']}")
    
    async for session in get_db():
        try:
            print("\n[1] 데이터베이스에서 테스트 케이스를 조회...")
            print("[2] 코드를 컴파일하고 실행하여 채점을 시작...")
            
            # --- 핵심 테스트 실행 ---
            result = await grading_code_challenge(MOCK_JOB_DATA, session)
            
            print("\n" + "="*40)
            print("채점 완료 최종 결과:")
            import json
            print(json.dumps(result, indent=2))
            print("="*40)

        except Exception as e:
            print(f"\n테스트 중 심각한 에러 발생: {e}")
        finally:
            await session.close()
            await db_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())