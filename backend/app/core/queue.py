"""
Message Queue using Redis Streams
For async booking confirmations and other background tasks
"""

import json
import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
import redis.asyncio as redis
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException

from app.core.config import settings

logger = logging.getLogger(__name__)


class MessageQueue:
    """Redis Streams-based message queue for async tasks"""
    
    # Stream names
    CONFIRMATION_STREAM = "bookings:confirmations"
    CONSUMER_GROUP = "confirmation_workers"
    
    def __init__(self, redis_client: redis.Redis):
        self.client = redis_client
    
    async def ensure_consumer_group(self):
        """Create consumer group if it doesn't exist"""
        try:
            await self.client.xgroup_create(
                self.CONFIRMATION_STREAM,
                self.CONSUMER_GROUP,
                id='0',
                mkstream=True
            )
            logger.info(f"Consumer group '{self.CONSUMER_GROUP}' created")
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                # Group already exists
                pass
            else:
                raise
    
    async def enqueue_confirmation(
        self,
        booking_id: str,
        phone: str,
        booking_data: Dict[str, Any]
    ) -> str:
        """
        Enqueue a booking confirmation message.
        
        Args:
            booking_id: UUID of the booking
            phone: User's phone number
            booking_data: Dict with car details, dates, amount, etc.
        
        Returns:
            Message ID from Redis Stream
        """
        message = {
            "booking_id": booking_id,
            "phone": phone,
            "car_make": booking_data.get("make", ""),
            "car_model": booking_data.get("model", ""),
            "car_year": str(booking_data.get("year", "")),
            "booking_start": booking_data.get("booking_start", ""),
            "booking_end": booking_data.get("booking_end", ""),
            "total_amount": str(booking_data.get("total_amount", 0)),
            "enqueued_at": datetime.utcnow().isoformat()
        }
        
        try:
            # Add to stream
            message_id = await self.client.xadd(
                self.CONFIRMATION_STREAM,
                message,
                maxlen=10000  # Keep last 10k messages
            )
            logger.info(f"Enqueued confirmation for booking {booking_id}: {message_id}")
            return message_id
        except Exception as e:
            logger.error(f"Failed to enqueue confirmation: {e}", exc_info=True)
            raise
    
    async def send_confirmation_message(self, message_data: Dict[str, Any]) -> bool:
        """
        Send WhatsApp confirmation message via Twilio.
        
        Args:
            message_data: Message data from Redis Stream
        
        Returns:
            True if sent successfully, False otherwise
        """
        booking_id = message_data.get("booking_id")
        phone = message_data.get("phone")
        
        # Skip if Twilio not configured
        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            logger.warning(f"[DEV] Would send confirmation to {phone} for booking {booking_id}")
            logger.info(f"[DEV] Booking details: {message_data}")
            return True  # Consider it successful in dev mode
        
        try:
            twilio_client = TwilioClient(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN
            )
            
            whatsapp_to = f"whatsapp:{phone}" if not phone.startswith("whatsapp:") else phone
            
            # Format dates nicely - convert UTC to IST
            from datetime import datetime, timezone, timedelta
            ist = timezone(timedelta(hours=5, minutes=30))
            
            try:
                start = datetime.fromisoformat(message_data.get("booking_start", ""))
                end = datetime.fromisoformat(message_data.get("booking_end", ""))
                
                # Convert to IST if datetime is timezone-aware
                if start.tzinfo is not None:
                    start = start.astimezone(ist)
                if end.tzinfo is not None:
                    end = end.astimezone(ist)
                
                start_str = start.strftime("%b %d, %I:%M %p IST")
                end_str = end.strftime("%b %d, %I:%M %p IST")
            except:
                start_str = message_data.get("booking_start", "")
                end_str = message_data.get("booking_end", "")
            
            # Build confirmation message
            car_info = f"{message_data.get('car_make')} {message_data.get('car_model')} ({message_data.get('car_year')})"
            amount = message_data.get('total_amount', '0')
            
            # Use content template if configured, otherwise send plain text
            if settings.TWILIO_BOOKING_CONFIRMATION_TEMPLATE_SID:
                # Template variables (customize based on your Twilio template)
                content_vars = json.dumps({
                    "1": booking_id[:8],  # Short booking ID
                    "2": car_info,
                    "3": start_str,
                    "4": end_str,
                    "5": amount
                })
                
                message = twilio_client.messages.create(
                    from_=settings.TWILIO_WHATSAPP_FROM,
                    content_sid=settings.TWILIO_BOOKING_CONFIRMATION_TEMPLATE_SID,
                    content_variables=content_vars,
                    to=whatsapp_to
                )
            else:
                # Fallback: plain text message
                body = (
                    f"🎉 Booking Confirmed!\n\n"
                    f"Booking ID: {booking_id[:8]}...\n"
                    f"Car: {car_info}\n"
                    f"Pickup: {start_str}\n"
                    f"Return: {end_str}\n"
                    f"Total: ₹{amount}\n\n"
                    f"Have a great trip!"
                )
                
                message = twilio_client.messages.create(
                    from_=settings.TWILIO_WHATSAPP_FROM,
                    body=body,
                    to=whatsapp_to
                )
            
            logger.info(f"Confirmation sent for booking {booking_id}: {message.sid}")
            return True
            
        except TwilioRestException as e:
            logger.error(f"Twilio error sending confirmation for {booking_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending confirmation for {booking_id}: {e}", exc_info=True)
            return False
    
    async def process_confirmations(self, consumer_name: str = "worker-1"):
        """
        Process confirmation messages from the stream.
        This is the main consumer loop for the worker process.
        
        Args:
            consumer_name: Unique name for this consumer instance
        """
        await self.ensure_consumer_group()
        
        logger.info(f"Starting confirmation processor: {consumer_name}")
        
        try:
            while True:
                try:
                    # Read messages from stream (blocking with 5s timeout)
                    messages = await self.client.xreadgroup(
                        groupname=self.CONSUMER_GROUP,
                        consumername=consumer_name,
                        streams={self.CONFIRMATION_STREAM: '>'},
                        count=10,  # Process up to 10 messages at a time
                        block=5000  # 5 second timeout
                    )
                    
                    if not messages:
                        continue
                    
                    # Process each message
                    for stream_name, stream_messages in messages:
                        for message_id, message_data in stream_messages:
                            try:
                                # Send confirmation
                                success = await self.send_confirmation_message(message_data)
                                
                                if success:
                                    # Acknowledge message
                                    await self.client.xack(
                                        self.CONFIRMATION_STREAM,
                                        self.CONSUMER_GROUP,
                                        message_id
                                    )
                                    logger.info(f"Processed and acked message {message_id}")
                                else:
                                    # Don't ack - message will be retried
                                    logger.warning(f"Failed to send confirmation {message_id}, will retry")
                                    # TODO: Implement retry limit and DLQ
                                
                            except Exception as e:
                                logger.error(f"Error processing message {message_id}: {e}", exc_info=True)
                                # Don't ack - will retry on next read
                
                except Exception as e:
                    logger.error(f"Error in consumer loop: {e}", exc_info=True)
                    await asyncio.sleep(5)  # Back off on error
                    
        except asyncio.CancelledError:
            logger.info(f"Processor {consumer_name} shutting down")
            raise
