import asyncio
import os
from typing import Dict, Any
from dotenv import load_dotenv
from db import get_db, engine as db_engine, Base
from rmq import RabbitMQClient
from judge import process_challenge_job
load_dotenv()

rmq_client = RabbitMQClient(os.getenv("RABBITMQ_URL"))

async def run_judge_server():
    """
    서버의 전체 생애주기(연결, 실행, 종료)를 관리하는 메인 비동기 함수
    """
    try:
        await rmq_client.connect()
        
        async def message_callback_with_db(job_data: Dict[str, Any]):
            async with get_db() as session:
                print("Database connect successfully...")
                await process_challenge_job(job_data, session, rmq_client)

        print("Judge Server Start... Waiting for jobs.")
        await rmq_client.start_consuming(
            queue_name="code_challenge_queue",
            on_message_callback=message_callback_with_db
        )

    finally:
        print("\n Shutting down...")

        print("Closing RabbitMQ connection...")
        if rmq_client and rmq_client.connection:
            await rmq_client.close()

        print("Closing DB connections...")
        if db_engine:
            await db_engine.dispose()
        
        print("Judge Server successfully shut down.")

if __name__ == "__main__":
    try:
        asyncio.run(run_judge_server())

    except KeyboardInterrupt:
        print("\n KeyboardInterrupt detected. Judge Server closed.")