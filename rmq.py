import aio_pika
import json
import logging
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
    
    async def start_consuming(self, queue_name:str, on_message_callback:Callable[[str,Any], Coroutine[Any,Any, None]]):
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
                    message_data = json.loads(message.body.decode())
                    await on_message_callback(message_data)
                except Exception as e:
                    logging.warning(f"Error occured while processing message: {e}")