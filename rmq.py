import aio_pika
import json
import logging
import asyncio
import uuid
from typing import Dict, Any, Callable, Coroutine

class RabbitMQClient:
    def __init__(self, rmq_url:str):
        self.RMQ_URL = rmq_url
        self.connection = aio_pika.Connection = None
        self.channel = aio_pika.Channel = None
        
    async def connect(self):
        try:
            self.connection = await aio_pika.connect_robust(self.RMQ_URL)
            self.channel = await self.connection.channel()
            print("Connection successfully RabbtMQ..")
        except Exception as e:
            raise e
        
    async def close(self):
        """
        Disconnect RabbitMQ
        """
        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()
        logging.info("Disconnect RabbitMQ..")
    
    async def publish_message(self, queue_name:str, message_body:Dict[str, Any]):
        """
        Publish the message to the specified queue (for Producer)
        """
        if not self.channel:
            raise ConnectionError(f"Not open RabbitMQ channel({self.channel})")
        await self.channel.declare_queue(queue_name, durable=True)
        
        message = aio_pika.Message(
            body=json.dumps(message_body).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        await self.channel.default_exchange.publish(message=message, routing_key=queue_name)
        logging.info(f"Completed publishing to '{queue_name}' / {message_body.get('job_id')}")
    
    async def start_consuming(self, 
                              queue_name:str, 
                              on_message_callback:Callable[[aio_pika.IncomingMessage], Coroutine[Any,Any, None]]):
        """
        Begins consuming messages from the specified queue (for consumer)
        """
        if not self.channel:
            raise ConnectionError(f"Not open RabbitMQ channel({self.channel})")
        
        await self.channel.set_qos(prefetch_count=1)
        queue = await self.channel.declare_queue(queue_name, durable=True)
        logging.info(f"Waiting message on {queue_name} queue..")
        
        async for message in queue:
            async with message.process(): # Automatically ack/nack after message processing
                try:
                    await on_message_callback(message)
                except Exception as e:
                    logging.warning(f"Error occured while processing message: {e}")
                    
    async def rpc_call(self, queue_name:str, message_body:Dict[str,Any], timeout:int=20)->Dict[str,Any]:
        """
        Send message using by RPC pattern and wait for a stable response
        """
        if not self.channel:
            raise ConnectionError("RabbitMQ channel is not open")
        correlation_id = str(uuid.uuid4())
        future = asyncio.Future()
        
        callback_queue = await self.channel.declare_queue(exclusive=True)
        async def on_response(message:aio_pika.IncomingMessage):
            async with message.process():
                if message.correlation_id == correlation_id:
                    if not future.done():
                        future.set_result(json.loads(message.body.decode()))
                        
        await callback_queue.consume(on_response)
        
        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message_body).encode(),
                correlation_id=correlation_id,
                reply_to=callback_queue.name,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key=queue_name
        )
        print(f"Sent RPC job to '{queue_name}' : '{correlation_id}'")
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            raise Exception(
                "Time out"
            )